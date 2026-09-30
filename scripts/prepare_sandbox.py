"""Seed disposable repositories for manual lifecycle testing and demo recordings.

Every scenario writes only below the directories it is given, so the sandbox
and the demo recorder can build the same fixture without touching the host's
home directory or Protostar configuration.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import tomlkit

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import OutputStyle, report

CONFIG_ENV_VAR = "PROTOSTAR_CONFIG"

ORIGINAL_SETUP = "Run `uv sync` before running checks."
LOCAL_SETUP = "Run `uv sync --group dev` before running checks."
UPDATED_SETUP = "Run `uv sync --all-groups` before running checks."


def write_file(root: Path, name: str, content: str) -> None:
    """Write one fixture file below a scenario-owned directory."""
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def run(*args: str, cwd: Path, config: Path | None = None) -> None:
    """Run a fixture setup command, optionally against the scenario's own configuration."""
    env = os.environ.copy()
    if config is not None:
        env[CONFIG_ENV_VAR] = str(config)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def commit(workspace: Path, message: str) -> None:
    """Record a realistic project baseline without host Git identity or hooks."""
    run("git", "add", ".", cwd=workspace)
    run(
        "git",
        "-c",
        "user.name=Sandbox Developer",
        "-c",
        "user.email=sandbox@example.invalid",
        "commit",
        "--quiet",
        "--no-verify",
        "-m",
        message,
        cwd=workspace,
    )


def existing_project(workspace: Path) -> None:
    """Create a small Python repo with user-owned configuration and source."""
    run("git", "init", "--quiet", "-b", "main", cwd=workspace)
    write_file(
        workspace,
        "pyproject.toml",
        '[project]\nname = "sandbox-app"\nversion = "0.1.0"\n'
        'requires-python = ">=3.12"\ndependencies = []\n\n'
        "[tool.ruff]\nline-length = 100  # The team chose this limit.\n",
    )
    write_file(
        workspace,
        "README.md",
        "# Sandbox app\n\nA small existing Python project maintained by a team.\n",
    )
    write_file(workspace, ".gitignore", ".venv/\n__pycache__/\n")
    write_file(
        workspace,
        "src/sandbox_app/__init__.py",
        '"""The existing application."""\n\n\n'
        'def greet(name: str) -> str:\n    """Greet a user."""\n'
        '    return f"Hello, {name}!"\n',
    )
    write_file(
        workspace,
        "tests/test_app.py",
        "from sandbox_app import greet\n\n\n"
        'def test_greet() -> None:\n    assert greet("Ada") == "Hello, Ada!"\n',
    )
    write_file(
        workspace,
        "justfile",
        "test:\n    uv run pytest\n",
    )
    commit(workspace, "chore: establish existing project")
    report(
        "Existing project ready. Try `protostar init` or `protostar init --dry-run`.",
        style=OutputStyle.SUCCESS,
    )


def template_text(
    version: str,
    coverage_floor: int,
    *,
    show_missing: bool,
    setup: str | None = None,
) -> str:
    """Render the team template's managed TOML contribution."""
    content = (
        'name = "Team Template"\n'
        'description = "The shared starting point for the team\'s Python services"\n'
        f'version = "{version}"\n'
        "ruff = false\n\n"
        "[dev.pyproject]\n"
        "coverage = '''\n"
        "[tool.coverage.report]\n"
        f"fail_under = {coverage_floor}\n"
        f"show_missing = {str(show_missing).lower()}\n"
        "'''\n"
    )
    if setup is not None:
        content += (
            '\n[appends."docs/development.md".setup]\n'
            "content = '''\n"
            "## Development setup\n\n"
            f"{setup}\n"
            "'''\n"
        )
    return content


def sync_project(workspace: Path, fixture: Path, *, conflict: bool = False) -> Path:
    """Initialize from a local template, then make its next revision available.

    Args:
        workspace: The empty project directory to initialize.
        fixture: A scenario-owned directory for the template and the
            Protostar configuration the project is initialized with.
        conflict: Whether the project also edits what the update changes.

    Returns:
        The configuration file to point ``PROTOSTAR_CONFIG`` at, so later
        commands see the configuration the project was initialized with.
    """
    template = fixture / "team-template"
    config = fixture / "config.toml"
    # Only a configured template is trusted to run its setup commands headlessly.
    write_file(
        fixture,
        "config.toml",
        f'[templates.team-template]\nsource = "{template.as_posix()}"\n'
        'trusted = true\n\n[env]\npython_version = "3.13"\n',
    )
    run("git", "init", "--quiet", "-b", "main", cwd=workspace)
    write_file(
        template,
        "protostar.toml",
        template_text(
            "1.0.0",
            80,
            show_missing=False,
            setup=ORIGINAL_SETUP if conflict else None,
        ),
    )
    write_file(
        template,
        "template/notes/maintenance.md",
        "# Maintenance\n\nTemplate guidance for maintainers.\n",
    )
    run(
        "protostar",
        "init",
        "--template",
        "team-template",
        cwd=workspace,
        config=config,
    )
    commit(workspace, "chore: initialize from the team template")

    write_file(
        workspace,
        "notes/maintenance.md",
        "# Maintenance\n\nTemplate guidance for maintainers.\n\n"
        "Our team also checks the nightly reports.\n",
    )
    if conflict:
        development = workspace / "docs/development.md"
        content = development.read_text(encoding="utf-8")
        development.write_text(
            content.replace(ORIGINAL_SETUP, LOCAL_SETUP)
            + "\nProject note: Check the macOS smoke tests before release.\n",
            encoding="utf-8",
        )
        target = workspace / "pyproject.toml"
        document = tomlkit.parse(target.read_text(encoding="utf-8"))
        document["tool"]["coverage"]["report"]["fail_under"] = 85
        target.write_text(tomlkit.dumps(document), encoding="utf-8")
    commit(workspace, "docs: add local maintenance guidance")

    write_file(
        template,
        "protostar.toml",
        template_text(
            "1.1.0",
            90,
            show_missing=True,
            setup=UPDATED_SETUP if conflict else None,
        ),
    )
    write_file(
        template,
        "template/docs/setup.md",
        "# Setup\n\nThe updated template now includes setup guidance.\n",
    )
    return config


def main() -> None:
    """Prepare the requested scenario in a disposable workspace."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=("existing", "sync", "sync-conflict"))
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--fixture",
        type=Path,
        help="Directory for the scenario's template and configuration "
        "(defaults to a 'fixture' directory beside the workspace).",
    )
    args = parser.parse_args()
    if args.scenario == "existing":
        existing_project(args.workspace)
        return
    fixture = args.fixture or args.workspace.parent / "fixture"
    sync_project(args.workspace, fixture, conflict=args.scenario == "sync-conflict")
    report(f"Updated template: {fixture / 'team-template'}", style=OutputStyle.WARNING)
    if args.scenario == "sync":
        report(
            "Managed project ready. Try `protostar status`, `protostar diff`, or `protostar sync`.",
            style=OutputStyle.DETAIL,
        )
    else:
        report(
            "Conflict ready. Run `protostar sync` to choose a resolution.",
            style=OutputStyle.WARNING,
        )


if __name__ == "__main__":
    main()
