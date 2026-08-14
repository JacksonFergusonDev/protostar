"""Preset module for command-line interface applications."""

import logging
from typing import TYPE_CHECKING

from protostar.utils import resolve_package_name, resolve_project_name

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
        init_content = f'"""Package {package_name}."""\n\n__version__ = "0.1.0"\n'
        manifest.add_file_injection(f"src/{package_name}/__init__.py", init_content)

        # 3. Starter CLI entrypoint with Typer and Rich
        cli_content = f'''"""Command-line interface for {raw_name}."""

import typer
from rich.console import Console

app = typer.Typer(
    name="{raw_name}",
    help="Command-line interface for {raw_name}.",
    add_completion=False,
)
console = Console()


@app.command()
def hello(name: str = "World") -> None:
    """Says hello to NAME."""
    console.print(f"Hello, [bold cyan]{{name}}[/bold cyan]!")


def main() -> None:
    """Entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
'''
        manifest.add_file_injection(f"src/{package_name}/cli.py", cli_content)

        # 4. Starter CLI tests with Typer CliRunner
        test_content = f'''"""Tests for the {raw_name} CLI."""

from typer.testing import CliRunner

from {package_name}.cli import app

runner = CliRunner()


def test_hello_default() -> None:
    """Test the hello command with default argument."""
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "Hello, World!" in result.stdout


def test_hello_custom_name() -> None:
    """Test the hello command with a custom name."""
    result = runner.invoke(app, ["hello", "--name", "Protostar"])
    assert result.exit_code == 0
    assert "Hello, Protostar!" in result.stdout
'''
        manifest.add_file_injection("tests/test_cli.py", test_content)

        # 5. Starter README.md
        desc = manifest.metadata.get("description", "")
        desc_line = f"\n{desc}\n" if desc else ""
        manifest.add_file_injection("README.md", f"# {raw_name}\n{desc_line}")

        # 6. Inject [project.scripts] entry point into pyproject.toml
        project_script = f"""[project.scripts]
{raw_name} = "{package_name}.cli:app"
"""
        manifest.add_file_append("pyproject.toml", project_script)
