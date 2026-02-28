import json
import logging
import shutil
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
        direnv: bool = False,
    ) -> None:
        """Initializes the orchestrator with the requested modules and presets.

        Args:
            modules: The ordered stack of bootstrap layers to execute.
            presets: Domain-specific dependency and directory presets. Defaults to an empty list.
            docker: If True, scaffolds a .dockerignore from the manifest ignores. Defaults to False.
            direnv: If True, scaffolds a .envrc file and allows it via direnv. Defaults to False.
        """
        self.modules = modules
        self.presets = presets or []
        self.docker = docker
        self.direnv = direnv
        self.manifest = EnvironmentManifest()

    def run(self) -> None:
        """Executes the pre-flight, build, and realization phases."""
        console.print("[bold]Protostar Ignition Sequence Initiated[/bold]")

        try:
            # Phase 1: Pre-flight Verification
            if self.direnv:
                self._pre_flight_direnv()

            for mod in self.modules:
                mod.pre_flight()

            # Phase 2: Manifest Aggregation
            if self.direnv:
                self.manifest.add_vcs_ignore(".envrc.local")
                self.manifest.add_vcs_ignore(".direnv/")

            for mod in self.modules:
                mod.build(self.manifest)

            for preset in self.presets:
                logger.debug(f"Building {preset.name} preset.")
                preset.build(self.manifest)

            # Phase 3: System Execution
            self._execute_tasks()
            self._create_directories()
            self._write_envrc()
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

    def _pre_flight_direnv(self) -> None:
        """Ensures direnv is installed before any disk mutations occur."""
        if not shutil.which("direnv"):
            raise RuntimeError(
                "direnv is not installed. Install it with: brew install direnv\n\n"
                "Once installed, ensure the shell hook is active in your ~/.zshrc:\n"
                '    eval "$(direnv hook zsh)"\n\n'
                "Then re-run: protostar init"
            )

    def _write_envrc(self) -> None:
        """Scaffolds the .envrc and executes the allow hook."""
        if not self.direnv:
            return

        envrc = Path(".envrc")
        if envrc.exists():
            logger.debug("Skipping .envrc generation; file already exists.")
            return

        config = ProtostarConfig.load()
        init_cmd = (
            "uv sync"
            if config.python_package_manager == "uv"
            else "python3 -m venv .venv"
        )

        content = (
            "# Ensure the venv exists\n"
            'if [ ! -d ".venv" ]; then\n'
            f"    {init_cmd}\n"
            "fi\n\n"
            "# Activate properly — direnv captures env changes, not shell functions\n"
            'export VIRTUAL_ENV="$(pwd)/.venv"\n'
            "PATH_add .venv/bin\n\n"
            "# Local overrides (not committed to git)\n"
            "source_env_if_exists .envrc.local\n"
        )

        envrc.write_text(content)
        logger.debug("Generated .envrc context.")

        run_quiet(["direnv", "allow"], "Evaluating direnv configuration")

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
                logger.warning("Existing settings.json is malformed. Overwriting.")

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
        if not self.manifest.dependencies:
            return

        config = ProtostarConfig.load()

        if config.python_package_manager == "uv":
            cmd = ["uv", "add"] + self.manifest.dependencies
            run_quiet(
                cmd,
                f"Resolving and installing {len(self.manifest.dependencies)} dependencies",
            )
        else:
            venv_pip = Path(".venv/bin/pip")
            pip_cmd = str(venv_pip) if venv_pip.exists() else "pip"

            cmd = [pip_cmd, "install"] + self.manifest.dependencies

            run_quiet(
                cmd,
                f"Resolving and installing {len(self.manifest.dependencies)} dependencies",
            )

            # Freeze the state to mirror uv's declarative pyproject.toml updates
            try:
                result = subprocess.run(
                    [pip_cmd, "freeze"], capture_output=True, text=True, check=True
                )
                Path("requirements.txt").write_text(result.stdout)
                logger.debug("Successfully froze dependencies to requirements.txt")
            except Exception as e:
                logger.warning(
                    f"Failed to freeze dependencies to requirements.txt: {e}"
                )
