import argparse
import difflib
import sys
import types
from collections.abc import Iterable, Sequence
from typing import Any, ClassVar, cast

import argcomplete
from rich import box
from rich.style import Style
from rich.table import Table
from rich_argparse import RawTextRichHelpFormatter

from protostar.cli import completion, schema, ui
from protostar.cli import main as cli_main
from protostar.cli.completion import Shell
from protostar.config import UserConfig
from protostar.docs_registry import DocsPage
from protostar.errors import InvalidUsageError
from protostar.models import InitRequest
from protostar.modules import TOOLING_MODULES, PythonCore, SystemWorkspaceModule
from protostar.orchestrator import Orchestrator
from protostar.wizard import run_init_wizard


def _resolve_usage_doc_path() -> str:
    """Returns the docs_path for the active subcommand, or CLI reference for unknown.

    Iterates through sys.argv to identify the first non-flag subcommand.
    Returns a mapped docs_path if the subcommand is known. If unknown, it attempts
    to guess the intended command using difflib. If no match is found, it defaults
    to the CLI reference page.

    Returns:
        A docs_path string suitable for passing to InvalidUsageError.
    """
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            if arg in _SUBCOMMAND_DOC_PATHS:
                return _SUBCOMMAND_DOC_PATHS[arg].value

            # Try to guess the command for typos (e.g. "initt" -> "init")
            matches = difflib.get_close_matches(
                arg, _SUBCOMMAND_DOC_PATHS.keys(), n=1, cutoff=0.6
            )
            if matches:
                return _SUBCOMMAND_DOC_PATHS[matches[0]].value

            return DocsPage.CLI_REFERENCE.value
    return DocsPage.CLI_REFERENCE.value


