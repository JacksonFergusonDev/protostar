"""Seed disposable sandbox repositories for manual lifecycle testing."""

import argparse
import subprocess
from pathlib import Path

import tomlkit

ORIGINAL_SETUP = "Run `uv sync` before running checks."
LOCAL_SETUP = "Run `uv sync --group dev` before running checks."
UPDATED_SETUP = "Run `uv sync --all-groups` before running checks."


def write_file(root: Path, name: str, content: str) -> None:
    """Write one fixture file below a sandbox-owned directory."""
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def run(*args: str, cwd: Path) -> None:
    """Run a fixture setup command in the disposable repository."""
    subprocess.run(args, cwd=cwd, check=True)


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
    print("Existing project ready. Try `protostar init` or `protostar init --dry-run`.")


def template_text(
    version: str,
    coverage_floor: int,
    *,
    show_missing: bool,
    setup: str | None = None,
) -> str:
    """Render the local template's managed TOML contribution."""
    content = (
        'name = "Sandbox Template"\n'
        'description = "A small local template for practicing sync"\n'
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


def sync_project(workspace: Path, *, conflict: bool = False) -> None:
    """Initialize from a local template, then make its next revision available."""
    template = workspace.parent / "template"
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
    write_file(
        Path.home(),
        ".config/protostar/config.toml",
        f'[templates.sandbox-upgrade]\nsource = "{template.as_posix()}"\n'
        "trusted = true\n",
    )
    run("protostar", "init", "--template", "sandbox-upgrade", cwd=workspace)
    commit(workspace, "chore: initialize with sandbox template")

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
    print(f"Updated local template: {template}")
    if not conflict:
        print(
            "Managed project ready. Try `protostar status`, `protostar diff`, "
            "or `protostar sync`."
        )


def sync_conflict_project(workspace: Path) -> None:
    """Make coverage policy and instructions conflict with the template."""
    sync_project(workspace, conflict=True)
    target = workspace / "pyproject.toml"
    document = tomlkit.parse(target.read_text(encoding="utf-8"))
    document["tool"]["coverage"]["report"]["fail_under"] = 85
    target.write_text(tomlkit.dumps(document), encoding="utf-8")
    commit(workspace, "test: raise the project's coverage threshold")
    print("Conflict ready. Run `protostar sync` in this shell to choose a resolution.")


def main() -> None:
    """Prepare the requested scenario in a disposable workspace."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=("existing", "sync", "sync-conflict"))
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    if args.scenario == "existing":
        existing_project(args.workspace)
    elif args.scenario == "sync":
        sync_project(args.workspace)
    else:
        sync_conflict_project(args.workspace)


if __name__ == "__main__":
    main()
