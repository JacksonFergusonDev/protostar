import argparse
import difflib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from protostar.orchestrator import Orchestrator

import argcomplete
from rich import box
from rich.console import Console
from rich.table import Table

from protostar.cli import completion, schema, ui
from protostar.cli import main as cli_main
from protostar.cli.completion import Shell
from protostar.config import UserConfig
from protostar.docs_registry import DocsPage
from protostar.errors import InvalidUsageError
from protostar.models import InitRequest
from protostar.modules import TOOLING_MODULES, PythonCore, SystemWorkspaceModule
from protostar.wizard import run_init_wizard


def _resolve_usage_doc_path() -> DocsPage:
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
                return _SUBCOMMAND_DOC_PATHS[arg]

            # Try to guess the command for typos (e.g. "initt" -> "init")
            matches = difflib.get_close_matches(
                arg, _SUBCOMMAND_DOC_PATHS.keys(), n=1, cutoff=0.6
            )
            if matches:
                return _SUBCOMMAND_DOC_PATHS[matches[0]]

            return DocsPage.CLI_REFERENCE
    return DocsPage.CLI_REFERENCE


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

    def print_help(self, file: Any = None) -> None:
        """Prints help output formatted as bordered Rich tables."""
        print_table_help(self, file)


def print_table_help(self: argparse.ArgumentParser, file: Any = None) -> None:
    """Custom help printer that formats action groups as bordered Rich tables."""
    console = ui.console if file in (None, sys.stdout) else Console(file=file)

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

        # Catch default argparse groups and normalize them to Title Case
        display_title = group.title or ""
        if display_title.lower() in ("options", "positional arguments", "subcommands"):
            display_title = display_title.title()

        table = Table(
            show_header=False,
            title=display_title,
            box=box.ROUNDED,
            show_lines=False,
            padding=(0, 1),
            title_justify="left",
            title_style="bold blue",
        )
        table.add_column("Arguments", style="cyan", no_wrap=True)
        table.add_column("Description")

        for action in actions:
            if isinstance(action, argparse._SubParsersAction):
                choices_actions = getattr(action, "_choices_actions", [])
                if choices_actions:
                    for choice_action in choices_actions:
                        if choice_action.help == argparse.SUPPRESS:
                            continue
                        sub_help: Any = choice_action.help or ""
                        if hasattr(sub_help, "get_renderable"):
                            sub_help = sub_help.get_renderable()
                        elif hasattr(sub_help, "__str__") and not isinstance(
                            sub_help, str
                        ):
                            sub_help = str(sub_help)
                        table.add_row(choice_action.dest, sub_help)
                else:
                    for name, subparser in action.choices.items():
                        sub_help = getattr(subparser, "description", "") or ""
                        table.add_row(name, sub_help)
                continue

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

        if table.row_count > 0:
            console.print(table)
            console.print()

    # Append the parser's epilog block if one is defined
    if self.epilog:
        if hasattr(self.epilog, "get_renderable"):
            renderable_method = cast(Any, self.epilog).get_renderable
            console.print(renderable_method())
        else:
            console.print(self.epilog)


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
        ui.console.print(f"{parser.prog} {_get_version()}")
        parser.exit()


