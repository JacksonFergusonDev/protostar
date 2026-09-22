"""Tests for the demo_project CLI."""

from typer.testing import CliRunner

from demo_project.cli import app

runner = CliRunner()


def test_version() -> None:
    """Test the --version flag displays the version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "demo_project version" in result.stdout


def test_help() -> None:
    """Test the --help flag displays the help message."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "demo_project" in result.stdout
