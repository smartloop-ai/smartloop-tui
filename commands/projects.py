"""ProjectsCommand — ``projects`` CLI sub-command."""

from __future__ import annotations

import requests
from prettytable import PrettyTable
from requests.exceptions import RequestException, HTTPError

from smartloop.constants import SLP_PRIMARY

from commands.base import Command
from commands.console import console


class ProjectsCommand(Command):
    """Handles ``projects`` CLI sub-commands (create / list / update / switch)."""

    args: object
    project_name: str | None
    developer_token: str
    projects_parser: object

    def execute(self) -> None:
        """Dispatch projects sub-commands."""
        if not self._require_server():
            return
        sub = getattr(self, f"projects_{self.args.projects_command}", None)
        if sub:
            sub()
        else:
            self.projects_parser.print_help()

    def projects_create(self) -> None:
        project_model_name = getattr(self.args, "model", None)
        project_dev_token = getattr(self.args, "developer_token", None) or self.developer_token
        try:
            payload = {"name": self.args.name}
            if project_model_name:
                payload["model_name"] = project_model_name
            if project_dev_token:
                payload["developer_token"] = project_dev_token
            if self.project_name:
                payload["project_name"] = self.project_name
            status_msg = (
                f"[bold cyan]Creating project with model {project_model_name}...[/bold cyan]"
                if project_model_name
                else "[bold cyan]Creating project...[/bold cyan]"
            )
            with console.status(status_msg, spinner="dots"):
                resp = requests.post(f"{self._base_url()}/v1/projects", json=payload, timeout=600)
                resp.raise_for_status()
            data = resp.json()
            model_info = f", model={data['model_name']}" if data.get("model_name") else ""
            console.print(
                f"[{SLP_PRIMARY}]Project created: {data['name']} (id={data['id']}{model_info})[/{SLP_PRIMARY}]"
            )
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")

    def projects_list(self) -> None:
        try:
            resp = requests.get(f"{self._base_url()}/v1/projects", timeout=30)
            resp.raise_for_status()
            data = resp.json()
            table = PrettyTable()
            table.align = "l"
            table.title = "Projects"
            table.field_names = ["ID", "Name", "Model", "Current"]
            for p in data.get("projects", []):
                table.add_row([
                    p["id"],
                    p.get("name") or "",
                    p.get("model_name") or "",
                    "yes" if p.get("current") else "",
                ])
            print(table)
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")

    def projects_update(self) -> None:
        try:
            resp = requests.get(f"{self._base_url()}/v1/projects", timeout=30)
            resp.raise_for_status()
            projects_data = resp.json().get("projects", [])
            target = next((p for p in projects_data if p.get("name") == self.args.name), None)
            if target is None:
                console.print(f"[red]Project not found: {self.args.name}[/red]")
                return
            resp = requests.patch(
                f"{self._base_url()}/v1/projects/{target['id']}",
                json={"model_name": self.args.model},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            console.print(
                f"[{SLP_PRIMARY}]Project updated: {data['name']} (model={data.get('model_name')})[/{SLP_PRIMARY}]"
            )
        except HTTPError as e:
            detail = ""
            if e.response is not None:
                try:
                    detail = e.response.json().get("detail", "")
                except Exception:
                    pass
            console.print(f"[red]API Error: {detail or e}[/red]")
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")

    def projects_switch(self) -> None:
        try:
            resp = requests.get(f"{self._base_url()}/v1/projects", timeout=30)
            resp.raise_for_status()
            projects_data = resp.json().get("projects", [])
            target = next((p for p in projects_data if p.get("name") == self.args.name), None)
            if target is None:
                console.print(f"[red]Project not found: {self.args.name}[/red]")
            else:
                resp = requests.post(
                    f"{self._base_url()}/v1/models/load",
                    json={"mode": "inference", "project_id": target["id"]},
                    timeout=300,
                )
                resp.raise_for_status()
                console.print(f"[{SLP_PRIMARY}]Switched to project: {target['name']} (id={target['id']})[/{SLP_PRIMARY}]")
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")
