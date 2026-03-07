import logging
import subprocess

logger = logging.getLogger("protostar")


def execute_subprocess(cmd: list[str]) -> None:
    """Executes a subprocess silently and captures telemetry on failure.

    Args:
        cmd: The command and its arguments as a list of strings.

    Raises:
        RuntimeError: If the subprocess returns a non-zero exit code.
    """
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        output = e.stderr or e.stdout
        logger.error(f"Task failed: {' '.join(cmd)}\nOutput:\n{output}")

        # Catch known edge cases where uv fails to resolve/download python versions
        if cmd[0] == "uv" and "python" in (output or "").lower():
            raise RuntimeError(
                f"Command failed during setup: {cmd[0]}\n"
                "Hint: `uv` encountered an error resolving the requested Python version. "
                "If you have a global `uv.toml` (e.g., at `~/.config/uv/uv.toml`), "
                "ensure `python-downloads` is not set to 'never', or verify the requested "
                "version exists locally."
            ) from e

        error_msg = (
            f"Command failed during setup: {' '.join(cmd)}\n\n"
            f"Details:\n{output.strip() if output else 'No standard error output captured.'}"
        )
        raise RuntimeError(error_msg) from e
