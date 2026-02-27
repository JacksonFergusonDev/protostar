import json
import logging
from pathlib import Path

from rich.console import Console

from .manifest import EnvironmentManifest
from .modules import BootstrapModule
from .system import run_quiet

logger = logging.getLogger("protostar")
console = Console()


class Orchestrator:
    """Manages the lifecycle of the environment scaffolding process."""

    def __init__(self, modules: list[BootstrapModule]):
        """Initializes the orchestrator with the requested modules.

        Args:
            modules (list[BootstrapModule]): The initialized stack layers.
        """
        self.modules = modules
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

            # Phase 3: System Execution
            self._execute_tasks()
            self._write_ignores()
            self._write_ide_settings()
            self._install_dependencies()

            console.print(
                "\n[bold green]SUCCESS:[/bold green] Accretion disk stabilized. Environment ready."
            )

        except Exception as e:
            console.print(f"\n[bold red]ABORTED:[/bold red] {e}")
            logger.debug("Stack trace:", exc_info=True)

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
