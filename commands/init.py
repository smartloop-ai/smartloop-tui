"""InitCommand — init / bootstrap / SSE-stream command."""

from __future__ import annotations

import json
import sys

import requests
from requests.exceptions import RequestException

from smartloop.constants import SLP_PRIMARY

from commands.base import Command
from commands.console import console

# ANSI escape helpers for the block-style progress bar
_PINK = "\033[38;5;205m"
_DIM = "\033[0;2m"
_NC = "\033[0m"

_BAR_WIDTH = 40
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"


def _format_bytes(n: int) -> str:
    if n >= 1_073_741_824:
        return f"{n / 1_073_741_824:.1f} GB"
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f} MB"
    return f"{n / 1024:.0f} KB"


def _render_progress(filename: str, downloaded: int, total: int) -> None:
    """Print an in-place block progress bar matching the TUI style."""
    if total <= 0:
        return
    ratio = min(downloaded / total, 1.0)
    pct = ratio * 100
    filled = int(ratio * _BAR_WIDTH)
    empty = _BAR_WIDTH - filled

    bar = f"{_PINK}{'█' * filled}{_DIM}{'░' * empty}{_NC}"
    label = f"{_DIM}Downloading {filename}  {_format_bytes(downloaded)} / {_format_bytes(total)}{_NC}"

    # \033[K clears rest of line to prevent old text bleeding through
    sys.stdout.write(f"{_HIDE_CURSOR}\r\033[K{label}\n\r\033[K{bar} {_PINK}{pct:3.0f}%{_NC}\033[1A\r")
    sys.stdout.flush()


def _clear_progress() -> None:
    """Clear the two-line progress display."""
    sys.stdout.write(f"\r\033[K\n\r\033[K\033[1A\r{_SHOW_CURSOR}")
    sys.stdout.flush()


class InitCommand(Command):
    """Handles ``init`` and ``_bootstrap`` CLI commands."""

    args: object
    developer_token: str

    def execute(self) -> None:
        """CLI entry-point for the ``init`` command."""
        if not self._require_server():
            return

        explicit_model = getattr(self.args, "model", None)
        if explicit_model:
            self._init()
            return

        if self._is_ready():
            try:
                health = requests.get(f"{self._base_url()}/health", timeout=5).json()
                model_name = health.get("model_name", "unknown")
            except RequestException:
                model_name = "unknown"
            console.print(f"[{SLP_PRIMARY}][+] Already set up with base model: {model_name}[/{SLP_PRIMARY}]")
            console.print(
                "[dim]To install additional models use your developer token:[/dim]\n"
                "[dim]  slp init --model=gemma3-4b --developer-token=<your-token>[/dim]"
            )
            return

        if self.developer_token:
            self._init()
            return

        self._bootstrap()

    def _init(self) -> None:
        """Authenticated init — download a specific model via /init."""
        payload = {}
        if m := getattr(self.args, "model", None):
            payload["model_name"] = m
        if self.developer_token:
            payload["developer_token"] = self.developer_token
        try:
            with requests.post(
                f"{self._base_url()}/v1/init",
                json=payload,
                stream=True,
                timeout=600,
            ) as resp:
                self._consume_sse_stream(resp)
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")

    def _bootstrap(self) -> None:
        """Unauthenticated bootstrap — download model + create default project."""
        try:
            with requests.post(
                f"{self._base_url()}/v1/bootstrap",
                stream=True,
                timeout=1800,
            ) as resp:
                self._consume_sse_stream(resp)
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")

    def _consume_sse_stream(self, resp: requests.Response) -> None:
        """Read an SSE response and render download progress / status messages.

        The server sends typed SSE frames::

            event: progress
            data: {"filename": "...", "downloaded": 123, "total": 456}

            event: complete
            data: {"model_name": "...", "project": {...}}
        """
        if not resp.ok:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            console.print(f"[red]{detail}[/red]")
            return

        showing_progress = False
        current_event_type: str | None = None
        current_filename: str | None = None

        for raw in resp.iter_lines():
            if not raw:
                current_event_type = None
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw

            if line.startswith("event:"):
                current_event_type = line[6:].strip()
                continue

            if not line.startswith("data:"):
                continue
            try:
                data = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue

            event_type = current_event_type or ""
            status = data.get("status", "")
            msg = data.get("message", "")

            # Progress event — download bytes
            if "downloaded" in data and "total" in data:
                total = data["total"]
                downloaded = data["downloaded"]
                filename = data.get("filename", "model")
                if total:
                    if showing_progress and filename != current_filename:
                        _clear_progress()
                        console.print(f"[cyan][+] Downloaded {current_filename}[/cyan]")
                    showing_progress = True
                    current_filename = filename
                    _render_progress(filename, downloaded, total)

            # Complete event
            elif event_type == "complete" or status == "completed":
                if showing_progress:
                    _clear_progress()
                    console.print(f"[cyan][+] Downloaded {current_filename}[/cyan]")
                    showing_progress = False
                    current_filename = None
                console.print(f"[cyan][+] {msg}[/cyan]")

            # Project created
            elif status == "project_created":
                project = data.get("project", {})
                console.print(
                    f"[green][+] Project created: "
                    f"{project.get('name', '')} (id={project.get('id', '')})[/green]"
                )

            # Error
            elif event_type == "error" or status == "error":
                if showing_progress:
                    _clear_progress()
                    showing_progress = False
                    current_filename = None
                console.print(f"[red]{msg}[/red]")

            # Status messages — skip "Downloading..." since the progress bar
            # already shows that info
            else:
                if msg and not msg.lower().startswith("downloading"):
                    if showing_progress:
                        _clear_progress()
                        showing_progress = False
                        current_filename = None
                    console.print(f"[dim]{msg}[/dim]")

            current_event_type = None

        if showing_progress:
            _clear_progress()
            if current_filename:
                console.print(f"[cyan][+] Downloaded {current_filename}[/cyan]")
