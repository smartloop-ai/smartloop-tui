"""CommandMenu — slash-command autocomplete widget."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from tui.constants import SLASH_COMMANDS


class CommandMenu(OptionList):
    """Slash command menu shown when the user types '/' in the prompt."""

    can_focus = False

    DEFAULT_CSS = """
    CommandMenu {
        display: none;
        height: auto;
        max-height: 10;
        background: #1c1528;
        border-left: thick #ec4899;
        border-top: none;
        border-right: none;
        border-bottom: none;
        padding: 0 1;
    }

    CommandMenu > .option-list--option-highlighted {
        background: #ec4899;
        color: #e2d9f3;
    }

    CommandMenu > .option-list--option {
        padding: 0 1;
    }
    """

    def filter_commands(self, query: str) -> None:
        """Filter SLASH_COMMANDS by query and rebuild the option list."""
        matches = [
            (cmd, desc) for cmd, desc in SLASH_COMMANDS
            if query.lower() in cmd.lower()
        ]
        self.clear_options()
        if not matches:
            self.display = False
            return
        for cmd, desc in matches:
            label = Text()
            label.append(cmd, style="#f9a8d4")
            label.append(f"  {desc}", style="#b0a3c0")
            self.add_option(Option(label, id=cmd))
        self.display = True
        self.highlighted = 0
