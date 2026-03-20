"""Textual ColorSystem theme for the Smartloop TUI."""

from textual.design import ColorSystem

from smartloop.constants import (
    SLP_PRIMARY,
    SLP_SECONDARY,
    SLP_ACCENT,
    SLP_WARNING,
    SLP_ERROR,
    SLP_SUCCESS,
    SLP_BG,
    SLP_SURFACE,
    SLP_PANEL,
)

SLP_DARK = ColorSystem(
    primary=SLP_PRIMARY,
    secondary=SLP_SECONDARY,
    accent=SLP_ACCENT,
    warning=SLP_WARNING,
    error=SLP_ERROR,
    success=SLP_SUCCESS,
    background=SLP_BG,
    surface=SLP_SURFACE,
    panel=SLP_PANEL,
    dark=True,
)
