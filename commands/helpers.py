"""Standalone CLI helper functions shared across CLI command mixins."""

from __future__ import annotations

import json
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from requests.exceptions import RequestException

from smartloop import __version__
from smartloop.constants import SLP_PRIMARY
from smartloop.server import is_server_running

from commands.console import console

# Key bindings shared by interactive input helpers
kb = KeyBindings()


@kb.add_binding(Keys.Escape, Keys.Enter)
def _(event):
    """Escape+Enter to submit."""
    event.current_buffer.validate_and_handle()


def get_server_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def load_file_content(filepath: str) -> str:
    """Load content from a file if it exists."""
    try:
        path = Path(filepath)
        if path.is_file():
            return path.read_text()
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
    return ""


def get_editable_input() -> str:
    """Get user input with multiline support."""
    console.print("[dim]Enter your prompt (Escape+Enter to send, /attach <path> to upload file)[/dim]")
    user_input = prompt(
        "> ",
        multiline=True,
        key_bindings=kb,
    )
    return user_input


def get_skill_input() -> str:
    """Get skill input with multiline support."""
    console.print("[bold cyan]Enter skill text (Escape+Enter to finish):[/bold cyan]")
    console.print("[dim]Supports markdown formatting. Press Escape+Enter when done.[/dim]\n")
    return get_editable_input()


def get_skill_name_input() -> str:
    """Prompt for a skill name."""
    return prompt("Skill name: ").strip()


def upload_asset_cli(filepath: str, host: str, port: int) -> str | None:
    """Upload a file as an asset and return its asset_id, or None on failure."""
    path = Path(filepath)
    if not path.is_file():
        console.print(f"[red]File not found: {filepath}[/red]")
        return None
    url = f"{get_server_url(host, port)}/v1/assets"
    try:
        with console.status(f"[bold cyan]Uploading {path.name}...[/bold cyan]", spinner="dots"):
            with path.open("rb") as fh:
                resp = requests.post(url, files={"file": (path.name, fh)}, timeout=120)
        if resp.status_code in (400, 422):
            detail = resp.json().get("detail", str(resp.text))
            console.print(f"[red]Upload rejected: {detail}[/red]")
            return None
        resp.raise_for_status()
        data = resp.json()
        asset_id = data["asset_id"]
        markdown = data.get("markdown", False)
        console.print(
            f"[{SLP_PRIMARY}]Attached:[/{SLP_PRIMARY}] {path.name}  "
            f"[dim](id={asset_id}, markdown={'yes' if markdown else 'no'})[/dim]"
        )
        return asset_id
    except RequestException as e:
        console.print(f"[red]Upload error: {e}[/red]")
        return None


