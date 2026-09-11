"""System-level subprocess execution utilities for Protostar."""

import logging
import os
import shutil
import signal
import subprocess
import sys

from .errors import CommandExecutionError, CommandTimeoutError

logger = logging.getLogger("protostar")


def execute_subprocess(
    cmd: list[str],
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Executes a subprocess silently and captures diagnostic output on failure.

    Sanitizes environment variables (such as VIRTUAL_ENV and PYTHONHOME) so target
    workspace subprocesses execute in clean isolation from caller environments, while
    allowing intentional caller-supplied env overrides.

    Uses Popen with process groups to ensure the entire tree can be terminated
    if the execution is interrupted.

    Args:
        cmd: The command and its arguments as a list of strings.
        timeout: The maximum execution time in seconds. Defaults to None.
        env: Optional environment dictionary override.

    Raises:
        CommandTimeoutError: If the execution time limit is exceeded.
        CommandExecutionError: If the process returns a non-zero exit code.
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

    kwargs = {}
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

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as e:
        _terminate_process_tree(process)
        logger.debug(f"Task timed out after {timeout} seconds: {' '.join(cmd)}")
        raise CommandTimeoutError(command=cmd, timeout=timeout or 0) from e
    except BaseException:
        _terminate_process_tree(process)
        raise

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


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            process.send_signal(signal.CTRL_BREAK_EVENT)
            process.kill()
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except OSError:
        process.kill()
    process.wait()


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
