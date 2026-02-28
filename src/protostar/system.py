import logging
import subprocess

from rich.console import Console

logger = logging.getLogger("protostar")
console = Console()


def run_quiet(cmd: list[str], description: str) -> None:
    """Executes a subprocess silently, displaying a Rich spinner to the user.

    Args:
        cmd: The command and its arguments as a list of strings.
        description: The human-readable label to display in the spinner.

    Raises:
        RuntimeError: If the subprocess returns a non-zero exit code.
    """
    with console.status(f"[bold blue]{description}...[/bold blue]", spinner="dots"):
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
            if cmd[0] == "uv" and "python" in output.lower():
                raise RuntimeError(
                    f"Command failed during setup: {cmd[0]}\n"
                    "Hint: `uv` encountered an error resolving the requested Python version. "
                    "If you have a global `uv.toml` (e.g., at `~/.config/uv/uv.toml`), "
                    "ensure `python-downloads` is not set to 'never', or verify the requested "
                    "version exists locally."
                ) from e

            raise RuntimeError(f"Command failed during setup: {cmd[0]}") from e
