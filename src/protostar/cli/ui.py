from __future__ import annotations

import io
import json
import shlex
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from protostar.cli import schema
from protostar.config import active_config_source
from protostar.errors import (
    ProtostarError,
    SecurityViolationError,
    WorkspaceCollisionError,
)
from protostar.init_draft import InitDecision
from protostar.manifest import DiagnosticEvent, EnvironmentManifest, Severity
from protostar.merge import NO_RESOLUTIONS
from protostar.models import ExecutionResult, InitRequest
from protostar.progress import ProgressStep

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


def heading(title: str, style: str = "bold cyan") -> Rule:
    """Builds a section heading in the TUI's style: the title, then a rule.

    Args:
        title: The section's name, shown in capitals.
        style: The title's style; errors pass ``bold red``.

    Returns:
        A rule from the title to the console's edge. A stream that cannot
        encode box drawing, such as a redirected cp1252 stream, gets dashes.
    """
    rule = "red" if "red" in style else "bright_black"
    return Rule(Text(title.upper(), style), align="left", style=rule)


def indented(renderable: RenderableType) -> Padding:
    """Indents a section's body under its heading.

    Args:
        renderable: The section's body.

    Returns:
        The body, two columns in.
    """
    return Padding(renderable, (0, 0, 0, 2), expand=False)


_CONFIG_SUFFIXES = frozenset(
    {".cfg", ".ini", ".json", ".jsonc", ".lock", ".toml", ".yaml", ".yml"}
)
_CONFIG_NAMES = frozenset({"Dockerfile", "Justfile", "Makefile", "justfile"})


def path_style(name: str, *, directory: bool) -> str:
    """Styles a path by kind, as ``eza`` does, so a tree can be skimmed.

    Directories are bold blue, configuration is yellow, and hidden paths are
    dimmed; everything else, mostly source and docs, keeps the default color.

    Args:
        name: The path's last component.
        directory: Whether the path is a directory.

    Returns:
        A Rich style, empty for the default.
    """
    if directory:
        style = "bold blue"
    elif name in _CONFIG_NAMES or any(
        name.endswith(suffix) for suffix in _CONFIG_SUFFIXES
    ):
        style = "yellow"
    else:
        style = ""
    return f"{style} dim".strip() if name.startswith(".") else style


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
    done = (glyph("✔", "+"), "green")
    failed = (glyph("✖", "x"), "bold red")

    with console.status(initial, spinner_style="cyan") as status:

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

    table = Table(box=None, show_header=False, padding=(0, 2, 0, 0), expand=True)
    table.add_column("Template", style="bold cyan", no_wrap=True)
    table.add_column("Description", ratio=1)
    table.add_column("Type", no_wrap=True)

    for tmpl in discovered:
        # External templates run code from elsewhere, so they stand out.
        type_str = (
            Text("Built-in", "dim")
            if tmpl.type == TemplateType.BUILT_IN
            else Text("External", "yellow")
        )

        table.add_row(Text(tmpl.name), Text(tmpl.description), type_str)

    console.print(heading("Available templates"))
    console.print(indented(table))

    # Exit with 1 if it was a failure, 0 if it was an intentional listing
    sys.exit(1 if error_msg else 0)


def untrusted_commands(
    request: InitRequest, manifest: EnvironmentManifest
) -> tuple[tuple[str, ...], ...]:
    """Returns every command a run of an untrusted external template executes.

    Args:
        request: The resolved init request, carrying the template's trust facts.
        manifest: The planned manifest.

    Returns:
        Each system and post-install command in execution order, or nothing
        when the template is built in or configured as trusted.
    """
    if not request.is_external or request.is_trusted:
        return ()
    return tuple(
        tuple(task.command)
        for task in (*manifest.tasks.system_tasks, *manifest.tasks.post_install_tasks)
    )


def needs_review(request: InitRequest, manifest: EnvironmentManifest) -> bool:
    """Returns whether a collision or trust decision is still open.

    Args:
        request: The resolved init request.
        manifest: The planned manifest.

    Returns:
        True if existing files collide with no strategy chosen, or an untrusted
        template would run commands.
    """
    return bool(
        (manifest.collisions and manifest.collision_strategy is None)
        or untrusted_commands(request, manifest)
    )


