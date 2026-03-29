#!/usr/bin/env python3
"""
SLP Framework - Full CLI with persistent background API server for inference and training.

The server is started automatically if not running, and stays running
to avoid reloading the model on each invocation.
"""

import argparse
import os
import certifi
import multiprocessing

from smartloop import __version__
from smartloop.auth import credential_store
from smartloop.server import read_port_file

from commands.base import Command
from commands.init import InitCommand
from commands.model import ModelCommand
from commands.run import RunCommand
from commands.token import TokenCommand
from commands.server import ServerCommand

# Use certifi CA bundle for SSL verification (required for PyInstaller builds
# where system certificates are not available)
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"


# ---------------------------------------------------------------------------
# Command Handler
# ---------------------------------------------------------------------------

class CommandHandler(
    InitCommand,
    ModelCommand,
    RunCommand,
    TokenCommand,
    ServerCommand,
):
    """Dispatches CLI commands via HTTP to the running API server."""

    def __init__(
        self,
        args,
        host: str,
        port: int,
        model_name: str,
        project_id: str | None,
        project_name: str | None,
        developer_token: str,
        parser,
        server_parser,
    ):
        self.args = args
        self.host = host
        self.port = port
        self.model_name = model_name
        self.project_id = project_id
        self.project_name = project_name
        self.developer_token = developer_token
        self.parser = parser
        self.server_parser = server_parser

    def dispatch(self) -> None:
        """Resolve and invoke the correct command handler."""

        command_maps = {
            "run": RunCommand,
            "init": InitCommand,
            "status": ModelCommand,
            "token": TokenCommand,
            "server": ServerCommand,
        }

        if not self.args.command or getattr(self.args, "resume", None):
            RunCommand.execute(self)
        else:
            command_maps.get(self.args.command).execute(self)
         
def main():
    """Main Command Line entry point."""
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(
        description="Smartloop SLM framework for inferencing and tuning models on edge devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--resume", metavar="CONVERSATION_ID", default=None,
                        help="Resume a previous conversation by session ID")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Initialize command
    init_parser = subparsers.add_parser("init", help="Initialize a model")
    init_parser.add_argument(
        "--model", "-m", nargs="?",
        help="Model name to use (default: $SLP_BASE_MODEL_NAME or gemma3_it_text)",
        default=None
    )
    init_parser.add_argument(
        "--developer-token", "-t",
        help="Smartloop developer token to download model (falls back to SLP_DEVELOPER_TOKEN in .env)",
    )

    # Run command
    run_parser = subparsers.add_parser("run", help="Run interactive chat with the model")
    run_parser.add_argument("--model", "-m", help="Model name (default: $SLP_BASE_MODEL_NAME or gemma3_it_text)")
    run_parser.add_argument("--project-name", help="Project name (default: $SLP_PROJECT_NAME)")
    run_parser.add_argument("--host", help="API server host (default: $API_HOST or 127.0.0.1)")
    run_parser.add_argument("--port", "-p", type=int, help="API server port (default: $API_PORT or 8000)")
    run_parser.add_argument("--resume", metavar="CONVERSATION_ID", default=None,
                           help="Resume a previous conversation by session ID")

    # Status command
    subparsers.add_parser("status", help="Show project status")

    # Server management commands
    server_parser = subparsers.add_parser("server", help="Server management commands")
    server_subparsers = server_parser.add_subparsers(dest="server_command", help="Server commands")
    start_parser = server_subparsers.add_parser("start", help="Start the API server in background")
    start_parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode (load base model + LoRA adapters)")
    start_parser.add_argument("--no-service", action="store_true", help="Disable auto-restart on crash")
    server_subparsers.add_parser("stop", help="Stop the background API server")
    server_subparsers.add_parser("status", help="Show server status")
    restart_parser = server_subparsers.add_parser("restart", help="Restart the API server")
    restart_parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode (load base model + LoRA adapters)")
    restart_parser.add_argument("--no-service", action="store_true", help="Disable auto-restart on crash")

    # Token management commands
    token_parser = subparsers.add_parser("token", help="Manage your developer token")
    token_subparsers = token_parser.add_subparsers(dest="token_command", help="Token commands")
    token_set_parser = token_subparsers.add_parser("set", help="Set your developer token")
    token_set_parser.add_argument("token_value", nargs="?", default=None, help="Developer token (prompted if omitted)")
    token_subparsers.add_parser("clear", help="Remove stored token")

    args = parser.parse_args()

    # Persist -t token to keychain so it's available to all consumers
    cli_token = getattr(args, "developer_token", None)
    if cli_token:
        credential_store.set_token(cli_token)

    # Re-resolve after potential keychain write so the value reflects -t
    developer_token = cli_token or os.environ.get("SLP_DEVELOPER_TOKEN")

    # Resolve configuration
    model_name = getattr(args, "model", None) or os.environ.get("SLP_BASE_MODEL_NAME")
    project_id = os.environ.get("SLP_PROJECT_ID")
    project_name = getattr(args, "project_name", None) or os.environ.get("SLP_PROJECT_NAME")
    host = os.environ.get("API_HOST", "127.0.0.1")
    port_env = os.environ.get("API_PORT")
    port = int(port_env) if port_env else (read_port_file() or 0)

    CommandHandler(
        args=args,
        host=host,
        port=port,
        model_name=model_name,
        project_id=project_id,
        project_name=project_name,
        developer_token=developer_token,
        parser=parser,
        server_parser=server_parser,
    ).dispatch()

if __name__ == "__main__":
    main()
