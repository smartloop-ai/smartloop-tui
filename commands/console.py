"""Shared console / logger / settings singletons for CLI command mixins."""

from rich.console import Console
from smartloop.utils import ConsoleLogger
from smartloop.config import AppSettings

settings = AppSettings()
console = Console()
logger = ConsoleLogger(console)