def build_parser() -> argparse.ArgumentParser:
    """Constructs and returns the primary argument parser with dynamically injected modules."""
    base_parser = JsonAwareParser(add_help=False)
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

    # Subcommand base parser: accepts global flags like --verbose but hides them from help output
    suppressed_base_parser = JsonAwareParser(add_help=False)
    suppressed_base_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    suppressed_base_parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    parser = JsonAwareParser(
        prog="protostar",
        description="High-velocity, zero-friction Python environment scaffolding.",
        epilog="Run 'protostar help <command>' or 'protostar <command> --help' for detailed options.",
        add_help=False,
        usage=argparse.SUPPRESS,
        parents=[base_parser],
    )
    parser.add_argument(
        "--version",
        action=_VersionAction,
        help="Show the application's version and exit.",
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

    from protostar.cli.reviews import handle_review

    for command, description in (
        (
            "status",
            "Summarize accepted updates, conflicts, and preserved local intent.",
        ),
        (
            "diff",
            "Review accepted file diffs, conflicts, and proposed resolver actions.",
        ),
    ):
        review_parser = subparsers.add_parser(
            command,
            help=description,
            description=description,
            parents=[base_parser],
            epilog="Inspects the current directory. Requires [tool.protostar] and .protostar.lock.toml; never executes tasks or writes files.",
        )
        review_parser.set_defaults(func=handle_review)

    from protostar.cli.reviews import handle_sync

    sync_parser = subparsers.add_parser(
        "sync",
        help="Apply safe project updates and retain conflicting local content.",
        description="Apply accepted lifecycle updates transactionally in the current directory.",
        parents=[base_parser],
        epilog="Requires the project recipe in pyproject.toml and .protostar.lock.toml. Never replays initialization tasks or IDE probes. Conflicts commit safe changes with exit 1.",
    )
    sync_modes = sync_parser.add_mutually_exclusive_group()
    sync_modes.add_argument(
        "--dry-run",
        action="store_true",
        help="Review accepted diffs without writing files or running subprocesses.",
    )
    sync_modes.add_argument(
        "--check",
        action="store_true",
        help="Read-only check; exit 1 when accepted work, state advancement, or conflicts remain.",
    )
    sync_parser.set_defaults(func=handle_sync)

    # --- Init Subparser ---
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new Python environment and aggregate manifest configurations.",
        description="Scaffolds base Python configurations, dependencies, and environment files.",
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
        help="Path or URL to an external template (TOML file, directory, or archive).",
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
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate Dockerfile and .dockerignore container scaffolding",
    )

    tooling_group.add_argument(
        "--bind",
        action="append",
        default=[],
        metavar="VARIABLE=ENVIRONMENT",
        help="Bind a custom template variable to an environment variable for replay.",
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

    # --- Export Schema Subparser ---
    export_schema_parser = subparsers.add_parser(
        "export-schema",
        help="Export the JSON Schema for the TOML template format.",
        description="Generates and prints the JSON Schema representing the layout of Protostar template files. Intended for IDE tooling and programmatic interrogation.",
        usage=argparse.SUPPRESS,
        parents=[suppressed_base_parser],
    )
    export_schema_parser.set_defaults(func=schema.handle_export_schema)

    # --- Config Subparser ---
    config_parser = subparsers.add_parser(
        "config",
        help="Manage global Protostar configuration.",
        description="Opens the global configuration file in your system's default $EDITOR.",
        usage=argparse.SUPPRESS,
        parents=[suppressed_base_parser],
    )
    config_parser.add_argument(
        "-f",
        "--force",
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
        usage=argparse.SUPPRESS,
        epilog=(
            "[bold]Examples:[/bold]\n"
            "  # Zsh (macOS/Linux):\n"
            "  protostar completion zsh > ~/.protostar-completion.zsh\n"
            "  echo 'source ~/.protostar-completion.zsh' >> ~/.zshrc\n\n"
            "  # Bash (Linux/macOS):\n"
            "  protostar completion bash > ~/.protostar-completion.bash\n"
            "  echo 'source ~/.protostar-completion.bash' >> ~/.bashrc\n\n"
            "  # Fish:\n"
            "  mkdir -p ~/.config/fish/completions\n"
            "  protostar completion fish > ~/.config/fish/completions/protostar.fish\n\n"
            "  # PowerShell (Windows):\n"
            '  protostar completion powershell > "$HOME\\protostar-completion.ps1"\n'
            "  Add-Content -Path $PROFILE -Value '. \"$HOME\\protostar-completion.ps1\"'"
        ),
        parents=[suppressed_base_parser],
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
        usage=argparse.SUPPRESS,
        parents=[suppressed_base_parser],
    )

    # Dynamically grab registered commands, excluding 'help' itself
    available_commands = [k for k in subparsers.choices if k != "help"]

    help_parser.add_argument(
        "topic",
        nargs="?",
        choices=available_commands,
        metavar="<command>",
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

    # --version --json  (any order, top-level only)
    if "--version" in argv_set and subcommand is None:
        ui.emit_json(
            {
                "api_version": schema.CLI_API_VERSION,
                "status": "success",
                "version": _get_version(),
            }
        )
        sys.exit(0)

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

        min_py = selections.project_metadata.get("minimum_python")
        min_py = str(min_py) if min_py else None
        selected_license = selections.project_metadata.get("license")
        selected_license = str(selected_license) if selected_license else None

        modules.insert(
            1, PythonCore(python_version=min_py, project_license=selected_license)
        )

        from dataclasses import replace

        from protostar.manifest import ProjectMetadata
        from protostar.recipe import RecipeIntent, Tool, establish_recipe, read_recipe

        existing_recipe = read_recipe(Path("pyproject.toml"))
        recipe = establish_recipe(
            user_config,
            RecipeIntent(
                selections.blueprint.reference if selections.blueprint else None,
                cast(ProjectMetadata, selections.project_metadata),
                selections.docker,
                min_py,
            ),
        )
        if existing_recipe:
            context = dict(recipe.context)
            context["CURRENT_YEAR"] = dict(existing_recipe.context)["CURRENT_YEAR"]
            recipe = replace(
                recipe,
                fallback=existing_recipe.fallback,
                context=tuple(sorted(context.items())),
                bindings=existing_recipe.bindings,
            )
        selected = {m.config_key for m in modules if m.config_key}
        opinions = (
            selections.blueprint.tooling_overrides if selections.blueprint else {}
        )
        tools = dict(existing_recipe.tools) if existing_recipe else {}
        for tool in Tool:
            enabled = tool in selected
            if enabled != opinions.get(tool, dict(recipe.fallback)[tool]):
                tools[tool] = enabled
        recipe = replace(recipe, tools=tuple(sorted(tools.items())))
        request = InitRequest(
            recipe=recipe,
            template_blueprint=selections.blueprint,
            template_reference=selections.blueprint.reference
            if selections.blueprint
            else None,
            docker=selections.docker,
            force_merge=False,
            force_replace=False,
            metadata=selections.project_metadata,
            is_external=selections.is_external,
            is_user_aliased=selections.is_user_aliased,
            is_trusted=selections.is_trusted,
        )
        orchestrator_cls: type[Orchestrator] = sys.modules[__name__].Orchestrator
        engine = orchestrator_cls(modules, user_config, request=request)
        ui._run_engine(engine, request)
        sys.exit(0)


_SUBCOMMAND_DOC_PATHS: dict[str, DocsPage] = {
    "init": DocsPage.INIT,
    "config": DocsPage.CONFIGURATION,
    "completion": DocsPage.CLI_REFERENCE,
}


def __getattr__(name: str) -> Any:
    """Lazy evaluation for heavy CLI dependencies."""
    if name == "Orchestrator":
        from protostar.orchestrator import Orchestrator

        globals()["Orchestrator"] = Orchestrator
        return Orchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
