"""PromptTextArea — Enter-to-submit TextArea with command menu routing."""

from __future__ import annotations

from textual import events
from textual.widgets import TextArea

from tui.constants import SLASH_COMMANDS
from tui.widgets.command_menu import CommandMenu


class PromptTextArea(TextArea):
    """TextArea subclass: Enter submits, Ctrl+A selects all."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._history: list[str] = []
        self._history_index: int = -1
        self._draft: str = ""

    def _on_paste(self, event: events.Paste) -> None:
        """Strip backslash-escaped spaces (e.g. foo\\ bar.txt) on paste."""
        cleaned = event.text
        # Strip file:// prefix from drag-and-drop paths
        if cleaned.lower().startswith("file://"):
            cleaned = cleaned[7:]
        cleaned = cleaned.replace("\\ ", " ")
        if cleaned != event.text:
            event.prevent_default()
            self.insert(cleaned)

    async def _on_key(self, event: events.Key) -> None:
        # Route keys to command menu when visible
        try:
            menu = self.app.query_one("#command-menu", CommandMenu)
            menu_visible = menu.display
        except Exception:
            menu_visible = False

        if menu_visible:
            if event.key == "up":
                event.stop()
                event.prevent_default()
                menu.action_cursor_up()
                return
            if event.key == "down":
                event.stop()
                event.prevent_default()
                menu.action_cursor_down()
                return
            if event.key in ("tab", "enter"):
                event.stop()
                event.prevent_default()
                if menu.highlighted is not None:
                    option = menu.get_option_at_index(menu.highlighted)
                    cmd = option.id
                    menu.display = False
                    self.app._suppress_menu = True
                    needs_input = any(
                        c == cmd and "<" in c
                        for c, _ in SLASH_COMMANDS
                    )
                    if needs_input:
                        base = cmd.split("<")[0].rstrip() + " "
                        self.load_text(base)
                        self.action_cursor_line_end()
                    else:
                        self.load_text(cmd)
                        self.post_message(self.Submitted(self))
                return
            if event.key == "escape":
                event.stop()
                event.prevent_default()
                menu.display = False
                return

        # History navigation — only when cursor is on first/last line
        if event.key == "up" and self.cursor_location[0] == 0 and self._history:
            event.stop()
            event.prevent_default()
            if self._history_index == -1:
                self._draft = self.text
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
                self.load_text(self._history[self._history_index])
                self.action_cursor_line_end()
            return
        if event.key == "down" and self._history_index >= 0:
            row_count = self.document.line_count
            if self.cursor_location[0] == row_count - 1:
                event.stop()
                event.prevent_default()
                self._history_index -= 1
                if self._history_index == -1:
                    self.load_text(self._draft)
                else:
                    self.load_text(self._history[self._history_index])
                self.action_cursor_line_end()
                return

        if event.key in ("shift+enter", "ctrl+j"):
            event.stop()
            event.prevent_default()
            self.insert("\n")
            return
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            text = self.text.strip()
            if text and (not self._history or self._history[0] != text):
                self._history.insert(0, text)
            self._history_index = -1
            self._draft = ""
            self.post_message(self.Submitted(self))
            return
        if event.key == "ctrl+a":
            event.stop()
            event.prevent_default()
            self.action_select_all()
            return
        await super()._on_key(event)

    class Submitted(TextArea.Changed):
        """Posted when the user presses Enter to submit."""
        pass
