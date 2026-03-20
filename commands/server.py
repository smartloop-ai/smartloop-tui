"""ServerCommand — ``server`` CLI sub-command."""

from __future__ import annotations

import time

from smartloop.constants import SLP_PRIMARY
from smartloop.server import is_server_running, stop_server, start_server, get_status

from commands.base import Command
from commands.console import console


class ServerCommand(Command):
    """Handles ``server`` CLI sub-commands (start / stop / status / restart)."""

    args: object
    host: str
    port: int
    server_parser: object

    def execute(self) -> None:
        """Dispatch server sub-commands."""
        sub = getattr(self, f"server_{self.args.server_command}", None)
        if sub:
            sub()
        else:
            self.server_parser.print_help()

    def server_start(self) -> None:
        if is_server_running(self.host, self.port):
            console.print(f"[{SLP_PRIMARY}]Server already running at http://{self.host}:{self.port}[/{SLP_PRIMARY}]")
        else:
            debug = getattr(self.args, "debug", False)
            if debug:
                console.print("[bold yellow]🔧 Debug mode enabled - loading base model with LoRA adapters[/bold yellow]")
            start_server(
                self.host, self.port,
                debug=debug,
                service=not getattr(self.args, "no_service", False),
            )

    def server_stop(self) -> None:
        stop_server()

    def server_status(self) -> None:
        status = get_status(self.host, self.port)
        if status["running"]:
            console.print(f"[{SLP_PRIMARY}]Server running at http://{self.host}:{self.port}[/{SLP_PRIMARY}]")
            console.print(f"  PID: {status.get('pid') or 'unknown'}")
            console.print(f"  Model loaded: {status.get('model_loaded', False)}")
            console.print(f"  Model name: {status.get('model_name', 'none')}")
        else:
            console.print("[dim]Server not running[/dim]")

    def server_restart(self) -> None:
        stop_server()
        time.sleep(1)
        debug = getattr(self.args, "debug", False)
        if debug:
            console.print("[bold yellow]🔧 Debug mode enabled - loading base model with LoRA adapters[/bold yellow]")
        start_server(
            self.host, self.port,
            debug=debug,
            service=not getattr(self.args, "no_service", False),
        )
