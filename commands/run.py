"""RunCommand — ``run`` / ``run-cli`` interactive session command."""

from __future__ import annotations

import requests
from requests.exceptions import RequestException

from smartloop.constants import SLP_PRIMARY

from commands.base import Command
from commands.console import console
from commands.helpers import run_interactive, print_exit_message


class RunCommand(Command):
    """Handles ``run`` and ``run-cli`` CLI commands."""

    args: object
    host: str
    port: int
    model_name: str
    project_id: str | None
    project_name: str | None

    def execute(self) -> None:
        """Start interactive chat session (TUI or CLI with --no-tui)."""
        if getattr(self.args, "no_tui", False):
            self._run_cli()
            return

        if not self._require_server():
            return

        from tui.chat import SLPChat
        try:
            resume_id = getattr(self.args, "resume", None)
            app = SLPChat(
                server_url=self._base_url(),
                model_name=self.model_name or "",
                session_id=resume_id or "",
            )
            app.run()
        finally:
            try:
                requests.post(f"{self._base_url()}/v1/models/unload", timeout=30)
                print_exit_message(app.session_id)
            except Exception:
                pass

    def run_cli(self) -> None:
        """Alias for backward compatibility (slp run-cli)."""
        self._run_cli()

    def _run_cli(self) -> None:
        """Start interactive CLI chat session."""
        if not self._require_server():
            return

        if not self._ensure_ready():
            console.print("[red]Could not initialise workspace. Run 'slp init' for details.[/red]")
            return

        project_rules = ""
        project_id = self.project_id
        try:
            data = requests.get(f"{self._base_url()}/v1/projects", timeout=10).json()
            projects = data.get("projects", [])
            project = None
            if self.project_name:
                project = next((p for p in projects if p.get("name") == self.project_name), None)
            if project is None:
                project = next((p for p in projects if p.get("current")), None)
            if project:
                project_id = project.get("id", project_id)
                rules_val = project.get("rules", [])
                project_rules = "\n".join(r["content"] for r in rules_val) if rules_val else ""
            else:
                console.print(f"[yellow]Project '{self.project_name}' not found, proceeding without project context[/yellow]")
                return
        except RequestException:
            pass

        try:
            health = requests.get(f"{self._base_url()}/health", timeout=5).json()
            if not health.get("model_loaded"):
                load_payload = {"mode": "inference"}
                if project_id:
                    load_payload["project_id"] = project_id
                with console.status("[bold cyan]Loading model...[/bold cyan]", spinner="dots"):
                    resp = requests.post(
                        f"{self._base_url()}/v1/models/load",
                        json=load_payload,
                        timeout=300,
                    )
                    resp.raise_for_status()
                console.print(f"[dim]{resp.json().get('message', 'Model loaded')}[/dim]")
        except RequestException as e:
            console.print(f"[yellow]Warning: could not load model: {e}[/yellow]")

        resume_id = getattr(self.args, "resume", None)
        try:
            run_interactive(self.model_name, self.host, self.port, project_rules, session_id=resume_id)
        finally:
            try:
                requests.post(f"{self._base_url()}/v1/models/unload", timeout=30)
            except Exception:
                pass
