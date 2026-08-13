"""System-level subprocess execution utilities for Protostar."""

import logging
import subprocess

from .errors import CommandExecutionError, CommandTimeoutError

logger = logging.getLogger("protostar")


def execute_subprocess(cmd: list[str], timeout: int | None = None) -> None:
    """Executes a subprocess silently and captures telemetry on failure.

    Args:
        cmd: The command and its arguments as a list of strings.
        timeout: The maximum execution time in seconds. Defaults to None.

    Raises:
        CommandTimeoutError: If the execution time limit is exceeded.
        CommandExecutionError: If the process returns a non-zero exit code.
    """
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        logger.debug(f"Task timed out after {timeout} seconds: {' '.join(cmd)}")
        raise CommandTimeoutError(command=cmd, timeout=timeout or 0) from e
    except subprocess.CalledProcessError as e:
        stdout = e.stdout or ""
        stderr = e.stderr or ""

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
            returncode=e.returncode,
            stdout=stdout,
            stderr=stderr,
        ) from e
