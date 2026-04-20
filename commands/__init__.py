"""CLI command classes."""

from version import __version__

from .base import Command
from .init import InitCommand
from .document import DocumentCommand
from .skill import SkillCommand
from .model import ModelCommand
from .run import RunCommand
from .token import TokenCommand
from .mcp import McpCommand
from .server import ServerCommand
from .projects import ProjectsCommand
from .console import settings

settings.version = __version__

__all__ = [
    "Command",
    "InitCommand",
    "DocumentCommand",
    "SkillCommand",
    "ModelCommand",
    "RunCommand",
    "TokenCommand",
    "McpCommand",
    "ServerCommand",
    "ProjectsCommand",
]
