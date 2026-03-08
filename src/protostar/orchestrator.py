import logging
import os
import platform
import sys
import traceback
import urllib.parse

from rich.console import Console

from .config import ProtostarConfig
from .executor import SystemExecutor
from .manifest import CollisionStrategy, EnvironmentManifest
from .modules import BootstrapModule
from .presets.base import PresetModule

logger = logging.getLogger("protostar")
console = Console()


class Orchestrator:
    """Manages the lifecycle of the environment scaffolding process."""

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

        # Evaluate non-interactive fallback logic
        if not sys.stdin.isatty() or "PYTEST_CURRENT_TEST" in os.environ:
            if self.force:
                logger.debug(
                    "Non-interactive environment detected. --force flag provided. "
                    "Defaulting to MERGE collision strategy."
                )
                self.manifest.collision_strategy = CollisionStrategy.MERGE
                return
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

            # Inject global configuration states using the injected config
            if self.config.global_dev_dependencies:
                logger.debug("Injecting global dev dependencies from configuration.")
                for dep in self.config.global_dev_dependencies:
                    self.manifest.add_dev_dependency(dep)

            if self.config.pyproject_injections:
                logger.debug(
                    "Injecting global pyproject.toml payloads from configuration."
                )
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

        except Exception as e:
            # Catch expected operational errors and OS-level I/O constraints
            if isinstance(e, (RuntimeError, ValueError, FileExistsError, OSError)):
                console.print(f"\n[bold red]ABORTED:[/bold red] {e}")
                sys.exit(1)

            console.print(
                "\n[bold red]CRITICAL FAILURE:[/bold red] Protostar encountered an unexpected error."
            )

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
