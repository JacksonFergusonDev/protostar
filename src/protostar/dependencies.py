"""Dependency resolution and package installation via uv."""

import enum
import logging
from collections.abc import Callable

from .errors import CommandExecutionError, CommandTimeoutError
from .manifest import DependencyManifest, Severity
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
    on_diagnostic: Callable[[str, Severity, str | None], None],
) -> None:
    """Installs a specific group of packages using uv add."""
    if not packages:
        return

    cmd = ["uv", "add", *group.cli_args, *packages]
    try:
        logger.info(f"Resolving and installing {len(packages)} {group.label} payloads")
        execute_subprocess(cmd, timeout=600)
    except (CommandExecutionError, CommandTimeoutError) as e:
        detail = e.output_detail if isinstance(e, CommandExecutionError) else None
        on_diagnostic(
            f"{group.label.capitalize()} dependency resolution failed: {e}",
            Severity.WARNING,
            detail,
        )


def install_dependencies(
    dependencies_manifest: DependencyManifest,
    on_diagnostic: Callable[[str, Severity, str | None], None],
) -> None:
    """Installs queued dependencies using uv.

    Args:
        dependencies_manifest: Domain slice containing standard, dev, and docs dependencies.
        on_diagnostic: Callback invoked with (message, severity, detail) on error.
    """
    if (
        not dependencies_manifest.dependencies
        and not dependencies_manifest.dev_dependencies
        and not dependencies_manifest.docs_dependencies
    ):
        return

    _install_group(
        dependencies_manifest.dependencies, DependencyGroup.MAIN, on_diagnostic
    )
    _install_group(
        dependencies_manifest.dev_dependencies, DependencyGroup.DEV, on_diagnostic
    )
    _install_group(
        dependencies_manifest.docs_dependencies, DependencyGroup.DOCS, on_diagnostic
    )