def stream_from_api(
    user_input: str,
    model_name: str,
    host: str,
    port: int,
    session_id: str = None,
    attachment_ids: list[str] | None = None,
) -> None:
    """Stream a chat completion response from the API server."""
    url = f"{get_server_url(host, port)}/v1/chat/completions"
    payload = dict(
        model=model_name,
        messages=[{
            "role": "user",
            "content": user_input,
            **(({"attachments": attachment_ids}) if attachment_ids else {}),
        }],
        stream=True,
    )
    if session_id:
        payload["session_id"] = session_id

    token_count = 0
    start_time = time.time()

    try:
        with requests.post(url, json=payload, stream=True, timeout=300) as response:
            response.raise_for_status()
            status_live = None
            for line in response.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    if not line_str.startswith("data: "):
                        continue
                    data = line_str[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    if chunk.get("object") == "chat.status":
                        if chunk.get("status") == "processing":
                            msg = chunk.get("message", "Processing...")
                            if status_live is None:
                                status_live = console.status(
                                    f"[bold cyan]{msg}[/bold cyan]", spinner="dots"
                                )
                                status_live.start()
                            else:
                                status_live.update(f"[bold cyan]{msg}[/bold cyan]")
                        elif chunk.get("status") in ("completed", "error"):
                            if status_live is not None:
                                status_live.stop()
                                status_live = None
                        continue

                    if status_live is not None:
                        status_live.stop()
                        status_live = None
                        console.print()

                    if chunk.get("choices") and chunk["choices"][0].get("delta"):
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            token_count += 1
                            console.print(content, end="")

            if status_live is not None:
                status_live.stop()

            duration = time.time() - start_time
            tokens_per_sec = token_count / duration if duration > 0 else 0
            console.print("\n")
            console.print("[dim]" + "-" * 50 + "[/dim]")
            console.print(f"[dim]{tokens_per_sec:.1f} tok/s[/dim]")
            console.print("")

    except RequestException as e:
        console.print(f"[red]API Error: {e}[/red]")


def print_exit_message(session_id: str) -> None:
    console.print("\n[bold blue]Bye![/bold blue]")
    console.print(f"Resume conversation with:\n[dim]slp --resume={session_id}[/dim]")


def run_interactive(
    model_name: str,
    host: str,
    port: int,
    project_rules: str = None,
    session_id: str = None,
) -> None:
    """Run interactive prompt — connects to a running server."""
    if not is_server_running(host, port):
        console.print(f"[red]Server not running at {host}:{port}[/red]")
        console.print("[dim]Start server with: slp server start[/dim]")
        return

    if session_id:
        console.print(f"[{SLP_PRIMARY}]Resuming conversation: {session_id}[/{SLP_PRIMARY}]")
    else:
        session_id = str(uuid.uuid4())

    console.print(f"[{SLP_PRIMARY}]Connected to server at {host}:{port}[/{SLP_PRIMARY}]")
    console.print("\n[bold cyan]Interactive Prompt Mode[/bold cyan]")
    console.print(
        "[dim]Commands: /attach <path> to upload a file attachment, "
        "Escape+Enter to send, Ctrl+C to exit[/dim]\n"
    )

    if project_rules and project_rules.strip():
        console.print("[bold yellow]Active Project Skills:[/bold yellow]")
        console.print(f"[dim]{project_rules}[/dim]")
        console.print()

    while True:
        try:
            pending_attachments: list[str] = []
            while True:
                user_input = get_editable_input()
                if not user_input.strip():
                    continue
                if user_input.strip().lower() in ("exit", "quit"):
                    raise KeyboardInterrupt
                if user_input.strip().lower().startswith("/attach "):
                    filepath = user_input.strip()[8:].strip()
                    aid = upload_asset_cli(filepath, host, port)
                    if aid:
                        pending_attachments.append(aid)
                        console.print(
                            f"[dim]{len(pending_attachments)} attachment(s) queued. "
                            "Type your message and press Escape+Enter to send.[/dim]"
                        )
                    continue
                break

            stream_from_api(
                user_input, model_name, host, port, session_id,
                attachment_ids=pending_attachments or None,
            )

        except KeyboardInterrupt:
            print_exit_message(session_id)
            break
        except EOFError:
            print_exit_message(session_id)
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def _find_free_port() -> int:
    """Find a free port on localhost."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_oauth_callback_server(port: int, expected_state: str) -> str | None:
    """Start a temporary HTTP server to receive the OAuth callback."""
    auth_code = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            state = params.get("state", [None])[0]
            code = params.get("code", [None])[0]
            error = params.get("error", [None])[0]

            if error:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    f"<html><body><h2>Authorization failed: {error}</h2>"
                    f"<p>You can close this tab.</p></body></html>".encode()
                )
                return

            if state != expected_state:
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h2>Invalid state parameter</h2></body></html>")
                return

            auth_code = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Authorization successful!</h2>"
                b"<p>You can close this tab and return to the terminal.</p></body></html>"
            )

        def log_message(self, format, *args):
            pass  # suppress request logging

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 120
    server.handle_request()
    return auth_code
