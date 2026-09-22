from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from protostar.metadata import MetadataKey

from .base import BootstrapModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")

_ACTIONLINT_HOOK = """      - id: actionlint
        name: actionlint
        entry: uv run actionlint
        language: system
        files: ^\\.github/workflows/.*\\.ya?ml$"""


def _declare_actionlint(manifest: EnvironmentManifest) -> None:
    """Lints the generated workflows with the locked actionlint binary.

    Args:
        manifest: The centralized state object.
    """
    manifest.dependencies.add_dev("actionlint-py")
    manifest.tooling.add_pre_commit_local_hook(_ACTIONLINT_HOOK)
    manifest.tooling.add_ci_step(
        "      - name: Run actionlint\n        run: uv run actionlint"
    )
    if "uv run actionlint" not in manifest.tooling.just_lint_commands:
        manifest.tooling.just_lint_commands.append("uv run actionlint")


class CIModule(BootstrapModule):
    """Configures standard GitHub Actions CI workflows for testing and linting."""

    cli_flags = ("--ci",)
    cli_help = "Scaffold standard GitHub Actions CI workflows"
    config_key = "ci"
    required_metadata = (MetadataKey.SUPPORTED_OS, MetadataKey.MINIMUM_PYTHON)

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "GitHub Actions CI"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Flags the manifest to trigger CI generation in the orchestrator/executor."""
        logger.debug("Building CI tooling layer.")
        manifest.tooling.wants_ci = True
        manifest.filesystem.add_directory(".github/workflows")
        _declare_actionlint(manifest)


class ReleaseModule(BootstrapModule):
    """Configures GitHub Actions release workflows for PyPI publishing."""

    cli_flags = ("--release",)
    cli_help = "Scaffold GitHub Actions PyPI release workflows"
    config_key = "release"

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "GitHub Actions Release"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Flags the manifest to trigger release generation in the orchestrator/executor."""
        logger.debug("Building Release tooling layer.")
        manifest.tooling.wants_release = True
        manifest.filesystem.add_directory(".github/workflows")
        _declare_actionlint(manifest)
