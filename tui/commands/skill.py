"""SkillCommandsMixin — /skill add|list|remove commands."""

from __future__ import annotations

import httpx
from textual import work

from rich.table import Table
from textual.containers import VerticalScroll
from textual.widgets import Static

class Skill:
    """Command handler for _handle_skill_command and all _skill_* helpers."""

    server_url: str

    def _handle_skill_command(self, args: str) -> None:
        """Dispatch /skill sub-commands."""
        if args.startswith("add "):
            skill_text = args[4:].strip()
            if skill_text:
                self._skill_add(skill_text)
            else:
                self._append_system("Usage: /skill add <text>")
        elif args == "list":
            self._skill_list()
        elif args.startswith("remove "):
            skill_id = args[7:].strip()
            if skill_id:
                self._skill_remove(skill_id)
            else:
                self._append_system("Usage: /skill remove <id>")
        else:
            self._append_system("Usage: /skill <add|list|remove>")

    @work(exclusive=True)
    async def _skill_add(self, skill_text: str) -> None:
        """Add a skill to the project with an auto-generated name."""
        if not self.project_id:
            self._append_system("No project selected. Use /project add or /project list to switch to one.")
            return
        self._set_loading("Adding skill...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Fetch existing skills to generate the next name
                list_resp = await client.get(
                    f"{self.server_url}/v1/projects/{self.project_id}/skills",
                )
                count = len(list_resp.json().get("skills", [])) if list_resp.is_success else 0
                name = f"skill_{count + 1}"

                resp = await client.post(
                    f"{self.server_url}/v1/projects/{self.project_id}/skills",
                    json={"name": name, "content": skill_text},
                )
                resp.raise_for_status()
                self._append_system("New skill added")
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()

    @work(exclusive=True)
    async def _skill_list(self) -> None:
        """Show current project skills."""
        if not self.project_id:
            self._append_system("No project selected.")
            return
        self._set_loading("Fetching skills...")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.server_url}/v1/projects/{self.project_id}/skills",
                )
                resp.raise_for_status()
                skills = resp.json().get("skills", [])

            if not skills:
                self._append_system("No skills are set")
                return

            table = Table(style="#8b949e", show_lines=True)
            table.add_column("#", style="dim", width=3)
            table.add_column("Description")
            for i, s in enumerate(skills, 1):
                table.add_row(str(i), s.get("content", ""))
            log = self.query_one("#chat-log", VerticalScroll)
            log.mount(Static(table, classes="system-msg"))
            log.scroll_end(animate=False)
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()

    @work(exclusive=True)
    async def _skill_remove(self, idx: str) -> None:
        """Remove a skill from the project by 1-based index."""
        if not self.project_id:
            self._append_system("No project selected.")
            return
        try:
            index = int(idx)
        except ValueError:
            self._append_system("Usage: /skill remove <number>  (use /skill list to see indices)")
            return
        self._set_loading("Removing skill...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Fetch skills to resolve index → id
                resp = await client.get(
                    f"{self.server_url}/v1/projects/{self.project_id}/skills",
                )
                resp.raise_for_status()
                skills = resp.json().get("skills", [])

                if index < 1 or index > len(skills):
                    self._append_system(f"Invalid index {index}. Use /skill list to see available skills.")
                    return

                skill_id = skills[index - 1].get("id")
                resp = await client.delete(
                    f"{self.server_url}/v1/projects/{self.project_id}/skills/{skill_id}",
                )
                resp.raise_for_status()
                self._append_system(f"Skill {index} removed")
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()
