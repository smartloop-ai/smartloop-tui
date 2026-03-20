"""McpCommand — ``mcp`` CLI command (synchronous)."""

from __future__ import annotations

import webbrowser
from urllib.parse import urlparse

import requests
from prettytable import PrettyTable
from requests.exceptions import RequestException

from smartloop.constants import SLP_PRIMARY

from commands.base import Command
from commands.console import console


class McpCommand(Command):
    """Handles ``mcp`` CLI sub-commands (add / list / remove)."""

    args: object

    def execute(self) -> None:
        """Dispatch mcp sub-commands."""
        sub = getattr(self, f"mcp_{self.args.mcp_command}", None)
        if sub:
            sub()
        else:
            console.print("[dim]Usage: slp mcp <add|list|remove>[/dim]")

    def mcp_add(self) -> None:
        """Register a remote MCP server via the unified register endpoint."""
        if not self._require_server():
            return
        project_id = self._resolve_project_id()
        if not project_id:
            console.print("[red]No current project. Create or switch to a project first.[/red]")
            return

        server_url = self.args.url
        parsed = urlparse(server_url)
        if not parsed.scheme or not parsed.netloc:
            console.print("[red]Invalid URL. Please provide a full URL (e.g. https://example.com/mcp)[/red]")
            return

        payload = {"server_type": "remote", "server_url": server_url}

        with console.status("[bold cyan]Connecting to MCP server...[/bold cyan]", spinner="dots"):
            try:
                resp = requests.post(
                    f"{self._base_url()}/v1/projects/{project_id}/mcp/register",
                    json=payload,
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
            except RequestException as e:
                console.print(f"[red]Failed to register MCP server: {e}[/red]")
                return

        if data.get("auth_type") == "oauth":
            auth_url = data.get("auth_url")
            if not auth_url:
                console.print("[red]OAuth required but no authorization URL returned[/red]")
                return
            console.print("\n[bold]Opening browser for authorization...[/bold]")
            console.print("[dim]If the browser doesn't open, visit:[/dim]")
            console.print(f"[link]{auth_url}[/link]\n")
            webbrowser.open(auth_url)
            console.print(f"[{SLP_PRIMARY}]Complete authorization in your browser. "
                          f"The server will be registered automatically.[/{SLP_PRIMARY}]")
        else:
            server = data.get("server")
            if server:
                console.print(f"\n[{SLP_PRIMARY}]MCP server registered: {server.get('name')}[/{SLP_PRIMARY}]")
            else:
                console.print(f"[{SLP_PRIMARY}]MCP server registered[/{SLP_PRIMARY}]")

    def mcp_list(self) -> None:
        """List registered MCP servers."""
        if not self._require_server():
            return
        project_id = self._resolve_project_id()
        if not project_id:
            console.print("[red]No current project. Create or switch to a project first.[/red]")
            return
        try:
            resp = requests.get(f"{self._base_url()}/v1/projects/{project_id}/mcp", timeout=10)
            resp.raise_for_status()
            servers = resp.json().get("servers", [])
            if not servers:
                console.print("[dim]No MCP servers registered[/dim]")
                return
            table = PrettyTable()
            table.align = "l"
            table.title = "MCP Servers"
            table.field_names = ["ID", "Name", "Type", "Tools", "Enabled"]
            table.align["Tools"] = "r"
            for s in servers:
                table.add_row([
                    s["id"][:8],
                    s["name"],
                    s.get("server_type", "local"),
                    len(s.get("tools", [])),
                    "yes" if s.get("enabled") else "no",
                ])
            print(table)
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")

    def mcp_remove(self) -> None:
        """Remove a registered MCP server."""
        if not self._require_server():
            return
        project_id = self._resolve_project_id()
        if not project_id:
            console.print("[red]No current project. Create or switch to a project first.[/red]")
            return
        target_id = self.args.id
        try:
            resp = requests.get(f"{self._base_url()}/v1/projects/{project_id}/mcp", timeout=10)
            resp.raise_for_status()
            servers = resp.json().get("servers", [])
            found = next(
                (s for s in servers if s["id"] == target_id or s["id"].startswith(target_id)), None
            )
            if not found:
                console.print(f"[red]MCP server not found: {target_id}[/red]")
                return
            del_resp = requests.delete(f"{self._base_url()}/v1/projects/{project_id}/mcp/{found['id']}", timeout=10)
            del_resp.raise_for_status()
            console.print(f"[{SLP_PRIMARY}]Removed MCP server: {found['name']} ({found['id'][:8]})[/{SLP_PRIMARY}]")
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")
