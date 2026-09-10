import importlib.resources
import json
import logging
import shlex
import sys
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.tree import Tree

from protostar.cli import schema
from protostar.config import CONFIG_FILE, UserConfig
from protostar.errors import (
    ExecutionAbortedError,
    ProtostarError,
    SecurityViolationError,
    WorkspaceCollisionError,
)
from protostar.manifest import CollisionStrategy, EnvironmentManifest, Severity
from protostar.models import ExecutionResult, InitRequest
from protostar.orchestrator import Orchestrator
from protostar.system import is_interactive
from protostar.ui import Choice, confirm, select
from protostar.ui import Style as UIStyle

# Marks the agent interface as experimental. Increment when the schema
# stabilises and a compatibility commitment is made.


# Global JSON mode state, dynamically evaluated during CLI dispatch.
is_json_mode: bool = False

# Primary Rich console for human-readable output to stdout.
console = Console()

# Dedicated stderr console used in JSON mode to keep stdout clean.
_stderr_console = Console(stderr=True)


def emit_json(payload: dict[str, Any]) -> None:
    """Writes exactly one JSON document to stdout and flushes immediately.

    This is the sole exit path for all machine-readable output. Callers are
    responsible for calling ``sys.exit()`` immediately after to ensure exactly
    one document is emitted per invocation.

    Args:
        payload: A JSON-serializable dictionary to emit.
    """
    print(json.dumps(payload, sort_keys=True), flush=True)  # noqa: T201


class SpinnerHandler(logging.Handler):
    """Routes INFO-level logs to update a rich Status spinner."""

    def __init__(self, status_obj: Status) -> None:
        super().__init__(level=logging.INFO)
        self.status_obj = status_obj

    def emit(self, record: logging.LogRecord) -> None:
        """Processes the log record and updates the status spinner if level is INFO."""
        # Only update the spinner for INFO logs (ignore DEBUG)
        if record.levelno == logging.INFO:
            self.status_obj.update(record.getMessage())


def _print_templates_and_exit(error_msg: str | None = None) -> None:
    """Renders a rich table of all available templates and exits.

    In JSON mode, emits a structured list of template objects instead of a
    Rich table, then exits with the appropriate code.

    Args:
        error_msg: If provided, prints a red error warning before the table
            and exits with a status code of 1 instead of 0.
    """
    # Collect template metadata for both JSON and human output paths
    templates: list[dict[str, str]] = []
    try:
        template_dir = importlib.resources.files("protostar.templates")
        for item in template_dir.iterdir():
            if item.is_file() and item.name.endswith(".toml"):
                templates.append(
                    {
                        "name": item.name[:-5],
                        "type": "built-in",
                        "source": "protostar.templates",
                    }
                )
    except (OSError, TypeError, ValueError, AttributeError, ModuleNotFoundError):
        pass

    user_config = UserConfig.load()
    if user_config.templates:
        for alias, source in user_config.templates.items():
            templates.append({"name": alias, "type": "global-alias", "source": source})

    if is_json_mode:
        if error_msg:
            emit_json(
                {
                    "api_version": schema.CLI_API_VERSION,
                    "status": "error",
                    "error": {
                        "type": "InvalidUsageError",
                        "message": error_msg,
                    },
                    "templates": templates,
                }
            )
            sys.exit(1)
        emit_json(
            {
                "api_version": schema.CLI_API_VERSION,
                "status": "success",
                "templates": templates,
            }
        )
        sys.exit(0)

    if error_msg:
        console.print(f"[bold red]Error:[/bold red] {error_msg}\n")

    table = Table(
        title="Available Templates",
        box=box.ROUNDED,
        title_style="bold blue",
        title_justify="left",
        padding=(0, 1),
    )
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Source", style="dim")

    for tmpl in templates:
        table.add_row(
            tmpl["name"], tmpl["type"].replace("-", " ").title(), tmpl["source"]
        )

    console.print(table)

    # Exit with 1 if it was a failure, 0 if it was an intentional listing
    sys.exit(1 if error_msg else 0)


