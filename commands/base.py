"""Command — base class inherited by all CLI command classes."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from requests.exceptions import RequestException

from smartloop.server import is_server_running, read_port_file
from smartloop.utils.log_utils import print_logo

from commands.console import console, logger, settings


class Command:
    """Base class for all CLI commands."""

    args: object
    host: str
    port: int

    def execute(self) -> None:
        """Execute the primary command action."""
        raise NotImplementedError

    def _base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _require_server(self) -> bool:
        """Ensure the API server is reachable; auto-start if needed."""
        for port in dict.fromkeys([self.port, read_port_file()]):
            if port and is_server_running(self.host, port):
                self.port = port
                return True

        from smartloop import __version__
        print_logo(version=__version__, console=console)

        try:
            home_dir = Path(settings.home_dir)
            log_file = str(home_dir / "server.log")
            os.makedirs(home_dir, exist_ok=True)
            with open(log_file, "a") as lf:
                if getattr(sys, "frozen", False):
                    cmd = [sys.executable, "server", "start"]
                else:
                    cmd = [sys.executable, sys.argv[0], "server", "start"]
                subprocess.Popen(cmd, stdout=lf, stderr=lf, start_new_session=True)
            with console.status("Please wait while server is heating up...", spinner="dots") as status:
                for i in range(30):
                    time.sleep(1)
                    check_port = read_port_file() or self.port
                    if is_server_running(self.host, check_port):
                        self.port = check_port
                        return True
                    if i % 5 == 4:
                        status.update("Still waiting for server...")
            logger.error(f"Server failed to start. Check {Path(settings.home_dir) / 'server.log'} for details.")
            return False
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False

    def _is_ready(self) -> bool:
        """Return True when the server has a loaded model and at least one project."""
        try:
            health = requests.get(f"{self._base_url()}/health", timeout=5).json()
            if not health.get("model_loaded"):
                return False
        except RequestException:
            return False
        try:
            data = requests.get(f"{self._base_url()}/v1/projects", timeout=10).json()
            if not data.get("projects"):
                return False
        except RequestException:
            return False
        return True

    def _resolve_project_id(self) -> str | None:
        """Return the current project ID, resolving from the server if needed."""
        pid = getattr(self, "project_id", None)
        if pid:
            return pid
        try:
            data = requests.get(f"{self._base_url()}/v1/projects", timeout=10).json()
            for p in data.get("projects", []):
                if p.get("current"):
                    return p["id"]
        except RequestException:
            pass
        return None

    def _ensure_ready(self) -> bool:
        """Guarantee the server has a model + project (fast no-op if already ready)."""
        if self._is_ready():
            return True
        if getattr(self.args, "model", None):
            self._init()
        else:
            self._bootstrap()
        return self._is_ready()
