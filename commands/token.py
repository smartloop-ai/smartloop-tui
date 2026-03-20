"""TokenCommand — ``token`` CLI command."""

from __future__ import annotations

from prompt_toolkit import prompt

from smartloop.auth import credential_store

from commands.base import Command
from commands.console import console


class TokenCommand(Command):
    """Handles ``token`` CLI sub-commands (set / clear / show)."""

    args: object

    def execute(self) -> None:
        """Dispatch token sub-commands."""
        sub = self.args.token_command
        if sub == "set":
            self._token_set()
        elif sub == "clear":
            self._token_clear()
        else:
            self._token_show()

    def _token_show(self) -> None:
        t = credential_store.get_token()
        if t:
            masked = t[:8] + "..." + t[-3:] if len(t) > 14 else "***"
            console.print(f"[green]Token:[/green] {masked}")
        else:
            console.print(
                "[dim]No token set. Use [bold]slp token set[/bold] to add one.[/dim]\n"
                "[dim]Get your token at[/dim] [bold]https://app.smartloop.ai/developer[/bold]"
            )

    def _token_set(self) -> None:
        t = getattr(self.args, "token_value", None)
        if not t:
            console.print(
                "[cyan]Paste your developer token below.[/cyan]\n"
                "[dim]Get one at[/dim] [bold]https://app.smartloop.ai/developer[/bold]"
            )
            t = prompt("Token: ")
        if t.strip():
            credential_store.set_token(t.strip())
            masked = t[:8] + "..." + t[-3:] if len(t) > 14 else "***"
            console.print(f"[green]Token saved:[/green] {masked}")
        else:
            console.print("[yellow]No token provided.[/yellow]")

    def _token_clear(self) -> None:
        credential_store.clear_token()
        console.print("[green]Token removed.[/green]")
