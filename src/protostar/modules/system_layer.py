from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from protostar.errors import MissingDependencyError
from protostar.system_deps import GlobalExecutable

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

    def __init__(self) -> None:
        self._git_already_initialized: bool = False

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "System Workspace"

    def pre_flight(self) -> None:
        """Verifies environment prerequisites and inspects VCS workspace state."""
        if Path(".git").exists():
            self._git_already_initialized = True
            return

        if not shutil.which("git"):
            raise MissingDependencyError(
                dependency=GlobalExecutable.GIT,
                purpose="git repository initialization",
            )

    def build(self, manifest: EnvironmentManifest) -> None:
        """Appends universal artifacts to the ignore and workspace hide lists."""
        logger.debug("Building universal system workspace layer.")

        if not self._git_already_initialized:
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