def _run_engine(
    engine: Orchestrator,
    request: InitRequest,
    decision: InitDecision | None = None,
) -> ExecutionResult:
    """Runs the full plan → guards → execute → render pipeline for the CLI.

    Every decision is made before this runs: by flags and configuration, or
    in the change review, whose outcome ``decision`` carries. An open
    collision or trust decision here aborts instead of prompting.

    In JSON mode:
    - ``WorkspaceCollisionError`` re-raises immediately.
    - Untrusted external templates raise ``SecurityViolationError``.
    - The progress trail and all human-readable output are suppressed to preserve
      ``stdout`` for the JSON payload emitted by the caller.

    Args:
        engine: A fully constructed Orchestrator.
        request: The InitRequest used to build the engine.
        decision: The change review's outcome, if one ran. Execution reuses its
            registry snapshot, and runs an untrusted template's commands only
            if they are exactly the ones it confirmed.

    Returns:
        The ExecutionResult produced by the engine.
    """
    # --- Collision Guard ---
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
            console.print(Text(f"  - {path}"))

        raise ProtostarError(
            "Workspace collision detected: The target workspace is not empty.\n"
            "Aborting to prevent destructive mutations in a non-interactive context.\n"
            "Use the --force-merge or --force-replace flag to bypass this check."
        ) from error

    # --- Trust Boundary ---
    commands = untrusted_commands(request, manifest)
    if commands and (decision is None or decision.confirmed_commands != commands):
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
        for command in commands:
            console.print(Text(f"  - {shlex.join(command)}"))
        console.print()

        raise ProtostarError(
            "Execution aborted: Untrusted external template contains executable tasks.\n"
            "To trust this template in non-interactive environments, add its URL to "
            "the [templates] block in your global configuration."
        )

    # --- Execute ---
    hook_revisions = decision.hook_revisions if decision else None
    resolutions = decision.resolutions if decision else NO_RESOLUTIONS
    if is_json_mode:
        result = engine.execute(
            manifest, hook_revisions=hook_revisions, resolutions=resolutions
        )
    else:
        console.print(heading("Ignition sequence initiated"))
        with progress_trail("Preparing workspace") as progress:
            result = engine.execute(
                manifest,
                hook_revisions=hook_revisions,
                progress=progress,
                resolutions=resolutions,
            )

        # --- Render Diagnostics ---
        has_warnings = any(
            event.severity == Severity.WARNING for event in result.diagnostics
        )
        if result.diagnostics:
            console.print()
            console.print(diagnostics_report(result.diagnostics))

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


def diagnostics_report(events: Sequence[DiagnosticEvent]) -> Group:
    """Renders execution diagnostics as a section, one line per event.

    Args:
        events: The diagnostics an execution reported.

    Returns:
        A ``Diagnostics`` heading over the events: warnings in yellow, skips
        dimmed, and everything else marked in cyan.
    """
    warning = glyph("⚠", "!")
    lines: list[Text] = []
    for event in events:
        # Messages can quote template text: data, never markup.
        tag = f"[{event.phase}]"
        if event.severity == Severity.WARNING:
            lines.append(
                Text.assemble((f"{warning} {tag}", "yellow"), f" {event.message}")
            )
        elif event.severity == Severity.SKIP:
            lines.append(Text(f"[i] {tag} {event.message}", "dim"))
        else:
            lines.append(Text.assemble((f"• {tag}", "cyan"), f" {event.message}"))
        if event.detail:
            lines.append(Text(f"  {event.detail}", "dim"))
    return Group(heading("Diagnostics"), indented(Group(*lines)))


def planned_paths(manifest: EnvironmentManifest) -> tuple[list[str], set[str]]:
    """Returns every planned path, sorted, and the subset that are directories.

    Args:
        manifest: The planned environment manifest.

    Returns:
        The POSIX paths of every file and directory to create or update, and
        the directories among them.
    """
    directories = {path.as_posix() for path in manifest.target_directories()}
    paths = sorted(directories | {path.as_posix() for path in manifest.written_files()})
    return paths, directories


def plan_tree(manifest: EnvironmentManifest) -> Tree:
    """Builds the workspace tree of every path the manifest creates or updates.

    Args:
        manifest: The planned environment manifest.

    Returns:
        A tree rooted at the workspace, with a trailing slash on directories.
    """
    paths, directories = planned_paths(manifest)
    tree = Tree(
        Text.assemble((".", "bold blue"), (" (Workspace Root)", "dim")),
        guide_style="bright_black",
    )
    nodes: dict[str, Tree] = {"": tree}
    for path in paths:
        parts = path.split("/")
        current = ""
        for index, part in enumerate(parts):
            parent = current
            current = f"{current}/{part}" if current else part
            if current not in nodes:
                is_file = index == len(parts) - 1 and path not in directories
                # Paths come from templates: render them as data, never markup.
                nodes[current] = nodes[parent].add(
                    Text(
                        part if is_file else f"{part}/",
                        path_style(part, directory=not is_file),
                    )
                )
    return tree


