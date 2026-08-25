"""Command-line interface and entry point for Protostar."""

import argparse
import importlib.resources
import json
import logging
import os
import platform
import shlex
import shutil
import subprocess
import sys
import traceback
import types
import urllib.parse
from collections.abc import Iterable
from typing import Any, ClassVar, cast

import argcomplete
from rich import box
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.status import Status
from rich.style import Style
from rich.table import Table
from rich_argparse import RawTextRichHelpFormatter

from protostar import __version__

from .config import CONFIG_FILE, DEFAULT_CONFIG_CONTENT, TemplateBlueprint, UserConfig
from .errors import (
    CommandExecutionError,
    ConfigurationError,
    ExecutionAbortedError,
    FileSystemError,
    InvalidUsageError,
    MissingDependencyError,
    NetworkFetchError,
    ProtostarError,
    SecurityViolationError,
    TemplateResolutionError,
    WorkspaceCollisionError,
)
from .fs import atomic_write_text
from .manifest import CollisionStrategy, Severity
from .metadata import resolve_auto_metadata
from .models import InitRequest
from .modules import (
    TOOLING_MODULES,
    BootstrapModule,
    PythonCore,
    SystemWorkspaceModule,
)
from .orchestrator import Orchestrator
from .system import is_interactive
from .wizard import (
    resolve_missing_variables,
    run_init_wizard,
)

# ---------------------------------------------------------------------------
# JSON Mode Infrastructure
# ---------------------------------------------------------------------------

# Marks the agent interface as experimental. Increment when the schema
# stabilises and a compatibility commitment is made.
CLI_API_VERSION: int = 0

# Evaluated at import time so the flag is position-independent (e.g. both
# `protostar --json init` and `protostar init --json` are equivalent).
is_json_mode: bool = "--json" in sys.argv

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


