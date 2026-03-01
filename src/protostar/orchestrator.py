import json
import logging
import re
import subprocess
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
            self._write_pre_commit_config()  # Inject execution here
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
            console.print(f"\n[bold red]ABORTED:[/bold red] {e}")
            logger.debug("Stack trace:", exc_info=True)
            console.print("[dim]Run with --verbose for a full stack trace.[/dim]")

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

    def _append_files(self) -> None:
        """Appends late-binding configuration payloads to their target files."""
        if not self.manifest.file_appends:
            return

        # Dynamically resolve the active Python version for token interpolation
        python_version = "3.12"  # Safe modern fallback
        pyproject_path = Path("pyproject.toml")

        if pyproject_path.exists():
            content = pyproject_path.read_text()
            # Lightweight extraction of requires-python without a heavy TOML parser
            match = re.search(
                r'requires-python\s*=\s*"(?:>=|==|~=|>|)?(\d+\.\d+)', content
            )
            if match:
                python_version = match.group(1)

        for filepath, contents in self.manifest.file_appends.items():
            target = Path(filepath)
            combined_content = "\n\n".join(contents)

            # Interpolate state tokens
            combined_content = combined_content.replace(
                "{{PYTHON_VERSION}}", python_version
            )

            prefix = ""
            if target.exists():
                existing_content = target.read_text()
                if existing_content and not existing_content.endswith("\n"):
                    prefix = "\n"
            else:
                target.parent.mkdir(parents=True, exist_ok=True)

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