def _run_engine(engine: Orchestrator, request: InitRequest) -> ExecutionResult:
    """Runs the full plan → trust → execute → render pipeline for the CLI.

    Encapsulates the collision prompt loop, remote trust boundary, execution,
    and diagnostic rendering so both the argument-driven and wizard-driven
    entry points share the same presentation logic.

    In JSON mode:
    - ``WorkspaceCollisionError`` re-raises immediately (no interactive prompt).
    - Untrusted external templates raise ``SecurityViolationError`` rather than
      prompting for confirmation.
    - The Rich spinner and all human-readable output are suppressed to preserve
      ``stdout`` for the JSON payload emitted by the caller.

    Args:
        engine: A fully constructed Orchestrator.
        request: The InitRequest used to build the engine. May be replaced if
            the user resolves a collision interactively.

    Returns:
        The ExecutionResult produced by the engine.
    """
    # --- Collision Loop ---
    try:
        manifest = engine.plan()
    except WorkspaceCollisionError as e:
        # JSON mode: let the error bubble to main()'s ProtostarError handler.
        if is_json_mode:
            raise

        console.print(
            "\n[bold yellow]Workspace Collision:[/bold yellow] Protostar detected "
            "existing configuration files in the workspace."
        )
        for path in sorted(e.paths):
            console.print(f"  - {path}")

        if not is_interactive():
            raise ProtostarError(
                "Workspace collision detected: The target workspace is not empty.\n"
                "Aborting to prevent destructive mutations in a non-interactive context.\n"
                "Use the --force-merge or --force-replace flag to bypass this check."
            ) from e

        choice = select(
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
            style=UIStyle(
                [
                    ("answer", "fg:cyan bold"),
                    ("pointer", "fg:cyan bold"),
                    ("selected", "fg:cyan"),
                ]
            ),
        )

        if not choice or choice == CollisionStrategy.ABORT:
            raise ExecutionAbortedError(
                "Environment initialization cancelled by user."
            ) from None

        # Rebuild engine with updated force flag and re-plan with a fresh manifest
        if choice == CollisionStrategy.MERGE:
            request = InitRequest(
                template_blueprint=request.template_blueprint,
                python_version=request.python_version,
                docker=request.docker,
                force_merge=True,
                force_replace=False,
                metadata=request.metadata,
                is_external=request.is_external,
                is_user_aliased=request.is_user_aliased,
            )
        else:
            request = InitRequest(
                template_blueprint=request.template_blueprint,
                python_version=request.python_version,
                docker=request.docker,
                force_merge=False,
                force_replace=True,
                metadata=request.metadata,
                is_external=request.is_external,
                is_user_aliased=request.is_user_aliased,
            )
        engine = Orchestrator(engine.modules, engine.user_config, request=request)
        manifest = engine.plan()

    # --- Trust Boundary ---
    if request.is_external and not request.is_user_aliased:
        tasks = [*manifest.tasks.system_tasks, *manifest.tasks.post_install_tasks]
        if tasks:
            # JSON mode: reject immediately without prompting to avoid blocking agents.
            if is_json_mode:
                raise SecurityViolationError(
                    "Execution aborted: Untrusted external template contains "
                    "executable tasks. To trust this source, add its URL to the "
                    "[templates] block in your global configuration.",
                    hint=(
                        "Add the URL to the [templates] section of "
                        f"{CONFIG_FILE} and re-run with --from."
                    ),
                )

            console.print(
                "\n[bold red]⚠️  REMOTE TEMPLATE WARNING ⚠️[/bold red]\n\n"
                "This template was loaded from an external source and will execute "
                "the following shell commands on your system:"
            )
            for task in tasks:
                console.print(f"  - {' '.join(task.command)}")
            console.print()

            if not is_interactive():
                raise ProtostarError(
                    "Execution aborted: Untrusted external template contains executable tasks.\n"
                    "To trust this template in non-interactive environments, add its URL to "
                    "the [templates] block in your global configuration."
                )

            confirmed = confirm(
                "Do you trust this source to modify your system?", default=False
            )
            if not confirmed or confirmed is None:
                raise ExecutionAbortedError(
                    "Execution cancelled: Untrusted external source."
                )

    # --- Execute ---
    logger = logging.getLogger("protostar")
    # Temporarily drop the log level to INFO so the spinner receives the events
    previous_level = logger.level
    if logger.getEffectiveLevel() > logging.INFO:
        logger.setLevel(logging.INFO)

    if is_json_mode:
        # Bypass the spinner entirely in JSON mode to keep stdout clean.
        result = engine.execute(manifest)
        logger.setLevel(previous_level)
    else:
        console.print("[bold]Protostar Ignition Sequence Initiated[/bold]")
        with console.status("Initializing...") as status:
            spinner_handler = SpinnerHandler(status)
            logger.addHandler(spinner_handler)
            try:
                result = engine.execute(manifest)
            finally:
                logger.removeHandler(spinner_handler)
                logger.setLevel(previous_level)

        # --- Render Diagnostics ---
        has_warnings = False
        if result.diagnostics:
            lines = []
            for event in result.diagnostics:
                if event.severity == Severity.WARNING:
                    has_warnings = True
                    lines.append(f"[yellow]⚠ [{event.phase}][/yellow] {event.message}")
                elif event.severity == Severity.SKIP:
                    lines.append(
                        rf"[dim white]\[i] [{event.phase}] {event.message}[/dim white]"
                    )
                else:
                    lines.append(f"[blue]• [{event.phase}][/blue] {event.message}")

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

        if has_warnings:
            console.print(
                "\n[bold yellow]PARTIAL SUCCESS:[/bold yellow] Environment scaffolded, "
                "but some non-critical tasks encountered issues."
            )
        else:
            console.print(
                "\n[bold green]SUCCESS:[/bold green] Accretion disk stabilized. Environment ready."
            )

    return result


