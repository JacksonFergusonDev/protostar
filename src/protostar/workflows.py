"""Pure string and template generators for CI/CD workflows and workspace boilerplate."""

from .enums import CIFlag, TargetOS
from .workspace import generate_python_version_range

__all__ = [
    "CIWorkflowSpec",
    "DockerfileSpec",
    "JustfileSpec",
    "generate_ci_workflow",
    "generate_dockerfile",
    "generate_dockerignore",
    "generate_gitignore",
    "generate_justfile",
    "generate_pre_commit_config",
    "generate_release_workflow",
]


from dataclasses import dataclass


@dataclass(frozen=True)
class CIWorkflowSpec:
    """CI Workflow specification."""

    supported_os: list[TargetOS | str]
    min_python: str
    ci_flags: set[CIFlag | str]
    ci_steps: list[str]


@dataclass(frozen=True)
class JustfileSpec:
    """Justfile specification."""

    format_commands: list[str]
    lint_commands: list[str]
    typecheck_commands: list[str]
    ci_flags: set[CIFlag | str]
    clean_paths: list[str]


@dataclass(frozen=True)
class DockerfileSpec:
    """Dockerfile specification."""

    python_version: str
    project_name: str
    package_name: str
    dependencies: list[str]
    is_script_or_typer: bool
    docker_port: str | None = None


def generate_pre_commit_config(
    local_hooks: list[str],
    remote_hooks: list[str],
    dependencies: list[str] | None = None,
) -> str:
    """Assembles and formats the .pre-commit-config.yaml content."""
    base_yaml = """repos:
  # Generic hooks (configured to IGNORE Python)
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
        exclude: \\.py$
      - id: end-of-file-fixer
        exclude: \\.py$
      - id: check-yaml
        exclude: \\.py$
      - id: check-added-large-files"""

    repo_blocks: list[str] = []

    if local_hooks:
        joined_local = "\n\n".join(local_hooks)
        local_block = (
            f"  # Local Python Toolchain (Managed via uv.lock)\n"
            f"  - repo: local\n"
            f"    hooks:\n"
            f"{joined_local}"
        )
        repo_blocks.append(local_block)

    if remote_hooks:
        repo_blocks.extend(remote_hooks)

    # Enforce exactly one empty line between all dynamic payloads
    hooks_yaml = "\n\n".join(repo_blocks)

    # Enforce exactly one empty line between the base block and the dynamic payloads
    full_yaml = f"{base_yaml}\n\n{hooks_yaml}\n" if hooks_yaml else f"{base_yaml}\n"

    if "<% MYPY_DEPENDENCIES %>" in full_yaml:
        deps = dependencies or []
        if deps:
            # Guarantee exactly 10 spaces of indentation for each list item
            deps_formatted = "\n".join(f"{' ' * 10}- {d}" for d in deps)
            full_yaml = full_yaml.replace("<% MYPY_DEPENDENCIES %>", deps_formatted)
        else:
            # If no runtime dependencies, strip the key cleanly
            full_yaml = full_yaml.replace(
                "        additional_dependencies:\n<% MYPY_DEPENDENCIES %>", ""
            )

    return full_yaml


