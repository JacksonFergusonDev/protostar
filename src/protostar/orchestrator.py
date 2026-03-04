import json
import logging
import platform
import re
import subprocess
import sys
import tomllib
import traceback
import urllib.parse
from pathlib import Path

from rich.console import Console

from .config import ProtostarConfig
from .manifest import EnvironmentManifest
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
    ) -> None:
        """Initializes the orchestrator with the requested modules and presets.

        Args:
            modules: The ordered stack of bootstrap layers to execute.
            presets: Domain-specific dependency and directory presets. Defaults to an empty list.
            docker: If True, scaffolds a .dockerignore from the manifest ignores. Defaults to False.
        """
        self.modules = modules
        self.presets = presets or []
        self.docker = docker
        self.manifest = EnvironmentManifest()

    def run(self) -> None:
        """Executes the pre-flight, build, and realization phases."""
        console.print("[bold]Protostar Ignition Sequence Initiated[/bold]")

        try:
            # Phase 1: Pre-flight Verification
            for mod in self.modules:
                mod.pre_flight()

            # Phase 2: Manifest Aggregation
            for mod in self.modules:
                mod.build(self.manifest)

            for preset in self.presets:
                logger.debug(f"Building {preset.name} preset.")
                preset.build(self.manifest)

            # Phase 3: System Execution
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
        if target.exists():
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
            if not target.exists():
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

    def _toml_has_overlap(self, existing: dict, payload: dict) -> bool:
        """Recursively evaluates TOML dictionaries to prevent duplicate table definitions.

        Since configurations are appended as raw strings, injecting a payload that defines
        a table already present in the existing file will result in a TOML parsing error
        (e.g., 'Cannot redefine table'). This function checks for exact table or scalar key collisions.

        Args:
            existing: The parsed TOML dictionary of the target file.
            payload: The parsed TOML dictionary of the incoming configuration block.

        Returns:
            True if a collision is detected, False otherwise.
        """
        for key, value in payload.items():
            if key in existing:
                if isinstance(value, dict) and isinstance(existing[key], dict):
                    # If the payload attempts to add scalar values to an existing table,
                    # a string append would result in a duplicate table header error.
                    has_scalars = any(not isinstance(v, dict) for v in value.values())
                    if has_scalars:
                        return True

                    # Otherwise, both are topological namespaces (e.g., [tool]). Traverse deeper.
                    if self._toml_has_overlap(existing[key], value):
                        return True
                else:
                    # Direct collision on a specific key or mismatched types
                    return True
        return False

    def _append_files(self) -> None:
        """Appends late-binding configuration payloads to their target files.

        Evaluates payloads against existing file state. For TOML files, performs a
        structural DAG comparison to prevent syntax errors like table redefinitions.
        """
        if not self.manifest.file_appends:
            return

        # Dynamically resolve the active Python version
        python_version = None

        # 1. Attempt to scrape uv's generated footprint
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            match = re.search(
                r'requires-python\s*=\s*"(?:>=|==|~=|>|)?(\d+\.\d+)', content
            )
            if match:
                python_version = match.group(1)

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

            existing_content = ""
            if target.exists():
                existing_content = target.read_text()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)

            is_toml = target.suffix == ".toml"
            existing_toml_dict = {}

            if is_toml and existing_content:
                try:
                    existing_toml_dict = tomllib.loads(existing_content)
                except tomllib.TOMLDecodeError:
                    logger.warning(
                        f"Malformed TOML detected in {filepath}. Falling back to string heuristic."
                    )
                    is_toml = False

            missing_payloads = []
            for payload in contents:
                interpolated = payload.replace("{{PYTHON_VERSION}}", python_version)
                payload_dict = {}
                collision = False
                fallback_string = not is_toml

                if is_toml:
                    try:
                        payload_dict = tomllib.loads(interpolated)
                        collision = self._toml_has_overlap(
                            existing_toml_dict, payload_dict
                        )
                    except tomllib.TOMLDecodeError:
                        logger.warning(
                            "Incoming payload is invalid TOML. Falling back to string heuristic."
                        )
                        fallback_string = True

                # Fallback to string-matching heuristic if TOML parsing is bypassed
                if fallback_string:
                    first_line = interpolated.strip().split("\n")[0]
                    if first_line and first_line in existing_content:
                        collision = True

                if not collision:
                    missing_payloads.append(interpolated)

                    # Mutate the in-memory TOML dictionary to prevent identical subsequent
                    # payloads in the same queue from duplicating. A deep merge is not required
                    # here; injecting the top-level keys handles most idempotency edge cases.
                    if is_toml and payload_dict:
                        existing_toml_dict.update(payload_dict)

            if not missing_payloads:
                continue

            combined_content = "\n\n".join(missing_payloads)

            # Ensure clean newline separation
            prefix = (
                "\n" if existing_content and not existing_content.endswith("\n") else ""
            )

            with target.open("a") as f:
                f.write(prefix + combined_content + "\n")

            logger.debug(f"Appended configuration to {filepath}")

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

        # Currently handles VS Code / Cursor architecture.
        # Extensible here if other IDEs require JSON injection.
        vscode_dir = Path(".vscode")
        settings_path = vscode_dir / "settings.json"

        settings = {}
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text())
            except json.JSONDecodeError:
                console.print(
                    "[yellow]Warning:[/yellow] Existing settings.json is malformed. Overwriting."
                )

        # Deep merge isn't strictly necessary for top-level keys like files.exclude,
        # but we do standard dictionary updates to prevent clobbering other settings.
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
            try:
                result = subprocess.run(
                    [pip_cmd, "freeze"], capture_output=True, text=True, check=True
                )
                Path("requirements.txt").write_text(result.stdout)
                logger.debug("Successfully froze dependencies to requirements.txt")
            except Exception as e:
                console.print(
                    f"[yellow]Warning:[/yellow] Failed to freeze dependencies to requirements.txt: {e}"
                )
