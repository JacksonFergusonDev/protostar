"""Pure string and template generators for CI/CD workflows and workspace boilerplate."""

import enum
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass

from .registry import RemoteHook
from .workspace import (
    PackageName,
    ProjectName,
    PythonVersion,
    generate_python_version_range,
)

__all__ = [
    "DOCKERFILE",
    "AgentsSpec",
    "CIFlag",
    "CIWorkflowSpec",
    "DockerfileSpec",
    "HookRunner",
    "JustfileSpec",
    "TargetOS",
    "YAMLBuilder",
    "generate_agents_md",
    "generate_ci_workflow",
    "generate_dockerfile",
    "generate_dockerignore",
    "generate_gitignore",
    "generate_justfile",
    "generate_pre_commit_config",
    "generate_release_workflow",
]


class YAMLBuilder:
    """Lightweight zero-dependency builder for assembling cleanly formatted YAML documents."""

    def __init__(self) -> None:
        self._blocks: list[str] = []

    def append_block(self, content: str, indent: int = 0) -> "YAMLBuilder":
        """Dedents content and optionally indents it before appending."""
        dedented = textwrap.dedent(content).strip("\n")
        if dedented:
            indented = (
                textwrap.indent(dedented, " " * indent) if indent > 0 else dedented
            )
            self._blocks.append(indented)
        return self

    def append_raw(self, content: str) -> "YAMLBuilder":
        """Appends a raw content string directly."""
        stripped = content.strip("\n")
        if stripped:
            self._blocks.append(stripped)
        return self

    def build(self, separator: str = "\n\n") -> str:
        """Assembles the final document with standardized spacing and trailing newline."""
        return separator.join(b for b in self._blocks if b) + "\n"


class TargetOS(enum.StrEnum):
    """Enumeration of supported target operating systems."""

    MACOS = "MacOS"
    LINUX = "Linux"
    WINDOWS = "Windows"

    @property
    def runner_name(self) -> str:
        """Returns the default GitHub Actions runner tag for this OS."""
        mapping = {
            TargetOS.MACOS: "macos-latest",
            TargetOS.LINUX: "ubuntu-latest",
            TargetOS.WINDOWS: "windows-latest",
        }
        return mapping[self]

    @property
    def trove_classifier(self) -> str:
        """Returns the PEP 621 PyPI trove classifier for this OS."""
        mapping = {
            TargetOS.MACOS: "Operating System :: MacOS",
            TargetOS.LINUX: "Operating System :: POSIX :: Linux",
            TargetOS.WINDOWS: "Operating System :: Microsoft :: Windows",
        }
        return mapping[self]


class CIFlag(enum.StrEnum):
    """Enumeration of feature flags for CI workflow and justfile generators."""

    PYTEST = "pytest"
    CODECOV = "codecov"
    ZENSICAL = "zensical"


class HookRunner(enum.StrEnum):
    """Enumeration of supported Git hook managers."""

    NONE = "none"
    PRE_COMMIT = "pre-commit"
    PREK = "prek"


@dataclass(frozen=True)
class CIWorkflowSpec:
    """CI Workflow specification."""

    supported_os: list[TargetOS | str]
    min_python: PythonVersion | str
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
class AgentsSpec:
    """AGENTS.md specification, derived from the aggregated tooling state."""

    python_version: str
    hook_runner: HookRunner
    wants_just: bool
    format_commands: list[str]
    lint_commands: list[str]
    typecheck_commands: list[str]
    ci_flags: set[CIFlag | str]


DOCKERFILE = "Dockerfile"
"""Workspace path of the generated container image definition."""


@dataclass(frozen=True)
class DockerfileSpec:
    """Dockerfile specification."""

    python_version: PythonVersion | str
    project_name: ProjectName | str
    package_name: PackageName | str
    dependencies: list[str]
    is_script_or_typer: bool
    docker_port: str | None = None


