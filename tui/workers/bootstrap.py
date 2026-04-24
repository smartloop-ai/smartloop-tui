"""BootstrapMixin — model bootstrap SSE rendering."""

from __future__ import annotations

import httpx
from textual import work
from textual.containers import VerticalScroll
from textual.widgets import Static

from smartloop.config import AppSettings
from smartloop.conversation_store import ConversationStore
from tui.events import (
    BootstrapProgress,
    BootstrapStatus,
    BootstrapComplete,
    BootstrapError,
    parse_bootstrap_sse,
)
from tui.markdown import markdown_to_markup
from tui.widgets import PromptTextArea
from tui.widgets.selectable_static import SelectableStatic

class Bootstrap:
    """Mixin for _render_block_bar, _run_bootstrap."""

    server_url: str

    async def _load_conversation(self) -> None:
        """Restore conversation history from disk into the chat log."""
        if not self.session_id:
            return
        history = ConversationStore(AppSettings().home_dir).load(self.session_id)
        if not history:
            return
        log = self.query_one("#chat-log", VerticalScroll)
        for msg in history:
            if msg.role == "user":
                log.mount(SelectableStatic(f"> {msg.content}", copyable_text=msg.content, classes="user-msg"))
            else:
                log.mount(SelectableStatic(markdown_to_markup(msg.content), copyable_text=msg.content, classes="assistant-msg"))
        log.scroll_end(animate=False)

    @staticmethod
    def _render_block_bar(downloaded: int, total: int, width: int = 30) -> str:
        """Render a progress bar using square block characters in the primary theme color."""
        if total <= 0:
            return ""
        ratio = min(downloaded / total, 1.0)
        filled = int(ratio * width)
        empty = width - filled
        return f"[#ec4899]{'█' * filled}[/#ec4899][#21262d]{'█' * empty}[/#21262d]"

    @work(exclusive=True)
    async def _run_bootstrap(self) -> None:
        """Call POST /v1/bootstrap and render SSE progress in the chat log."""
        log = self.query_one("#chat-log", VerticalScroll)

        # Show command guide first — download progress appears below it
        self._show_command_guide(log)

        download_label: Static | None = None
        progress_widget: Static | None = None

        def _format_bytes(n: int) -> str:
            if n >= 1_073_741_824:
                return f"{n / 1_073_741_824:.1f} GB"
            if n >= 1_048_576:
                return f"{n / 1_048_576:.1f} MB"
            return f"{n / 1024:.0f} KB"

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                async with client.stream(
                    "POST",
                    f"{self.server_url}/v1/bootstrap",
                ) as response:
                    response.raise_for_status()
                    async for event in parse_bootstrap_sse(response):
                        match event:
                            case BootstrapProgress(filename=fn, downloaded=dl, total=total):
                                if download_label is None:
                                    download_label = Static("", classes="bootstrap-status")
                                    await log.mount(download_label)
                                if progress_widget is None:
                                    progress_widget = Static("", classes="bootstrap-progress")
                                    await log.mount(progress_widget)
                                pct = (dl / total * 100) if total else 0
                                bar = self._render_block_bar(dl, total)
                                progress_widget.update(
                                    f"{bar} [#8b949e]{pct:3.0f}%[/#8b949e]"
                                )
                                friendly_fn = self._friendly_filename(fn)
                                download_label.update(
                                    f"Downloading {friendly_fn}  "
                                    f"{_format_bytes(dl)} / {_format_bytes(total)}"
                                )
                                log.scroll_end(animate=False)

                            case BootstrapStatus(status=st, message=msg):
                                _done_statuses = (
                                    "download_complete", "model_ready",
                                    "creating_project", "loading", "model_loaded",
                                )
                                if progress_widget is not None and st in _done_statuses:
                                    await progress_widget.remove()
                                    progress_widget = None
                                if download_label is not None and st in _done_statuses:
                                    await download_label.remove()
                                    download_label = None
                                _status_labels = {
                                    "downloading": "[-] Downloading ...",
                                    "building": "[*] Building ...",
                                    "loading": "[~] Loading ...",
                                    "model_loaded": "[+] Model loaded",
                                    "creating_project": "[~] Creating project ...",
                                    "download_complete": "[+] Download complete",
                                    "model_ready": "[+] Model ready",
                                }
                                label = _status_labels.get(st, msg or "[~] Heating up ...")
                                self._update_loading(label)

                            case BootstrapComplete(model_name=mn, project=proj):
                                self.model_name = mn
                                self.sub_title = mn
                                if proj:
                                    self.project_id = proj.get("id")
                                    pname = proj.get("name", "")
                                    self.project_rules = proj.get("rules", "")
                                    if pname:
                                        self.title = pname
                                self._bootstrap_done = True

                            case BootstrapError(message=msg):
                                self._append_system(f"[red]Bootstrap failed: {msg}[/red]")
                                return

        except httpx.HTTPStatusError as exc:
            self._append_system(f"[red]Bootstrap failed: {exc.response.status_code}[/red]")
            return
        except httpx.RequestError as exc:
            self._append_system(f"[red]Bootstrap failed: {exc}[/red]")
            return

        # Clean up any remaining progress widgets
        if progress_widget is not None:
            await progress_widget.remove()
        if download_label is not None:
            await download_label.remove()

        # Confirm model name from health endpoint
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.server_url}/health")
                if resp.is_success:
                    loaded_model = resp.json().get("model_name")
                    if loaded_model:
                        self.model_name = loaded_model
        except Exception:
            pass

        # Enable the prompt
        self._refresh_info_bar()
        self._update_loading("")
        prompt = self.query_one("#prompt-box", PromptTextArea)
        prompt.load_text("")
        prompt.disabled = False
        prompt.focus()

        await self._load_conversation()

