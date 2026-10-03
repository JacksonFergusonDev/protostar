"""IDE extension verification."""

from __future__ import annotations

import enum
from collections.abc import Callable
from typing import TYPE_CHECKING

from .errors import ProcessTerminationError
from .progress import ProgressStep, no_progress
from .system import ProcessRunner
from .system_deps import find_executable

if TYPE_CHECKING:
    from .manifest import Severity

__all__ = ["IDEType", "check_ide_extensions"]


class IDEType(enum.StrEnum):
    """Enumeration of supported integrated development environments."""

    VSCODE = "vscode"
    CURSOR = "cursor"
    NONE = "none"

    @property
    def binary_name(self) -> str | None:
        """Returns the CLI executable name for this IDE, or None if disabled."""
        mapping = {
            IDEType.VSCODE: "code",
            IDEType.CURSOR: "cursor",
            IDEType.NONE: None,
        }
        return mapping[self]


def check_ide_extensions(
    ide: IDEType | str | None,
    ide_extensions: set[str | tuple[str, ...]],
    on_diagnostic: Callable[[str, Severity], None],
    process_runner: ProcessRunner | None = None,
    progress: ProgressStep = no_progress,
) -> None:
    """Verifies that the configured IDE has the recommended extensions installed.

    Does nothing when no editor with an extension CLI is configured or its CLI
    is not installed. A probe that fails is reported as a skip; a probe that
    finds extensions missing is reported as a warning.

    Args:
        ide: Configured IDE identifier (e.g. IDEType.VSCODE, "cursor").
        ide_extensions: Set of required extension IDs or alternatives tuple.
        on_diagnostic: Callback invoked with (message, severity) when extensions are missing
            or check fails.
        process_runner: Subprocess runner for executing the IDE CLI in an isolated process group.
            If None, a default runner is created.
        progress: Brackets the IDE CLI probe, which runs only when the CLI is installed.
            A failed probe is reported as a skip and still completes the step.
    """
    from .manifest import Severity

    if not ide_extensions or ide is None:
        return

    try:
        ide_type = ide if isinstance(ide, IDEType) else IDEType(str(ide))
    except ValueError:
        return

    if ide_type not in (IDEType.VSCODE, IDEType.CURSOR):
        return

    ide_binary = ide_type.binary_name
    ide_path = find_executable(ide_binary) if ide_binary else None
    if ide_path is None:
        return

    runner = process_runner or ProcessRunner()

    # A failed probe is a skip, not a failure, so it completes the step.
    with progress("Checking editor extensions"):
        try:
            stdout = runner.run([ide_path, "--list-extensions"], timeout=5)
            # Normalize to lowercase for safe diffing
            installed = {ext.lower() for ext in stdout.strip().splitlines()}
            missing = []

            for ext_req in ide_extensions:
                if isinstance(ext_req, tuple):
                    if not any(e.lower() in installed for e in ext_req):
                        missing.append(f"{' or '.join(ext_req)}")
                else:
                    if ext_req.lower() not in installed:
                        missing.append(ext_req)

            if missing:
                on_diagnostic(
                    f"Missing recommended {ide_type.value} extensions: {', '.join(missing)}",
                    Severity.WARNING,
                )
        except ProcessTerminationError:
            # An unreaped process must stop execution, even for an optional probe.
            raise
        except Exception as e:
            # Reached if the CLI crashes, hangs past 5s, or throws an unexpected I/O error.
            on_diagnostic(
                f"IDE extension verification skipped due to an unexpected error: {e}",
                Severity.SKIP,
            )
