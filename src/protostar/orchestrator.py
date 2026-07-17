import logging
import os
import sys

from rich.console import Console

from .config import ProtostarConfig
from .errors import ProtostarError
from .executor import SystemExecutor
from .manifest import CollisionStrategy, EnvironmentManifest, Severity
from .modules import BootstrapModule
from .presets.base import PresetModule

logger = logging.getLogger("protostar")
console = Console()


class Orchestrator:
    """Manages the lifecycle of the Python environment scaffolding process."""

    def __init__(
        self,
        modules: list[BootstrapModule],
        config: ProtostarConfig,
        presets: list[PresetModule] | None = None,
        docker: bool = False,
        force: bool = False,
    ) -> None:
        """Initializes the orchestrator with the requested modules and presets.

        Args:
            modules: The ordered stack of bootstrap layers to execute.
            config: The active Protostar configuration instance.
            presets: Domain-specific dependency and directory presets. Defaults to an empty list.
            docker: If True, scaffolds a .dockerignore from the manifest ignores. Defaults to False.
            force: If True, bypasses interactive prompts and forces a merge on collisions. Defaults to False.
        """
        self.modules = modules
        self.config = config
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

        # 1. Immediate override: Evaluate explicit force flag first
        if self.force:
            logger.debug(
                "--force flag provided. Defaulting to MERGE collision strategy."
            )
            self.manifest.collision_strategy = CollisionStrategy.MERGE
            return

        # 2. Evaluate non-interactive fallback logic
        if not sys.stdin.isatty() or "PYTEST_CURRENT_TEST" in os.environ:
            raise ProtostarError(
                "Orbital Collision Detected: The target workspace is not empty.\n"
                "Aborting to prevent destructive mutations in a non-interactive context.\n"
                "Use the --force flag to bypass this check and merge safely."
            )

        # 3. Fallback to interactive prompt
        import questionary
        from questionary import Choice

        console.print(
            "\n[bold yellow]Gravitational Anomaly:[/bold yellow] Protostar detected existing configuration files in the workspace."
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

        # Phase 1: Collision Intercept
        self._evaluate_collisions()

        # Phase 2: Pre-flight Verification
        for warning in self.config._parsing_warnings:
            self.manifest.add_diagnostic(
                phase="Config",
                message=warning,
                severity=Severity.WARNING,
            )

        for mod in self.modules:
            mod.pre_flight()

        # Phase 3: Manifest Aggregation
        for mod in self.modules:
            mod.build(self.manifest)

        for preset in self.presets:
            logger.debug(f"Building {preset.name} preset.")
            preset.build(self.manifest)

        # Inject global configuration states using the injected config
        if self.config.global_dev_dependencies:
            logger.debug("Injecting global dev dependencies from configuration.")
            for dep in self.config.global_dev_dependencies:
                self.manifest.add_dev_dependency(dep)

        if self.config.pyproject_injections:
            logger.debug("Injecting global pyproject.toml payloads from configuration.")
            for payload in self.config.pyproject_injections.values():
                self.manifest.add_file_append("pyproject.toml", payload)

        # Phase 4: System Execution
        executor = SystemExecutor(self.manifest, self.config, self.docker)
        executor.execute()

        # Phase 5: Telemetry Evaluation
        if executor.warnings:
            console.print(
                "\n[bold yellow]PARTIAL SUCCESS:[/bold yellow] Environment scaffolded, but some non-critical tasks encountered issues."
            )
            for warning in executor.warnings:
                console.print(f"[yellow]  ⚠ {warning}[/yellow]")
        else:
            console.print(
                "\n[bold green]SUCCESS:[/bold green] Accretion disk stabilized. Environment ready."
            )
