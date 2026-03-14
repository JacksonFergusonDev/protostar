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
        """Returns the human-readable module name."""
        return "VS Code"

    @property
    def aliases(self) -> list[str]:
        """Returns CLI aliases that activate this module."""
        return ["vscode", "cursor"]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Evaluates IDE configuration intent.

        Note:
            Settings injection is currently delegated to language-specific
            modules (e.g., PythonModule) to ensure tight contextual coupling.
        """
        logger.debug("Building VS Code IDE layer.")
        pass


class JetBrainsModule(BootstrapModule):
    """Configures workspace exclusions for JetBrains IDEs."""

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "JetBrains"

    @property
    def aliases(self) -> list[str]:
        """Returns CLI aliases that activate this module."""
        return ["jetbrains"]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends the .idea/ directory to the global ignore and hide lists."""
        logger.debug("Building JetBrains IDE layer.")
        manifest.add_vcs_ignore(".idea/")
        manifest.add_workspace_hide(".idea/")
