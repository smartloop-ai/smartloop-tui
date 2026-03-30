"""ModelCommand — ``status``, ``train``, and ``build`` CLI commands."""

from __future__ import annotations

import json

import requests
from prettytable import PrettyTable
from requests.exceptions import RequestException
from tqdm import tqdm

from smartloop.server import is_server_running, read_pid_file

from commands.base import Command
from commands.console import console


class ModelCommand(Command):
    """Handles the ``status``, ``train``, and ``build`` CLI commands."""

    args: object
    host: str
    port: int

    def execute(self) -> None:
        """Route to status, build, or train based on the active command."""
        handler = getattr(self, self.args.command, None)
        if handler:
            handler()

    def status(self) -> None:
        """Show server, model, and GPU status."""
        if not is_server_running(self.host, self.port):
            console.print("[dim]Server not running[/dim]")
            return

        table = PrettyTable()
        table.field_names = ["Property", "Value"]
        table.align["Property"] = "l"
        table.align["Value"] = "l"

        try:
            health = requests.get(f"{self._base_url()}/health", timeout=5).json()
            table.add_row(["Server", f"http://{self.host}:{self.port}"])
            pid = read_pid_file()
            if pid:
                table.add_row(["PID", pid])
            table.add_row(["Model loaded", health.get("model_loaded", False)])
            if health.get("model_name"):
                table.add_row(["Model", health["model_name"]])
            if health.get("quantization"):
                table.add_row(["Quantization", health["quantization"]])
            if health.get("n_ctx"):
                table.add_row(["Context window", health["n_ctx"]])
            if health.get("n_gpu_layers") is not None:
                table.add_row(["GPU layers", health["n_gpu_layers"]])
            if health.get("flash_attn") is not None:
                table.add_row(["Flash attention", health["flash_attn"]])
            model_bytes = health.get("model_size_bytes", 0)
            if model_bytes:
                size_gb = model_bytes / (1024 ** 3)
                table.add_row(["Model size", f"{size_gb:.1f} GB" if size_gb >= 1 else f"{model_bytes / (1024 ** 2):.0f} MB"])
            if health.get("memory_percent") is not None:
                table.add_row(["Memory usage", f"{health['memory_percent']}%"])
            try:
                import torch
                if torch.cuda.is_available():
                    table.add_row(["GPU", torch.cuda.get_device_name(0)])
                    table.add_row(["GPU memory", f"{torch.cuda.get_device_properties(0).total_memory / (1024 ** 3):.1f} GB"])
                elif torch.backends.mps.is_available():
                    table.add_row(["GPU", "Apple Silicon (MPS)"])
                else:
                    table.add_row(["GPU", "None (CPU only)"])
            except Exception:
                pass
        except RequestException:
            pass

        try:
            data = requests.get(f"{self._base_url()}/v1/projects", timeout=10).json()
            current = next((p for p in data.get("projects", []) if p.get("current")), None)
            if current:
                table.add_row(["Active project", f"{current.get('name')} (id={current.get('id')})"])
                table.add_row(["Project model", current.get("model_name") or "default"])
        except RequestException:
            pass

        console.print(table)

    def train(self) -> None:
        """Fine-tune the model with LoRA on project documents."""
        if not self._require_server():
            return

        project_id = self._resolve_project_id()
        if not project_id:
            console.print("[red]No active project. Run 'slp init' first.[/red]")
            return

        payload = {"mode": "train", "project_id": project_id}
        self._stream_model_load(payload, desc="Training")

    def build(self) -> None:
        """Convert the model to GGUF format."""
        if not self._require_server():
            return

        project_id = self._resolve_project_id()
        if not project_id:
            console.print("[red]No active project. Run 'slp init' first.[/red]")
            return

        payload = {"mode": "build", "project_id": project_id}
        quantize = getattr(self.args, "quantize", None)
        if quantize:
            payload["quantize"] = quantize
        self._stream_model_load(payload, desc="Building")

    def _stream_model_load(self, payload: dict, desc: str = "Processing") -> None:
        """POST to /v1/models/load and stream SSE progress."""
        try:
            with requests.post(
                f"{self._base_url()}/v1/models/load",
                json=payload,
                stream=True,
                timeout=1800,
            ) as resp:
                if not resp.ok:
                    try:
                        detail = resp.json().get("detail", resp.text)
                    except Exception:
                        detail = resp.text
                    console.print(f"[red]{detail}[/red]")
                    return

                progress_bar = None
                for raw in resp.iter_lines():
                    if not raw:
                        continue
                    line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                    if not line.startswith("data:"):
                        continue
                    try:
                        data = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue

                    stage = data.get("stage", "")
                    current = data.get("current", 0)
                    total = data.get("total", 0)
                    message = data.get("message", "")

                    if total and current is not None:
                        if progress_bar is None:
                            progress_bar = tqdm(
                                total=total, desc=stage or desc,
                                dynamic_ncols=True,
                            )
                        elif stage and progress_bar.desc != stage:
                            progress_bar.reset(total=total)
                            progress_bar.set_description(stage)
                        progress_bar.n = current
                        progress_bar.refresh()
                    elif stage == "complete" or stage == "completed":
                        if progress_bar is not None:
                            progress_bar.n = progress_bar.total
                            progress_bar.refresh()
                            progress_bar.close()
                            progress_bar = None
                        console.print(f"[cyan][:rocket:] {message or f'{desc} complete'}[/cyan]")
                    elif stage == "error":
                        if progress_bar is not None:
                            progress_bar.close()
                            progress_bar = None
                        console.print(f"[red]{message}[/red]")
                    else:
                        if message:
                            console.print(f"[dim]{message}[/dim]")

                if progress_bar is not None:
                    progress_bar.close()
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")
