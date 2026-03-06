"""Preset module for command-line interface applications."""

import logging
from typing import TYPE_CHECKING

from .base import PresetModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class CliPreset(PresetModule):
    """Injects TUI rendering and argument parsing dependencies."""

    cli_flags = ("--cli",)
    cli_help = "Inject CLI application dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "CLI Application"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends CLI framework packages and source directories.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building CLI preset layer.")

        if self._apply_overrides(manifest):
            return

        packages = [
            "typer",
            "rich",
        ]
        for pkg in packages:
            manifest.add_dependency(pkg)

        # Scaffold standard source and unit testing boundaries
        for directory in ["src", "tests"]:
            manifest.add_directory(directory)
