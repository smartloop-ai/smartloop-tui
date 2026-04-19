"""DocumentCommand — ``add`` and ``delete`` document commands."""

from __future__ import annotations

from pathlib import Path

import requests
from requests.exceptions import RequestException, HTTPError

from smartloop.constants import SLP_PRIMARY

from commands.base import Command
from commands.console import console


class DocumentCommand(Command):
    """Handles ``add`` and ``delete`` CLI commands."""

    args: object

    def execute(self) -> None:
        """Route to add or delete based on the active command."""
        if self.args.command == "add":
            self.add()
        else:
            self.delete()

    def add(self) -> None:
        """Add a document source."""
        if not self._require_server():
            return
        project_id = self._resolve_project_id()
        if not project_id:
            console.print("[red]No current project. Create or switch to a project first.[/red]")
            return
        try:
            with console.status("[bold cyan]Processing document...", spinner="dots"):
                resp = requests.post(
                    f"{self._base_url()}/v1/projects/{project_id}/documents",
                    json={"source": self.args.file_path},
                    timeout=300,
                )
                resp.raise_for_status()
                data = resp.json()
                documents = data.get("documents", [])
            for doc in documents:
                console.print(f"[{SLP_PRIMARY}]Added: {Path(doc['path']).name} (id={doc['id']})[/{SLP_PRIMARY}]")
            if documents:
                console.print("[dim]Use /document list to check processing status.[/dim]")
            if not documents:
                console.print("[yellow]No new documents added (may already exist)[/yellow]")
        except requests.HTTPError as e:
            detail = e.response.json().get("detail", str(e)) if e.response is not None else str(e)
            console.print(f"[red]{detail}[/red]")
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")

    def delete(self) -> None:
        """Delete a document by ID."""
        if not self._require_server():
            return
        project_id = self._resolve_project_id()
        if not project_id:
            console.print("[red]No current project. Create or switch to a project first.[/red]")
            return
        try:
            resp = requests.delete(
                f"{self._base_url()}/v1/projects/{project_id}/documents/{self.args.document_id}",
                timeout=30,
            )
            resp.raise_for_status()
            console.print(f"[{SLP_PRIMARY}]{resp.json().get('message', 'Document deleted')}[/{SLP_PRIMARY}]")
        except HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                console.print(f"[red]Document not found: {self.args.document_id}[/red]")
            else:
                console.print(f"[red]API Error: {e}[/red]")
        except RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")