def generate_ci_workflow(spec: CIWorkflowSpec) -> str:
    """Assembles and formats the .github/workflows/ci.yml content."""
    runner_map = {
        "MacOS": "macos-latest",
        "Linux": "ubuntu-latest",
        "Windows": "windows-latest",
    }
    os_matrix = []
    for os_name in spec.supported_os:
        try:
            target_os = (
                os_name if isinstance(os_name, TargetOS) else TargetOS(str(os_name))
            )
            os_matrix.append(target_os.runner_name)
        except ValueError:
            os_matrix.append(runner_map.get(str(os_name), "ubuntu-latest"))

    if not os_matrix:
        os_matrix = ["ubuntu-latest"]

    python_matrix = generate_python_version_range(spec.min_python)
    if not python_matrix:
        python_matrix = [spec.min_python]

    # Determine the primary runner for coverage
    primary_os = "ubuntu-latest" if "ubuntu-latest" in os_matrix else os_matrix[0]
    primary_python = python_matrix[-1]

    # Build the pytest/codecov logic
    has_pytest = CIFlag.PYTEST in spec.ci_flags or "pytest" in spec.ci_flags
    has_codecov = CIFlag.CODECOV in spec.ci_flags or "codecov" in spec.ci_flags

    pytest_step = ""
    if has_pytest:
        if has_codecov:
            pytest_step = f"""      - name: Run tests with coverage # (for Codecov)
        if: ${{{{ matrix.os == '{primary_os}' && matrix.python-version == '{primary_python}' }}}}
        run: uv run pytest --cov --cov-report=xml --junitxml=junit.xml -o junit_family=legacy

      - name: Run tests # (without coverage to avoid overhead on non-Codecov runs)
        if: ${{{{ !(matrix.os == '{primary_os}' && matrix.python-version == '{primary_python}') }}}}
        run: uv run pytest

      - name: Upload coverage to Codecov
        if: matrix.os == '{primary_os}' && matrix.python-version == '{primary_python}'
        uses: codecov/codecov-action@v7
        with:
          token: ${{{{ secrets.CODECOV_TOKEN }}}}
          files: coverage.xml
          disable_search: true
          name: coverage
          fail_ci_if_error: true

      - name: Upload test analytics to Codecov
        if: ${{{{ matrix.os == '{primary_os}' && matrix.python-version == '{primary_python}' && !cancelled() }}}}
        uses: codecov/codecov-action@v7
        with:
          token: ${{{{ secrets.CODECOV_TOKEN }}}}
          files: junit.xml
          disable_search: true
          report_type: test_results
          name: test-results"""
        else:
            pytest_step = """      - name: Run Tests
        run: uv run pytest"""

    # Assemble the rest of the steps
    tool_steps = "\n\n".join(spec.ci_steps)
    if pytest_step:
        if tool_steps:
            tool_steps += "\n\n" + pytest_step
        else:
            tool_steps = pytest_step

    os_matrix_str = ", ".join(f'"{o}"' for o in os_matrix)
    python_matrix_str = ", ".join(f'"{p}"' for p in python_matrix)

    return f"""name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Test on ${{{{ matrix.os }}}} with Python ${{{{ matrix.python-version }}}}
    runs-on: ${{{{ matrix.os }}}}
    strategy:
      matrix:
        os: [{os_matrix_str}]
        python-version: [{python_matrix_str}]

    steps:
      - uses: actions/checkout@v7
      
      - name: Install uv
        uses: astral-sh/setup-uv@v10.0.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
          python-version: ${{{{ matrix.python-version }}}}

      - name: Install dependencies
        run: |
          uv sync --all-extras --dev
          uv pip install pytest-github-actions-annotate-failures

{tool_steps}
"""


def generate_release_workflow() -> str:
    """Assembles and returns the .github/workflows/release.yml content."""
    return """name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  pypi-publish:
    name: Build and Publish to PyPI
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/${{ github.event.repository.name }}
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v7
      
      - name: Install uv
        uses: astral-sh/setup-uv@v10.0.0
        
      - name: Build package
        run: uv build
        
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
"""


def generate_justfile(spec: JustfileSpec) -> str:
    """Assembles and returns the justfile content."""
    justfile_content = [
        'set shell := ["bash", "-euc", "-o", "pipefail"]',
        "set unstable",
        "set quiet",
        "",
        "# --- ANSI Colors ---",
        "",
        "blue := '\\033[1;34m'",
        "green := '\\033[1;32m'",
        "yellow := '\\033[1;33m'",
        "nc := '\\033[0m'",
        "",
        "# Show available commands",
        "default:",
        "    @just --list",
        "",
        "# Sync/install dependencies using uv",
        "sync:",
        "    uv sync --quiet",
    ]

    # Format recipe
    if spec.format_commands:
        justfile_content.extend(
            [
                "",
                "# Auto-format code",
                "format: sync",
                '    @printf "\\n{{ blue }}=== Formatting Code ==={{ nc }}\\n"',
            ]
        )
        for cmd in spec.format_commands:
            justfile_content.append(f"    {cmd}")
        justfile_content.append(
            '    @printf "{{ green }}✔ Formatting complete{{ nc }}\\n"'
        )

    # Lint recipe
    if spec.lint_commands:
        justfile_content.extend(
            [
                "",
                "# Run linters",
                "lint: sync",
                '    @printf "\\n{{ blue }}=== Running Linters ==={{ nc }}\\n"',
            ]
        )
        for cmd in spec.lint_commands:
            justfile_content.append(f"    {cmd}")
        justfile_content.append('    @printf "{{ green }}✔ Linting passed{{ nc }}\\n"')

    # Typecheck recipe
    if spec.typecheck_commands:
        justfile_content.extend(
            [
                "",
                "# Run static type checking",
                "typecheck: sync",
                '    @printf "\\n{{ blue }}=== Running Type Checks ==={{ nc }}\\n"',
            ]
        )
        for cmd in spec.typecheck_commands:
            justfile_content.append(f"    {cmd}")
        justfile_content.append(
            '    @printf "{{ green }}✔ Type checking passed{{ nc }}\\n"'
        )

    # Pytest recipes
    if "pytest" in spec.ci_flags:
        justfile_content.extend(
            [
                "",
                "# Run the full automated testing matrix",
                "test: sync",
                '    @printf "\\n{{ blue }}=== Running Tests ==={{ nc }}\\n"',
                "    uv run pytest",
                '    @printf "{{ green }}✔ All tests passed{{ nc }}\\n"',
                "",
                "# Run tests with coverage",
                "test-cov: sync",
                '    @printf "\\n{{ blue }}=== Running Tests with Coverage ==={{ nc }}\\n"',
                "    uv run pytest --cov",
                '    @printf "{{ green }}✔ Coverage run complete{{ nc }}\\n"',
            ]
        )

    # CI recipe
    ci_deps = []
    if spec.lint_commands:
        ci_deps.append("lint")
    if spec.typecheck_commands:
        ci_deps.append("typecheck")
    if CIFlag.PYTEST in spec.ci_flags or "pytest" in spec.ci_flags:
        ci_deps.append("test")

    if ci_deps:
        deps_str = " ".join(ci_deps)
        justfile_content.extend(
            [
                "",
                "# Run the fast local CI pipeline executed before pushing",
                f"ci: {deps_str}",
                '    @printf "\\n{{ green }}✔ Local CI pipeline completed successfully. Clear to push!{{ nc }}\\n"',
            ]
        )

    # Clean recipe
    justfile_content.extend(
        [
            "",
            "# Remove caches, artifacts, and temp files",
            "clean:",
            '    @printf "\\n{{ blue }}=== Cleaning Workspace ==={{ nc }}\\n"',
        ]
    )

    all_clean_paths = list(spec.clean_paths)
    if CIFlag.PYTEST in spec.ci_flags or "pytest" in spec.ci_flags:
        all_clean_paths.extend(["htmlcov", ".coverage", "coverage.xml"])

    if all_clean_paths:
        justfile_content.append("    rm -rf \\")
        for path in all_clean_paths[:-1]:
            justfile_content.append(f"        {path} \\")
        justfile_content.append(f"        {all_clean_paths[-1]}")

    justfile_content.extend(
        [
            '    find . -type d -name "__pycache__" -exec rm -rf {} +',
            '    @printf "{{ green }}✔ Workspace cleaned{{ nc }}\\n"',
        ]
    )

    # Serve recipe (Zensical)
    if CIFlag.ZENSICAL in spec.ci_flags or "zensical" in spec.ci_flags:
        justfile_content.extend(
            [
                "",
                "# Start the documentation preview server",
                "serve: sync",
                '    @printf "\\n{{ blue }}=== Launching Zensical Server ==={{ nc }}\\n"',
                "    uv run zensical serve -o",
            ]
        )

    return "\n".join(justfile_content) + "\n"


