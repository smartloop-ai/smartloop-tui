"""MCPCommandsMixin — /mcp add|list|remove commands."""

from __future__ import annotations

import webbrowser
from urllib.parse import urlparse

import httpx
from rich.table import Table
from textual import work
from textual.containers import VerticalScroll
from textual.widgets import Static


class MCP:
    """Command handler for _handle_mcp_command and all _mcp_* helpers."""

    server_url: str
    model_name: str
    project_id: str | None
    _current_worker: object

    # ------------------------------------------------------------------

    def _handle_mcp_command(self, args: str) -> None:
        """Dispatch /mcp sub-commands."""
        if not self.project_id:
            self._append_system("No current project. Create or switch to a project first.")
            return
        if args.startswith("add local "):
            rest = args[10:].strip()
            parts = rest.split()
            if parts:
                name = parts[0]
                cmd_args = parts[1:] if len(parts) > 1 else []
                self._current_worker = self._mcp_add_local(name, cmd_args)
            else:
                self._append_system("Usage: /mcp add local <name> [args...]")
        elif args.startswith("add "):
            url = args[4:].strip()
            if url:
                self._current_worker = self._mcp_add(url)
            else:
                self._append_system("Usage: /mcp add <url>")
        elif args == "list":
            self._mcp_list()
        elif args.startswith("remove "):
            server_id = args[7:].strip()
            if server_id:
                self._mcp_remove(server_id)
            else:
                self._append_system("Usage: /mcp remove <id>")
        else:
            self._append_system("Usage: /mcp <add|list|remove>")

    @work(exclusive=True)
    async def _mcp_add(self, server_url: str) -> None:
        """Register a remote MCP server via the unified register endpoint."""
        parsed = urlparse(server_url)
        if not parsed.scheme or not parsed.netloc:
            self._append_system("Invalid URL. Provide a full URL (e.g. https://example.com/mcp)")
            return

        self._set_loading("Connecting to MCP server...")

        try:
            payload = {"server_type": "remote", "server_url": server_url}
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.server_url}/v1/projects/{self.project_id}/mcp/register",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("auth_type") == "oauth":
                auth_url = data.get("auth_url")
                if not auth_url:
                    self._append_system("OAuth required but no authorization URL returned")
                    return
                webbrowser.open(auth_url)
                self._append_system(
                    "Opening browser for authorization. "
                    "Complete authorization to register the server."
                )
            else:
                server = data.get("server")
                if server:
                    tool_count = len(server.get("tools", []))
                    self._append_system(
                        f"MCP server registered: {server.get('name')} ({tool_count} tools)"
                    )
                else:
                    self._append_system("MCP server registered")

        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:
                pass
            self._append_system(f"Failed to register MCP server{': ' + detail if detail else ''}")
        except httpx.RequestError:
            self._append_system("Request failed")
        except Exception as e:
            self._append_system(f"Error: {e}")
        finally:
            self._current_worker = None
            self._clear_loading()

    @work(exclusive=True)
    async def _mcp_add_local(self, name: str, args: list[str] = []) -> None:
        """Register a local MCP server via the unified register endpoint."""
        self._set_loading(f"Registering local MCP server '{name}'...")
        try:
            payload: dict = {"server_type": "local", "name": name}
            if args:
                payload["args"] = args
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.server_url}/v1/projects/{self.project_id}/mcp/register",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                server = data.get("server", {})
                tool_count = len(server.get("tools", []))
                self._append_system(
                    f"MCP server registered: {server.get('name', name)} ({tool_count} tools)"
                )
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:
                pass
            self._append_system(f"Failed to register MCP server{': ' + detail if detail else ''}")
        except httpx.RequestError:
            self._append_system("Request failed")
        finally:
            self._current_worker = None
            self._clear_loading()

    @work(exclusive=True)
    async def _mcp_list(self) -> None:
        """List registered MCP servers."""
        self._set_loading("Fetching MCP servers...")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.server_url}/v1/projects/{self.project_id}/mcp"
                )
                resp.raise_for_status()
                servers = resp.json().get("servers", [])
            if not servers:
                self._append_system("No MCP servers registered")
                return
            table = Table(style="#6b5b7b")
            table.add_column("#", style="dim", width=3)
            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Tools", justify="right", width=5)
            table.add_column("Tool Names", style="dim")
            table.add_column("Enabled")
            for i, s in enumerate(servers, 1):
                tools = s.get("tools", [])
                tool_names = ", ".join(t["name"] for t in tools) if tools else "—"
                table.add_row(
                    str(i),
                    s["name"],
                    s.get("server_type", "local"),
                    str(len(tools)),
                    tool_names,
                    "yes" if s.get("enabled") else "no",
                )
            log = self.query_one("#chat-log", VerticalScroll)
            log.mount(Static(table, classes="system-msg"))
            log.scroll_end(animate=False)
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()

    @work(exclusive=True)
    async def _mcp_remove(self, index_str: str) -> None:
        """Remove a registered MCP server by its index number."""
        try:
            index = int(index_str)
        except ValueError:
            self._append_system("Invalid index. Use /mcp list to see numbered servers.")
            return

        self._set_loading("Removing MCP server...")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.server_url}/v1/projects/{self.project_id}/mcp"
                )
                resp.raise_for_status()
                servers = resp.json().get("servers", [])

                if index < 1 or index > len(servers):
                    self._append_system(f"Invalid index {index}. Servers have {len(servers)} entries.")
                    return

                server = servers[index - 1]
                del_resp = await client.delete(
                    f"{self.server_url}/v1/projects/{self.project_id}/mcp/{server['id']}"
                )
                del_resp.raise_for_status()
                self._append_system(f"Removed MCP server: {server['name']}")
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()
