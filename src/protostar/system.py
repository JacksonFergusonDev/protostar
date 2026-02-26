import logging
import subprocess

from rich.console import Console

logger = logging.getLogger("protostar")
console = Console()


def run_quiet(cmd: list[str], description: str) -> None:
    """Executes a subprocess silently, displaying a rich spinner to the user.

    If the command fails, the raw stderr is dumped to the logger and an
    exception is raised to halt the accretion process.

    Args:
        cmd (list[str]): The command and its arguments.
        description (str): The human-readable string to display in the spinner.

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
