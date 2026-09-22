from __future__ import annotations

import dataclasses
import io
import json
import shlex
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from protostar.cli import schema
from protostar.cli.prompts import Choice, confirm, select
from protostar.cli.prompts import Style as UIStyle
from protostar.config import active_config_source
from protostar.errors import (
    ExecutionAbortedError,
    ProtostarError,
    SecurityViolationError,
    WorkspaceCollisionError,
)
from protostar.manifest import CollisionStrategy, EnvironmentManifest, Severity
from protostar.models import ExecutionResult, InitRequest
from protostar.progress import ProgressStep
from protostar.system import is_interactive

if TYPE_CHECKING:
    from protostar.orchestrator import Orchestrator

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


def replace_unencodable_output() -> None:
    """Makes stdout and stderr replace characters their encoding cannot represent.

    A redirected stream on Windows encodes with the locale code page, usually
    cp1252. Under the default strict error handler, any path, template text, or
    Rich traceback marker outside that code page raises ``UnicodeEncodeError``
    mid-render and buries Protostar's own output under a Python traceback. A
    handler chosen explicitly, e.g. through ``PYTHONIOENCODING``, is kept.
    """
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper) and stream.errors == "strict":
            stream.reconfigure(errors="replace")


def printable(text: str) -> str:
    """Replaces the characters the CLI console's stream cannot encode with ``?``.

    Args:
        text: Text about to be printed to ``console``.

    Returns:
        ``text`` with each unencodable character replaced.
    """
    encoding = console.encoding
    return text.encode(encoding, "replace").decode(encoding)


def glyph(symbol: str, fallback: str) -> str:
    """Picks a decorative symbol that the CLI console's stream can encode.

    Args:
        symbol: The preferred Unicode symbol.
        fallback: An ASCII stand-in for streams that cannot encode ``symbol``,
            such as a redirected cp1252 stream on Windows.

    Returns:
        ``symbol`` if the stream can encode it, otherwise ``fallback``.
    """
    return symbol if printable(symbol) == symbol else fallback


@contextmanager
def progress_trail(initial: str) -> Iterator[ProgressStep]:
    """Renders execution steps as a persistent checklist above a live spinner.

    A running step's label animates in the spinner; when the step ends, a ``✔``
    line (``✖`` if it raised) is printed above the spinner and stays on screen
    after the spinner clears. Off a terminal, Rich draws no spinner and only the
    checklist lines are written. A stream that cannot encode the marks, such as a
    redirected cp1252 stream on Windows, gets ``+`` and ``x`` instead.

    Unlike other output, the trail sanitizes its labels itself instead of relying
    on ``replace_unencodable_output``: a write error here would escape the step
    and roll back the work the step just reported.

    Args:
        initial: Spinner text shown until the first step starts.

    Yields:
        The step hook to hand to the engine.
    """
    done = (glyph("✔", "+"), "bold green")
    failed = (glyph("✖", "x"), "bold red")

    with console.status(initial) as status:

        @contextmanager
        def step(label: str) -> Iterator[None]:
            # Text, not markup: template-authored task descriptions reach here.
            shown = printable(label)
            status.update(Text(shown))
            succeeded = False
            try:
                yield
                succeeded = True
            finally:
                # Clear the label first, or the spinner redrawn beneath the new
                # line would repeat the step that just finished. Rich ignores an
                # empty update, so a blank stands in for no label.
                status.update(Text(" "))
                mark = done if succeeded else failed
                console.print(Text.assemble("  ", mark, f" {shown}"))

        yield step


