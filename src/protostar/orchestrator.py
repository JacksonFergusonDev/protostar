import json
import logging
import os
import platform
import re
import subprocess
import sys
import tomllib
import traceback
import urllib.parse
from pathlib import Path
from typing import Any

from rich.console import Console

from .config import ProtostarConfig
from .manifest import CollisionStrategy, EnvironmentManifest
from .modules import BootstrapModule
from .presets.base import PresetModule
from .system import run_quiet

logger = logging.getLogger("protostar")
console = Console()


class Orchestrator:
    """Manages the lifecycle of the environment scaffolding process."""

    def __init__(
        self,
        modules: list[BootstrapModule],
        presets: list[PresetModule] | None = None,
        docker: bool = False,
        force: bool = False,
    ) -> None:
        """Initializes the orchestrator with the requested modules and presets.

        Args:
            modules: The ordered stack of bootstrap layers to execute.
            presets: Domain-specific dependency and directory presets. Defaults to an empty list.
            docker: If True, scaffolds a .dockerignore from the manifest ignores. Defaults to False.
            force: If True, bypasses interactive prompts and forces a merge on collisions. Defaults to False.
        """
        self.modules = modules
        self.presets = presets or []
        self.docker = docker
        self.force = force
        self.manifest = EnvironmentManifest()

    def _evaluate_collisions(self) -> None:
        """Evaluates the workspace for critical configuration file collisions.

        Halts execution with an interactive prompt if existing configuration markers
        are found on disk. Non-interactive environments default to a safe abort
        unless the --force flag is explicitly provided.
        """
        collision_targets = set()
        for mod in self.modules:
            for marker in mod.collision_markers:
                if marker.exists():
                    collision_targets.add(marker)

        if not collision_targets:
            return

        # Evaluate non-interactive fallback logic
        if not sys.stdin.isatty() or "PYTEST_CURRENT_TEST" in os.environ:
            if self.force:
                logger.debug(
                    "Non-interactive environment detected. --force flag provided. "
                    "Defaulting to MERGE collision strategy."
                )
                self.manifest.collision_strategy = CollisionStrategy.MERGE
                return
            else:
                console.print(
                    "\n[bold red]Collision Detected:[/bold red] The target environment is not empty."
                )
                console.print(
                    "Aborting to prevent destructive mutations in a non-interactive context.\n"
                    "Use the [bold cyan]--force[/bold cyan] flag to bypass this check and merge safely."
                )
                sys.exit(1)

        import questionary
        from questionary import Choice

        console.print(
            "\n[bold yellow]Collision Warning:[/bold yellow] Protostar detected existing configuration files."
        )
        for target in collision_targets:
            console.print(f"  - {target}")

        choice = questionary.select(
            "\nHow would you like to proceed?",
            choices=[
                Choice(
                    title="Merge     (Safely injects missing configs; preserves existing user data)",
                    value=CollisionStrategy.MERGE,
                ),
                Choice(
                    title="Overwrite (Forces injection; updates existing keys to match Protostar)",
                    value=CollisionStrategy.OVERWRITE,
                ),
                Choice(
                    title="Abort     (Safely exit without modifying the environment)",
                    value=CollisionStrategy.ABORT,
                ),
            ],
            style=questionary.Style(
                [
                    ("answer", "fg:cyan bold"),
                    ("pointer", "fg:cyan bold"),
                    ("selected", "fg:cyan"),
                ]
            ),
        ).ask()

        if not choice or choice == CollisionStrategy.ABORT:
            console.print(
                "\n[bold red]ABORTED:[/bold red] Environment initialization cancelled by user."
            )
            sys.exit(1)

        self.manifest.collision_strategy = choice

    def run(self) -> None:
        """Executes the pre-flight, build, and realization phases."""
        console.print("[bold]Protostar Ignition Sequence Initiated[/bold]")

        try:
            # Phase 1: Collision Intercept
            self._evaluate_collisions()

            # Phase 2: Pre-flight Verification
            for mod in self.modules:
                mod.pre_flight()

            # Phase 3: Manifest Aggregation
            for mod in self.modules:
                mod.build(self.manifest)

            for preset in self.presets:
                logger.debug(f"Building {preset.name} preset.")
                preset.build(self.manifest)

            # Inject global configuration states
            config = ProtostarConfig.load()

            if config.global_dev_dependencies:
                logger.debug("Injecting global dev dependencies from configuration.")
                for dep in config.global_dev_dependencies:
                    self.manifest.add_dev_dependency(dep)

            if config.pyproject_injections:
                logger.debug(
                    "Injecting global pyproject.toml payloads from configuration."
                )
                for payload in config.pyproject_injections.values():
                    self.manifest.add_file_append("pyproject.toml", payload)

            # Phase 4: System Execution
            self._create_directories()
            self._write_injected_files()
            self._write_pre_commit_config()
            self._execute_tasks()
            self._append_files()
            self._write_ignores()
            self._write_docker_artifacts()
            self._write_ide_settings()
            self._install_dependencies()

            console.print(
                "\n[bold green]SUCCESS:[/bold green] Accretion disk stabilized. Environment ready."
            )

        except Exception as e:
            # Expected runtime boundaries (e.g., missing binaries, failed network requests)
            if isinstance(e, (RuntimeError, ValueError, FileExistsError)):
                console.print(f"\n[bold red]ABORTED:[/bold red] {e}")
                sys.exit(1)

            # Unexpected internal anomalies: Capture telemetry and prompt for a bug report
            console.print(
                "\n[bold red]CRITICAL FAILURE:[/bold red] Protostar encountered an unexpected error."
            )

            # Extract stack trace and environmental vector
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            issue_body = (
                "### Environment\n"
                f"- **OS**: {platform.system()} {platform.release()}\n"
                f"- **Python**: {sys.version.split()[0]}\n"
                f"- **Command**: `{' '.join(sys.argv)}`\n\n"
                "### Traceback\n"
                f"```python\n{tb_str}\n```\n"
            )

            encoded_body = urllib.parse.quote(issue_body)
            issue_url = f"https://github.com/jacksonfergusondev/protostar/issues/new?title=Crash+Report&body={encoded_body}"

            console.print(
                "This looks like a bug. Please help us fix it by submitting an issue with your telemetry:"
            )
            console.print(f"[bold cyan]{issue_url}[/bold cyan]")

            logger.debug("Stack trace:", exc_info=True)
            sys.exit(1)

    def _write_pre_commit_config(self) -> None:
        """Assembles and interpolates the pre-commit configuration."""
        if not self.manifest.wants_pre_commit:
            return

        target = Path(".pre-commit-config.yaml")
        if (
            target.exists()
            and self.manifest.collision_strategy != CollisionStrategy.OVERWRITE
        ):
            logger.debug(
                "Skipping .pre-commit-config.yaml generation; file already exists."
            )
            return

        # Start with the universal baseline hooks
        base_yaml = """repos:
  # 1. Generic hooks (configured to ignore Python to avoid formatting conflicts)
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
        exclude: \\.py$
      - id: end-of-file-fixer
        exclude: \\.py$
      - id: check-yaml
      - id: check-added-large-files
"""

        # Append all queued hook payloads
        hooks_yaml = "\n".join(self.manifest.pre_commit_hooks)
        full_yaml = f"{base_yaml}\n{hooks_yaml}\n" if hooks_yaml else f"{base_yaml}\n"

        # Late-bind the Mypy dependencies to guarantee static evaluation captures all packages
        if "{{MYPY_DEPENDENCIES}}" in full_yaml:
            deps = self.manifest.dependencies + self.manifest.dev_dependencies
            if deps:
                # Format as a YAML list array with correct indentation
                deps_formatted = "\n".join(f"          - {d}" for d in deps)
            else:
                deps_formatted = "          []"

            full_yaml = full_yaml.replace("{{MYPY_DEPENDENCIES}}", deps_formatted)

        target.write_text(full_yaml)
        logger.debug("Scaffolded .pre-commit-config.yaml")

    def _write_injected_files(self) -> None:
        """Writes all queued boilerplate files to the local workspace."""
        if not self.manifest.file_injections:
            return

        for filepath, content in self.manifest.file_injections.items():
            target = Path(filepath)

            # Allow injections to overwrite existing files if the strategy permits
            if (
                not target.exists()
                or self.manifest.collision_strategy == CollisionStrategy.OVERWRITE
            ):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
                logger.debug(f"Injected configuration file: {filepath}")

    def _create_directories(self) -> None:
        """Scaffolds all queued directories in the local workspace."""
        if not self.manifest.directories:
            return

        for dir_path in self.manifest.directories:
            path = Path(dir_path)
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Scaffolded directory: {path}")

    def _execute_tasks(self) -> None:
        """Runs the accumulated system tasks (e.g., initialization commands)."""
        for task in self.manifest.system_tasks:
            # Use the first argument (e.g., 'uv', 'cargo') as the context descriptor
            run_quiet(task, f"Executing {task[0]}")

    def _deep_merge_tomlkit(
        self, base: Any, payload: Any, overwrite: bool = False
    ) -> None:
        """Recursively deep-merges a tomlkit payload into a base document.

        Handles nested tables and cleanly appends to Arrays of Tables (AoT)
        without overwriting existing list elements. If overwrite is True,
        colliding leaf tables are completely replaced.
        """
        import tomlkit.items

        for key, value in payload.items():
            if key in base:
                if isinstance(value, tomlkit.items.Table) and isinstance(
                    base[key], tomlkit.items.Table
                ):
                    # Check if the table has nested tables inside it
                    has_sub_tables = any(
                        isinstance(v, (tomlkit.items.Table, tomlkit.items.AoT))
                        for v in value.values()
                    )

                    if overwrite and not has_sub_tables:
                        # It's a leaf table (like [tool.ruff]), replace it entirely
                        base[key] = value
                    else:
                        # It's a super-table (like [tool]), keep recursing
                        self._deep_merge_tomlkit(base[key], value, overwrite)

                elif isinstance(value, tomlkit.items.AoT) and isinstance(
                    base[key], tomlkit.items.AoT
                ):
                    if overwrite:
                        base[key] = value
                    else:
                        for item in value:
                            base[key].append(item)
                else:
                    base[key] = value
            else:
                base[key] = value

    def _append_files(self) -> None:
        """Appends late-binding configuration payloads to their target files.

        For TOML files, leverages tomlkit to modify the Abstract Syntax Tree (AST)
        dynamically while preserving formatting and comments. Lazy-loads the
        parser to maintain sub-3ms initialization latency.
        """
        if not self.manifest.file_appends:
            return

        # Dynamically resolve the active Python version
        python_version = None

        # 1. Attempt to safely parse uv's generated footprint using tomllib
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            try:
                with pyproject_path.open("rb") as f:
                    pyproject_data = tomllib.load(f)
                    req_python = pyproject_data.get("project", {}).get(
                        "requires-python", ""
                    )

                    # Regex is now only used to strip PEP 440 operators (>=, ~=) from the validated string
                    match = re.search(r"(\d+\.\d+)", req_python)
                    if match:
                        python_version = match.group(1)
            except Exception as e:
                logger.debug(f"Failed to parse pyproject.toml for python version: {e}")

        # 2. Attempt to scrape pip's generated footprint
        if not python_version:
            pyvenv_path = Path(".venv/pyvenv.cfg")
            if pyvenv_path.exists():
                content = pyvenv_path.read_text()
                match = re.search(r"version\s*=\s*(\d+\.\d+)", content)
                if match:
                    python_version = match.group(1)

        # 3. Fallback to the configuration state, then 3.12
        if not python_version:
            config = ProtostarConfig.load()
            python_version = config.python_version or "3.12"

        for filepath, contents in self.manifest.file_appends.items():
            target = Path(filepath)

            original_content = ""
            if target.exists():
                original_content = target.read_text()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)

            existing_content = original_content
            is_toml = target.suffix == ".toml"

            # 1. Attempt to lazy-load tomlkit
            if is_toml:
                try:
                    import tomlkit
                except ImportError:
                    logger.debug("tomlkit not found. Falling back to string heuristic.")
                    is_toml = False

            # 2. Parse the existing file AST
            doc = None
            if is_toml:
                try:
                    doc = (
                        tomlkit.parse(existing_content)
                        if existing_content
                        else tomlkit.document()
                    )
                except Exception as e:
                    logger.warning(
                        f"Malformed TOML detected in {filepath}: {e}. Falling back to strings."
                    )
                    is_toml = False

            # 3. Apply the payloads to the AST
            if is_toml and doc is not None:
                ast_mutated = False
                for payload in contents:
                    interpolated = payload.replace("{{PYTHON_VERSION}}", python_version)
                    try:
                        payload_doc = tomlkit.parse(interpolated)
                        ast_mutated = True

                        # Use our updated deep merge function to handle both strategies cleanly
                        is_overwrite = (
                            self.manifest.collision_strategy
                            == CollisionStrategy.OVERWRITE
                        )
                        self._deep_merge_tomlkit(
                            doc, payload_doc, overwrite=is_overwrite
                        )

                    except Exception as e:
                        logger.warning(
                            f"Failed to parse incoming TOML payload: {e}. Falling back."
                        )
                        is_toml = False
                        break

                # If AST parsing was successful across all payloads, write to disk and exit the loop
                if is_toml and ast_mutated:
                    new_content = tomlkit.dumps(doc)
                    if new_content.strip() != original_content.strip():
                        target.write_text(new_content)
                        logger.debug(f"Updated configuration AST in {filepath}")
                    continue

            # 4. Fallback for standard string appends (or if TOML failed)
            missing_payloads = []
            for payload in contents:
                interpolated = payload.replace("{{PYTHON_VERSION}}", python_version)
                first_line = interpolated.strip().split("\n")[0]

                if (
                    first_line
                    and first_line in existing_content
                    and self.manifest.collision_strategy != CollisionStrategy.OVERWRITE
                ):
                    continue

                missing_payloads.append(interpolated)

            existing_clean = existing_content.rstrip()

            if not missing_payloads and existing_clean == original_content.rstrip():
                continue

            combined_content = "\n\n".join(missing_payloads)
            prefix = "\n\n" if existing_clean and combined_content else ""

            target.write_text(existing_clean + prefix + combined_content + "\n")
            logger.debug(f"Updated configuration string block in {filepath}")

    def _write_ignores(self) -> None:
        """Deduplicates and appends paths to the local .gitignore."""
        if not self.manifest.vcs_ignores:
            return

        gitignore = Path(".gitignore")
        existing_content = ""

        if gitignore.exists():
            existing_content = gitignore.read_text()

        missing = [p for p in self.manifest.vcs_ignores if p not in existing_content]

        if missing:
            with gitignore.open("a") as f:
                prefix = (
                    "\n"
                    if existing_content and not existing_content.endswith("\n")
                    else ""
                )
                f.write(prefix + "\n".join(missing) + "\n")
            logger.debug(f"Appended {len(missing)} items to .gitignore")

    def _write_docker_artifacts(self) -> None:
        """Generates a .dockerignore to optimize container build contexts."""
        if not self.docker:
            return

        dockerignore = Path(".dockerignore")
        existing_content = ""

        if dockerignore.exists():
            existing_content = dockerignore.read_text()

        # Combine manifest ignores with standard daemon context bloat exclusions
        base_ignores = {".git/", "tests/", "docs/", "README*", ".vscode/", ".idea/"}

        # Exclude local Python version pins from the daemon context if managed by uv.
        # We only append this if uv is actively generating the project footprint.
        has_uv_init = any(
            task[:2] == ["uv", "init"] for task in self.manifest.system_tasks
        )
        if has_uv_init:
            base_ignores.add(".python-version")

        combined_ignores = self.manifest.vcs_ignores | base_ignores

        missing = [p for p in combined_ignores if p not in existing_content]

        if missing:
            with dockerignore.open("a") as f:
                prefix = (
                    "\n"
                    if existing_content and not existing_content.endswith("\n")
                    else ""
                )
                # Sort for clean diffs and readability
                f.write(prefix + "\n".join(sorted(missing)) + "\n")
            logger.debug(f"Appended {len(missing)} items to .dockerignore")

    def _write_ide_settings(self) -> None:
        """Writes the aggregated IDE configuration to the appropriate local files."""
        if not self.manifest.ide_settings:
            return

        vscode_dir = Path(".vscode")
        settings_path = vscode_dir / "settings.json"

        settings = {}
        if settings_path.exists():
            try:
                # Note: This will fail if the file contains JSONC (comments).
                settings = json.loads(settings_path.read_text())
            except json.JSONDecodeError:
                console.print(
                    "[yellow]Warning:[/yellow] Existing settings.json contains comments or is malformed. "
                    "Skipping IDE settings injection to prevent data loss."
                )
                return

        for key, value in self.manifest.ide_settings.items():
            if isinstance(value, dict) and isinstance(settings.get(key), dict):
                settings[key].update(value)
            else:
                settings[key] = value

        vscode_dir.mkdir(exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=4) + "\n")

    def _install_dependencies(self) -> None:
        """Installs queued dependencies using the active Python manager."""
        if not self.manifest.dependencies and not self.manifest.dev_dependencies:
            return

        config = ProtostarConfig.load()

        if config.python_package_manager == "uv":
            if self.manifest.dependencies:
                cmd = ["uv", "add"] + self.manifest.dependencies
                run_quiet(
                    cmd,
                    f"Resolving and installing {len(self.manifest.dependencies)} dependencies",
                )

            if self.manifest.dev_dependencies:
                dev_cmd = ["uv", "add", "--dev"] + self.manifest.dev_dependencies
                run_quiet(
                    dev_cmd,
                    f"Resolving and installing {len(self.manifest.dev_dependencies)} development dependencies",
                )

        else:
            venv_pip = Path(".venv/bin/pip")
            pip_cmd = str(venv_pip) if venv_pip.exists() else "pip"

            # Pip does not have a native project-level dev dependency segregation concept
            # like uv without external files, so we install them collectively into the environment.
            all_deps = self.manifest.dependencies + self.manifest.dev_dependencies

            cmd = [pip_cmd, "install"] + all_deps

            run_quiet(
                cmd,
                f"Resolving and installing {len(all_deps)} total dependencies",
            )

            # Freeze the state to mirror uv's declarative pyproject.toml updates
            req_path = Path("requirements.txt")
            if req_path.exists():
                console.print(
                    "[yellow]Warning:[/yellow] requirements.txt already exists. "
                    "Dependencies were installed to the virtual environment, but the file was not overwritten."
                )
            else:
                try:
                    result = subprocess.run(
                        [pip_cmd, "freeze"], capture_output=True, text=True, check=True
                    )
                    req_path.write_text(result.stdout)
                    logger.debug("Successfully froze dependencies to requirements.txt")
                except Exception as e:
                    console.print(
                        f"[yellow]Warning:[/yellow] Failed to freeze dependencies to requirements.txt: {e}"
                    )
