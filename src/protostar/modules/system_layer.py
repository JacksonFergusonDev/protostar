import logging
from typing import TYPE_CHECKING

from .base import BootstrapModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class SystemWorkspaceModule(BootstrapModule):
    """Configures universal environment artifacts and workspace exclusions.

    Ignores common host machine artifacts, IDE workspace
    directories, and standard credential files to enforce repository hygiene.
    """

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "System Workspace"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends universal artifacts to the ignore and workspace hide lists."""
        logger.debug("Building universal system workspace layer.")

        universal_artifacts = [
            ".DS_Store",
            "Thumbs.db",
            "*~",
            ".idea/",
            ".vscode/",
            ".env",
        ]

        for artifact in universal_artifacts:
            manifest.add_environment_artifact(artifact)