class JsonAwareParser(argparse.ArgumentParser):
    """ArgumentParser subclass that emits structured JSON errors in JSON mode.

    When ``--json`` is detected in ``sys.argv``, parse failures (e.g., unrecognised
    flags, missing required arguments) are intercepted and routed through
    ``emit_json()`` as a machine-readable error envelope rather than being
    printed to ``stderr`` in argparse's human-readable format.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        """Overrides argparse's default error handler.

        Args:
            message: The human-readable error description produced by argparse.
        """
        if is_json_mode:
            emit_json(
                {
                    "api_version": CLI_API_VERSION,
                    "status": "error",
                    "error": {
                        "type": "InvalidUsageError",
                        "message": message,
                    },
                }
            )
            sys.exit(os.EX_USAGE)
        super().error(message)


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
    except Exception:
        pass

    user_config = UserConfig.load()
    if user_config.templates:
        for alias, source in user_config.templates.items():
            templates.append({"name": alias, "type": "global-alias", "source": source})

    if is_json_mode:
        if error_msg:
            emit_json(
                {
                    "api_version": CLI_API_VERSION,
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
                "api_version": CLI_API_VERSION,
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


def _run_engine(engine: Orchestrator, request: InitRequest) -> None:
    """Runs the full plan → trust → execute → render pipeline for the CLI.

    Encapsulates the collision prompt loop, remote trust boundary, execution,
    and diagnostic rendering so both the argument-driven and wizard-driven
    entry points share the same presentation logic.

    Args:
        engine: A fully constructed Orchestrator.
        request: The InitRequest used to build the engine. May be replaced if
            the user resolves a collision interactively.
    """
    import questionary
    from questionary import Choice

    # --- Collision Loop ---
    try:
        manifest = engine.plan()
    except WorkspaceCollisionError as e:
        console.print(
            "\n[bold yellow]Gravitational Anomaly:[/bold yellow] Protostar detected "
            "existing configuration files in the workspace."
        )
        for path in sorted(e.paths):
            console.print(f"  - {path}")

        if not is_interactive():
            raise ProtostarError(
                "Orbital Collision Detected: The target workspace is not empty.\n"
                "Aborting to prevent destructive mutations in a non-interactive context.\n"
                "Use the --force-merge or --force-replace flag to bypass this check."
            ) from e

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

            confirmed = questionary.confirm(
                "Do you trust this source to modify your system?", default=False
            ).ask()
            if not confirmed or confirmed is None:
                raise ExecutionAbortedError(
                    "Execution cancelled: Untrusted external source."
                )

    # --- Execute ---
    console.print("[bold]Protostar Ignition Sequence Initiated[/bold]")

    logger = logging.getLogger("protostar")
    # Temporarily drop the log level to INFO so the spinner receives the events
    previous_level = logger.level
    if logger.getEffectiveLevel() > logging.INFO:
        logger.setLevel(logging.INFO)

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


def handle_init(args: argparse.Namespace) -> None:
    """Handles the 'init' subcommand to scaffold environments."""
    if getattr(args, "list_templates", False):
        _print_templates_and_exit()

    override_target = getattr(args, "from_path", None)
    template_name = getattr(args, "template_name", None)

    # Intercept a dangling --template flag
    if template_name == "":
        _print_templates_and_exit(
            "The '--template' flag requires a name argument. Choose from the list below:"
        )

    template_context = getattr(args, "template_context", {})

    user_config = UserConfig.load()
    is_external = False
    is_user_aliased = False

    if override_target and template_name:
        raise ConfigurationError(
            "Cannot use both '--template' and '--from' simultaneously."
        )

    if override_target:
        is_external = True

    if template_name:
        # 1. Check built-ins
        target = importlib.resources.files("protostar.templates").joinpath(
            f"{template_name}.toml"
        )
        if target.is_file():
            override_target = str(target)
        # 2. Check user aliases
        elif template_name in user_config.templates:
            override_target = user_config.templates[template_name]
            is_external = True
            is_user_aliased = True
        else:
            raise ConfigurationError(
                f"Template '{template_name}' not found in built-ins or global configuration aliases."
            )

    blueprint = None

    if override_target:
        blueprint = TemplateBlueprint.load(
            override_target,
            template_context=template_context,
            variable_resolver=resolve_missing_variables,
        )

    modules: list[BootstrapModule] = []

    # 1. Universal System Layer
    modules.append(SystemWorkspaceModule())

    # 2. Mandatory Python Core
    python_core = PythonCore(
        python_version=getattr(args, "python_version", None),
    )
    modules.append(python_core)

    # 3. Tooling Layers
    for mod in TOOLING_MODULES:
        # 3. Lowest priority: User's global defaults
        is_active = getattr(user_config, mod.config_key, False)

        # 2. Medium priority: Template author's explicit overrides
        if blueprint and mod.config_key in blueprint.tooling_overrides:
            is_active = blueprint.tooling_overrides[mod.config_key]

        # 1. Highest priority: User's CLI flags for this specific run
        if mod.cli_flags:
            cli_override = getattr(args, mod.__class__.__name__, None)
            if cli_override is not None:
                is_active = cli_override

        if is_active:
            modules.append(mod)

    # Validate mutually exclusive tooling modules
    active_tooling_names = [type(mod).__name__ for mod in modules]
    if (
        "PreCommitModule" in active_tooling_names
        and "PrekModule" in active_tooling_names
    ):
        raise ConfigurationError(
            "Cannot use both '--pre-commit' and '--prek' simultaneously. "
            "Please choose one git hook manager."
        )

    if (
        "ReadTheDocsModule" in active_tooling_names
        and "ZensicalModule" not in active_tooling_names
    ):
        raise ConfigurationError(
            "Cannot scaffold Read the Docs without the Zensical module enabled. "
            "Please enable '--zensical' or configure 'zensical = true'."
        )

    # 4. Undocumented Crash Test Injection
    if getattr(args, "crash_test", False):

        class CrashModule(BootstrapModule):
            @property
            def name(self) -> str:
                return "CrashTest"

            def pre_flight(self) -> None:
                raise TypeError("INTENTIONAL_CRASH")

            def build(self, manifest: Any) -> None:
                pass

        modules.append(CrashModule())

    required_keys: set[str] = set()
    for mod in modules:
        required_keys.update(mod.required_metadata)

    resolved_metadata = resolve_auto_metadata(required_keys)

    request = InitRequest(
        template_blueprint=blueprint,
        docker=args.docker,
        force_merge=getattr(args, "force_merge", False),
        force_replace=getattr(args, "force_replace", False),
        metadata=resolved_metadata,
        is_external=is_external,
        is_user_aliased=is_user_aliased,
    )
    engine = Orchestrator(modules, user_config, request=request)
    _run_engine(engine, request)


class ProtoHelpFormatter(RawTextRichHelpFormatter):
    """Custom help formatter for Protostar CLI using rich-argparse.

    Inherits from RawTextRichHelpFormatter to leverage native rich styling
    while respecting explicit line breaks in docstrings and argument parameters.
    """

    # Establish global syntactic styling identifiers
    styles: ClassVar[dict[str, str | Style]] = {
        "argparse.args": "cyan",
        "argparse.groups": "bold blue",
        "argparse.help": "default",
        "argparse.metavar": "dark_orange",
    }

    def add_usage(
        self,
        usage: str | None,
        actions: Iterable[argparse.Action],
        groups: Iterable[argparse._MutuallyExclusiveGroup],
        prefix: str | None = None,
    ) -> None:
        """Overrides the default 'usage: ' prefix for a cleaner aesthetic."""
        if prefix is None:
            prefix = "Usage: "
        super().add_usage(usage, actions, groups, prefix)


def print_table_help(self: argparse.ArgumentParser, file: Any = None) -> None:
    """Custom help printer that formats action groups as bordered Rich tables."""
    # Print main parser description
    if self.description:
        console.print(f"{self.description}\n")

    # Note: argparse does not provide a public API for iterating over groups.
    # Accessing _action_groups and _group_actions is the standard community workaround.
    for group in self._action_groups:
        # Filter out explicitly suppressed arguments and the default HelpAction
        actions = [
            a
            for a in group._group_actions
            if a.help != argparse.SUPPRESS and not isinstance(a, argparse._HelpAction)
        ]

        if not actions:
            continue

        # Catch the default argparse 'options' group and capitalize it
        display_title = (
            group.title.capitalize() if group.title == "options" else group.title
        )

        table = Table(
            show_header=False,
            title=display_title,  # Inject the patched title
            box=box.ROUNDED,
            show_lines=False,
            padding=(0, 1),
            title_justify="left",
            title_style="bold blue",
        )
        table.add_column("Arguments", style="cyan", no_wrap=True)
        table.add_column("Description")

        for action in actions:
            # Build the invocation string (e.g., "-p, --python")
            if action.option_strings:
                invocation = ", ".join(action.option_strings)

                # Append metavars for arguments that take values
                if (
                    action.nargs != 0
                    and action.dest != "help"
                    and not isinstance(action, argparse.BooleanOptionalAction)
                ):
                    if action.metavar:
                        metavar_str = (
                            " ".join(action.metavar)
                            if isinstance(action.metavar, tuple)
                            else action.metavar
                        )
                    else:
                        metavar_str = action.dest.upper()
                    invocation += f" {metavar_str}"
            else:
                if action.metavar:
                    invocation = (
                        " ".join(action.metavar)
                        if isinstance(action.metavar, tuple)
                        else action.metavar
                    )
                else:
                    invocation = action.dest

            # Extract help payload, prioritizing native Rich renderables if available
            help_text: Any = action.help or ""
            if hasattr(help_text, "get_renderable"):
                help_text = help_text.get_renderable()
            elif hasattr(help_text, "__str__") and not isinstance(help_text, str):
                help_text = str(help_text)

            table.add_row(invocation, help_text)

        console.print(table)
        console.print()

    # Append the parser's epilog block if one is defined
    if self.epilog:
        if hasattr(self.epilog, "get_renderable"):
            renderable_method = cast(Any, self.epilog).get_renderable
            console.print(renderable_method())
        else:
            console.print(self.epilog)


def build_parser() -> argparse.ArgumentParser:
    """Constructs and returns the primary argument parser with dynamically injected modules."""
    base_parser = JsonAwareParser(add_help=False)
    base_parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the application's version and exit.",
    )
    base_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,  # Prevents subparser from overwriting root namespace
        help="Enable verbose debug output and rich tracebacks.",
    )

    parser = JsonAwareParser(
        description="A modular CLI tool for quickly scaffolding Python environments. ",
        epilog="Run 'protostar help <command>' or 'protostar <command> --help' for detailed options.",
        formatter_class=ProtoHelpFormatter,
        add_help=False,
        usage=argparse.SUPPRESS,
        parents=[base_parser],
    )

    # Manually re-add the help flags but suppress them from the visual output
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="Subcommands",
        metavar="<command>",
    )

    # --- Init Subparser ---
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new Python environment and aggregate manifest configurations.",
        description="Scaffolds base Python configurations, dependencies, and environment files.",
        formatter_class=ProtoHelpFormatter,
        usage=argparse.SUPPRESS,
        epilog="[bold]Example:[/bold]\n  protostar init --template astro --mypy",
        parents=[base_parser],
    )

    init_parser.add_argument(
        "--crash-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    base_group = init_parser.add_argument_group("Base Configuration")

    base_group.add_argument(
        "-t",
        "--template",
        type=str,
        nargs="?",  # Allow 0 or 1 arguments
        const="",  # Value if flag is present but no argument is provided
        default=None,  # Value if flag is omitted entirely
        dest="template_name",
        help="Name of a template to apply (run with --list-templates to view available).",
        metavar="NAME",
    )
    base_group.add_argument(
        "--list-templates",
        action="store_true",
        help="List all available built-in and global alias templates.",
    )
    base_group.add_argument(
        "--from",
        type=str,
        dest="from_path",
        help="Path to a portable configuration TOML file to apply.",
        metavar="PATH",
    )
    base_group.add_argument(
        "--python-version",
        type=str,
        help="Specify the Python version to scaffold (e.g., 3.13). Overrides global configuration.",
        dest="python_version",
        metavar="VERSION",
    )

    # Tooling Context
    tooling_group = init_parser.add_argument_group("Tooling & Context")

    # The force flags for collision bypass
    tooling_group.add_argument(
        "--force-merge",
        action="store_true",
        help="Bypass interactive prompts and safely merge on file collisions.",
    )

    tooling_group.add_argument(
        "--force-replace",
        action="store_true",
        help="Bypass interactive prompts and forcibly overwrite file collisions.",
    )

    tooling_group.add_argument(
        "--docker",
        action="store_true",
        help="Generate Dockerfile and .dockerignore container scaffolding",
    )

    for mod in TOOLING_MODULES:
        if mod.cli_flags:
            tooling_group.add_argument(
                *mod.cli_flags,
                action=argparse.BooleanOptionalAction,
                help=mod.cli_help,
                dest=mod.__class__.__name__,
            )

    init_parser.set_defaults(func=handle_init)
    init_parser.print_help = types.MethodType(print_table_help, init_parser)  # type: ignore[method-assign]

    # --- Config Subparser ---
    config_parser = subparsers.add_parser(
        "config",
        help="Manage global Protostar configuration.",
        description="Opens the global configuration file in your system's default $EDITOR.",
        formatter_class=ProtoHelpFormatter,
        usage=argparse.SUPPRESS,
        parents=[base_parser],
    )
    config_parser.add_argument(
        "--force-replace",
        action="store_true",
        help="Bypass confirmation prompt when resetting configuration.",
    )
    config_parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the global configuration file to its default state.",
    )
    config_parser.set_defaults(func=handle_config)

    # --- Help Subparser ---
    help_parser = subparsers.add_parser(
        "help",
        help="Show this help message or a subcommand's manual.",
        description="Displays the CLI help manual.",
        formatter_class=ProtoHelpFormatter,
        parents=[base_parser],
    )

    # Dynamically grab registered commands, excluding 'help' itself
    available_commands = [k for k in subparsers.choices if k != "help"]

    help_parser.add_argument(
        "topic",
        nargs="?",
        choices=available_commands,
        help="The specific subcommand to explain.",
    )

    def dispatch_help(parsed_args: argparse.Namespace) -> None:
        """Closure to evaluate and print the requested help scope."""
        if getattr(parsed_args, "topic", None):
            # Print the localized help for the specific subcommand
            subparsers.choices[parsed_args.topic].print_help()
        else:
            # Fall back to the global help
            parser.print_help()

    help_parser.set_defaults(func=dispatch_help)

    # Inject argcomplete to evaluate the AST of the parser for shell tab-completion
    argcomplete.autocomplete(parser)

    return parser


def _build_capabilities_schema(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Introspects the parser to build a dynamic capabilities schema.

    Generates a structured description of all available subcommands and their
    flags by walking the parser's action groups. This is the payload emitted
    when ``--help --json`` or bare ``--json`` is invoked.

    Args:
        parser: The fully constructed root argument parser.

    Returns:
        A JSON-serializable capabilities dictionary.
    """
    commands: dict[str, Any] = {}
    subparsers_action = next(
        (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
        None,
    )
    if subparsers_action is not None:
        for name, subparser in subparsers_action.choices.items():
            flags: list[dict[str, Any]] = []
            for action in subparser._actions:
                if isinstance(action, argparse._HelpAction):
                    continue
                if action.help == argparse.SUPPRESS:
                    continue
                flag_entry: dict[str, Any] = {
                    "names": action.option_strings or [action.dest],
                    "help": action.help or "",
                }
                if action.metavar:
                    flag_entry["metavar"] = action.metavar
                if (
                    isinstance(
                        action,
                        (
                            argparse.BooleanOptionalAction,
                            argparse._StoreTrueAction,
                            argparse._StoreFalseAction,
                        ),
                    )
                    or action.nargs == 0
                ):
                    flag_entry["type"] = "bool"
                else:
                    flag_entry["type"] = "str"
                flags.append(flag_entry)
            commands[name] = {
                "description": subparser.description or "",
                "flags": flags,
            }
    return {"commands": commands}


def _dispatch_preparser_flags(parser: argparse.ArgumentParser) -> None:
    """Intercepts JSON-mode meta-flags before argparse runs.

    Examines raw ``sys.argv`` for flag combinations that should short-circuit
    normal parsing: ``--version --json``, ``--help --json``, and bare ``--json``
    with no subcommand. Each path emits exactly one JSON document and exits.

    Must be called after ``build_parser()`` but before ``parse_known_args()``.

    Args:
        parser: The fully constructed root argument parser, used to build the
            capabilities schema payload.
    """
    if not is_json_mode:
        return

    argv_set = set(sys.argv[1:])

    # --version --json  (any order)
    if "--version" in argv_set:
        emit_json(
            {
                "api_version": CLI_API_VERSION,
                "status": "success",
                "version": __version__,
            }
        )
        sys.exit(0)

    # --help --json or bare --json with no recognised subcommand
    has_known_subcommand = bool(
        argv_set - {"--json", "--help", "-h", "--verbose", "-v"}
    )
    if "--help" in argv_set or "-h" in argv_set or not has_known_subcommand:
        emit_json(
            {
                "api_version": CLI_API_VERSION,
                "status": "success",
                "capabilities": _build_capabilities_schema(parser),
            }
        )
        sys.exit(0)


# --- CLI Design Note: Pre-Parser Interception & POSIX Exit Mapping ---
# 1. Interactive TUI Interception: Evaluates raw `sys.argv` before `argparse.parse_args()`
#    to seamlessly drop users into interactive wizards when flags are omitted, avoiding generic
#    argparse help outputs.
# 2. POSIX Sysexits Mapping: Domain exceptions map directly to standard POSIX status codes
#    (e.g., EX_CONFIG=78, EX_UNAVAILABLE=69, EX_IOERR=74) to allow automated shell scripts and CI/CD
#    runners to programmatically differentiate configuration errors from disk or network failures.
def intercept_interactive_wizards(parser: argparse.ArgumentParser) -> None:
    """Evaluates sys.argv to route execution to TUI wizards if parameters are omitted."""
    if len(sys.argv) == 1:
        sys.argv.append("init")

    # Intercept parameter-less subcommands for interactive wizards
    if len(sys.argv) == 2:
        cmd = sys.argv[1]

        if cmd == "init":
            selections = run_init_wizard()
            if not selections:
                return

            user_config = UserConfig.load()
            modules = selections.modules

            # Inject mandatory universal layers implicitly
            modules.insert(0, SystemWorkspaceModule())
            modules.insert(1, PythonCore())

            request = InitRequest(
                template_blueprint=selections.blueprint,
                docker=selections.docker,
                force_merge=False,
                force_replace=False,
                metadata=selections.project_metadata,
                is_external=selections.is_external,
                is_user_aliased=selections.is_user_aliased,
            )
            engine = Orchestrator(modules, user_config, request=request)
            _run_engine(engine, request)
            sys.exit(0)


def configure_logging() -> None:
    """Injects Rich tracebacks and debug handlers into the global logger.

    In JSON mode, the handler writes to ``stderr`` to preserve ``stdout`` for
    the exclusive use of machine-readable JSON payloads.
    """
    log_console = _stderr_console if is_json_mode else console
    logger = logging.getLogger("protostar")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(
        RichHandler(console=log_console, markup=True, rich_tracebacks=True)
    )


def handle_config(args: argparse.Namespace) -> None:
    """Handles the 'config' subcommand to manage global CLI settings.

    Opens the global configuration file in the system's default editor.
    Ensures the parent directory exists and seeds a default configuration
    template if the file is missing. Safely tokenizes the $EDITOR environment
    variable to support complex commands (e.g., 'code --wait').

    Args:
        args: Parsed CLI arguments mapping to this command.
    """
    if not CONFIG_FILE.parent.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    if getattr(args, "reset", False):
        if not getattr(args, "force_merge", False) and not getattr(
            args, "force_replace", False
        ):
            import questionary

            confirmed = questionary.confirm(
                "Warning: this will erase your current configuration, are you sure you want to do this?",
                default=False,
            ).ask()
            if confirmed is None:
                raise ExecutionAbortedError("Configuration reset aborted.")
            if not confirmed:
                console.print("[yellow]Configuration reset aborted.[/yellow]")
                return

        atomic_write_text(CONFIG_FILE, DEFAULT_CONFIG_CONTENT)
        console.print(
            f"[bold green]Reset configuration at {CONFIG_FILE} to default state.[/bold green]"
        )
        return

    if not CONFIG_FILE.exists():
        atomic_write_text(CONFIG_FILE, DEFAULT_CONFIG_CONTENT)
        console.print(
            f"[bold green]Initialized default configuration at {CONFIG_FILE}[/bold green]"
        )

    editor_env = os.environ.get("EDITOR", "nano")
    editor_cmd = shlex.split(editor_env)

    if not editor_cmd:
        raise ConfigurationError("The $EDITOR environment variable is empty.")

    if not shutil.which(editor_cmd[0]):
        raise ConfigurationError(
            f"Could not resolve editor executable '{editor_cmd[0]}'.\n"
            "Ensure your $EDITOR environment variable is set to a valid binary in your PATH."
        )

    editor_cmd.append(str(CONFIG_FILE))

    try:
        subprocess.run(editor_cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise ConfigurationError(
            f"Editor '{editor_env}' exited with non-zero status: {e}"
        ) from e


def _parse_dynamic_kwargs(unknown_args: list[str]) -> dict[str, str]:
    """Parses trailing unknown CLI arguments into a variable dictionary.

    Args:
        unknown_args: The trailing list of arguments rejected by the main parser.

    Returns:
        A dictionary mapping the dynamic flag names to their values.

    Raises:
        ConfigurationError: If positional (non-flag) arguments are encountered.
    """
    kwargs = {}
    i = 0
    while i < len(unknown_args):
        arg = unknown_args[i]
        if arg.startswith("--"):
            key = arg.lstrip("-")
            if "=" in key:
                k, v = key.split("=", 1)
                kwargs[k] = v
            else:
                if i + 1 < len(unknown_args) and not unknown_args[i + 1].startswith(
                    "--"
                ):
                    kwargs[key] = unknown_args[i + 1]
                    i += 1
                else:
                    kwargs[key] = ""
        else:
            raise ConfigurationError(
                f"Unrecognized positional argument for interpolation: {arg}"
            )
        i += 1
    return kwargs


# Maps known subcommands to their documentation page.
# Only include subcommands that have a dedicated reference page.
# Unmapped subcommands fall back to the docs root.
_SUBCOMMAND_DOC_PATHS: dict[str, str] = {
    "init": "usage/init/",
    "config": "usage/configuration/",
}


def _resolve_usage_doc_path() -> str:
    """Returns the docs_path for the active subcommand, or '' for the root page.

    Reads sys.argv[1] to identify the subcommand. Returns a mapped docs_path
    if the subcommand is known, otherwise returns '' which resolves to the
    documentation root. This is intentionally conservative: an incorrect link
    is worse than the root page.

    Returns:
        A docs_path string suitable for passing to InvalidUsageError.
    """
    if len(sys.argv) >= 2:
        return _SUBCOMMAND_DOC_PATHS.get(sys.argv[1], "")
    return ""


def main() -> None:
    """Main execution pipeline for the Protostar CLI."""
    parser = build_parser()
    _dispatch_preparser_flags(parser)

    try:
        intercept_interactive_wizards(parser)
        args, unknown = parser.parse_known_args()

        if unknown and (
            getattr(args, "command", None) != "init"
            or not getattr(args, "from_path", None)
        ):
            raise InvalidUsageError(
                f"Unrecognized arguments: {' '.join(unknown)}",
                docs_path=_resolve_usage_doc_path(),
            )

        args.template_context = _parse_dynamic_kwargs(unknown)

        if getattr(args, "verbose", False):
            configure_logging()

        if not getattr(args, "command", None):
            parser.print_help()
            sys.exit(1)

        args.func(args)

    except ProtostarError as e:
        # Expected domain errors route here for clean terminal formatting
        console.print()

        body = str(e)
        if isinstance(e, CommandExecutionError) and e.output_detail:
            body += f"\n\n[dim]{e.output_detail}[/dim]"
        if e.hint:
            body += f"\n\n[dim]Hint: {e.hint}[/dim]"
        if e.docs_url:
            body += f"\n\n[bold cyan][link={e.docs_url}]Read the documentation ↗[/link][/bold cyan]"

        console.print(
            Panel(
                body,
                title="[bold red]Execution Aborted",
                border_style="red",
                expand=False,
                padding=(1, 2),
            )
        )

        # Route specific domain exceptions to standard POSIX status codes
        if isinstance(e, InvalidUsageError):
            sys.exit(os.EX_USAGE)  # 64: Command line usage error
        if isinstance(e, SecurityViolationError):
            sys.exit(os.EX_NOPERM)  # 77: Permission denied / Security constraint
        if isinstance(e, ConfigurationError):
            sys.exit(os.EX_CONFIG)  # 78: Malformed configuration tables
        if isinstance(e, TemplateResolutionError):
            sys.exit(
                os.EX_DATAERR
            )  # 65: Data format error (e.g., bad zip, missing variables)
        if isinstance(e, NetworkFetchError):
            sys.exit(os.EX_TEMPFAIL)  # 75: Temporary failure (network drop)
        if isinstance(e, MissingDependencyError):
            sys.exit(
                os.EX_UNAVAILABLE
            )  # 69: Expected background tool executable missing
        if isinstance(e, FileSystemError):
            sys.exit(os.EX_IOERR)  # 74: Critical disk access or storage write faults
        if isinstance(e, ExecutionAbortedError):
            sys.exit(130)  # User aborted via interactive prompt

        sys.exit(1)  # Generic operational failure fallback

    except KeyboardInterrupt:
        # Catch Ctrl+C cleanly
        console.print("\n[bold red]Aborted by user.[/bold red]")
        sys.exit(130)

    except Exception as e:
        # Unexpected core system bugs route here for the crash report payload
        console.print(
            "\n[bold red]CRITICAL FAILURE:[/bold red] Protostar encountered an unexpected error."
        )

        console.print_exception(show_locals=False, max_frames=10)

        # Cap the traceback to 10 frames to avoid exceeding URL length limits
        tb_str = "".join(
            traceback.format_exception(type(e), e, e.__traceback__, limit=10)
        )
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
            "\nThis looks like a bug. Please help us fix it by submitting an issue with your telemetry:"
        )
        console.print(
            f"[bold cyan][link={issue_url}]Click here to open a GitHub issue with your telemetry[/link][/bold cyan]"
        )
        sys.exit(os.EX_SOFTWARE)  # 70: Internal software malfunction code


if __name__ == "__main__":
    main()
