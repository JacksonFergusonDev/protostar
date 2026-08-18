import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BootstrapModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class CIModule(BootstrapModule):
    """Configures standard GitHub Actions CI workflows for testing and linting."""

    cli_flags = ("--ci",)
    cli_help = "Scaffold standard GitHub Actions CI workflows"
    config_key = "ci"
    required_metadata = ("supported_os", "minimum_python")

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "GitHub Actions CI"

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for the CI workflow."""
        return [Path(".github/workflows/ci.yml")]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Flags the manifest to trigger CI generation in the orchestrator/executor."""
        logger.debug("Building CI tooling layer.")
        manifest.tooling.wants_ci = True
        manifest.filesystem.add_directory(".github/workflows")


class ReleaseModule(BootstrapModule):
    """Configures GitHub Actions release workflows for PyPI publishing."""

    cli_flags = ("--release",)
    cli_help = "Scaffold GitHub Actions PyPI release workflows"
    config_key = "release"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "GitHub Actions Release"

    @property
    def collision_markers(self) -> list[Path]:
        """Returns the primary collision markers for the release workflow."""
        return [Path(".github/workflows/release.yml")]

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Flags the manifest to trigger release generation in the orchestrator/executor."""
        logger.debug("Building Release tooling layer.")
        manifest.tooling.wants_release = True
        manifest.filesystem.add_directory(".github/workflows")
