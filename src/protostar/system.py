import logging
import subprocess

logger = logging.getLogger("protostar")


def execute_subprocess(cmd: list[str], timeout: int | None = None) -> None:
    """Executes a subprocess silently and captures telemetry on failure.

    Args:
        cmd: The command and its arguments as a list of strings.
        timeout: The maximum execution time in seconds. Defaults to None.

    Raises:
        RuntimeError: If the subprocess returns a non-zero exit code or times out.
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
        raise RuntimeError(
            f"Command timed out after {timeout} seconds: {' '.join(cmd)}\n"
            "Hint: This is often caused by a stalled network request or an unresponsive registry."
        ) from e
    except subprocess.CalledProcessError as e:
        # Concatenate both streams to prevent critical context loss
        output_blocks = []
        if e.stdout:
            output_blocks.append(f"--- STDOUT ---\n{e.stdout.strip()}")
        if e.stderr:
            output_blocks.append(f"--- STDERR ---\n{e.stderr.strip()}")

        output = (
            "\n\n".join(output_blocks)
            if output_blocks
            else "No standard output or error captured."
        )
        logger.debug(f"Task failed: {' '.join(cmd)}\nOutput:\n{output}")

        # Give Protostar's context first, then yield the floor to the downstream tool.
        error_msg = (
            f"Protostar failed to execute: {' '.join(cmd)}\n"
            f"Subprocess exited with code {e.returncode}.\n\n"
            f"--- Upstream Diagnostics ({cmd[0]}) ---\n"
            f"{output}"
        )
        raise RuntimeError(error_msg) from e
