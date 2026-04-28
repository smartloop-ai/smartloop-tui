"""Textual ColorSystem themes for the Smartloop TUI."""

from textual.design import ColorSystem

from smartloop.constants import (
    SLP_PRIMARY,
    SLP_WARNING,
    SLP_ERROR,
    SLP_SUCCESS,
)


class SmartloopDark:
    """Dark theme — GitHub-inspired neutrals with pink accent."""

    BG = "#0d1117"
    SURFACE = "#161b22"
    SURFACE_ALT = "#151b23"
    PANEL = "#21262d"
    BORDER = "#30363d"

    TEXT = "#e6edf3"
    TEXT_SECONDARY = "#c9d1d9"
    TEXT_MUTED = "#8b949e"
    TEXT_DIM = "#484f58"
    SECONDARY = "#6e7681"

    ACCENT = SLP_PRIMARY       # #ec4899
    ACCENT_LIGHT = "#f9a8d4"

    WARNING = SLP_WARNING
    ERROR = SLP_ERROR
    SUCCESS = SLP_SUCCESS
    GREEN = "#3fb950"
    RED = "#f85149"
    LIME = "#a3e635"

    COLOR_SYSTEM = ColorSystem(
        primary=SLP_PRIMARY,
        secondary="#6e7681",
        accent=SLP_PRIMARY,
        warning=SLP_WARNING,
        error=SLP_ERROR,
        success=SLP_SUCCESS,
        background="#0d1117",
        surface="#161b22",
        panel="#21262d",
        dark=True,
    )


# Active theme — swap this to switch themes
Theme = SmartloopDark