def generate_pre_commit_config(
    local_hooks: list[str] | None = None,
    remote_hooks: list[str] | None = None,
    core_rev: str | None = None,
    gitleaks_rev: str | None = None,
    dependencies: list[str] | None = None,
    hook_runner: HookRunner = HookRunner.PRE_COMMIT,
    install_hook_types: set[str] | Sequence[str] | None = None,
) -> str:
    """Assembles and formats the .pre-commit-config.yaml content."""
    if hook_runner == HookRunner.PREK:
        base_yaml = """repos:
  # Generic hooks (configured to IGNORE Python)
  - repo: builtin
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: check-case-conflict
      - id: check-symlinks
      - id: check-executables-have-shebangs
      - id: trailing-whitespace
        exclude: \\.py$
      - id: end-of-file-fixer
        exclude: \\.py$
      - id: check-yaml
      - id: check-json
      - id: check-toml"""
    else:
        resolved_core_rev = core_rev or RemoteHook.PRE_COMMIT_HOOKS.placeholder
        base_yaml = f"""repos:
  # Generic hooks (configured to IGNORE Python)
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: {resolved_core_rev}
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: check-case-conflict
      - id: check-symlinks
      - id: check-executables-have-shebangs
      - id: trailing-whitespace
        exclude: \\.py$
      - id: end-of-file-fixer
        exclude: \\.py$
      - id: check-yaml
      - id: check-json
      - id: check-toml"""

    repo_blocks: list[str] = []

    uv_lock_hook = """      - id: uv-lock-check
        name: uv lock check
        entry: uv lock --check
        language: system
        pass_filenames: false
        files: ^(pyproject\\.toml|uv\\.lock)$"""

    local_hooks_with_uv = [uv_lock_hook] + (local_hooks or [])
    joined_local = "\n\n".join(local_hooks_with_uv)
    local_block = (
        f"  # Local Python Toolchain (Managed via uv.lock)\n"
        f"  - repo: local\n"
        f"    hooks:\n"
        f"{joined_local}"
    )
    repo_blocks.append(local_block)

    resolved_gitleaks_rev = gitleaks_rev or RemoteHook.GITLEAKS.placeholder
    gitleaks_hook = f"""  # Check for accidental commits of secrets
  - repo: https://github.com/gitleaks/gitleaks
    rev: {resolved_gitleaks_rev}
    hooks:
      - id: gitleaks"""

    repo_blocks.append(gitleaks_hook)

    if remote_hooks:
        repo_blocks.extend(remote_hooks)

    hook_types = ["pre-commit", *sorted(set(install_hook_types or ()) - {"pre-commit"})]
    header = "default_install_hook_types:\n" + "".join(
        f"  - {kind}\n" for kind in hook_types
    )
    header += "\ndefault_stages:\n  - pre-commit\n\n"

    # Enforce exactly one empty line between all dynamic payloads
    hooks_yaml = "\n\n".join(repo_blocks)

    # Enforce exactly one empty line between the base block and the dynamic payloads
    full_yaml = (
        f"{header}{base_yaml}\n\n{hooks_yaml}\n"
        if hooks_yaml
        else f"{header}{base_yaml}\n"
    )

    if "<% MYPY_DEPENDENCIES %>" in full_yaml:
        deps = dependencies or []
        if deps:
            # Guarantee exactly 10 spaces of indentation for each list item
            deps_formatted = textwrap.indent(
                "\n".join(f"- {d}" for d in deps), " " * 10
            )
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
        python_matrix = [str(spec.min_python)]

    # Determine the primary runner for coverage and baseline for linting
    primary_os = "ubuntu-latest" if "ubuntu-latest" in os_matrix else os_matrix[0]
    primary_python = python_matrix[-1]
    baseline_python = python_matrix[0]

    # Build the pytest/codecov logic
    has_pytest = CIFlag.PYTEST in spec.ci_flags or "pytest" in spec.ci_flags
    has_codecov = CIFlag.CODECOV in spec.ci_flags or "codecov" in spec.ci_flags

    is_single_matrix = len(os_matrix) == 1 and len(python_matrix) == 1

    # Every step is named, and a logical step keeps its name across variants:
    # the workflow merge matches steps by name, so a renamed step would be added
    # alongside its old self instead of updated in place.
    coverage_args = "--cov --cov-report=xml --junitxml=junit.xml -o junit_family=legacy"
    include_block = ""
    pytest_step = ""
    if has_pytest:
        if has_codecov and not is_single_matrix:
            include_block = f"""
        include:
          - os: {primary_os}
            python-version: "{primary_python}"
            coverage: true"""
            # One step for every matrix entry; only the coverage entry pays for it.
            pytest_run = (
                f"uv run pytest ${{{{ matrix.coverage && '{coverage_args}' || '' }}}}"
            )
            coverage_if = "\n        if: matrix.coverage"
            analytics_if = "${{ matrix.coverage && !cancelled() }}"
        elif has_codecov:
            pytest_run = f"uv run pytest {coverage_args}"
            coverage_if = ""
            analytics_if = "${{ !cancelled() }}"
        else:
            pytest_run = "uv run pytest"
        pytest_step = f"""      - name: Run tests
        run: {pytest_run}"""
        if has_codecov:
            pytest_step += f"""

      - name: Upload coverage to Codecov{coverage_if}
        uses: codecov/codecov-action@v7
        with:
          token: ${{{{ secrets.CODECOV_TOKEN }}}}
          files: coverage.xml
          disable_search: true
          name: coverage
          fail_ci_if_error: true

      - name: Upload test analytics to Codecov
        if: {analytics_if}
        uses: codecov/codecov-action@v7
        with:
          token: ${{{{ secrets.CODECOV_TOKEN }}}}
          files: junit.xml
          disable_search: true
          report_type: test_results
          name: test-results"""

    os_matrix_str = ", ".join(f'"{o}"' for o in os_matrix)
    python_matrix_str = ", ".join(f'"{p}"' for p in python_matrix)

    if is_single_matrix:
        test_steps_list = [
            "      - name: Checkout",
            "        uses: actions/checkout@v7",
            "",
            "      - name: Install uv",
            "        uses: astral-sh/setup-uv@v10.0.0",
            "        with:",
            "          enable-cache: true",
            f'          python-version: "{python_matrix[0]}"',
            "",
            "      - name: Install dependencies",
            "        run: |",
            "          uv sync --all-extras --dev --locked",
            "          uv pip install pytest-github-actions-annotate-failures",
        ]
    else:
        test_steps_list = [
            "      - name: Checkout",
            "        uses: actions/checkout@v7",
            "",
            "      - name: Install uv",
            "        uses: astral-sh/setup-uv@v10.0.0",
            "        with:",
            "          enable-cache: true",
            "          python-version: ${{ matrix.python-version }}",
            "",
            "      - name: Install dependencies",
            "        run: |",
            "          uv sync --all-extras --dev --locked",
            "          uv pip install pytest-github-actions-annotate-failures",
        ]

    if pytest_step:
        test_steps_list.append("")
        test_steps_list.append(pytest_step)

    test_steps = "\n".join(test_steps_list)

    jobs_builder = YAMLBuilder()
    if spec.ci_steps:
        lint_steps = "\n\n".join(spec.ci_steps)
        lint_steps = lint_steps.replace("<% PRIMARY_OS %>", primary_os)
        lint_steps = lint_steps.replace("<% BASELINE_PYTHON %>", baseline_python)
        jobs_builder.append_raw(f"""  lint:
    name: Lint & Type Check
    runs-on: {primary_os}

    steps:
      - name: Checkout
        uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@v10.0.0
        with:
          enable-cache: true
          python-version: "{baseline_python}"

      - name: Install dependencies
        run: uv sync --all-extras --dev --locked

{lint_steps}""")

    if is_single_matrix:
        jobs_builder.append_raw(f"""  test:
    name: Test on {os_matrix[0]} with Python {python_matrix[0]}
    runs-on: {os_matrix[0]}

    steps:
{test_steps}""")
    else:
        jobs_builder.append_raw(f"""  test:
    name: Test on ${{{{ matrix.os }}}} with Python ${{{{ matrix.python-version }}}}
    runs-on: ${{{{ matrix.os }}}}
    strategy:
      matrix:
        os: [{os_matrix_str}]
        python-version: [{python_matrix_str}]{include_block}

    steps:
{test_steps}""")

    jobs_body = jobs_builder.build(separator="\n\n")

    return f"""name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
{jobs_body}"""