def _print_dry_run_summary(manifest: EnvironmentManifest) -> None:
    """Renders a human-readable summary of the planned environment manifest."""
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("Category", justify="right", style="bold")
    table.add_column("Details")

    # Filesystem
    files_to_create = len(manifest.filesystem.directories) + len(
        manifest.filesystem.file_injections
    )
    table.add_row("Filesystem:", f"{files_to_create} files/directories to scaffold")

    # Dependencies
    deps_total = (
        len(manifest.dependencies.dependencies)
        + len(manifest.dependencies.dev_dependencies)
        + len(manifest.dependencies.docs_dependencies)
    )
    table.add_row("Dependencies:", f"{deps_total} packages to install")

    # Tasks
    tasks_total = len(manifest.tasks.system_tasks) + len(
        manifest.tasks.post_install_tasks
    )
    table.add_row("Tasks:", f"{tasks_total} system commands to execute")

    # Collision Strategy
    table.add_row("Collision Strategy:", manifest.collision_strategy.value.title())

    console.print()
    console.print(
        Panel(
            table,
            title="[bold]Summary",
            border_style="cyan",
            padding=(0, 2),
            expand=False,
        )
    )

    if deps_total > 0:
        dep_lines = []
        if manifest.dependencies.dependencies:
            pkgs = ", ".join(manifest.dependencies.dependencies)
            dep_lines.append(f"[bold]Standard:[/bold] {pkgs}")
        if manifest.dependencies.dev_dependencies:
            pkgs = ", ".join(manifest.dependencies.dev_dependencies)
            dep_lines.append(f"[bold]Development:[/bold] {pkgs}")
        if manifest.dependencies.docs_dependencies:
            pkgs = ", ".join(manifest.dependencies.docs_dependencies)
            dep_lines.append(f"[bold]Documentation:[/bold] {pkgs}")

        console.print()
        console.print(
            Panel(
                "\n".join(dep_lines),
                title="[bold]Dependencies",
                border_style="cyan",
                padding=(0, 2),
                expand=False,
            )
        )

    if tasks_total > 0:
        task_lines = []
        for i, task in enumerate(manifest.tasks.system_tasks, 1):
            cmd = shlex.join(task.command)
            task_lines.append(f"  {i}. {cmd}")
        offset = len(manifest.tasks.system_tasks)
        for i, task in enumerate(manifest.tasks.post_install_tasks, offset + 1):
            cmd = shlex.join(task.command)
            task_lines.append(f"  {i}. {cmd}")

        console.print()
        console.print(
            Panel(
                "\n".join(task_lines),
                title="[bold]Tasks",
                border_style="cyan",
                padding=(0, 2),
                expand=False,
            )
        )

    if files_to_create > 0:
        tree = Tree("[bold].[/bold] (Workspace Root)", guide_style="dim")
        all_paths = set(manifest.filesystem.directories)
        all_paths.update(manifest.filesystem.file_injections.keys())
        all_paths.update(manifest.filesystem.file_appends.keys())

        sorted_paths = sorted(all_paths)
        nodes: dict[str, Tree] = {"": tree}

        for path in sorted_paths:
            parts = path.split("/")
            current = ""
            for idx, part in enumerate(parts):
                parent = current
                current = f"{current}/{part}" if current else part

                if current not in nodes:
                    is_file = (idx == len(parts) - 1) and (
                        path not in manifest.filesystem.directories
                    )
                    if is_file:
                        nodes[current] = nodes[parent].add(f"{part}")
                    else:
                        nodes[current] = nodes[parent].add(f"{part}/")

        console.print()
        console.print(
            Panel(
                tree,
                title="[bold]Filesystem",
                border_style="cyan",
                padding=(0, 2),
                expand=False,
            )
        )

    console.print("\n[dim]No changes were made to your system.[/dim]")
