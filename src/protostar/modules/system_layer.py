from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BootstrapModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class SystemWorkspaceModule(BootstrapModule):
    """Configures universal environment artifacts and workspace exclusions.

    Ignores common host machine artifacts, IDE workspace
    directories, and standard credential files to enforce repository hygiene.
    Initializes a git repository if git is installed and not already present.
    """

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "System Workspace"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Appends universal artifacts to the ignore and workspace hide lists."""
        logger.debug("Building universal system workspace layer.")

        if shutil.which("git") and not Path(".git").exists():
            manifest.tasks.add_system_task(
                ["git", "init"], description="Initializing git repository"
            )

        universal_artifacts = [
            ".DS_Store",
            "Thumbs.db",
            "*~",
            ".idea/",
            ".vscode/",
            ".env",
        ]

        for artifact in universal_artifacts:
            manifest.filesystem.add_environment_artifact(artifact)
