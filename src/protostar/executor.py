import hashlib
import json
import logging
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from rich.console import Console

from .config import ProtostarConfig
from .errors import (
    CommandExecutionError,
    CommandTimeoutError,
    ConfigurationError,
    ExecutionAbortedError,
    FileSystemError,
    ProtostarError,
)
from .fs import atomic_write_text
from .interpolation import render_template
from .manifest import CollisionStrategy, EnvironmentManifest, Severity
from .system import execute_subprocess, is_interactive
from .workspace import (
    generate_python_version_range,
    resolve_package_name,
    resolve_project_name,
    resolve_python_version,
)

logger = logging.getLogger("protostar")
console = Console()


class SystemExecutor:
    """Executes the materialized environment manifest by mutating the local disk and shell."""

    def __init__(
        self,
        manifest: EnvironmentManifest,
        config: ProtostarConfig,
        docker: bool = False,
    ) -> None:
        """Initializes the executor with the target manifest state.

        Args:
            manifest: The centralized state object containing all execution directives.
            config: The active Protostar configuration instance.
            docker: If True, scaffolds a .dockerignore from the manifest ignores.
        """
        self.manifest = manifest
        self.config = config
        self.docker = docker

    @property
    def interpolation_context(self) -> dict[str, str]:
        """Dynamically generates the context for template interpolation."""
        return {
            "PROJECT_NAME": resolve_project_name(self.manifest.metadata),
            "PACKAGE_NAME": resolve_package_name(self.manifest.metadata),
            "PYTHON_VERSION": resolve_python_version(self.manifest.metadata)
            or self.config.python_version
            or "3.13",
        }

    # --- Architecture Note: Deterministic Pipeline Sequencing ---
    # The execution phases in `execute()` follow a strict dependency order:
    #   1. Pre-flight Validation: Fast C-optimized TOML syntax check before writing to disk.
    #   2. Directory & File Realization: Basic structure & config injection prior to task invocation.
    #   3. System Tasks: Git initialization must occur before pre-commit/nbdime post-install tasks.
    #   4. Dependency Resolution: `uv add` runs before post-install tasks so installed binaries
    #      are present in `.venv/bin`.
    #   5. IDE Diagnostics: Runs last as non-blocking telemetry warnings.
    def execute(self) -> None:
        """Executes the materialized manifest in a deterministic sequence."""
        self._validate_targets()
        self._create_directories()
        self._write_injected_files()
        self._write_pre_commit_config()
        self._write_ci_workflow()
        self._write_release_workflow()
        self._write_justfile()
        self._execute_tasks()
        self._install_dependencies()
        self._append_files()
        self._write_ignores()
        self._write_docker_artifacts()
        self._write_ide_settings()
        self._execute_post_install_tasks()
        self._check_ide_extensions()

    def _check_ide_extensions(self) -> None:
        """Verifies that the configured IDE has the recommended extensions installed.

        Fails silently if the IDE CLI is unavailable or execution fails. Appends a warning
        diagnostic only on a successful check that uncovers missing extensions.
        """
        if not self.manifest.ide_extensions or self.config.ide not in (
            "vscode",
            "cursor",
        ):
            return

        binary_map = {"vscode": "code", "cursor": "cursor"}
        ide_binary = binary_map[self.config.ide]

        if not shutil.which(ide_binary):
            return

        try:
            result = subprocess.run(
                [ide_binary, "--list-extensions"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            # Normalize to lowercase for safe diffing
            installed = {ext.lower() for ext in result.stdout.strip().splitlines()}
            missing = []

            for ext_req in self.manifest.ide_extensions:
                if isinstance(ext_req, tuple):
                    if not any(e.lower() in installed for e in ext_req):
                        missing.append(f"{' or '.join(ext_req)}")
                else:
                    if ext_req.lower() not in installed:
                        missing.append(ext_req)

            if missing:
                self.manifest.add_diagnostic(
                    phase="IDE",
                    message=f"Missing recommended {self.config.ide} extensions: {', '.join(missing)}",
                    severity=Severity.WARNING,
                )
        except Exception as e:
            # Reached if the CLI crashes, hangs past 5s, or throws an unexpected I/O error.
            self.manifest.add_diagnostic(
                phase="IDE",
                message=f"IDE extension verification skipped due to an unexpected error: {e}",
                severity=Severity.SKIP,
            )

    def _validate_targets(self) -> None:
        """Validates the syntax of existing target files before disk I/O begins.

        Uses the C-optimized tomllib to quickly evaluate target workspace files,
        ensuring that subsequent tomlkit operations will not fail mid-execution
        and leave the environment fragmented.

        Raises:
            SystemExit: If an existing target TOML file contains syntax errors.
        """
        for filepath in self.manifest.file_appends:
            target = Path(filepath)
            if target.suffix == ".toml" and target.exists():
                try:
                    with target.open("rb") as f:
                        tomllib.load(f)
                except tomllib.TOMLDecodeError as e:
                    raise ConfigurationError(
                        f"Syntax error in existing workspace file: {filepath}\n"
                        f"Details: {e}\n"
                        "Protostar cannot safely merge configurations into a malformed file. "
                        "Please fix the syntax error and re-run the command."
                    ) from e

    def _write_pre_commit_config(self) -> None:
        """Assembles and interpolates the pre-commit configuration."""
        if not self.manifest.wants_pre_commit and not self.manifest.wants_prek:
            return

        target = Path(".pre-commit-config.yaml")
        if self.manifest.should_skip_file(target, phase="Pre-commit"):
            return

        base_yaml = """repos:
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

        # Enforce exactly one empty line between all dynamic payloads
        hooks_yaml = "\n\n".join(self.manifest.pre_commit_hooks)

        # Enforce exactly one empty line between the base block and the dynamic payloads
        full_yaml = f"{base_yaml}\n\n{hooks_yaml}\n" if hooks_yaml else f"{base_yaml}\n"

        if "<% MYPY_DEPENDENCIES %>" in full_yaml:
            deps = self.manifest.dependencies
            if deps:
                # Guarantee exactly 10 spaces of indentation for each list item
                deps_formatted = "\n".join(f"{' ' * 10}- {d}" for d in deps)
                full_yaml = full_yaml.replace("<% MYPY_DEPENDENCIES %>", deps_formatted)
            else:
                # If no runtime dependencies, strip the key cleanly
                full_yaml = full_yaml.replace(
                    "        additional_dependencies:\n<% MYPY_DEPENDENCIES %>", ""
                )

        try:
            atomic_write_text(target, full_yaml)
        except OSError as e:
            raise FileSystemError("write configuration file", str(target), e) from e
        logger.debug("Scaffolded .pre-commit-config.yaml")

    def _write_injected_files(self) -> None:
        """Writes all queued boilerplate files to the local workspace."""
        if not self.manifest.file_injections:
            return

        for filepath, content in self.manifest.file_injections.items():
            interpolated_filepath = render_template(
                filepath, self.interpolation_context
            )
            content = render_template(content, self.interpolation_context)
            target = Path(interpolated_filepath)
            if not self.manifest.should_skip_file(target, phase="Executor"):
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    atomic_write_text(target, content)
                except OSError as e:
                    raise FileSystemError(
                        "inject boilerplate file", str(target), e
                    ) from e
                logger.debug(f"Injected configuration file: {interpolated_filepath}")

    def _create_directories(self) -> None:
        """Scaffolds all queued directories in the local workspace."""
        if not self.manifest.directories:
            return

        for dir_path in self.manifest.directories:
            interpolated_path = render_template(dir_path, self.interpolation_context)
            path = Path(interpolated_path)
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise FileSystemError(
                    "create scaffolding directory", str(path), e
                ) from e
            logger.debug(f"Scaffolded directory: {path}")

    def _execute_tasks(self) -> None:
        """Runs the accumulated system tasks (e.g., initialization commands)."""
        for task in self.manifest.system_tasks:
            binary_name = Path(task.command[0]).name
            msg = task.description or f"Propelling sequence: {binary_name}"
            with console.status(msg):
                execute_subprocess(task.command, timeout=task.timeout)

    def _execute_post_install_tasks(self) -> None:
        """Runs accumulated tasks that require dependencies to be installed first."""
        for task in self.manifest.post_install_tasks:
            binary_name = Path(task.command[0]).name
            msg = task.description or f"Propelling sequence: {binary_name}"
            with console.status(msg):
                execute_subprocess(task.command, timeout=task.timeout)

    def _write_ci_workflow(self) -> None:
        """Assembles and writes the .github/workflows/ci.yml file if requested."""
        if not self.manifest.wants_ci:
            return

        # 1. Resolve matrix dimensions
        supported_os = self.manifest.metadata.get("supported_os", ["Linux"])
        runner_map = {
            "MacOS": "macos-latest",
            "Linux": "ubuntu-latest",
            "Windows": "windows-latest",
        }
        os_matrix = [
            runner_map.get(os_name, "ubuntu-latest") for os_name in supported_os
        ]
        if not os_matrix:
            os_matrix = ["ubuntu-latest"]

        min_python = self.manifest.metadata.get("minimum_python", "3.13")
        python_matrix = generate_python_version_range(min_python)
        if not python_matrix:
            python_matrix = [min_python]

        # Determine the primary runner for coverage
        primary_os = "ubuntu-latest" if "ubuntu-latest" in os_matrix else os_matrix[0]
        primary_python = python_matrix[-1]

        # Build the pytest/codecov logic
        has_pytest = "pytest" in self.manifest.ci_flags
        has_codecov = "codecov" in self.manifest.ci_flags

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
        tool_steps = "\n\n".join(self.manifest.ci_steps)
        if pytest_step:
            if tool_steps:
                tool_steps += "\n\n" + pytest_step
            else:
                tool_steps = pytest_step

        os_matrix_str = ", ".join(f'"{o}"' for o in os_matrix)
        python_matrix_str = ", ".join(f'"{p}"' for p in python_matrix)

        workflow = f"""name: CI

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
        atomic_write_text(Path(".github/workflows/ci.yml"), workflow)

    def _write_release_workflow(self) -> None:
        """Assembles and writes the .github/workflows/release.yml file if requested."""
        if not self.manifest.wants_release:
            return

        workflow = """name: Release

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
        atomic_write_text(Path(".github/workflows/release.yml"), workflow)

    def _write_justfile(self) -> None:
        """Assembles and writes the justfile if requested."""
        if not self.manifest.wants_just:
            return

        target = Path("justfile")
        if self.manifest.should_skip_file(target, phase="Just"):
            return

        # Base header
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
        if self.manifest.just_format_commands:
            justfile_content.extend(
                [
                    "",
                    "# Auto-format code",
                    "format: sync",
                    '    @printf "\\n{{ blue }}=== Formatting Code ==={{ nc }}\\n"',
                ]
            )
            for cmd in self.manifest.just_format_commands:
                justfile_content.append(f"    {cmd}")
            justfile_content.append(
                '    @printf "{{ green }}✔ Formatting complete{{ nc }}\\n"'
            )

        # Lint recipe
        if self.manifest.just_lint_commands:
            justfile_content.extend(
                [
                    "",
                    "# Run linters",
                    "lint: sync",
                    '    @printf "\\n{{ blue }}=== Running Linters ==={{ nc }}\\n"',
                ]
            )
            for cmd in self.manifest.just_lint_commands:
                justfile_content.append(f"    {cmd}")
            justfile_content.append(
                '    @printf "{{ green }}✔ Linting passed{{ nc }}\\n"'
            )

        # Typecheck recipe
        if self.manifest.just_typecheck_commands:
            justfile_content.extend(
                [
                    "",
                    "# Run static type checking",
                    "typecheck: sync",
                    '    @printf "\\n{{ blue }}=== Running Type Checks ==={{ nc }}\\n"',
                ]
            )
            for cmd in self.manifest.just_typecheck_commands:
                justfile_content.append(f"    {cmd}")
            justfile_content.append(
                '    @printf "{{ green }}✔ Type checking passed{{ nc }}\\n"'
            )

        # Pytest recipes
        if "pytest" in self.manifest.ci_flags:
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
        if self.manifest.just_lint_commands:
            ci_deps.append("lint")
        if self.manifest.just_typecheck_commands:
            ci_deps.append("typecheck")
        if "pytest" in self.manifest.ci_flags:
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

        clean_paths = self.manifest.just_clean_paths
        if "pytest" in self.manifest.ci_flags:
            clean_paths.extend(["htmlcov", ".coverage", "coverage.xml"])

        if clean_paths:
            justfile_content.append("    rm -rf \\")
            for path in clean_paths[:-1]:
                justfile_content.append(f"        {path} \\")
            justfile_content.append(f"        {clean_paths[-1]}")

        justfile_content.extend(
            [
                '    find . -type d -name "__pycache__" -exec rm -rf {} +',
                '    @printf "{{ green }}✔ Workspace cleaned{{ nc }}\\n"',
            ]
        )

        # Serve recipe (Zensical)
        if "zensical" in self.manifest.ci_flags:
            justfile_content.extend(
                [
                    "",
                    "# Start the documentation preview server",
                    "serve: sync",
                    '    @printf "\\n{{ blue }}=== Launching Zensical Server ==={{ nc }}\\n"',
                    "    uv run zensical serve -o",
                ]
            )

        full_content = "\n".join(justfile_content) + "\n"
        atomic_write_text(target, full_content)

    # --- Architectural Note: AST-Preserving TOML Merging ---
    # Protostar uses `tomlkit` AST parsing rather than standard dictionary updates or tomllib/tomli.
    #
    # Rationale:
    #   1. Comment & Format Preservation: Simple deserialization/reserialization strips user comments,
    #      custom ordering, and blank lines in pyproject.toml.
    #   2. Selective Overwrites: In OVERWRITE mode, scalar keys are purged from target tables while
    #      sibling tables (e.g., [tool.pytest] vs [tool.ruff]) are preserved to prevent destroying
    #      unrelated tooling configuration.
    #   3. AST Parity Guards: Type mismatches (e.g., merging a table into a scalar key) emit non-fatal
    #      diagnostics rather than corrupting the AST.
    def _deep_merge_tomlkit(
        self,
        base: Any,
        payload: Any,
        overwrite: bool = False,
        path: tuple[str, ...] = (),
    ) -> None:
        """Recursively deep-merges a tomlkit payload into a base document.

        Args:
            base: The existing tomlkit document or table to mutate.
            payload: The incoming tomlkit table to merge into the base.
            overwrite: If True, unmatched scalar keys in the base will be purged,
                and array-of-tables will be completely replaced.
            path: The tuple of keys representing the current path in the document.
        """
        import tomlkit.items

        # Purge scalar/array keys in base that are missing from the payload
        # to enforce strict AST overwriting, while preserving sibling tables.
        # We explicitly protect the root document and the [project] table from being purged.
        if overwrite and len(path) > 0 and path[0] != "project":
            keys_to_remove = []
            for b_key, b_val in base.items():
                if b_key not in payload and not isinstance(
                    b_val, (tomlkit.items.Table, tomlkit.items.AoT)
                ):
                    keys_to_remove.append(b_key)
            for k in keys_to_remove:
                del base[k]

        for key, value in payload.items():
            if key in base:
                if isinstance(value, tomlkit.items.Table):
                    if value.get("__replace__") is True:
                        table_path = ".".join([*path, key])

                        if self.manifest.force_replace:
                            action = "replace"
                        elif self.manifest.force_merge:
                            action = "merge"
                        elif not is_interactive():
                            raise ProtostarError(
                                f"Template requested explicit replacement for '{table_path}' which would overwrite existing user data.\n"
                                f"Aborting to prevent destructive mutations in a non-interactive context.\n"
                                f"Use --force-merge or --force-replace to bypass this check."
                            )
                        else:
                            import questionary
                            from questionary import Choice

                            console.print(
                                f"\n[bold yellow]Configuration Collision:[/bold yellow] The template wants to completely replace [bold cyan]{table_path}[/bold cyan]."
                            )

                            action = questionary.select(
                                "How would you like to proceed?",
                                choices=[
                                    Choice(
                                        "Merge   (Safely deep-merge keys; keeps existing data)",
                                        value="merge",
                                    ),
                                    Choice(
                                        "Replace (Destructive; overwrites the entire table)",
                                        value="replace",
                                    ),
                                    Choice(
                                        "Skip    (Ignore this table entirely)",
                                        value="skip",
                                    ),
                                    Choice(
                                        "Abort   (Safely exit without modifying the environment)",
                                        value="abort",
                                    ),
                                ],
                            ).ask()

                        if action == "abort" or action is None:
                            raise ExecutionAbortedError()
                        if action == "skip":
                            continue
                        if action == "merge":
                            del value["__replace__"]
                            # Fall through to standard merge
                        else:
                            clean = tomlkit.table()
                            for k, v in value.items():
                                if k != "__replace__":
                                    clean.add(k, v)
                            del base[key]
                            base[key] = clean
                            continue

                    # Type Parity Guard
                    if not isinstance(base[key], tomlkit.items.Table):
                        self.manifest.add_diagnostic(
                            phase="Executor",
                            message=f"TOML Merge Collision: Expected a Table for key '{key}', but found {type(base[key]).__name__}. Skipping injection.",
                            severity=Severity.WARNING,
                        )
                        continue

                    has_sub_tables = any(
                        isinstance(v, (tomlkit.items.Table, tomlkit.items.AoT))
                        for v in value.values()
                    )

                    is_project = (key == "project" and len(path) == 0) or (
                        len(path) > 0 and path[0] == "project"
                    )

                    if overwrite and not has_sub_tables and not is_project:
                        base[key] = value
                    else:
                        self._deep_merge_tomlkit(
                            base[key], value, overwrite, (*path, key)
                        )

                elif isinstance(value, tomlkit.items.AoT):
                    # Type Parity Guard
                    if not isinstance(base[key], tomlkit.items.AoT):
                        self.manifest.add_diagnostic(
                            phase="Executor",
                            message=f"TOML Merge Collision: Expected an Array of Tables for key '{key}', but found {type(base[key]).__name__}. Skipping injection.",
                            severity=Severity.WARNING,
                        )
                        continue

                    if overwrite:
                        base[key] = value
                    else:
                        for item in value:
                            base[key].append(item)
                elif isinstance(value, tomlkit.items.Array):
                    if not isinstance(base[key], tomlkit.items.Array):
                        self.manifest.add_diagnostic(
                            phase="Executor",
                            message=f"TOML Merge Collision: Expected an Array for key '{key}', but found {type(base[key]).__name__}. Skipping injection.",
                            severity=Severity.WARNING,
                        )
                        continue

                    if overwrite:
                        base[key] = value
                    else:
                        for item in value:
                            if item not in base[key]:
                                base[key].append(item)
                else:
                    base[key] = value
            else:
                if isinstance(value, tomlkit.items.Table):
                    value.add(tomlkit.nl())
                elif isinstance(value, tomlkit.items.AoT) and len(value) > 0:
                    value[-1].add(tomlkit.nl())

                base[key] = value

    def _append_files(self) -> None:
        """Appends late-binding configuration payloads to their target files."""
        if not self.manifest.file_appends:
            return

        for filepath, contents in self.manifest.file_appends.items():
            target = Path(filepath)

            try:
                original_content = target.read_text() if target.exists() else ""
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise FileSystemError(
                    "read target append context", str(target), e
                ) from e

            if target.suffix == ".toml":
                import tomlkit

                doc = (
                    tomlkit.parse(original_content)
                    if original_content
                    else tomlkit.document()
                )
                ast_mutated = False

                for payload in contents:
                    interpolated = render_template(payload, self.interpolation_context)

                    try:
                        payload_doc = tomlkit.parse(interpolated)
                        ast_mutated = True
                        is_overwrite = (
                            self.manifest.collision_strategy
                            == CollisionStrategy.OVERWRITE
                        )
                        self._deep_merge_tomlkit(
                            doc, payload_doc, overwrite=is_overwrite
                        )
                    except Exception as e:
                        raise ConfigurationError(
                            f"Failed to parse injected TOML payload for {filepath}.\nDetails: {e}"
                        ) from e

                if ast_mutated:
                    new_content = tomlkit.dumps(doc)

                    # Apply visual separators safely using anchored regex to prevent substring collisions
                    tool_headers = [
                        ("Ruff", r"\[tool\.ruff\]"),
                        ("Mypy", r"\[tool\.mypy\]"),
                        ("Pytest", r"\[tool\.pytest\.ini_options\]"),
                        ("Commitizen", r"\[tool\.commitizen\]"),
                        ("Ty", r"\[tool\.ty(?:[^\]]*|)\]"),
                        ("Pyrefly", r"\[tool\.pyrefly\]"),
                    ]

                    for title, table_regex in tool_headers:
                        marker = f"# ---- {title} ---- #"
                        if not re.search(
                            rf"^{marker}", new_content, flags=re.MULTILINE
                        ):
                            new_content = re.sub(
                                rf"^{table_regex}\s*$",
                                f"{marker}\n\n\\g<0>",
                                new_content,
                                flags=re.MULTILINE,
                            )

                    # Add main Tool Configuration header before the first tool header if not exists
                    if "# Tool Configuration" not in new_content:
                        tool_match = re.search(
                            r"^# ---- (Ruff|Mypy|Pytest|Commitizen|Ty|Pyrefly) ---- #\s*$",
                            new_content,
                            flags=re.MULTILINE,
                        )
                        if tool_match:
                            header = "# ==================================================\n# Tool Configuration\n# ==================================================\n\n"
                            # Ensure empty line before the header
                            prefix = (
                                "\n"
                                if not new_content[: tool_match.start()].endswith(
                                    "\n\n"
                                )
                                else ""
                            )
                            new_content = (
                                new_content[: tool_match.start()]
                                + prefix
                                + header
                                + new_content[tool_match.start() :]
                            )

                    new_content = re.sub(r"\n{3,}", "\n\n", new_content)
                    if new_content.strip() != original_content.strip():
                        try:
                            atomic_write_text(target, new_content)
                        except OSError as e:
                            raise FileSystemError(
                                "mutate configuration AST", str(target), e
                            ) from e
                        logger.debug(f"Updated configuration AST in {filepath}")
                continue

            existing_clean = original_content.rstrip()
            missing_payloads = []

            for payload in contents:
                interpolated = render_template(payload, self.interpolation_context)

                # Generate a deterministic boundary marker
                payload_hash = hashlib.md5(payload.encode("utf-8")).hexdigest()[:8]
                marker = f"# --- Protostar Injection: {payload_hash} ---"

                if (
                    marker in original_content
                    and self.manifest.collision_strategy != CollisionStrategy.OVERWRITE
                ):
                    continue

                framed_payload = f"{marker}\n{interpolated.strip()}\n# --- End Protostar Injection ---"
                missing_payloads.append(framed_payload)

            if not missing_payloads:
                continue

            combined_content = "\n\n".join(missing_payloads)
            prefix = "\n\n" if existing_clean and combined_content else ""

            try:
                atomic_write_text(
                    target, existing_clean + prefix + combined_content + "\n"
                )
            except OSError as e:
                raise FileSystemError(
                    "append configurations block", str(target), e
                ) from e
            logger.debug(f"Updated configuration string block in {filepath}")

    def _write_ignores(self) -> None:
        """Deduplicates and appends paths to the local .gitignore."""
        if not self.manifest.vcs_ignores:
            return

        gitignore = Path(".gitignore")
        try:
            existing_content = gitignore.read_text() if gitignore.exists() else ""
            existing_lines = {line.strip() for line in existing_content.splitlines()}
            missing = [p for p in self.manifest.vcs_ignores if p not in existing_lines]

            if missing:
                prefix = (
                    "\n"
                    if existing_content and not existing_content.endswith("\n")
                    else ""
                )
                atomic_write_text(
                    gitignore,
                    existing_content + prefix + "\n".join(sorted(missing)) + "\n",
                )
                logger.debug(f"Appended {len(missing)} items to .gitignore")
        except OSError as e:
            raise FileSystemError(
                "update workspace ignore manifest (.gitignore)", str(gitignore), e
            ) from e

    def _write_docker_artifacts(self) -> None:
        """Generates container artifacts (.dockerignore and Dockerfile)."""
        if not self.docker:
            return

        dockerignore = Path(".dockerignore")
        try:
            existing_content = dockerignore.read_text() if dockerignore.exists() else ""
            existing_lines = {line.strip() for line in existing_content.splitlines()}
            base_ignores = {
                ".git/",
                "tests/",
                "docs/",
                "README*",
                ".vscode/",
                ".idea/",
            }

            has_uv_init = any(
                task.command[:2] == ["uv", "init"]
                for task in self.manifest.system_tasks
            )
            if has_uv_init:
                base_ignores.add(".python-version")

            combined_ignores = self.manifest.vcs_ignores | base_ignores
            missing = [p for p in combined_ignores if p not in existing_lines]

            if missing:
                prefix = (
                    "\n"
                    if existing_content and not existing_content.endswith("\n")
                    else ""
                )
                atomic_write_text(
                    dockerignore,
                    existing_content + prefix + "\n".join(sorted(missing)) + "\n",
                )
                logger.debug(f"Appended {len(missing)} items to .dockerignore")
        except OSError as e:
            raise FileSystemError(
                "scaffold container runtime ignore configurations",
                str(dockerignore),
                e,
            ) from e

        dockerfile = Path("Dockerfile")
        if not self.manifest.should_skip_file(dockerfile, phase="Docker"):
            try:
                context = self.interpolation_context
                py_version = context["PYTHON_VERSION"]
                project_name = context["PROJECT_NAME"]
                package_name = context["PACKAGE_NAME"]

                # Determine runtime command & exposure based on dependencies / presets
                if (
                    "fastapi" in self.manifest.dependencies
                    or "uvicorn" in self.manifest.dependencies
                ):
                    port = str(self.manifest.metadata.get("docker_port") or "8000")
                    runtime_block = (
                        f"EXPOSE {port}\n\n"
                        f'CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "{port}"]'
                    )
                elif "typer" in self.manifest.dependencies or any(
                    "project.scripts" in app
                    for app in self.manifest.file_appends.get("pyproject.toml", [])
                ):
                    runtime_block = f'ENTRYPOINT ["{project_name}"]'
                else:
                    runtime_block = f'CMD ["python", "-m", "{package_name}"]'

                dockerfile_content = f"""# syntax=docker/dockerfile:1

# --- Builder Stage ---
FROM ghcr.io/astral-sh/uv:python{py_version}-bookworm-slim AS builder

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
FROM python:{py_version}-slim-bookworm AS runtime

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
                atomic_write_text(dockerfile, dockerfile_content)
                logger.debug("Scaffolded Dockerfile")
            except OSError as e:
                raise FileSystemError(
                    "scaffold container runtime configurations (Dockerfile)",
                    str(dockerfile),
                    e,
                ) from e

    def _write_ide_settings(self) -> None:
        """Writes the aggregated IDE configuration to the appropriate local files."""
        if not self.manifest.ide_settings:
            return

        vscode_dir = Path(".vscode")
        settings_path = vscode_dir / "settings.json"
        settings = {}

        if settings_path.exists():
            try:
                original_content = settings_path.read_text()
                if original_content.strip():
                    parsed_data = json.loads(original_content)
                    if not isinstance(parsed_data, dict):
                        raise ValueError("Root JSON element is not an object.")
                    settings = parsed_data
            except (json.JSONDecodeError, ValueError):
                self.manifest.add_diagnostic(
                    phase="Executor",
                    message="Existing settings.json contains comments, trailing commas, or is malformed. Skipping IDE settings injection to prevent data loss.",
                    severity=Severity.WARNING,
                )
                return
            except OSError as e:
                raise FileSystemError(
                    "inspect active IDE settings files", str(settings_path), e
                ) from e

        # 1-level deep dictionary merge
        for key, value in self.manifest.ide_settings.items():
            if isinstance(value, dict) and isinstance(settings.get(key), dict):
                settings[key].update(value)
            else:
                settings[key] = value

        try:
            vscode_dir.mkdir(exist_ok=True)
            atomic_write_text(settings_path, json.dumps(settings, indent=4) + "\n")
        except OSError as e:
            raise FileSystemError(
                "synchronize IDE workspace preferences", str(settings_path), e
            ) from e

    def _install_group(self, packages: list[str], args: list[str], label: str) -> None:
        if not packages:
            return

        cmd = ["uv", "add", *args, *packages]
        try:
            with console.status(
                f"Resolving and installing {len(packages)} {label} payloads"
            ):
                execute_subprocess(cmd, timeout=600)
        except (CommandExecutionError, CommandTimeoutError) as e:
            self.manifest.add_diagnostic(
                phase="Executor",
                message=f"{label.capitalize()} dependency resolution failed: {e}",
                severity=Severity.WARNING,
                detail=e.output_detail
                if isinstance(e, CommandExecutionError)
                else None,
            )

    def _install_dependencies(self) -> None:
        """Installs queued dependencies using uv."""
        if (
            not self.manifest.dependencies
            and not self.manifest.dev_dependencies
            and not self.manifest.docs_dependencies
        ):
            return

        self._install_group(self.manifest.dependencies, [], "standard")
        self._install_group(self.manifest.dev_dependencies, ["--dev"], "development")
        self._install_group(
            self.manifest.docs_dependencies, ["--group", "docs"], "documentation"
        )
