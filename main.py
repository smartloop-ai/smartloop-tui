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
from commands.document import DocumentCommand
from commands.skill import SkillCommand
from commands.model import ModelCommand
from commands.run import RunCommand
from commands.token import TokenCommand
from commands.mcp import McpCommand
from commands.server import ServerCommand
from commands.projects import ProjectsCommand


# Use certifi CA bundle for SSL verification (required for PyInstaller builds
# where system certificates are not available)
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"


def load_file_content(filepath: str) -> str:
    from commands.helpers import load_file_content as _lcf
    return _lcf(filepath)


# ---------------------------------------------------------------------------
# Command Handler
# ---------------------------------------------------------------------------

class CommandHandler(
    InitCommand,
    DocumentCommand,
    SkillCommand,
    ModelCommand,
    RunCommand,
    TokenCommand,
    McpCommand,
    ServerCommand,
    ProjectsCommand,
):
    """Dispatches CLI commands via HTTP to the running API server."""

    def __init__(
        self,
        args,
        host: str,
        port: int,
        model_name: str,
        project_id: str,
        project_name: str,
        developer_token: str,
        parser,
        server_parser,
        projects_parser,
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
        self.projects_parser = projects_parser

    def dispatch(self) -> None:
        """Resolve and invoke the correct command handler."""
        from commands.init import InitCommand
        from commands.document import DocumentCommand
        from commands.skill import SkillCommand
        from commands.model import ModelCommand
        from commands.run import RunCommand
        from commands.token import TokenCommand
        from commands.mcp import McpCommand
        from commands.server import ServerCommand
        from commands.projects import ProjectsCommand

        _COMMAND_MAP = {
            "run": RunCommand,
            "init": InitCommand,
            "skills": SkillCommand,
            "add": DocumentCommand,
            "delete": DocumentCommand,
            "status": ModelCommand,
            "train": ModelCommand,
            "build": ModelCommand,
            "token": TokenCommand,
            "mcp": McpCommand,
            "server": ServerCommand,
            "projects": ProjectsCommand,
        }

        command = self.args.command or "run"
        if command == "run-cli":
            RunCommand.run_cli(self)
            return
        cls = _COMMAND_MAP.get(command)
        if cls:
            cls.execute(self)
        else:
            self.parser.print_help()



def main():
    """Main Command Line entry point."""
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(
        description="Smartloop SLM framework for inferencing and tuning models on edge devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--resume", metavar="CONVERSATION_ID", default=None,
                        help="Resume a previous conversation (implies 'run')")
    parser.add_argument("--no-tui", action="store_true", default=False,
                        help="Run in plain CLI mode instead of the TUI (implies 'run')")
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

    # Add source command
    add_parser = subparsers.add_parser("add", help="Add a new source")
    add_parser.add_argument("file_path", help="File path or URL for the new source")

    # Add skill command
    skill_parser = subparsers.add_parser("skills", help="Add a skill to the current project")
    skill_parser.add_argument("--name", "-n", help="Skill name")
    skill_parser.add_argument("--file", "-f", help="Read skill from a file")

    # Delete document command
    delete_parser = subparsers.add_parser("delete", help="Delete a document by ID")
    delete_parser.add_argument("document-id", help="Document ID to delete")

    # Status command
    subparsers.add_parser("status", help="Show project status")

    # Train command
    subparsers.add_parser("train", help="Fine-tune the model with LoRA on project documents")

    # Build command
    build_parser = subparsers.add_parser("build", help="Convert the model to GGUF format")
    build_parser.add_argument("--quantize", "-q", help="Quantization type (e.g. q4_0, q8_0, f16)")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run interactive chat with the model")
    run_parser.add_argument("--model", "-m", help="Model name (default: $SLP_BASE_MODEL_NAME or gemma3_it_text)")
    run_parser.add_argument("--project-name", help="Project name (default: $SLP_PROJECT_NAME)")
    run_parser.add_argument("--host", help="API server host (default: $API_HOST or 127.0.0.1)")
    run_parser.add_argument("--port", "-p", type=int, help="API server port (default: $API_PORT or 8000)")
    run_parser.add_argument("--no-tui", action="store_true", help="Run in plain CLI mode instead of the TUI")
    run_parser.add_argument("--resume", metavar="CONVERSATION_ID", default=None,
                           help="Resume a previous conversation by session ID")


    # MCP server management commands
    mcp_parser = subparsers.add_parser("mcp", help="MCP server management commands")
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_command", help="MCP commands")
    mcp_add_parser = mcp_subparsers.add_parser("add", help="Register a remote MCP server")
    mcp_add_parser.add_argument("url", help="MCP server URL")
    mcp_subparsers.add_parser("list", help="List registered MCP servers")
    mcp_remove_parser = mcp_subparsers.add_parser("remove", help="Remove an MCP server")
    mcp_remove_parser.add_argument("id", help="MCP server ID to remove")

    # Projects management commands
    projects_parser = subparsers.add_parser("projects", help="Project management commands")
    projects_subparsers = projects_parser.add_subparsers(dest="projects_command", help="Project commands")
    projects_create_parser = projects_subparsers.add_parser("create", help="Create a new project")
    projects_create_parser.add_argument("name", help="Project name")
    projects_create_parser.add_argument("--model", "-m", help="Model name for the project (default: current model)")
    projects_create_parser.add_argument("--developer-token", "-t", help="Developer token for model download (falls back to SLP_DEVELOPER_TOKEN in .env)")
    projects_subparsers.add_parser("list", help="List all projects")
    projects_update_parser = projects_subparsers.add_parser("update", help="Update a project's model")
    projects_update_parser.add_argument("name", help="Project name to update")
    projects_update_parser.add_argument("--model", "-m", required=True, help="New model name for the project")
    projects_switch_parser = projects_subparsers.add_parser("switch", help="Switch to a project")
    projects_switch_parser.add_argument("name", help="Project name to switch to")

    # Server management commands
    server_parser = subparsers.add_parser("server", help="Server management commands")
    server_subparsers = server_parser.add_subparsers(dest="server_command", help="Server commands")
    start_server_parser = server_subparsers.add_parser("start", help="Start the API server in background")
    start_server_parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode (load base model + LoRA adapters)")
    start_server_parser.add_argument("--no-service", action="store_true", help="Disable auto-restart on crash")
    server_subparsers.add_parser("stop", help="Stop the background API server")
    server_subparsers.add_parser("status", help="Show server status")
    restart_server_parser = server_subparsers.add_parser("restart", help="Restart the API server")
    restart_server_parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode (load base model + LoRA adapters)")
    restart_server_parser.add_argument("--no-service", action="store_true", help="Disable auto-restart on crash")

    # Token management commands
    token_parser = subparsers.add_parser("token", help="Manage your developer token")
    token_subparsers = token_parser.add_subparsers(dest="token_command", help="Token commands")
    token_set_parser = token_subparsers.add_parser("set", help="Set your developer token")
    token_set_parser.add_argument("token_value", nargs="?", default=None, help="Developer token (prompted if omitted)")
    token_subparsers.add_parser("clear", help="Remove stored token")

    args = parser.parse_args()

    # --resume / --no-tui at the top level imply the 'run' command
    if not args.command and (getattr(args, "resume", None) or getattr(args, "no_tui", False)):
        args.command = "run"

    # Persist -t token to keychain so it's available to all consumers
    cli_token = getattr(args, "developer_token", None)
    if cli_token:
        credential_store.set_token(cli_token)

    # Re-resolve after potential keychain write so the value reflects -t
    developer_token = cli_token or os.environ.get("SLP_DEVELOPER_TOKEN")

    # Resolve configuration
    model_name = getattr(args, "model", None) or os.environ.get("SLP_BASE_MODEL_NAME")
    project_id = getattr(args, "project_id", None) or os.environ.get("SLP_PROJECT_ID")
    project_name = getattr(args, "project_name", None) or os.environ.get("SLP_PROJECT_NAME", None)
    host = getattr(args, "host", None) or os.environ.get("API_HOST", "127.0.0.1")
    port = getattr(args, "port", None)
    if port is None:
        env_port = os.environ.get("API_PORT")
        if env_port is not None:
            port = int(env_port)
        else:
            port = read_port_file() or 0

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
        projects_parser=projects_parser,
    ).dispatch()

if __name__ == "__main__":
    main()
