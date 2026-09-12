"""System-level subprocess execution utilities for Protostar."""

import logging
import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .errors import CommandExecutionError, CommandTimeoutError, ProcessTerminationError

logger = logging.getLogger("protostar")


class ProcessRunner:
    """Owns and safely terminates managed subprocesses."""

    def __init__(self, termination_grace_seconds: float = 2.0) -> None:
        """Initializes the runner.

        Args:
            termination_grace_seconds: Time allowed for graceful termination before
                escalating to a forced kill.
        """
        self._active_process: subprocess.Popen[str] | None = None
        self._termination_grace_seconds = termination_grace_seconds

    @property
    def active_process(self) -> subprocess.Popen[str] | None:
        """Returns the currently active managed process, if any."""
        return self._active_process

    def run(
        self,
        cmd: list[str],
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """Executes a subprocess and captures diagnostic output on failure.

        Sanitizes environment variables inherited from an active Python environment,
        while allowing explicit caller overrides.

        Args:
            cmd: The command and its arguments.
            timeout: Optional execution timeout in seconds.
            env: Optional environment overrides.

        Raises:
            CommandTimeoutError: If the execution time limit is exceeded.
            CommandExecutionError: If the process returns a non-zero exit code.
            ProcessTerminationError: If an interrupted process cannot be reaped.
        """
        exe = shutil.which(cmd[0])
        resolved_cmd = list(cmd)
        if exe:
            resolved_cmd[0] = exe

        clean_env = dict(os.environ)
        clean_env.pop("VIRTUAL_ENV", None)
        clean_env.pop("PYTHONHOME", None)
        if env is not None:
            clean_env.update(env)

        kwargs: dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        process = subprocess.Popen(
            resolved_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=clean_env,
            **kwargs,
        )
        self._active_process = process

        process_completed = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            process_completed = True
        except subprocess.TimeoutExpired as e:
            self.terminate_active_process_tree()
            process_completed = True
            logger.debug(f"Task timed out after {timeout} seconds: {' '.join(cmd)}")
            raise CommandTimeoutError(command=cmd, timeout=timeout or 0) from e
        except BaseException:
            self.terminate_active_process_tree()
            process_completed = True
            raise
        finally:
            if process_completed:
                self._active_process = None

        if process.returncode != 0:
            stdout = stdout or ""
            stderr = stderr or ""
            output_blocks = []
            if stdout:
                output_blocks.append(f"--- STDOUT ---\n{stdout.strip()}")
            if stderr:
                output_blocks.append(f"--- STDERR ---\n{stderr.strip()}")

            log_output = (
                "\n\n".join(output_blocks) if output_blocks else "No output captured."
            )
            logger.debug(f"Task failed: {' '.join(cmd)}\nOutput:\n{log_output}")

            raise CommandExecutionError(
                command=cmd,
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr,
            )

    def terminate_active_process_tree(self) -> None:
        """Terminates and reaps the active process group, escalating if necessary."""
        process = self._active_process
        if process is None:
            return
        if process.poll() is not None:
            process.wait()
            self._active_process = None
            return

        self._signal_process_tree(process, force=False)
        try:
            process.wait(timeout=self._termination_grace_seconds)
            self._active_process = None
            return
        except subprocess.TimeoutExpired:
            self._signal_process_tree(process, force=True)
        try:
            process.wait(timeout=self._termination_grace_seconds)
        except subprocess.TimeoutExpired as e:
            raise ProcessTerminationError(
                process.pid,
                "the process remained active after forced termination",
            ) from e
        self._active_process = None

    @staticmethod
    def _signal_process_tree(process: subprocess.Popen[str], *, force: bool) -> None:
        """Signals the process group using platform-appropriate behavior."""
        try:
            if sys.platform == "win32":
                if force:
                    process.kill()
                else:
                    process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                group_signal = signal.SIGKILL if force else signal.SIGTERM
                os.killpg(os.getpgid(process.pid), group_signal)
        except OSError as group_error:
            try:
                if force:
                    process.kill()
                else:
                    process.terminate()
            except OSError as process_error:
                raise ProcessTerminationError(
                    process.pid, str(process_error)
                ) from group_error


@contextmanager
def shield_sigint() -> Iterator[None]:
    """Defers additional SIGINT delivery while a rollback is in progress."""
    previous_handler = signal.getsignal(signal.SIGINT)

    def _ignore_sigint(_signum: int, _frame: object) -> None:
        return

    handler_installed = False
    try:
        signal.signal(signal.SIGINT, _ignore_sigint)
        handler_installed = True
    except ValueError:
        # Signal handlers can only be installed from the main thread.
        pass
    try:
        yield
    finally:
        if handler_installed:
            signal.signal(signal.SIGINT, previous_handler)


def execute_subprocess(
    cmd: list[str],
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Executes one isolated subprocess using a short-lived process runner.

    Args:
        cmd: The command and its arguments.
        timeout: Optional execution timeout in seconds.
        env: Optional environment overrides.
    """
    ProcessRunner().run(cmd, timeout=timeout, env=env)


def is_interactive() -> bool:
    """Evaluates if the environment supports interactive TTY prompts."""
    if "PROTOSTAR_BENCHMARK_WIZARD" in os.environ:
        return True
    return sys.stdin.isatty() and sys.stdout.isatty()


def get_git_config(key: str) -> str | None:
    """Gets a global git configuration value."""
    try:
        result = subprocess.run(
            [shutil.which("git") or "git", "config", "--global", key],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        val = result.stdout.strip()
        return val if val else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
