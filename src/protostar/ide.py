"""IDE extension verification."""

from __future__ import annotations

import enum
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from .errors import ProcessTerminationError
from .progress import ProgressStep, no_progress
from .system import ProcessRunner
from .system_deps import find_executable

if TYPE_CHECKING:
    from .manifest import Severity

__all__ = ["IDEProbe", "IDEType", "check_ide_extensions", "start_ide_probe"]


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


class IDEProbe:
    """One editor CLI extension listing, running in the background until collected.

    The listing starts as soon as the probe exists, so it overlaps whatever the
    caller does next; ``finish`` waits for it and reports. The thread does
    nothing but run the one command on the runner it is given, and keeps its
    outcome for ``finish``. That runner must be the probe's own: a runner owns
    one process at a time.
    """

    def __init__(
        self,
        ide_type: IDEType,
        ide_path: str,
        ide_extensions: set[str | tuple[str, ...]],
        process_runner: ProcessRunner,
    ) -> None:
        self._ide_type = ide_type
        self._ide_path = ide_path
        self._ide_extensions = ide_extensions
        self._runner = process_runner
        self._cancelled = threading.Event()
        self._stdout: str | None = None
        self._error: BaseException | None = None
        self._thread = threading.Thread(
            target=self._list, name="ide-probe", daemon=True
        )
        self._thread.start()

    def _list(self) -> None:
        if self._cancelled.is_set():
            return
        try:
            self._stdout = self._runner.run(
                [self._ide_path, "--list-extensions"], timeout=5
            )
        except BaseException as error:
            self._error = error

    def finish(
        self,
        on_diagnostic: Callable[[str, Severity], None],
        progress: ProgressStep = no_progress,
    ) -> None:
        """Waits for the listing and reports the extensions it finds missing.

        Args:
            on_diagnostic: Callback invoked with (message, severity) when
                extensions are missing or the check fails.
            progress: Brackets the wait, so the step reads as the probe does.
                A failed probe is reported as a skip and still completes it.

        Raises:
            ProcessTerminationError: If the CLI could not be reaped.
        """
        from .manifest import Severity

        # A failed probe is a skip, not a failure, so it completes the step.
        with progress("Checking editor extensions"):
            self._thread.join()
            try:
                if self._error is not None:
                    raise self._error
                stdout = self._stdout or ""
                # Normalize to lowercase for safe diffing
                installed = {ext.lower() for ext in stdout.strip().splitlines()}
                missing = []

                for ext_req in self._ide_extensions:
                    if isinstance(ext_req, tuple):
                        if not any(e.lower() in installed for e in ext_req):
                            missing.append(f"{' or '.join(ext_req)}")
                    else:
                        if ext_req.lower() not in installed:
                            missing.append(ext_req)

                if missing:
                    on_diagnostic(
                        f"Missing recommended {self._ide_type.value} extensions: {', '.join(missing)}",
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

    def cancel(self) -> None:
        """Stops the listing and returns once its process is reaped.

        Safe to call at any time and more than once. A process the thread has
        not yet started is never started; one it has is terminated, repeatedly
        if the thread starts it in the meantime.

        Raises:
            ProcessTerminationError: If the CLI could not be reaped.
        """
        self._cancelled.set()
        while self._thread.is_alive():
            self._runner.terminate_active_process_tree()
            self._thread.join(0.05)


def start_ide_probe(
    ide: IDEType | str | None,
    ide_extensions: set[str | tuple[str, ...]],
    process_runner: ProcessRunner | None = None,
) -> IDEProbe | None:
    """Starts listing the configured editor's extensions in the background.

    Args:
        ide: Configured IDE identifier (e.g. IDEType.VSCODE, "cursor").
        ide_extensions: Set of required extension IDs or alternatives tuple.
        process_runner: The probe's own subprocess runner, for isolated process
            groups. If None, a new one is created.

    Returns:
        The running probe, or None when no editor with an extension CLI is
        configured or its CLI is not installed.
    """
    if not ide_extensions or ide is None:
        return None

    try:
        ide_type = ide if isinstance(ide, IDEType) else IDEType(str(ide))
    except ValueError:
        return None

    if ide_type not in (IDEType.VSCODE, IDEType.CURSOR):
        return None

    ide_binary = ide_type.binary_name
    ide_path = find_executable(ide_binary) if ide_binary else None
    if ide_path is None:
        return None

    return IDEProbe(
        ide_type, ide_path, ide_extensions, process_runner or ProcessRunner()
    )


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
    finds extensions missing is reported as a warning. This starts the probe
    and waits for it at once; a caller with other work starts it earlier with
    ``start_ide_probe`` and calls ``finish`` where it needs the result.

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
    probe = start_ide_probe(ide, ide_extensions, process_runner)
    if probe is not None:
        probe.finish(on_diagnostic, progress)