def _facts(rows: list[tuple[str, str]]) -> Table:
    """Lays out labelled facts: dim labels in a column, values beside them."""
    table = Table(box=None, show_header=False, padding=(0, 2, 0, 0))
    table.add_column("Label", style="dim", no_wrap=True)
    table.add_column("Value")
    for label, value in rows:
        # Values name packages and commands from templates: data, never markup.
        table.add_row(label, Text(value))
    return table


def _section(title: str, body: RenderableType) -> None:
    console.print()
    console.print(heading(title))
    console.print(indented(body))


def print_dry_run_summary(manifest: EnvironmentManifest) -> None:
    """Renders a human-readable summary of the planned environment manifest."""
    paths, _ = planned_paths(manifest)
    dependencies = manifest.dependencies
    deps_total = (
        len(dependencies.dependencies)
        + len(dependencies.dev_dependencies)
        + len(dependencies.docs_dependencies)
    )
    tasks = (*manifest.tasks.system_tasks, *manifest.tasks.post_install_tasks)
    collisions = (
        manifest.collision_strategy.value.title()
        if manifest.collision_strategy
        else "Unresolved"
        if manifest.collisions
        else "Not needed"
    )

    _section(
        "Summary",
        _facts(
            [
                ("Filesystem", f"{len(paths)} files/directories to create or update"),
                ("Dependencies", f"{deps_total} packages to install"),
                ("Tasks", f"{len(tasks)} system commands to execute"),
                ("Collision strategy", collisions),
            ]
        ),
    )

    if deps_total > 0:
        groups = (
            ("Standard", dependencies.dependencies),
            ("Development", dependencies.dev_dependencies),
            ("Documentation", dependencies.docs_dependencies),
        )
        _section(
            "Dependencies",
            _facts([(label, ", ".join(names)) for label, names in groups if names]),
        )

    if tasks:
        _section(
            "Tasks",
            _facts(
                [
                    (f"{number}.", shlex.join(task.command))
                    for number, task in enumerate(tasks, 1)
                ]
            ),
        )

    if paths:
        _section("Filesystem", plan_tree(manifest))

    console.print("\n[dim]No changes were made to your system.[/dim]")


def warn_credential_names(names: tuple[str, ...]) -> None:
    """Warns that a template asks for variables named like credentials.

    Args:
        names: The flagged variable names.
    """
    from rich.text import Text

    target = _stderr_console if is_json_mode else console
    target.print(
        Text(
            f"{glyph('⚠', '!')} Template variables named like credentials: "
            f"{', '.join(names)}. Their values are saved to pyproject.toml; "
            "don't enter secrets.",
            style="yellow",
        )
    )


def print_recipe_summary(request: InitRequest) -> None:
    """Leave a literal, encoding-safe summary after the decision app exits."""
    reference = request.template_reference
    template = (
        (reference.display_name or reference.locator) if reference else "No template"
    )
    tools = ""
    if request.recipe:
        opinions = (
            request.template_blueprint.tooling_overrides
            if request.template_blueprint
            else {}
        )
        tools = ", ".join(
            selection.tool.value
            for selection in request.recipe.selections(opinions)
            if selection.enabled
        )
    console.print(heading("Recipe"))
    console.print(
        indented(
            _facts(
                [
                    ("Template", template),
                    ("Tools", tools or "None"),
                    ("Docker", "yes" if request.docker else "no"),
                ]
            )
        )
    )


def print_review_summary(decision: InitDecision) -> None:
    """Leave the change review's decisions in scrollback after the app exits.

    Args:
        decision: The review's outcome.
    """
    rows = []
    if decision.draft.collision_strategy:
        rows.append(("Existing files", decision.draft.collision_strategy.value))
    if decision.confirmed_commands:
        count = len(decision.confirmed_commands)
        rows.append(
            (
                "Commands",
                f"{count} confirmed from an untrusted template",
            )
        )
    if decision.draft.allowed_secrets:
        rows.append(
            (
                "Kept values",
                "flagged as credentials: "
                + ", ".join(sorted(decision.draft.allowed_secrets)),
            )
        )
    if rows:
        console.print(heading("Review"))
        console.print(indented(_facts(rows)))
