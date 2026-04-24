"""StreamingMixin — LLM response streaming."""

from __future__ import annotations

import asyncio
import random
import time
import os

import httpx
from rich.text import Text as RichText
from textual import work
from textual.containers import VerticalScroll
from textual.widgets import Static

from tui.constants import LOADING_MESSAGES
from tui.events import SSEDone, SSEStatus, SSEUsage, SSEContent, parse_sse_stream
from tui.markdown import markdown_to_markup
from tui.theme import Theme as theme
from tui.widgets.selectable_static import SelectableStatic
from tui.widgets import PromptTextArea


class Streaming:
    """_stream_response."""

    server_url: str
    model_name: str
    session_id: str
    display_dir: str
    pending_attachments: list
    _attachment_names: list
    _streaming: bool
    _current_worker: object
    _context_used: int
    _context_max: int

    @work(exclusive=True)
    async def _stream_response(self, user_input: str) -> None:
        # Check server connectivity before sending
        if not await self._check_connected():
            secondary_color = theme.COLOR_SYSTEM.secondary.hex
            self._append_system(
                f"[{secondary_color}]!! Service is disconnected / crashed, "
                f"please wait for it to restart!![/{secondary_color}]"
            )
            return

        self._streaming = True
        self._refresh_shortcut_bar()

        prompt_box = self.query_one("#prompt-box", PromptTextArea)
        prompt_box.disabled = True
        self._update_loading(random.choice(LOADING_MESSAGES))

        log = self.query_one("#chat-log", VerticalScroll)
        log.scroll_end(animate=False)

        reply_widget = SelectableStatic("", classes="assistant-msg")

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": user_input,
                    **(
                        {"attachments": self.pending_attachments}
                        if self.pending_attachments
                        else {}
                    ),
                }
            ],
            "stream": True,
            "session_id": self.session_id,
            "cwd": os.path.expanduser(self.display_dir),
        }
        self.pending_attachments = []
        self._attachment_names = []
        self._refresh_info_bar()

        token_count = 0
        start_time = time.time()
        accumulated = ""
        reply_mounted = False
        interrupted = False

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream(
                    "POST",
                    f"{self.server_url}/v1/chat/completions",
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for event in parse_sse_stream(response):
                        match event:
                            case SSEDone():
                                break
                            case SSEStatus(status=s, message=msg):
                                if s == "processing":
                                    self._update_loading(f"[*] {msg}")
                                elif s in ("completed", "error"):
                                    self._update_loading(random.choice(LOADING_MESSAGES))
                                log.scroll_end(animate=False)
                            case SSEUsage(total_tokens=total, max_context_tokens=max_ctx):
                                self._context_used = total
                                self._context_max = max_ctx
                                self._refresh_info_bar()
                            case SSEContent(text=content):
                                if not reply_mounted:
                                    await log.mount(reply_widget)
                                    reply_mounted = True
                                token_count += 1
                                accumulated += content
                                self._context_used += 1
                                reply_widget.update(RichText(accumulated))
                                try:
                                    self.query_one("#cost-badge", Static).update(
                                        f"[#8b949e]{self._context_used:,}[/#8b949e] [dim]token(s) processed[/dim]"
                                    )
                                except Exception:
                                    pass
                                log.scroll_end(animate=False)

        except asyncio.CancelledError:
            interrupted = True
            if accumulated:
                interrupted_text = RichText(accumulated)
                interrupted_text.append("\n\n[interrupted]", style="dim")
                reply_widget.update(interrupted_text)
        except httpx.HTTPStatusError:
            self._append_system("Request failed")
            await self._check_connected()
        except httpx.RequestError:
            self._append_system("Request failed")
            await self._check_connected()
        finally:
            self._streaming = False
            self._current_worker = None
            self._refresh_shortcut_bar()
            self._update_loading("")
            try:
                prompt_box.disabled = False
                prompt_box.clear()
                prompt_box.focus()
            except asyncio.CancelledError:
                pass

        # Re-render the final response as Rich Markdown so code blocks,
        # bold, italics etc. display correctly on any terminal.
        if accumulated and reply_mounted:
            reply_widget._copyable_text = accumulated
            if not interrupted:
                try:
                    reply_widget.update(markdown_to_markup(accumulated))
                except Exception:
                    pass  # keep the escaped plain-text fallback on any error

        # Metrics
        duration = time.time() - start_time
        if token_count and duration > 0 and not interrupted:
            tok_s = token_count / duration
            metrics = Static(f"{tok_s:.1f} tok/s", classes="metrics-msg")
            await log.mount(metrics)
            log.scroll_end(animate=False)
