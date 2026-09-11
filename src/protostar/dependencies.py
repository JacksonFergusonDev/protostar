"""Dependency resolution and package installation via uv."""

import enum
import logging

from .manifest import DependencyManifest
from .system import execute_subprocess

logger = logging.getLogger("protostar")

__all__ = ["DependencyGroup", "install_dependencies"]


class DependencyGroup(enum.StrEnum):
    """Enumeration of dependency groups and uv installation targets."""

    MAIN = "main"
    DEV = "dev"
    DOCS = "docs"

    @property
    def cli_args(self) -> list[str]:
        """Returns the CLI arguments for uv add."""
        mapping = {
            DependencyGroup.MAIN: [],
            DependencyGroup.DEV: ["--dev"],
            DependencyGroup.DOCS: ["--group", "docs"],
        }
        return mapping[self]

    @property
    def label(self) -> str:
        """Returns the human-readable description for progress messages."""
        mapping = {
            DependencyGroup.MAIN: "standard",
            DependencyGroup.DEV: "development",
            DependencyGroup.DOCS: "documentation",
        }
        return mapping[self]


def _install_group(
    packages: list[str],
    group: DependencyGroup,
) -> None:
    """Installs a specific group of packages using uv add.

    Raises:
        CommandExecutionError | CommandTimeoutError: If installation fails.
    """
    if not packages:
        return

    cmd = ["uv", "add", *group.cli_args, *packages]
    logger.info(f"Resolving and installing {len(packages)} {group.label} dependencies")
    execute_subprocess(cmd, timeout=600)


def install_dependencies(
    dependencies_manifest: DependencyManifest,
) -> None:
    """Installs queued dependencies using uv.

    Raises:
        CommandExecutionError | CommandTimeoutError: If any installation fails.
    """
    if (
        not dependencies_manifest.dependencies
        and not dependencies_manifest.dev_dependencies
        and not dependencies_manifest.docs_dependencies
    ):
        return

    _install_group(dependencies_manifest.dependencies, DependencyGroup.MAIN)
    _install_group(dependencies_manifest.dev_dependencies, DependencyGroup.DEV)
    _install_group(dependencies_manifest.docs_dependencies, DependencyGroup.DOCS)