def generate_release_workflow() -> str:
    """Assembles and returns the .github/workflows/release.yml content."""
    return (
        YAMLBuilder()
        .append_block(
            """
        name: Release

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
              - name: Checkout
                uses: actions/checkout@v7

              - name: Install uv
                uses: astral-sh/setup-uv@v10.0.0

              - name: Build package
                run: uv build

              - name: Publish to PyPI
                uses: pypa/gh-action-pypi-publish@release/v1
    """
        )
        .build()
    )


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
    ci_deps = _just_ci_dependencies(
        spec.lint_commands, spec.typecheck_commands, spec.ci_flags
    )
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


def _just_ci_dependencies(
    lint_commands: list[str],
    typecheck_commands: list[str],
    ci_flags: set[CIFlag | str],
) -> list[str]:
    """Returns the recipes the justfile's ``ci`` recipe depends on, in run order."""
    deps = []
    if lint_commands:
        deps.append("lint")
    if typecheck_commands:
        deps.append("typecheck")
    if CIFlag.PYTEST in ci_flags:
        deps.append("test")
    return deps


def _command_block(commands: list[str]) -> list[str]:
    """Renders shell commands as a fenced Markdown block."""
    return ["", "```bash", *commands, "```"]


def generate_agents_md(spec: AgentsSpec) -> str:
    """Assembles the Protostar-managed AGENTS.md section.

    Every line states a fact about the scaffolded project, never general advice,
    so the section stays accurate as long as Protostar keeps it in sync.

    Args:
        spec: The aggregated tooling state to describe.

    Returns:
        The Markdown section, opening with the document's top-level heading so a
        freshly scaffolded file satisfies first-line-heading lint rules.
    """
    lines = [
        "# Agent Guide",
        "",
        "Protostar generates and updates this section from the project's tooling. "
        "Keep project notes outside the surrounding Protostar markers.",
        "",
        "## Environment",
        "",
        f"- Python {spec.python_version}, managed by uv. "
        "Run `uv sync` to create or update the environment.",
        "- Add dependencies with `uv add <package>`, or `uv add --dev <package>` "
        "for development tools. Do not edit dependency tables in `pyproject.toml` "
        "by hand.",
        "- Tooling is recorded in `[tool.protostar]` in `pyproject.toml`. "
        "To change it, edit `[tool.protostar.tools]` and run `protostar sync`.",
    ]

    has_pytest = CIFlag.PYTEST in spec.ci_flags
    if spec.wants_just:
        commands: list[str] = []
        if spec.format_commands:
            commands.append("- `just format`: apply formatters and safe lint fixes.")
        if spec.lint_commands:
            commands.append("- `just lint`: run the linters.")
        if spec.typecheck_commands:
            commands.append("- `just typecheck`: run static type checks.")
        if has_pytest:
            commands.append("- `just test`: run the test suite.")
        ci_deps = _just_ci_dependencies(
            spec.lint_commands, spec.typecheck_commands, spec.ci_flags
        )
        if ci_deps:
            commands.append(
                f"- `just ci`: run {', '.join(ci_deps)}; "
                "the local check to pass before pushing."
            )
        if commands:
            lines.extend(["", "## Commands", "", *commands])
    else:
        sections = [
            ("Format", spec.format_commands),
            ("Lint", spec.lint_commands),
            ("Type Check", spec.typecheck_commands),
            ("Test", ["uv run pytest"] if has_pytest else []),
        ]
        if any(commands for _, commands in sections):
            lines.extend(["", "## Commands"])
            for title, commands in sections:
                if commands:
                    lines.extend(["", f"### {title}", *_command_block(commands)])

    if spec.hook_runner is not HookRunner.NONE:
        # The pytest module adds a pre-push hook alongside its CI flag.
        push = (
            " and runs the tests before every push"
            if CIFlag.PYTEST in spec.ci_flags
            else ""
        )
        lines.extend(
            [
                "",
                "## Git Hooks",
                "",
                f"{spec.hook_runner.value} runs the hooks in `.pre-commit-config.yaml` "
                f"on every commit{push}. Let them run rather than invoking the same "
                "checks by hand first. If a hook fails or rewrites a file, fix the "
                "cause, restage, and commit again.",
            ]
        )

    return "\n".join(lines) + "\n"


def generate_dockerignore(
    vcs_ignores: set[str],
    has_uv_init: bool = False,
    existing_content: str = "",
) -> str | None:
    """Computes and returns the updated .dockerignore content, or None if no changes."""
    existing_lines = {line.strip() for line in existing_content.splitlines()}
    # README is deliberately not ignored: the scaffolded pyproject declares it as the
    # package readme, so the build backend fails inside the image without it.
    base_ignores = {
        ".git/",
        "tests/",
        "docs/",
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
        # `<package>.main:app` is the src-layout convention and what the api template
        # scaffolds; the project is installed by `uv sync`, so the package is importable.
        runtime_block = (
            f"EXPOSE {port}\n\n"
            f'CMD ["uvicorn", "{spec.package_name}.main:app", '
            f'"--host", "0.0.0.0", "--port", "{port}"]'
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
