"""Preset module for command-line interface applications."""

import logging

from .base import PresetModule

logger = logging.getLogger("protostar")


class CliPreset(PresetModule):
    """Injects TUI rendering and argument parsing dependencies."""

    cli_flags = ("--cli",)
    cli_help = "Inject CLI application dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "CLI Application"

    @property
    def default_dependencies(self) -> list[str]:
        """Returns a list of default packages to inject for this preset."""
        return ["typer", "rich"]

    @property
    def default_directories(self) -> list[str]:
        """Returns a list of default directories to scaffold for this preset."""
        return ["src", "tests"]

    @property
    def default_ignores(self) -> list[str]:
        """Returns a list of default VCS ignore patterns for this preset."""
        return []
