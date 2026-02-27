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
            logger.error(
                f"Task failed: {' '.join(cmd)}\nOutput:\n{e.stderr or e.stdout}"
            )
            raise RuntimeError(f"Command failed during setup: {cmd[0]}") from e
