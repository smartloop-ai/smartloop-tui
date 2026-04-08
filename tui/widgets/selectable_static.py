"""SelectableStatic — Static widget with drag-to-select and copy."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text
from textual import events
from textual.widgets import Static


class SelectableStatic(Static):
    """Static widget that supports mouse-drag text selection and copies to clipboard."""

    def __init__(self, *args, copyable_text: str = "", **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._copyable_text = copyable_text
        self._selecting = False
        self._sel_start: tuple[int, int] | None = None
        self._sel_end: tuple[int, int] | None = None
        self._original_content = None
        self._plain_lines: list[str] = []

    def _get_plain_lines(self) -> list[str]:
        """Render current content to plain-text lines at widget width."""
        width = self.content_size.width or 80
        console = Console(width=width, no_color=True)
        with console.capture() as capture:
            console.print(self._Static__content, end="")
        return capture.get().splitlines()

    def _content_xy(self, event: events.MouseEvent) -> tuple[int, int]:
        """Convert widget-relative mouse coords to content-relative coords."""
        gutter = self.gutter
        return (event.x - gutter.left, event.y - gutter.top)

    def _get_selected_text(self) -> str:
        if not self._sel_start or not self._sel_end or not self._plain_lines:
            return ""

        sy, sx = self._sel_start
        ey, ex = self._sel_end
        if (sy, sx) > (ey, ex):
            sy, sx, ey, ex = ey, ex, sy, sx

        lines = self._plain_lines
        sy = max(0, min(sy, len(lines) - 1))
        ey = max(0, min(ey, len(lines) - 1))

        if sy == ey:
            line = lines[sy]
            sx = max(0, min(sx, len(line)))
            ex = max(0, min(ex, len(line)))
            return line[sx:ex]

        selected: list[str] = []
        for y in range(sy, ey + 1):
            if y >= len(lines):
                break
            line = lines[y]
            if y == sy:
                selected.append(line[max(0, min(sx, len(line))):])
            elif y == ey:
                selected.append(line[:max(0, min(ex, len(line)))])
            else:
                selected.append(line)
        return "\n".join(selected)

    def _render_with_highlight(self) -> None:
        if not self._sel_start or not self._sel_end or not self._plain_lines:
            return

        lines = self._plain_lines
        sy, sx = self._sel_start
        ey, ex = self._sel_end
        if (sy, sx) > (ey, ex):
            sy, sx, ey, ex = ey, ex, sy, sx

        text = Text()
        for y, line in enumerate(lines):
            if y > 0:
                text.append("\n")
            if y < sy or y > ey:
                text.append(line)
            elif sy == ey and y == sy:
                sc = max(0, min(sx, len(line)))
                ec = max(0, min(ex, len(line)))
                text.append(line[:sc])
                text.append(line[sc:ec], style="reverse")
                text.append(line[ec:])
            elif y == sy:
                sc = max(0, min(sx, len(line)))
                text.append(line[:sc])
                text.append(line[sc:], style="reverse")
            elif y == ey:
                ec = max(0, min(ex, len(line)))
                text.append(line[:ec], style="reverse")
                text.append(line[ec:])
            else:
                text.append(line, style="reverse")

        super().update(text)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        event.stop()
        self._selecting = True
        self._original_content = self._Static__content
        self._plain_lines = self._get_plain_lines()
        cx, cy = self._content_xy(event)
        self._sel_start = (cy, cx)
        self._sel_end = (cy, cx)
        self.capture_mouse()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._selecting:
            return
        event.stop()
        cx, cy = self._content_xy(event)
        self._sel_end = (cy, cx)
        self._render_with_highlight()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._selecting:
            return
        event.stop()
        self._selecting = False
        self.release_mouse()
        cx, cy = self._content_xy(event)
        self._sel_end = (cy, cx)

        selected = self._get_selected_text()

        # Restore original rendering
        if self._original_content is not None:
            super().update(self._original_content)
            self._original_content = None

        if selected.strip():
            self.app.copy_to_clipboard(selected)

        self._sel_start = None
        self._sel_end = None
        self._plain_lines = []
