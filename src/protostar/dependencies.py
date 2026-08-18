"""Dependency resolution and package installation via uv."""

from collections.abc import Callable

from rich.console import Console

from .errors import CommandExecutionError, CommandTimeoutError
from .manifest import DependencyManifest, Severity
from .system import execute_subprocess

console = Console()

__all__ = ["install_dependencies"]


def _install_group(
    packages: list[str],
    args: list[str],
    label: str,
    on_diagnostic: Callable[[str, Severity, str | None], None],
) -> None:
    """Installs a specific group of packages using uv add."""
    if not packages:
        return

    cmd = ["uv", "add", *args, *packages]
    try:
        with console.status(
            f"Resolving and installing {len(packages)} {label} payloads"
        ):
            execute_subprocess(cmd, timeout=600)
    except (CommandExecutionError, CommandTimeoutError) as e:
        detail = e.output_detail if isinstance(e, CommandExecutionError) else None
        on_diagnostic(
            f"{label.capitalize()} dependency resolution failed: {e}",
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

    _install_group(dependencies_manifest.dependencies, [], "standard", on_diagnostic)
    _install_group(
        dependencies_manifest.dev_dependencies, ["--dev"], "development", on_diagnostic
    )
    _install_group(
        dependencies_manifest.docs_dependencies,
        ["--group", "docs"],
        "documentation",
        on_diagnostic,
    )
