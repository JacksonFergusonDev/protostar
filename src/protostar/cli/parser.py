"""The argument parser for every subcommand, and dispatch to their handlers.

Each tool's ``--flag`` and help come from its module's ``ToolInfo``.
"""

from __future__ import annotations

import argparse
import difflib
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from protostar.orchestrator import Orchestrator
    from protostar.preparation import ResolutionRequest

import argcomplete
from rich.console import Console
from rich.table import Table

from protostar.cli import completion, schema, ui
from protostar.cli import main as cli_main
from protostar.cli.arguments import Operation, OutputFormat
from protostar.cli.completion import Shell
from protostar.config import UserConfig
from protostar.docs_registry import DocsPage
from protostar.errors import ExecutionAbortedError, InvalidUsageError
from protostar.intent import TemplateOrigin
from protostar.modules import TOOLING_MODULES
from protostar.registry import prefetch_hook_registry
from protostar.system import is_interactive
from protostar.system_deps import check_required_executables
from protostar.templates import discover_templates
from protostar.tiers import Tier


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


def format_invocation(action: argparse.Action) -> str:
    """Returns how a command line writes an argument, such as ``-t, --template NAME``.

    Help screens and the CLI reference both show arguments this way.
    """
    if not action.option_strings:
        metavar = action.metavar or action.dest
        return " ".join(metavar) if isinstance(metavar, tuple) else metavar
    invocation = ", ".join(action.option_strings)
    if action.nargs != 0 and not isinstance(action, argparse.BooleanOptionalAction):
        metavar = action.metavar or action.dest.upper()
        invocation += " " + (
            " ".join(metavar) if isinstance(metavar, tuple) else metavar
        )
    return invocation


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

        table = Table(show_header=False, box=None, padding=(0, 3, 0, 0))
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

            invocation = format_invocation(action)

            # Extract help payload, prioritizing native Rich renderables if available
            help_text: Any = action.help or ""
            if hasattr(help_text, "get_renderable"):
                help_text = help_text.get_renderable()
            elif hasattr(help_text, "__str__") and not isinstance(help_text, str):
                help_text = str(help_text)

            table.add_row(invocation, help_text)

        if table.row_count > 0:
            console.print(ui.heading(display_title))
            console.print(ui.indented(table))
            console.print()

    # Append the parser's epilog block if one is defined
    if self.epilog:
        if hasattr(self.epilog, "get_renderable"):
            renderable_method = cast(Any, self.epilog).get_renderable
            console.print(renderable_method())
        else:
            console.print(self.epilog, highlight=False)


def _get_version() -> str:
    """Returns the installed application version lazily."""
    import protostar

    return protostar.__version__


def _get_description() -> str | None:
    """Returns the installed application's summary from project metadata."""
    from importlib.metadata import PackageNotFoundError, metadata

    try:
        return metadata("protostar").get("Summary")
    except PackageNotFoundError:
        return None


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


_RESOLVE_HELP = "Settle conflicts by id, or every conflict in a file by path. CHOICE is local (keep yours), desired (take the update), or both (text lines only). Repeatable."


def _resolution_request(value: str) -> ResolutionRequest:
    """Parses one ``SELECTOR=CHOICE`` resolution for ``--resolve``."""
    from protostar.merge import ResolutionChoice
    from protostar.preparation import ResolutionRequest

    selector, _, choice = value.rpartition("=")
    choices = ", ".join(c.value for c in ResolutionChoice)
    if not selector or choice not in {c.value for c in ResolutionChoice}:
        raise argparse.ArgumentTypeError(
            f"expected SELECTOR=CHOICE with CHOICE one of {choices}, got {value!r}"
        )
    return ResolutionRequest(selector, ResolutionChoice(choice))


