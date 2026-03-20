"""ConnectionMixin — server connectivity helpers."""

from __future__ import annotations

import asyncio

import httpx
from textual import work


class Connection:
    """_check_connected and _probe_reconnect."""

    # Attributes provided by SLPChat.__init__
    server_url: str
    _connected: bool

    async def _check_connected(self) -> bool:
        """Ping the server health endpoint and update connection state."""
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{self.server_url}/health")
                resp.raise_for_status()
                connected = True
        except Exception:
            connected = False

        if connected != self._connected:
            self._connected = connected
            self._refresh_info_bar()
            if not connected:
                self._append_system("[#f87171]Server disconnected — probing for reconnection...[/#f87171]")
                self._probe_reconnect()
            else:
                self._append_system("[#a3e635]Server reconnected.[/#a3e635]")
        return connected

    @work(exclusive=True, group="reconnect")
    async def _probe_reconnect(self) -> None:
        """Probe the server periodically until it comes back."""
        delays = [2, 3, 5, 5, 10, 10, 15]
        for attempt, delay in enumerate(delays, 1):
            await asyncio.sleep(delay)
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    resp = await client.get(f"{self.server_url}/health")
                    resp.raise_for_status()
                    self._connected = True
                    self._refresh_info_bar()
                    self._append_system("[#a3e635]Server reconnected.[/#a3e635]")
                    return
            except Exception:
                self._append_system(f"[dim]Reconnect attempt {attempt}/{len(delays)} failed, retrying in {delays[min(attempt, len(delays)-1)]}s...[/dim]")

        self._append_system("[#f87171]Could not reconnect. Restart with [bold]slp server start[/bold][/#f87171]")


