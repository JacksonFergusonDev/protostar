import logging
from typing import Any, cast

from rich.console import Console
from rich.panel import Panel

from .config import TemplateBlueprint, UserConfig
from .errors import (
    ExecutionAbortedError,
    PartialExecutionAbortedError,
    ProtostarError,
)
from .executor import SystemExecutor
from .manifest import CollisionStrategy, EnvironmentManifest, ProjectMetadata, Severity
from .modules import BootstrapModule
from .system import is_interactive

logger = logging.getLogger("protostar")
console = Console()


class Orchestrator:
    """Manages the lifecycle of the Python environment scaffolding process."""

    def __init__(
        self,
        modules: list[BootstrapModule],
        user_config: UserConfig,
        blueprint: TemplateBlueprint | None = None,
        docker: bool = False,
        force_merge: bool = False,
        force_replace: bool = False,
        metadata: dict[str, Any] | None = None,
        is_external: bool = False,
        is_user_aliased: bool = False,
    ) -> None:
        """Initializes the orchestrator with the requested modules and presets.

        Args:
            modules: The ordered stack of bootstrap layers to execute.
            user_config: The active UserConfig instance.
            blueprint: The template blueprint.
            docker: If True, scaffolds a .dockerignore from the manifest ignores. Defaults to False.
            force_merge: If True, bypasses interactive prompts and forces a merge on collisions. Defaults to False.
            force_replace: If True, bypasses interactive prompts and forces replacement on collisions. Defaults to False.
            metadata: Pre-resolved metadata dictionary to inject into the manifest. Defaults to None.
            is_external: If True, the template was loaded from an external source.
            is_user_aliased: If True, the template was resolved via a trusted global configuration alias.
        """
        self.modules = modules
        self.user_config = user_config
        self.blueprint = blueprint
        self.docker = docker
        self.force_merge = force_merge
        self.force_replace = force_replace
        self.metadata = metadata
        self.is_external = is_external
        self.is_user_aliased = is_user_aliased
        self.manifest = EnvironmentManifest(
            force_merge=force_merge, force_replace=force_replace
        )

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

        # 1. Immediate override: Evaluate explicit force flags first
        if self.force_replace:
            logger.debug(
                "--force-replace flag provided. Defaulting to OVERWRITE collision strategy."
            )
            self.manifest.collision_strategy = CollisionStrategy.OVERWRITE
            return

        if self.force_merge:
            logger.debug(
                "--force-merge flag provided. Defaulting to MERGE collision strategy."
            )
            self.manifest.collision_strategy = CollisionStrategy.MERGE
            return

        # 2. Evaluate non-interactive fallback logic
        if not is_interactive():
            raise ProtostarError(
                "Orbital Collision Detected: The target workspace is not empty.\n"
                "Aborting to prevent destructive mutations in a non-interactive context.\n"
                "Use the --force-merge or --force-replace flag to bypass this check."
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
            raise ExecutionAbortedError("Environment initialization cancelled by user.")

        self.manifest.collision_strategy = choice

    def _prompt_remote_trust(self) -> None:
        """Evaluates the trust boundary for external templates containing executable tasks.

        Halts execution with a stark warning if an untrusted template attempts
        to run shell commands. Templates mapped in the user's global configuration
        aliases bypass this check.
        """
        if not self.is_external or self.is_user_aliased:
            return

        tasks = [*self.manifest.system_tasks, *self.manifest.post_install_tasks]
        if not tasks:
            return

        import questionary

        console.print(
            "\n[bold red]⚠️  REMOTE TEMPLATE WARNING ⚠️[/bold red]\n\n"
            "This template was loaded from an external source and will execute the following shell commands on your system:"
        )

        for task in tasks:
            console.print(f"  - {' '.join(task.command)}")

        console.print()

        if not is_interactive():
            raise ProtostarError(
                "Execution aborted: Untrusted external template contains executable tasks.\n"
                "To trust this template in non-interactive environments, add its URL to the [templates] block in your global configuration."
            )

        confirmed = questionary.confirm(
            "Do you trust this source to modify your system?", default=False
        ).ask()

        if not confirmed or confirmed is None:
            raise ExecutionAbortedError(
                "Execution cancelled: Untrusted external source."
            )

    def run(self) -> None:
        """Executes the pre-flight, build, and realization phases."""
        console.print("[bold]Protostar Ignition Sequence Initiated[/bold]")

        # Phase 1: Collision Intercept
        self._evaluate_collisions()

        # Phase 2: Pre-flight Verification
        for mod in self.modules:
            mod.pre_flight()

        # Phase 3: Manifest Aggregation
        if self.metadata:
            self.manifest.metadata.update(cast(ProjectMetadata, self.metadata))

        for mod in self.modules:
            mod.build(self.manifest)

        # Inject global configuration states using the injected config
        if self.blueprint:
            logger.debug("Injecting blueprint structural fields into manifest.")

            for dep in self.blueprint.dependencies:
                self.manifest.add_dependency(dep)

            for dep in self.blueprint.dev_dependencies:
                self.manifest.add_dev_dependency(dep)

            for dep in self.blueprint.docs_dependencies:
                self.manifest.add_docs_dependency(dep)

            for d in self.blueprint.directories:
                self.manifest.add_directory(d)

            for ig in self.blueprint.vcs_ignores:
                self.manifest.add_vcs_ignore(ig)

            for cmd in self.blueprint.system_tasks:
                self.manifest.add_system_task(cmd)

            for cmd in self.blueprint.post_install_tasks:
                self.manifest.add_post_install_task(cmd)

            if self.blueprint.pyproject_injections:
                logger.debug("Injecting pyproject.toml payloads from configuration.")
                for payload in self.blueprint.pyproject_injections.values():
                    self.manifest.add_file_append("pyproject.toml", payload)

            # Inject generic file appends
            if self.blueprint.appends:
                logger.debug("Injecting generic file appends from configuration.")
                for filepath, payloads in self.blueprint.appends.items():
                    for payload in payloads:
                        self.manifest.add_file_append(filepath, payload)

            if self.blueprint.files:
                logger.debug("Injecting static files from configuration.")
                for filepath, content in self.blueprint.files.items():
                    self.manifest.add_file_injection(filepath, content)

        # Phase 3.5: Trust Evaluation Boundary
        self._prompt_remote_trust()

        # Phase 4: System Execution
        executor = SystemExecutor(self.manifest, self.user_config, self.docker)
        try:
            executor.execute()
        except KeyboardInterrupt:
            if self.manifest.touched_paths:
                raise PartialExecutionAbortedError(
                    self.manifest.touched_paths
                ) from None
            raise ExecutionAbortedError(
                "Environment initialization cancelled by user."
            ) from None

        # Phase 5: Telemetry Evaluation
        if self.manifest.diagnostics:
            lines = []
            has_warnings = False

            for event in self.manifest.diagnostics:
                if event.severity == Severity.WARNING:
                    has_warnings = True
                    lines.append(f"[yellow]⚠ [{event.phase}][/yellow] {event.message}")
                elif event.severity == Severity.SKIP:
                    lines.append(
                        rf"[dim white]\[i] [{event.phase}] {event.message}[/dim white]"
                    )
                else:
                    lines.append(f"[blue]• [{event.phase}][/blue] {event.message}")

                # Append the payload detail indented below the main event
                if event.detail:
                    lines.append(f"  [dim]{event.detail}[/dim]")

            console.print()
            console.print(
                Panel(
                    "\n".join(lines),
                    title="[bold]Diagnostic Summary",
                    border_style="yellow" if has_warnings else "blue",
                    expand=False,
                    padding=(1, 2),
                )
            )
        else:
            has_warnings = False

        if has_warnings:
            console.print(
                "\n[bold yellow]PARTIAL SUCCESS:[/bold yellow] Environment scaffolded, but some non-critical tasks encountered issues."
            )
        else:
            console.print(
                "\n[bold green]SUCCESS:[/bold green] Accretion disk stabilized. Environment ready."
            )
