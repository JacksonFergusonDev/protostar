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

    @property
    def aliases(self) -> list[str]:
        return ["vscode", "cursor"]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Maps manifest workspace hides to VS Code exclusion rules."""
        logger.debug("Building VS Code IDE layer.")

        exclusions = {}
        for pattern in manifest.workspace_hides:
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

    @property
    def aliases(self) -> list[str]:
        return ["jetbrains"]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends the .idea/ directory to the global ignore and hide lists."""
        logger.debug("Building JetBrains IDE layer.")
        manifest.add_vcs_ignore(".idea/")
        manifest.add_workspace_hide(".idea/")
