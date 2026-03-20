"""tui/oauth.py — OAuth callback server helpers."""

from __future__ import annotations

import socket


def _find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_oauth_callback_server(port: int, expected_state: str) -> str | None:
    """Start a temporary HTTP server to receive the OAuth callback.

    Returns the authorization code, or None on timeout/error.
    """
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs

    auth_code = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            parsed = _urlparse(self.path)
            params = _parse_qs(parsed.query)

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
            pass  # Suppress request logging

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 120  # 2 minute timeout
    server.handle_request()
    return auth_code