def _print_templates_and_exit(error_msg: str | None = None) -> None:
    """Renders a rich table of all available templates and exits.

    In JSON mode, emits a structured list of template objects instead of a
    Rich table, then exits with the appropriate code.

    Args:
        error_msg: If provided, prints a red error warning before the table
            and exits with a status code of 1 instead of 0.
    """
    from protostar.templates import TemplateType, discover_templates

    discovered = discover_templates()
    templates = [t.to_dict() for t in discovered]

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
        expand=True,
    )
    table.add_column("Template", style="bold cyan", no_wrap=True)
    table.add_column("Description", style="white", ratio=1)
    table.add_column("Type", no_wrap=True)

    for tmpl in discovered:
        type_str = (
            "[green]Built-in[/green]"
            if tmpl.type == TemplateType.BUILT_IN
            else "[yellow]External[/yellow]"
        )

        table.add_row(
            tmpl.name,
            tmpl.description,
            type_str,
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
    - The progress trail and all human-readable output are suppressed to preserve
      ``stdout`` for the JSON payload emitted by the caller.

    Args:
        engine: A fully constructed Orchestrator.
        request: The InitRequest used to build the engine. May be replaced if
            the user resolves a collision interactively.

    Returns:
        The ExecutionResult produced by the engine.
    """
    # --- Collision Decision ---
    manifest = engine.plan()
    if manifest.collisions and manifest.collision_strategy is None:
        error = WorkspaceCollisionError(paths=manifest.collisions)
        # JSON mode: let the error bubble to main()'s ProtostarError handler.
        if is_json_mode:
            raise error

        console.print(
            "\n[bold yellow]Workspace Collision:[/bold yellow] Protostar detected "
            "existing configuration files in the workspace."
        )
        for path in sorted(manifest.collisions):
            console.print(f"  - {path}")

        if not is_interactive():
            raise ProtostarError(
                "Workspace collision detected: The target workspace is not empty.\n"
                "Aborting to prevent destructive mutations in a non-interactive context.\n"
                "Use the --force-merge or --force-replace flag to bypass this check."
            ) from error

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
                    value=None,
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

        if choice is None:
            raise ExecutionAbortedError(
                "Environment initialization cancelled by user."
            ) from None

        request = dataclasses.replace(request, collision_strategy=choice)
        engine.request = request
        manifest = engine.plan()

    # --- Trust Boundary ---
    if request.is_external and not request.is_trusted:
        tasks = [*manifest.tasks.system_tasks, *manifest.tasks.post_install_tasks]
        if tasks:
            # JSON mode: reject immediately without prompting to avoid blocking agents.
            if is_json_mode:
                raise SecurityViolationError(
                    "Execution aborted: Untrusted external template contains "
                    "executable tasks. To trust this source, configure it with "
                    "'trusted = true' in your global configuration.",
                    hint=(
                        f"Configure the template in {active_config_source().path} "
                        "with 'trusted = true' "
                        "and re-run."
                    ),
                )

            warning = glyph("⚠️", "!")
            console.print(
                f"\n[bold red]{warning}  REMOTE TEMPLATE WARNING {warning}[/bold red]\n\n"
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
    if is_json_mode:
        result = engine.execute(manifest)
    else:
        console.print("[bold]Protostar Ignition Sequence Initiated[/bold]")
        with progress_trail("Preparing workspace") as progress:
            result = engine.execute(manifest, progress=progress)

        # --- Render Diagnostics ---
        has_warnings = False
        if result.diagnostics:
            lines = []
            warning = glyph("⚠", "!")
            for event in result.diagnostics:
                if event.severity == Severity.WARNING:
                    has_warnings = True
                    lines.append(
                        f"[yellow]{warning} [{event.phase}][/yellow] {event.message}"
                    )
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


def print_dry_run_summary(manifest: EnvironmentManifest) -> None:
    """Renders a human-readable summary of the planned environment manifest."""
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("Category", justify="right", style="bold")
    table.add_column("Details")

    # Filesystem: one rendered path set feeds both the count and the tree.
    directories = {path.as_posix() for path in manifest.target_directories()}
    paths = sorted(directories | {path.as_posix() for path in manifest.written_files()})
    table.add_row("Filesystem:", f"{len(paths)} files/directories to create or update")

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
    table.add_row(
        "Collision Strategy:",
        manifest.collision_strategy.value.title()
        if manifest.collision_strategy
        else "Unresolved"
        if manifest.collisions
        else "Not needed",
    )

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

    if paths:
        tree = Tree("[bold].[/bold] (Workspace Root)", guide_style="dim")
        nodes: dict[str, Tree] = {"": tree}

        for path in paths:
            parts = path.split("/")
            current = ""
            for idx, part in enumerate(parts):
                parent = current
                current = f"{current}/{part}" if current else part

                if current not in nodes:
                    is_file = (idx == len(parts) - 1) and (path not in directories)
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