def build_parser() -> argparse.ArgumentParser:
    """Constructs and returns the primary argument parser with dynamically injected modules."""
    base_parser = JsonAwareParser(add_help=False)
    base_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,  # Prevents subparser from overwriting root namespace
        help="Show debug logs and full tracebacks.",
    )
    base_parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print one JSON payload on stdout and never prompt.",
    )
    base_parser.add_argument(
        "--config",
        metavar="<path>",
        default=argparse.SUPPRESS,
        help="Read global configuration from this file instead of the default location.",
    )
    base_parser.add_argument(
        "--no-config",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Ignore global configuration entirely and use built-in defaults.",
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
    suppressed_base_parser.add_argument(
        "--config",
        metavar="<path>",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    suppressed_base_parser.add_argument(
        "--no-config",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    parser = JsonAwareParser(
        prog="protostar",
        description=_get_description(),
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

    for command, description in (
        (
            "status",
            "Show what an update would change, every conflict, and each edit of yours that stays.",
        ),
        (
            "diff",
            "Show an update's changes line by line, with every conflict and the packages it adds.",
        ),
    ):
        review_parser = subparsers.add_parser(
            command,
            help=description,
            description=description,
            parents=[base_parser],
            epilog="Reads the project in the current directory, which needs its recipe in pyproject.toml and protostar.lock. Never runs a command or writes a file.",
        )
        review_parser.set_defaults(func=dispatch_operation, operation=Operation.REVIEW)

    sync_parser = subparsers.add_parser(
        "sync",
        help="Apply the update: safe changes land, and conflicts wait for your choice.",
        description="Apply the template's and Protostar's updates to the project in the current directory, keeping your edits.",
        parents=[base_parser],
        epilog="Needs the project's recipe in pyproject.toml and protostar.lock, and never reruns init's setup commands. In a terminal, conflicts you can settle open a screen before anything is applied. With conflicts left open, the safe changes still apply and sync exits 1.",
    )
    sync_parser.add_argument(
        "--resolve",
        action="append",
        default=[],
        type=_resolution_request,
        metavar="SELECTOR=CHOICE",
        help=_RESOLVE_HELP,
    )
    sync_parser.add_argument(
        "--to",
        metavar="REF",
        help="Move a repository template to a tag, branch, or full commit SHA, or to the newest release with 'latest'. Records the ref in pyproject.toml.",
    )
    sync_parser.add_argument(
        "--var",
        action="append",
        default=[],
        dest="variables",
        metavar="NAME=VALUE",
        help="Set a template variable, such as one a new template version adds; repeat for each. Values are saved to pyproject.toml, so never pass secrets.",
    )
    sync_parser.add_argument(
        "--option",
        action="append",
        default=[],
        dest="options",
        metavar="NAME=VALUE",
        help="Choose a template option: true or false, or one of its choices; repeat for each. Choices are saved to pyproject.toml.",
    )
    sync_parser.add_argument(
        "--tier",
        choices=[tier.value for tier in Tier],
        help="Follow the template's workbench tier (lean: exploring and analyzing) or production tier (the full quality gate: building something to publish). Only for templates that declare tiers; the choice is saved to pyproject.toml.",
    )
    sync_parser.add_argument(
        "--allow-secret",
        action="append",
        default=[],
        dest="allowed_secrets",
        metavar="NAME",
        help="Keep a variable's value even though it looks like a credential; repeat for each.",
    )
    sync_parser.add_argument(
        "--trust",
        action="store_true",
        help="Run the commands an untrusted template needs without asking, for this run only. They are still listed. Never saved; to trust a template every time, configure it as an alias with trusted = true.",
    )
    sync_modes = sync_parser.add_mutually_exclusive_group()
    sync_modes.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the changes sync would make, without writing a file or running a command.",
    )
    sync_modes.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when the project is behind its recipe or has an open conflict. Writes nothing, and edits you kept don't fail it.",
    )
    sync_parser.set_defaults(func=dispatch_operation, operation=Operation.SYNC)

    guide_parser = subparsers.add_parser(
        "guide",
        help="Show how to run, test, check, and document this project.",
        description="Show the commands for working on the project in the current directory: running it, where its code starts, its tests, checks, and docs.",
        parents=[base_parser],
        epilog="Reads the project recipe and pyproject.toml; never runs project commands or writes files. The commands match the project's AGENTS.md and CONTRIBUTING.md.",
    )
    guide_parser.set_defaults(func=dispatch_operation, operation=Operation.GUIDE)

    eject_parser = subparsers.add_parser(
        "eject",
        help="Stop Protostar managing the project, keeping every file it made.",
        description="Remove protostar.lock and the project recipe from pyproject.toml.",
        parents=[base_parser],
        epilog="Keeps uv.lock and every other project file. Interactive runs ask before applying; automation must pass --yes.",
    )
    eject_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the planned changes and pyproject.toml diff without writing files.",
    )
    eject_parser.add_argument(
        "--yes",
        action="store_true",
        help="Eject without asking. Needed where there is no terminal to ask in.",
    )
    eject_parser.set_defaults(func=dispatch_operation, operation=Operation.EJECT)

    # --- Init Subparser ---
    init_parser = subparsers.add_parser(
        "init",
        help="Set up a new project, or bring Protostar into one you already have.",
        description="Choose a template and tools, preview every file, and review the changes before anything is written.",
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
        help="Show the change review: every file, command, and decision, without writing a file or running a command.",
    )
    base_group = init_parser.add_argument_group("Base Configuration")

    template_action = base_group.add_argument(
        "-t",
        "--template",
        type=str,
        dest="template_name",
        help="A built-in template or one of your aliases; --list-templates shows them.",
        metavar="NAME",
    )
    template_action.completer = completion.template_completer  # type: ignore[attr-defined]

    base_group.add_argument(
        "--list-templates",
        action="store_true",
        help="List the built-in templates and your aliases.",
    )
    base_group.add_argument(
        "--one-shot",
        action="store_true",
        help="Set up the project without recording a recipe or protostar.lock, so sync can't update it later.",
    )
    from_action = base_group.add_argument(
        "--from",
        type=str,
        dest="from_path",
        help="A template file or directory, a repository on GitHub, GitLab, Bitbucket, Codeberg, or Sourcehut, or any HTTPS file or archive.",
        metavar="PATH",
    )
    from_action.completer = argcomplete.completers.FilesCompleter(  # type: ignore[attr-defined]
        allowednames=[".toml"]
    )

    base_group.add_argument(
        "--var",
        action="append",
        default=[],
        dest="variables",
        metavar="NAME=VALUE",
        help="Set a template variable; repeat for each. Values are saved to pyproject.toml, so never pass secrets.",
    )

    base_group.add_argument(
        "--option",
        action="append",
        default=[],
        dest="options",
        metavar="NAME=VALUE",
        help="Choose a template option: true or false, or one of its choices; repeat for each. Choices are saved to pyproject.toml.",
    )

    base_group.add_argument(
        "--tier",
        choices=[tier.value for tier in Tier],
        help="Follow the template's workbench tier (lean: exploring and analyzing) or production tier (the full quality gate: building something to publish). Only for templates that declare tiers; the choice is saved to pyproject.toml.",
    )

    base_group.add_argument(
        "--allow-secret",
        action="append",
        default=[],
        dest="allowed_secrets",
        metavar="NAME",
        help="Keep a variable's value even though it looks like a credential; repeat for each.",
    )

    base_group.add_argument(
        "--trust",
        action="store_true",
        help="Run the commands an untrusted template needs without asking, for this run only. They are still listed. Never saved; to trust a template every time, configure it as an alias with trusted = true.",
    )

    python_version_action = base_group.add_argument(
        "--python-version",
        type=str,
        help="The Python version the project targets, such as 3.13. Overrides your configuration.",
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
        help="Merge into files that already exist without asking: keep your values and add what's missing.",
    )

    tooling_group.add_argument(
        "--force-replace",
        action="store_true",
        help="Replace files that already exist with Protostar's version, without asking.",
    )

    tooling_group.add_argument(
        "--resolve",
        action="append",
        default=[],
        type=_resolution_request,
        metavar="SELECTOR=CHOICE",
        help=_RESOLVE_HELP,
    )

    for mod in TOOLING_MODULES:
        if mod.cli_flags:
            tooling_group.add_argument(
                *mod.cli_flags,
                action=argparse.BooleanOptionalAction,
                help=mod.info.summary,
                dest=mod.__class__.__name__,
            )

    init_parser.set_defaults(func=cli_main.handle_init)

    # --- Export Schema Subparser ---
    export_schema_parser = subparsers.add_parser(
        "export-schema",
        help="Export the JSON Schema for the TOML template format.",
        description="Print the JSON Schema for template files, for editors and validators. With --json, prints plain JSON to save to a file.",
        usage=argparse.SUPPRESS,
        parents=[suppressed_base_parser],
    )
    export_schema_parser.set_defaults(func=schema.handle_export_schema)

    # --- Check Template Subparser ---
    check_template_parser = subparsers.add_parser(
        "check-template",
        help="Check a template for errors and authoring problems before publishing it.",
        description="Checks that protostar init would accept a template, and that it follows the practices built-in templates follow. Runs no commands and writes nothing.",
        usage=argparse.SUPPRESS,
        epilog="Exits 1 when the template has errors, or warnings under --strict. A template that cannot be retrieved exits with its usual error code instead.\n\n[bold]Examples:[/bold]\n  protostar check-template\n  protostar check-template ./templates/backend.toml --strict\n  protostar check-template https://github.com/YourOrg/fastapi-template",
        parents=[suppressed_base_parser],
    )
    check_template_parser.add_argument(
        "source",
        nargs="?",
        default=".",
        metavar="<source>",
        help="A template directory, a template TOML file, or a URL. Defaults to the current directory.",
    )
    check_template_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings as well as errors.",
    )
    check_template_parser.add_argument(
        "--output-format",
        type=OutputFormat,
        choices=list(OutputFormat),
        default=OutputFormat.TEXT,
        metavar="<format>",
        help="text (default) for people, or github for GitHub Actions annotations on the template's files.",
    )
    check_template_parser.set_defaults(
        func=dispatch_operation, operation=Operation.CHECK_TEMPLATE
    )

    # --- Config Subparser ---
    config_parser = subparsers.add_parser(
        "config",
        help="Set your identity, editor, Python version, and tool defaults.",
        description="Edit your identity, editor, Python version, and tool defaults in a form.",
        usage=argparse.SUPPRESS,
        parents=[suppressed_base_parser],
    )
    config_parser.add_argument(
        "--edit",
        action="store_true",
        help="Open the file in $EDITOR instead of the form.",
    )
    config_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="With --reset, reset without asking.",
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
        help="Print the tab-completion script for your shell.",
        description="Print the tab-completion script for Bash, Zsh, Fish, or PowerShell.",
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
        help=f"The shell to print the script for: {', '.join(s.value for s in Shell)}. Without it, shows how to set up completion.",
    )
    completion_parser.set_defaults(func=completion.handle_completion)

    # --- Help Subparser ---
    help_parser = subparsers.add_parser(
        "help",
        help="Show this help message or a subcommand's manual.",
        description="Show the commands, or one command's options.",
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
        help="The command to show options for.",
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

    Must be called after ``build_parser()`` but before ``parse_args()``.

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


def maybe_run_interactive_init(parser: argparse.ArgumentParser) -> None:
    """Run interactive initialization when no CLI options select a headless path."""
    if ui.is_json_mode:
        return

    cmd = None
    if len(sys.argv) == 1:
        cmd = "init"
    elif len(sys.argv) == 2:
        cmd = sys.argv[1]

    # Open interactive initialization for a bare command.
    if cmd == "init":
        if not is_interactive():
            return
        # The editor previews hook pins; its request overlaps everything before
        # the first frame.
        prefetch_hook_registry()
        from protostar.analysis import analyze_project
        from protostar.cli.tui.launch import edit_recipe
        from protostar.init_draft import DraftTemplate, InitDraft, resolve_init
        from protostar.recipe import read_recipe
        from protostar.sync_state import read_workspace_state

        # Nothing can be applied without these, so fail before the editor opens.
        check_required_executables()
        user_config = UserConfig.load()
        catalog = discover_templates(user_config)
        existing_recipe = read_recipe(Path("pyproject.toml"))
        # Every preview would fail on unreadable state, so fail before the editor.
        read_workspace_state(Path.cwd())
        template = None
        if existing_recipe and existing_recipe.source:
            source = existing_recipe.source.acquire(Path.cwd())
            external = source.reference.origin is not TemplateOrigin.BUILT_IN
            template = DraftTemplate(
                source, is_external=external, is_trusted=not external
            )
        # The recipe editor benchmark measures time to its first frame.
        benchmark = "PROTOSTAR_BENCHMARK_RECIPE_EDITOR" in os.environ
        analysis = None if existing_recipe else analyze_project(Path.cwd())
        decision = edit_recipe(
            InitDraft(
                template=template, existing_recipe=existing_recipe, analysis=analysis
            ),
            catalog,
            user_config,
            exit_after_first_frame=benchmark,
        )
        if benchmark:
            sys.exit(0)
        if decision is None:
            raise ExecutionAbortedError("Recipe editing cancelled by user.")
        modules, request = resolve_init(decision.draft, user_config)
        ui.print_recipe_summary(request)
        ui.print_review_summary(decision)
        # Through the module, so the lazy __getattr__ imports Orchestrator on
        # first use and a test's patch of it is the one that runs.
        orchestrator_cls: type[Orchestrator] = sys.modules[__name__].Orchestrator
        engine = orchestrator_cls(modules, user_config, request=request)
        ui._run_engine(engine, request, decision)
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


def dispatch_operation(args: argparse.Namespace) -> None:
    """Load only the selected command's implementation after parsing finishes."""
    operation: Operation = args.operation
    match operation:
        case Operation.REVIEW:
            from protostar.cli.reviews import handle_review

            handle_review(args)
        case Operation.SYNC:
            from protostar.cli.reviews import handle_sync

            handle_sync(args)
        case Operation.GUIDE:
            from protostar.cli.guide import handle_guide

            handle_guide(args)
        case Operation.EJECT:
            from protostar.cli.eject import handle_eject

            handle_eject(args)
        case Operation.CHECK_TEMPLATE:
            from protostar.cli.check_template import handle_check_template

            handle_check_template(args)
