import logging
from typing import TYPE_CHECKING

from .base import BootstrapModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class VSCodeModule(BootstrapModule):
    """Configures workspace settings for VS Code and Cursor."""

    @property
    def name(self) -> str:
        return "VS Code"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Maps manifest ignores to VS Code exclusion rules."""
        logger.debug("Building VS Code IDE layer.")

        # We don't hardcode python.defaultInterpreterPath here anymore.
        # Instead, we pull the aggregated ignores from the manifest and
        # map them to VS Code's files.exclude format.

        exclusions = {}
        for pattern in manifest.ignored_paths:
            # Strip trailing slashes for standard VS Code globbing
            clean_pattern = pattern.rstrip("/")
            exclusions[f"**/{clean_pattern}"] = True

        if exclusions:
            manifest.add_ide_setting("files.exclude", exclusions)
            manifest.add_ide_setting("search.exclude", exclusions)


class JetBrainsModule(BootstrapModule):
    """Configures workspace exclusions for JetBrains IDEs."""

    @property
    def name(self) -> str:
        return "JetBrains"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends the .idea/ directory to the global ignore list."""
        logger.debug("Building JetBrains IDE layer.")
        manifest.add_ignore(".idea/")
