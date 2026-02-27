import json
import logging
from pathlib import Path

from rich.console import Console

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
    ):
        """Initializes the orchestrator with the requested modules and presets.

        Args:
            modules (list[BootstrapModule]): The initialized stack layers.
            presets (list[PresetModule] | None, optional): Domain-specific presets.
            docker (bool, optional): Whether to scaffold Docker context exclusions.
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
            self._execute_tasks()
            self._create_directories()
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

        # Assuming uv is the primary driver for dependency injection
        # if python dependencies were requested.
        cmd = ["uv", "add"] + self.manifest.dependencies
        run_quiet(
            cmd,
            f"Resolving and installing {len(self.manifest.dependencies)} dependencies",
        )
