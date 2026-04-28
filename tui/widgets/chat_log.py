"""ChatLog — chat log helper methods (append, welcome, help, command guide)."""

from __future__ import annotations

from rich.table import Table
from textual.containers import VerticalScroll
from textual.widgets import Static

from version import __version__
from smartloop.constants import LOGO

from tui.constants import SLASH_COMMANDS
from tui.theme import Theme as theme
from tui.widgets.selectable_static import SelectableStatic


class ChatLog:
    """_append_user, _append_system, _show_welcome, _show_help, _show_command_guide."""

    # Attributes provided by SLPChat.__init__
    project_rules: str | None

    def _append_user(self, text: str) -> None:
        log = self.query_one("#chat-log", VerticalScroll)
        log.mount(SelectableStatic(f"> {text}", copyable_text=text, classes="user-msg"))
        log.scroll_end(animate=False)

    def _append_system(self, text: str) -> None:
        log = self.query_one("#chat-log", VerticalScroll)
        log.mount(SelectableStatic(text, copyable_text=text, classes="system-msg"))
        log.scroll_end(animate=False)

    def _show_welcome(self) -> None:
        """Show project context at the top of the chat (minimal)."""
        log = self.query_one("#chat-log", VerticalScroll)
        lines = []
        if self.project_rules:
            lines.append(f"[{theme.ACCENT}]Skills:[/{theme.ACCENT}]")
            for rule in self.project_rules.strip().splitlines():
                lines.append(f"  [dim]{rule}[/dim]")
            lines.append("")
        if lines:
            log.mount(Static("\n".join(lines), classes="system-msg"))

    def _show_help(self) -> None:
        """Show logo, version, and the full commands table in the chat log."""
        log = self.query_one("#chat-log", VerticalScroll)
        header = f"[bold {theme.ACCENT}]{LOGO}[/bold {theme.ACCENT}]\n[{theme.TEXT_DIM}]v{__version__}[/{theme.TEXT_DIM}]\n"
        log.mount(Static(header, classes="system-msg"))
        commands_table = Table(
            show_header=True,
            header_style=theme.ACCENT,
            border_style=theme.BORDER,
            style=theme.TEXT_MUTED,
            expand=False,
            pad_edge=True,
            padding=(0, 1),
            show_lines=True,
        )
        commands_table.add_column("Command", style=theme.ACCENT_LIGHT, no_wrap=True)
        commands_table.add_column("Description", style="dim")
        for cmd, desc in SLASH_COMMANDS:
            commands_table.add_row(cmd, desc)
        log.mount(Static(commands_table, classes="system-msg"))
        log.scroll_end(animate=False)

    def _show_command_guide(self, log: VerticalScroll) -> None:
        """Show a friendly getting-started guide after bootstrap completes."""
        c = theme.ACCENT_LIGHT
        d = theme.TEXT_MUTED
        b = theme.BORDER
        h = theme.ACCENT

        lines = [
            f"[{b}]{'─' * 60}[/{b}]",
            "",
            f"  [{h}]Getting Started[/{h}]",
            "",
            f"  [{d}]Just type a message below and press Enter to chat.[/{d}]",
            f"  [{d}]Here are a few things you can do:[/{d}]",
            "",
            f"  [{c}]/attach <file>[/{c}]    [{d}]Attach a file in the conversation for the model to use[/{d}]",
            f"  [{c}]/document add[/{c}]     [{d}]Add documents to the model context, available in any conversation for the project[/{d}]",
            f"  [{c}]/skill add[/{c}]        [{d}]Set custom instructions on how the model should respond[/{d}]",
            f"  [{c}]/project add[/{c}]      [{d}]Create and switch between projects[/{d}]",
            f"  [{c}]/mcp add[/{c}]          [{d}]Connect external tools via MCP[/{d}]",
            f"  [{c}]/model[/{c}]             [{d}]Show current model info[/{d}]",
            "",
            f"  [{d}]Type[/{d}] [{c}]/help[/{c}] [{d}]to see all available commands.[/{d}]",
            "",
            f"[{b}]{'─' * 60}[/{b}]",
        ]
        log.mount(Static("\n".join(lines), classes="system-msg"))
        log.scroll_end(animate=False)

