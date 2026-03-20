"""AttachmentMixin — /attach file upload command."""

from __future__ import annotations

from pathlib import Path

import httpx
from textual import work


class Attachment:
    """Command handler for _upload_attachment."""

    server_url: str
    pending_attachments: list
    _attachment_names: list

    @work(exclusive=True)
    async def _upload_attachment(self, filepath: str) -> None:
        # Normalize pasted file paths (match /document add behaviour)
        filepath = filepath.strip().strip("'\"")
        filepath = filepath.replace("\\ ", " ")
        if filepath.lower().startswith("file://"):
            filepath = filepath[7:]
        path = Path(filepath).expanduser()
        if not path.is_file():
            self._append_system(f"File not found: {filepath}")
            return

        self._set_loading(f"Uploading {path.name}...")

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                with path.open("rb") as fh:
                    resp = await client.post(
                        f"{self.server_url}/v1/assets",
                        files={"file": (path.name, fh)},
                    )
                if resp.status_code in (400, 422):
                    detail = resp.json().get("detail", resp.text)
                    self._append_system(f"Upload rejected: {detail}")
                    return
                resp.raise_for_status()
                data = resp.json()
                asset_id = data["asset_id"]
                self.pending_attachments.append(asset_id)
                self._attachment_names.append(path.name)
                self._refresh_info_bar()
                md = "yes" if data.get("markdown") else "no"
                self._append_system(
                    f"Attached: {path.name} (id={asset_id}, markdown={md}) — "
                    f"{len(self.pending_attachments)} attachment(s) queued"
                )
        except httpx.RequestError:
            self._append_system("Upload failed")
        finally:
            self._clear_loading()