def generate_dockerignore(
    vcs_ignores: set[str],
    has_uv_init: bool = False,
    existing_content: str = "",
) -> str | None:
    """Computes and returns the updated .dockerignore content, or None if no changes."""
    existing_lines = {line.strip() for line in existing_content.splitlines()}
    base_ignores = {
        ".git/",
        "tests/",
        "docs/",
        "README*",
        ".vscode/",
        ".idea/",
    }
    if has_uv_init:
        base_ignores.add(".python-version")

    combined_ignores = vcs_ignores | base_ignores
    missing = [p for p in combined_ignores if p not in existing_lines]
    if not missing:
        return None

    prefix = "\n" if existing_content and not existing_content.endswith("\n") else ""
    return existing_content + prefix + "\n".join(sorted(missing)) + "\n"


def generate_dockerfile(spec: DockerfileSpec) -> str:
    """Generates the multi-stage Dockerfile content."""
    if "fastapi" in spec.dependencies or "uvicorn" in spec.dependencies:
        port = str(spec.docker_port or "8000")
        runtime_block = (
            f"EXPOSE {port}\n\n"
            f'CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "{port}"]'
        )
    elif spec.is_script_or_typer:
        runtime_block = f'ENTRYPOINT ["{spec.project_name}"]'
    else:
        runtime_block = f'CMD ["python", "-m", "{spec.package_name}"]'

    return f"""# syntax=docker/dockerfile:1

# --- Builder Stage ---
FROM ghcr.io/astral-sh/uv:python{spec.python_version}-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation and copy mode for uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies using cache and bind mounts for optimal layer caching
RUN --mount=type=cache,target=/root/.cache/uv \\
    --mount=type=bind,source=uv.lock,target=uv.lock \\
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \\
    uv sync --frozen --no-install-project --no-dev

# Copy application source and build the environment
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \\
    uv sync --frozen --no-dev

# --- Runtime Stage ---
FROM python:{spec.python_version}-slim-bookworm AS runtime

WORKDIR /app

# Security: Run as a non-privileged user
RUN useradd -m -u 10001 appuser
USER appuser

# Copy virtual environment and application code from builder
COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

{runtime_block}
"""


def generate_gitignore(
    vcs_ignores: set[str],
    existing_content: str = "",
) -> str | None:
    """Computes and returns the updated .gitignore content, or None if no changes."""
    existing_lines = {line.strip() for line in existing_content.splitlines()}
    missing = [p for p in vcs_ignores if p not in existing_lines]
    if not missing:
        return None

    prefix = "\n" if existing_content and not existing_content.endswith("\n") else ""
    return existing_content + prefix + "\n".join(sorted(missing)) + "\n"
