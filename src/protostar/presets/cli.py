"""Preset module for command-line interface applications."""

import logging
from typing import TYPE_CHECKING

from protostar.workspace import resolve_package_name, resolve_project_name

from .base import PresetModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


class CliPreset(PresetModule):
    """Injects TUI rendering and argument parsing dependencies."""

    cli_flags = ("--cli",)
    cli_help = "Inject CLI application dependencies"

    @property
    def name(self) -> str:
        """Returns the human-readable preset name."""
        return "CLI Application"

    @property
    def default_dependencies(self) -> list[str]:
        """Returns a list of default packages to inject for this preset."""
        return ["typer", "rich"]

    @property
    def default_directories(self) -> list[str]:
        """Returns a list of default directories to scaffold for this preset."""
        return ["src", "tests"]

    @property
    def default_ignores(self) -> list[str]:
        """Returns a list of default VCS ignore patterns for this preset."""
        return []

    @property
    def default_files(self) -> dict[str, str]:
        """Returns a dict mapping file paths to their initial content to scaffold."""
        return {"README.md": ""}

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Appends CLI dependencies, package directory, starter code, and entrypoints.

        Args:
            manifest: The centralized state object.
        """
        logger.debug(f"Building {self.name} preset layer.")

        if self._apply_overrides(manifest):
            return

        for dep in self.default_dependencies:
            manifest.add_dependency(dep)

        for artifact in self.default_ignores:
            manifest.add_vcs_ignore(artifact)

        raw_name = resolve_project_name(manifest.metadata)
        package_name = resolve_package_name(manifest.metadata)

        # 1. Directory Scaffolding
        manifest.add_directory(f"src/{package_name}")
        manifest.add_directory("tests")

        # 2. Package __init__.py
        desc = manifest.metadata.get("description", "").strip()
        docstring_header = f'"""{desc}"""\n\n' if desc else ""
        init_content = f"""{docstring_header}import contextlib
import importlib.metadata

__version__ = "unknown"
with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    __version__ = importlib.metadata.version("{raw_name}")
"""
        manifest.add_file_injection(f"src/{package_name}/__init__.py", init_content)

        help_text = desc if desc else f"Command-line interface for {raw_name}."

        # 3. Starter CLI entrypoint with Typer and Rich
        cli_content = f'''"""Command-line interface for {raw_name}."""

import typer
from rich.console import Console

from {package_name} import __version__

app = typer.Typer(
    name="{raw_name}",
    help="{help_text}",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print the version and exit eagerly."""
    if value:
        console.print(f"{raw_name} version [bold cyan]{{__version__}}[/bold cyan]")
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
'''

        manifest.add_file_injection(f"src/{package_name}/cli.py", cli_content)

        # 4. Starter CLI tests with Typer CliRunner
        test_content = f'''"""Tests for the {raw_name} CLI."""

from typer.testing import CliRunner

from {package_name}.cli import app

runner = CliRunner()


def test_version() -> None:
    """Test the --version flag displays the version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "{raw_name} version" in result.stdout


def test_help() -> None:
    """Test the --help flag displays the help message."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "{raw_name}" in result.stdout
'''
        manifest.add_file_injection("tests/test_cli.py", test_content)

        # 5. Starter README.md
        desc_line = f"\n{desc}\n" if desc else ""
        manifest.add_file_injection("README.md", f"# {raw_name}\n{desc_line}")

        # 6. Inject [project.scripts] entry point into pyproject.toml
        project_script = f"""[project.scripts]
{raw_name} = "{package_name}.cli:app"
"""
        manifest.add_file_append("pyproject.toml", project_script)
