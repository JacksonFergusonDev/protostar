import logging
from typing import TYPE_CHECKING

from .base import BootstrapModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class MacOSModule(BootstrapModule):
    """Configures macOS-specific environment artifacts."""

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "macOS"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends .DS_Store to the ignore and workspace hide lists."""
        logger.debug("Building macOS OS layer.")
        manifest.add_vcs_ignore(".DS_Store")
        manifest.add_workspace_hide(".DS_Store")


class LinuxModule(BootstrapModule):
    """Configures Linux-specific environment artifacts."""

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Linux"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends temporary editor files to the ignore and workspace hide lists."""
        logger.debug("Building Linux OS layer.")
        manifest.add_vcs_ignore("*~")
        manifest.add_workspace_hide("*~")
