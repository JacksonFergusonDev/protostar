"""GitHub Actions modules: the CI workflow and the PyPI release workflow."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from protostar.metadata import MetadataKey
from protostar.registry import RemoteHook

from .base import PathSignal, Signal, ToolInfo, ToolModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")

_ACTIONLINT_HOOK = f"""  # GitHub Actions workflow linting
  - repo: {RemoteHook.ACTIONLINT.value}
    rev: {RemoteHook.ACTIONLINT.placeholder}
    hooks:
      - id: actionlint"""

# actionlint ships no wheel, so a dev dependency would be built during init.
# The hook builds it with prek's Go toolchain on the first commit instead.
_ACTIONLINT_LINT = (
    "if command -v actionlint >/dev/null 2>&1; then \\\n"
    "        actionlint; \\\n"
    "    else \\\n"
    '        printf "⚠ actionlint not found. Skipping workflow linting.\\n"; \\\n'
    "    fi"
)


def _declare_actionlint(manifest: EnvironmentManifest) -> None:
    """Lints the generated workflows with actionlint, which Protostar never installs.

    Args:
        manifest: The centralized state object.
    """
    manifest.tooling.add_pre_commit_hook(_ACTIONLINT_HOOK)
    manifest.tooling.add_ci_step(
        "      - name: Run actionlint\n        uses: raven-actions/actionlint@v2"
    )
    if _ACTIONLINT_LINT not in manifest.tooling.just_lint_commands:
        manifest.tooling.just_lint_commands.append(_ACTIONLINT_LINT)


class CIModule(ToolModule):
    """Configures standard GitHub Actions CI workflows for testing and linting."""

    cli_flags = ("--ci",)
    info = ToolInfo(
        summary="Run the checks and tests on GitHub for every push and pull request",
        adds=(
            "A .github/workflows/ci.yml workflow, and actionlint to check "
            "workflow files."
        ),
        workflow=(
            "Every push and pull request on GitHub runs the project's checks "
            "and tests, and a pull request shows whether they passed."
        ),
        docs_url="https://docs.github.com/en/actions",
    )
    config_key = "ci"

    @property
    def signals(self) -> tuple[Signal, ...]:
        """Read the configuration locations declared by this tool's documents."""
        from protostar.documents import github_workflows

        return tuple(PathSignal(path) for path in github_workflows.CI_LOCATIONS.paths)

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


class ReleaseModule(ToolModule):
    """Configures GitHub Actions release workflows for PyPI publishing."""

    cli_flags = ("--release",)
    info = ToolInfo(
        summary="Publish the package to PyPI when you push a version tag",
        adds=(
            "A .github/workflows/release.yml workflow, and actionlint to check "
            "workflow files."
        ),
        workflow=(
            "Pushing a tag such as `v1.2.0` builds the package and publishes it "
            "to PyPI. It needs a trusted publisher set up for the project on "
            "PyPI first; no password or token is stored."
        ),
        docs_url="https://docs.pypi.org/trusted-publishers/",
    )
    config_key = "release"

    @property
    def signals(self) -> tuple[Signal, ...]:
        """Read the configuration locations declared by this tool's documents."""
        from protostar.documents import github_workflows

        return tuple(
            PathSignal(path) for path in github_workflows.RELEASE_LOCATIONS.paths
        )

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
