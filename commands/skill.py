"""SkillCommand — ``skills`` CLI command."""

from __future__ import annotations

import requests
from requests.exceptions import RequestException

from smartloop.constants import SLP_PRIMARY

from commands.base import Command
from commands.console import console
from commands.helpers import load_file_content, get_skill_input


class SkillCommand(Command):
    """Handles the ``skills`` CLI command."""

    args: object

    def execute(self) -> None:
        """Add a skill to the project via the dedicated skills endpoint."""
        if not self._require_server():
            return

        if self.args.file:
            skill_text = load_file_content(self.args.file)
        else:
            try:
                skill_text = get_skill_input()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Skill input cancelled[/yellow]")
                return

        if skill_text and skill_text.strip():
            try:
                resp = requests.post(
                    f"{self._base_url()}/v1/projects/{self.project_id}/skills/register",
                    json={"content": skill_text},
                    timeout=30,
                )
                resp.raise_for_status()
                console.print(f"[{SLP_PRIMARY}]Skill added[/{SLP_PRIMARY}]")
            except RequestException as e:
                console.print(f"[red]API Error: {e}[/red]")
        else:
            console.print("[red]No skill text provided[/red]")
