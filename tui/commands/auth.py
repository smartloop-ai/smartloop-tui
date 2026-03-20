"""Auth mixin — /token show|set|clear commands."""

from __future__ import annotations

from smartloop.auth import credential_store


class Auth:
    """Command handler for token/auth related slash commands."""

    def _handle_token_command(self, args: str) -> None:
        """Dispatch /token sub-commands."""
        if args == "set" or args.startswith("set "):
            value = args[4:].strip() if args.startswith("set ") else ""
            self._token_set(value)
        elif args == "clear":
            self._token_clear()
        elif args in ("", "show"):
            self._token_show()
        else:
            self._append_system("Usage: /token [show|set|clear]")

    def _token_show(self) -> None:
        """Display the current token status."""
        dev = credential_store.get_token()
        access = credential_store.get_access_token()

        if access:
            masked = access[:8] + "..." + access[-3:] if len(access) > 14 else "***"
            self._append_system(f"[green]Access token:[/green] {masked}")
        if dev:
            masked = dev[:8] + "..." + dev[-3:] if len(dev) > 14 else "***"
            self._append_system(f"[green]Developer token:[/green] {masked}")
        if not access and not dev:
            self._append_system(
                "[dim]No token set. Use [bold]/token set[/bold] to add one.\n"
                "Get your token at[/dim] [bold]https://app.smartloop.ai/developer[/bold]"
            )

    def _token_set(self, value: str) -> None:
        """Set the developer token."""
        if not value:
            self._append_system(
                "Usage: /token set <token>\n"
                "[dim]Get your token at[/dim] [bold]https://app.smartloop.ai/developer[/bold]"
            )
            return
        credential_store.set_token(value)
        masked = value[:8] + "..." + value[-3:] if len(value) > 14 else "***"
        self._append_system(f"[green]Token saved:[/green] {masked}")

    def _token_clear(self) -> None:
        """Remove the stored developer token."""
        credential_store.clear_token()
        self._append_system("[green]Developer token cleared.[/green]")