class JsonAwareParser(argparse.ArgumentParser):
    """ArgumentParser subclass that raises InvalidUsageError on parse failures.

    Intercepts standard argparse parse errors (e.g., invalid subcommands,
    missing required arguments, unrecognized choices) and raises
    ``InvalidUsageError``. This centralizes error handling through ``main()``'s
    ``ProtostarError`` handler so that both human mode (Rich pretty-printed
    error panel) and JSON mode (structured JSON envelope) are handled consistently
    with POSIX ``EX_USAGE`` exit codes.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        """Overrides argparse's default error handler.

        Args:
            message: The human-readable error description produced by argparse.

        Raises:
            InvalidUsageError: Always raised to route errors to the centralized handler.
        """
        raise InvalidUsageError(message, docs_path=_resolve_usage_doc_path())


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
        ui.console.print(f"{self.description}\n")

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

        ui.console.print(table)
        ui.console.print()

    # Append the parser's epilog block if one is defined
    if self.epilog:
        if hasattr(self.epilog, "get_renderable"):
            renderable_method = cast(Any, self.epilog).get_renderable
            ui.console.print(renderable_method())
        else:
            ui.console.print(self.epilog)


def _get_version() -> str:
    """Returns the installed application version lazily."""
    import protostar

    return protostar.__version__


class _VersionAction(argparse.Action):
    """Custom action to lazily resolve application version only when requested."""

    def __init__(
        self,
        option_strings: list[str],
        dest: str = argparse.SUPPRESS,
        default: str = argparse.SUPPRESS,
        help: str | None = "Show the application's version and exit.",  # noqa: A002
        **kwargs: Any,
    ) -> None:
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
            **kwargs,
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        formatter = parser._get_formatter()
        formatter.add_text(f"%(prog)s {_get_version()}")
        parser._print_message(formatter.format_help(), sys.stdout)
        parser.exit()


def build_parser() -> argparse.ArgumentParser:
    """Constructs and returns the primary argument parser with dynamically injected modules."""
    base_parser = JsonAwareParser(add_help=False)
    base_parser.add_argument(
        "--version",
        action=_VersionAction,
        help="Show the application's version and exit.",
    )
    base_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,  # Prevents subparser from overwriting root namespace
        help="Enable verbose debug output and rich tracebacks.",
    )
    base_parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,  # Hide from human help output
    )

    parser = JsonAwareParser(
        description="High-velocity, zero-friction Python environment scaffolding.",
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
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan the execution and print the resulting manifest without mutating the disk.",
    )
    base_group = init_parser.add_argument_group("Base Configuration")

    template_action = base_group.add_argument(
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
    template_action.completer = completion.template_completer  # type: ignore[attr-defined]

    base_group.add_argument(
        "--list-templates",
        action="store_true",
        help="List all available built-in and global alias templates.",
    )
    from_action = base_group.add_argument(
        "--from",
        type=str,
        dest="from_path",
        help="Path to a portable configuration TOML file to apply.",
        metavar="PATH",
    )
    from_action.completer = argcomplete.completers.FilesCompleter(  # type: ignore[attr-defined]
        allowednames=[".toml"]
    )

    python_version_action = base_group.add_argument(
        "--python-version",
        type=str,
        help="Specify the Python version to scaffold (e.g., 3.13). Overrides global configuration.",
        dest="python_version",
        metavar="VERSION",
    )
    python_version_action.completer = argcomplete.completers.ChoicesCompleter(  # type: ignore[attr-defined]
        {"3.12": "Python 3.12", "3.13": "Python 3.13", "3.14": "Python 3.14"}
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

    init_parser.set_defaults(func=cli_main.handle_init)
    init_parser.print_help = types.MethodType(print_table_help, init_parser)  # type: ignore[method-assign]

    # --- Export Schema Subparser ---
    export_schema_parser = subparsers.add_parser(
        "export-schema",
        help="Export the JSON Schema for the TOML template format.",
        description="Generates and prints the JSON Schema representing the layout of Protostar template files. Intended for IDE tooling and programmatic interrogation.",
        formatter_class=ProtoHelpFormatter,
        usage=argparse.SUPPRESS,
        parents=[base_parser],
    )
    export_schema_parser.set_defaults(func=schema.handle_export_schema)

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
    config_parser.set_defaults(func=cli_main.handle_config)

    # --- Completion Subparser ---
    completion_parser = subparsers.add_parser(
        "completion",
        help="Generate shell autocompletion scripts.",
        description="Generates dynamic autocompletion scripts for supported shells (Bash, Zsh, Fish, PowerShell).",
        formatter_class=ProtoHelpFormatter,
        usage=argparse.SUPPRESS,
        epilog=(
            "[bold]Examples:[/bold]\n"
            '  # Zsh (macOS/Linux):\n  eval "$(protostar completion zsh)"\n\n'
            '  # Bash (Linux/macOS):\n  eval "$(protostar completion bash)"\n\n'
            "  # Fish:\n  protostar completion fish | source\n\n"
            "  # PowerShell (Windows):\n  protostar completion powershell | Out-String | Invoke-Expression"
        ),
        parents=[base_parser],
    )
    completion_parser.add_argument(
        "shell",
        nargs="?",
        choices=[s.value for s in Shell],
        metavar="<shell>",
        help=f"Target shell ({', '.join(s.value for s in Shell)}). If omitted, displays configuration instructions.",
    )
    completion_parser.set_defaults(func=completion.handle_completion)

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
        if ui.is_json_mode:
            schema.emit_capabilities(
                parser, command=getattr(parsed_args, "topic", None)
            )

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
    if not ui.is_json_mode:
        return

    argv_set = set(sys.argv[1:])

    # --version --json  (any order)
    if "--version" in argv_set:
        ui.emit_json(
            {
                "api_version": schema.CLI_API_VERSION,
                "status": "success",
                "version": _get_version(),
            }
        )
        sys.exit(0)

    # Resolve available subcommands from parser choices
    subparsers_action = next(
        (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
        None,
    )
    known_commands = (
        set(subparsers_action.choices.keys()) if subparsers_action else set()
    )
    # Find any subcommand present in sys.argv (excluding 'help' if handled via dispatch_help)
    subcommand = next(
        (arg for arg in sys.argv[1:] if arg in known_commands and arg != "help"),
        None,
    )

    has_help_flag = "--help" in argv_set or "-h" in argv_set
    is_bare_json = not bool(argv_set - {"--json", "--verbose", "-v"})

    if has_help_flag:
        schema.emit_capabilities(parser, command=subcommand)

    if is_bare_json:
        schema.emit_capabilities(parser)


def intercept_interactive_wizards(parser: argparse.ArgumentParser) -> None:
    """Evaluates sys.argv to route execution to TUI wizards if parameters are omitted."""
    if ui.is_json_mode:
        return

    cmd = None
    if len(sys.argv) == 1:
        cmd = "init"
    elif len(sys.argv) == 2:
        cmd = sys.argv[1]

    # Intercept parameter-less subcommands for interactive wizards
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
        ui._run_engine(engine, request)
        sys.exit(0)


_SUBCOMMAND_DOC_PATHS: dict[str, DocsPage] = {
    "init": DocsPage.INIT,
    "config": DocsPage.CONFIGURATION,
    "completion": DocsPage.CLI_REFERENCE,
}
