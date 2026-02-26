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
        return "macOS"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends .DS_Store to the ignore list."""
        logger.debug("Building macOS OS layer.")
        manifest.add_ignore(".DS_Store")


class LinuxModule(BootstrapModule):
    """Configures Linux-specific environment artifacts."""

    @property
    def name(self) -> str:
        return "Linux"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends temporary editor files to the ignore list."""
        logger.debug("Building Linux OS layer.")
        manifest.add_ignore("*~")
