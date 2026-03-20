"""ProjectCommandsMixin — /project add|list|switch|remove commands."""

from __future__ import annotations

import httpx
from rich.table import Table
from textual import work
from textual.containers import VerticalScroll
from textual.widgets import Static


class Project:
    """Command handler for _handle_project_command and all _project_* helpers."""

    server_url: str
    model_name: str
    project_id: str | None
    title: str

    def _handle_project_command(self, args: str) -> None:
        """Dispatch /project sub-commands."""
        if args.startswith("add "):
            name = args[4:].strip()
            if name:
                self._project_add(name)
            else:
                self._append_system("Usage: /project add <name>")
        elif args == "list":
            self._project_list()
        elif args.startswith("switch "):
            index_str = args[7:].strip()
            if index_str:
                self._project_switch(index_str)
            else:
                self._append_system("Usage: /project switch <#>")
        elif args.startswith("remove "):
            index_str = args[7:].strip()
            if index_str:
                self._project_remove(index_str)
            else:
                self._append_system("Usage: /project remove <#>")
        else:
            self._append_system("Usage: /project <add|list|switch|remove>")

    @work(exclusive=True)
    async def _project_add(self, name: str) -> None:
        """Create a new project, reload the model to pick it up."""
        self._set_loading("Creating project...")
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.server_url}/v1/projects",
                    json={"name": name},
                )
                resp.raise_for_status()
                data = resp.json()
                project_id = data.get("id")
                project_name = data.get("name", name)
                self.model_name = data.get("model_name", self.model_name)

                # Unload and reload model so it picks up the new project
                self._update_loading("Reloading model...")
                await client.post(f"{self.server_url}/v1/models/unload")
                load_resp = await client.post(
                    f"{self.server_url}/v1/models/load",
                    json={"project_id": project_id},
                )
                load_resp.raise_for_status()

                # Update model name from what the server actually loaded
                health_resp = await client.get(f"{self.server_url}/health")
                if health_resp.is_success:
                    loaded_model = health_resp.json().get("model_name")
                    if loaded_model:
                        self.model_name = loaded_model

                self.project_id = project_id
                self.title = project_name
                self._refresh_info_bar()
                self._append_system(f"Project created: {project_name}")
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:
                pass
            self._append_system(f"Failed to create project{': ' + detail if detail else ''}")
        except httpx.RequestError:
            self._append_system("Request failed")
        finally:
            self._clear_loading()

    @work(exclusive=True)
    async def _project_list(self) -> None:
        """List all projects."""
        self._set_loading("Fetching projects...")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.server_url}/v1/projects")
                resp.raise_for_status()
                projects = resp.json().get("projects", [])
            if not projects:
                self._append_system("No projects found")
                return
            table = Table(style="#6b5b7b")
            table.add_column("#", style="dim", width=3)
            table.add_column("Name")
            table.add_column("Model")
            table.add_column("Current")
            for i, p in enumerate(projects, 1):
                table.add_row(
                    str(i),
                    p.get("name", ""),
                    p.get("model_name", ""),
                    "yes" if p.get("current") else "",
                )
            log = self.query_one("#chat-log", VerticalScroll)
            log.mount(Static(table, classes="system-msg"))
            log.scroll_end(animate=False)
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._append_system("Request failed")
        finally:
            self._clear_loading()

    @work(exclusive=True)
    async def _project_switch(self, index_str: str) -> None:
        """Switch to a project by its index number."""
        try:
            index = int(index_str)
        except ValueError:
            self._append_system("Invalid index. Use /project list to see numbered projects.")
            return

        self._set_loading("Switching project...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{self.server_url}/v1/projects")
                resp.raise_for_status()
                projects = resp.json().get("projects", [])

                if index < 1 or index > len(projects):
                    self._append_system(f"Invalid index {index}. Projects have {len(projects)} entries.")
                    return

                project = projects[index - 1]

                self._update_loading("Loading model...")
                load_resp = await client.post(
                    f"{self.server_url}/v1/models/load",
                    json={"mode": "inference", "project_id": project["id"]},
                    timeout=300,
                )
                load_resp.raise_for_status()

                # Update model name from what the server actually loaded
                health_resp = await client.get(f"{self.server_url}/health")
                if health_resp.is_success:
                    loaded_model = health_resp.json().get("model_name")
                    if loaded_model:
                        self.model_name = loaded_model

                self.project_id = project["id"]
                self.title = project.get("name", "project_name")
                self._refresh_info_bar()
                self._append_system(f"Switched to project: {project.get('name', project['id'])}")
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:
                pass
            self._append_system(f"Failed to switch project{': ' + detail if detail else ''}")
        except httpx.RequestError:
            self._append_system("Request failed")
        finally:
            self._clear_loading()

    @work(exclusive=True)
    async def _project_remove(self, index_str: str) -> None:
        """Remove a project by its index number."""
        try:
            index = int(index_str)
        except ValueError:
            self._append_system("Invalid index. Use /project list to see numbered projects.")
            return

        self._set_loading("Removing project...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{self.server_url}/v1/projects")
                resp.raise_for_status()
                projects = resp.json().get("projects", [])

                if index < 1 or index > len(projects):
                    self._append_system(f"Invalid index {index}. Projects have {len(projects)} entries.")
                    return

                project = projects[index - 1]
                if project.get("system"):
                    self._append_system("System projects cannot be removed")
                    return

                del_resp = await client.delete(f"{self.server_url}/v1/projects/{project['id']}")
                del_resp.raise_for_status()
                self._append_system(f"Removed project: {project.get('name', project['id'])}")

                # If we deleted the active project, reset the title
                if project.get("id") == self.project_id:
                    self.project_id = None
                    self.title = "project_name"
                    self._refresh_info_bar()
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:
                pass
            self._append_system(f"Failed to remove project{': ' + detail if detail else ''}")
        except httpx.RequestError:
            self._append_system("Request failed")
        finally:
            self._clear_loading()

