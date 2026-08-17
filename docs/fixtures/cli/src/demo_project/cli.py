"""Command-line interface for demo_project."""

import typer
from rich.console import Console

from demo_project import __version__

app = typer.Typer(
    name="demo_project",
    help="Command-line interface for demo_project.",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print the version and exit eagerly."""
    if value:
        console.print(f"demo_project version [bold cyan]{__version__}[/bold cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        help="Show the application version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Configure global CLI state."""


if __name__ == "__main__":
    app()
