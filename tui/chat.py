"""Textual TUI chat interface for SLP Framework."""

import json
import logging
import os
import uuid
from pathlib import Path

from rich.style import Style
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, OptionList, TextArea
from textual.widgets.text_area import TextAreaTheme

from smartloop.model_factory import SUPPORTED_MODELS
from tui.theme import Theme as theme
from tui.widgets import CommandMenu, PromptTextArea, ChatLog
from tui.workers import Connection, Bootstrap, Streaming
from tui.commands import (
    MCP,
    Document,
    ModelInfo,
    Project,
    Skill,
    Attachment,
    Auth,
)

# Suppress noisy info logs in the TUI
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("smartloop").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# TUI App
# ---------------------------------------------------------------------------

class SLPChat(
    MCP,
    Document,
    Project,
    Skill,
    ModelInfo,
    Attachment,
    Auth,
    ChatLog,
    Streaming,
    Bootstrap,
    Connection,
    App,
):
    """Chat TUI powered by Textual."""

    CSS_PATH = "css/chat.tcss"

    BINDINGS = [
        Binding("escape", "interrupt", "interrupt", show=False),
    ]

    def __init__(
        self,
        server_url: str,
        model_name: str = "",
        session_id: str = "",
        project_id: str | None = None,
        project_name: str | None = None,
        project_rules: str | None = None,
    ) -> None:
        super().__init__()
        self.server_url = server_url
        self.model_name = model_name
        self.session_id = session_id or str(uuid.uuid4())
        self.project_id = project_id
        self.project_rules = project_rules
        self.pending_attachments: list[str] = []
        self._attachment_names: list[str] = []
        self.current_dir = os.getcwd()
        self.display_dir = self.current_dir.replace(os.path.expanduser("~"), "~", 1)
        self.title = project_name or "project_name"
        self.sub_title = self.display_dir
        self._streaming = False
        self._current_worker = None
        self._bootstrap_done = False
        self._connected = True
        self._suppress_menu = False
        self._context_used = 0
        self._context_max = 0

    def get_css_variables(self) -> dict[str, str]:
        """Override theme colors with Smartloop dark-pink palette."""
        variables = super().get_css_variables()
        variables.update(theme.COLOR_SYSTEM.generate())
        return variables

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="chat-log")
        with Vertical(id="prompt-wrapper"):
            yield Static(id="status-bar")
            yield CommandMenu(id="command-menu")
            with Vertical(id="prompt-container"):
                yield PromptTextArea(id="prompt-box")
                yield Horizontal(id="info-bar")
            with Horizontal(id="shortcut-bar"):
                yield Static(self._shortcut_text(), id="shortcut-text")
                yield Static("", id="cost-badge")

    def on_mount(self) -> None:
        prompt = self.query_one("#prompt-box", PromptTextArea)
        prompt.show_line_numbers = False
        prompt.register_theme(TextAreaTheme(
            name="smartloop",
            base_style=Style(color=theme.TEXT),
            cursor_style=Style(color=theme.BG, bgcolor=theme.TEXT),
            cursor_line_style=Style.null(),
            cursor_line_gutter_style=Style.null(),
            gutter_style=Style.null(),
        ))
        prompt.theme = "smartloop"
        prompt.focus()
        self._refresh_info_bar()
        self._show_welcome()
        if not self._bootstrap_done:
            prompt.disabled = True
            self._update_loading("Bootstrapping...")
            self._run_bootstrap()

    @staticmethod
    def _make_badge(value: str, variant: str = "pink", icon: str | None = None) -> Horizontal:
        """Create a badge widget with optional icon, both vertically centered."""
        label = value.replace("_", " ").replace("-", " ")
        children = []
        if icon:
            children.append(Static(icon, classes="badge-icon"))
        children.append(Static(label, classes="badge-text"))
        return Horizontal(*children, classes=f"badge-group {variant}")

    @staticmethod
    def _friendly_filename(filename: str) -> str:
        """Resolve a .gguf filename to its SUPPORTED_MODELS key.

        Each model class has a model_id() like "google/gemma-3-4b-it".
        The gguf filename typically starts with the part after "/".
        Match against that to return the friendly key (e.g. "gemma3-4b").
        """
        base = Path(filename).name
        for key, model_cls in SUPPORTED_MODELS.items():
            model_suffix = Path(model_cls.model_id()).name
            if base.startswith(model_suffix):
                return key
        # Fallback: strip .gguf extension
        if base.endswith(".gguf"):
            base = base[:-5]
        return base

    @staticmethod
    def _friendly_message(msg: str) -> str:
        """Replace model keys or model_id suffixes with friendly key names."""
        for key, model_cls in SUPPORTED_MODELS.items():
            model_suffix = Path(model_cls.model_id()).name
            if model_suffix in msg:
                msg = msg.replace(model_suffix, key)
            elif key in msg:
                pass  # already friendly
        return msg

    def _shortcut_text(self) -> str:
        """Return the shortcut hint text based on current state."""
        return f"[{theme.TEXT_MUTED}]<esc>[/{theme.TEXT_MUTED}] [{theme.TEXT_DIM}]interrupt[/{theme.TEXT_DIM}]  [{theme.TEXT_MUTED}]<ctrl+j>[/{theme.TEXT_MUTED}] [{theme.TEXT_DIM}]new line[/{theme.TEXT_DIM}]"

    def _refresh_shortcut_bar(self) -> None:
        """Update the shortcut bar to reflect current state."""
        try:
            self.query_one("#shortcut-text", Static).update(self._shortcut_text())
        except Exception:
            pass

    def _refresh_info_bar(self) -> None:
        """Update the info bar with project name, model and attachments."""
        bar = self.query_one("#info-bar", Horizontal)
        bar.remove_children()
        if self.display_dir:
            bar.mount(self._make_badge(self.display_dir, "muted"))
        if self._bootstrap_done:
            if self.title and self.title not in ("Playground", "project_name"):
                bar.mount(self._make_badge(self.title, icon="▤", variant="muted"))

        if self._attachment_names:
            for name in self._attachment_names:
                bar.mount(self._make_badge(name, "muted"))

        try:
            self.query_one("#cost-badge", Static).update(
                f"[{theme.TEXT_MUTED}]{self._context_used:,}[/{theme.TEXT_MUTED}] [dim]token(s) processed[/dim]"
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Input handling — Enter sends, Shift+Enter for newline
    # ------------------------------------------------------------------

    def on_prompt_text_area_submitted(self, event: PromptTextArea.Submitted) -> None:
        """Handle Enter key — submit the prompt text."""
        if self._streaming:
            return
        ta = event.text_area
        content = ta.text.strip()
        if content:
            ta.clear()
            self._handle_input(content)
        else:
            ta.clear()
        # Reset prompt border back to chat mode (pink)
        try:
            self.query_one("#prompt-container").styles.border_left = ("tall", theme.ACCENT)
        except Exception:
            pass

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Prevent highlighted option from showing in the status bar."""
        event.stop()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Show/hide the command menu as the user types."""
        if self._suppress_menu:
            self._suppress_menu = False
            return
        if self._streaming or not self._bootstrap_done:
            return
        text = event.text_area.text
        # Update prompt border colour based on mode
        try:
            container = self.query_one("#prompt-container")
            container.styles.border_left = ("tall", theme.SECONDARY if text.startswith("!") else theme.ACCENT)
        except Exception:
            pass
        try:
            menu = self.query_one("#command-menu", CommandMenu)
        except Exception:
            return
        if text.startswith("/"):
            query = text[1:]
            menu.filter_commands(query)
        else:
            menu.display = False

    def _handle_input(self, text: str) -> None:
        text = text.strip()
        if not text:
            return

        if not self._bootstrap_done:
            self._append_system("Please wait for bootstrap to complete...")
            return

        if text.startswith("!"):
            cmd = text[1:].strip()
            if cmd:
                self._append_user(text)
                self._current_worker = self._run_shell_command(cmd)
            return

        if text.lower() in ("exit", "quit", "/exit"):
            self.exit()
            return

        if text.lower() == "/help":
            self._show_help()
            return


        if text.lower().startswith("/attach "):
            filepath = text[8:].strip()
            self._upload_attachment(filepath)
            return

        if text.lower().startswith("/mcp"):
            self._handle_mcp_command(text[4:].strip())
            return

        if text.lower().startswith("/document"):
            self._handle_document_command(text[9:].strip())
            return

        if text.lower().startswith("/skill"):
            self._handle_skill_command(text[6:].strip())
            return

        if text.lower() == "/model":
            self._model_info()
            return

        if text.lower().startswith("/token"):
            self._handle_token_command(text[6:].strip())
            return

        if text.lower().startswith("/project"):
            self._handle_project_command(text[8:].strip())
            return

        self._append_user(text)
        self._current_worker = self._stream_response(text)

    def _append_to_conversation(self, role: str, content: str) -> None:
        """Write a message directly to the session JSONL conversation file."""
        conv_dir = os.path.join(os.path.expanduser("~"), ".smartloop", "conversations")
        os.makedirs(conv_dir, exist_ok=True)
        path = os.path.join(conv_dir, f"{self.session_id}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"role": role, "content": content, "message_id": None, "rating": None, "citations": None}) + "\n")

    @work(exclusive=True)
    async def _run_shell_command(self, cmd: str) -> None:
        """Run a shell command, show output, and write it into the conversation history."""
        import asyncio
        self._set_loading(f"$ {cmd}")
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.expanduser(self.display_dir),
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode(errors="replace")
            err_output = stderr.decode(errors="replace")
            combined = output
            if err_output:
                combined += err_output
            display = combined.strip() if combined.strip() else f"(exit {proc.returncode})"
            self._append_shell(display)
            # Write command + output directly into the session conversation file
            self._append_to_conversation("user", f"$ {cmd}")
            self._append_to_conversation("assistant", f"```\n{display}\n```")
        except Exception as exc:
            self._append_system(f"[red]Error: {exc}[/red]")
        finally:
            self._clear_loading()

    def action_open_link(self, url: str) -> None:
        """Open a URL in the system browser."""
        from tui.widgets.selectable_static import _open_resource
        _open_resource(url)

    def action_interrupt(self) -> None:
        """Handle Escape — cancel streaming if active, ignore otherwise."""
        if self._streaming and self._current_worker is not None:
            self._current_worker.cancel()

    # ------------------------------------------------------------------
    # Loading state
    # ------------------------------------------------------------------

    def _set_loading(self, message: str) -> None:
        """Show loading state in the status bar above the prompt."""
        self._streaming = True
        self._refresh_shortcut_bar()
        self.query_one("#prompt-box", PromptTextArea).disabled = True
        status = self.query_one("#status-bar", Static)
        status.update(f"[dim]{message}[/dim]")

    def _update_loading(self, message: str) -> None:
        """Update the loading message in the status bar."""
        status = self.query_one("#status-bar", Static)
        status.update(f"[dim]{message}[/dim]")

    def _clear_loading(self) -> None:
        """Clear the status bar and restore state."""
        self._streaming = False
        self._refresh_shortcut_bar()
        status = self.query_one("#status-bar", Static)
        status.update("")
        prompt = self.query_one("#prompt-box", PromptTextArea)
        prompt.disabled = False
        prompt.focus()
