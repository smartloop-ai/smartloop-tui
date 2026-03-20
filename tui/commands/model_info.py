"""ModelInfoMixin — /model info command."""

from __future__ import annotations

import httpx
from rich.table import Table
from textual import work
from textual.containers import VerticalScroll
from textual.widgets import Static

from smartloop.utils.device_utils import get_device_config


class ModelInfo:
    """Command handler for _model_info."""

    server_url: str

    @work(exclusive=True)
    async def _model_info(self) -> None:
        """Show current model info from the health endpoint."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.server_url}/health")
                resp.raise_for_status()
                health = resp.json()

            device_config = get_device_config()
            device_type = device_config.device.type.upper()

            model_name = health.get("model_name", "—")
            quant = health.get("quantization", "—")
            n_ctx = health.get("n_ctx", "—")

            model_bytes = health.get("model_size_bytes", 0)
            if model_bytes:
                size_gb = model_bytes / (1024 ** 3)
                size_label = f"{size_gb:.1f} GB" if size_gb >= 1 else f"{model_bytes / (1024 ** 2):.0f} MB"
            else:
                size_label = "—"

            pct = health.get("memory_percent")
            pressure = f"{pct}%" if pct is not None else "—"

            table = Table(
                show_header=True,
                border_style="#272036",
                style="#6b5b7b",
                expand=False,
                pad_edge=True,
                padding=(0, 1),
            )
            table.add_column("Property", style="#6b5b7b", no_wrap=True)
            table.add_column("Value", style="#f9a8d4")
            table.add_row("Model", str(model_name))
            table.add_row("Quantization", str(quant))
            table.add_row("Context", str(n_ctx))
            table.add_row("Device", device_type)
            table.add_row("Size", size_label)
            table.add_row("Memory", pressure)

            log = self.query_one("#chat-log", VerticalScroll)
            log.mount(Static(table, classes="system-msg"))
            log.scroll_end(animate=False)
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Failed to fetch model info")


