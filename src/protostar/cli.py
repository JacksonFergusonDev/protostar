"""Command-line interface and entry point for Protostar."""

import argparse
import importlib.resources
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
from rich.style import Style
from rich.table import Table
from rich_argparse import RawTextRichHelpFormatter

from protostar import __version__

from .config import CONFIG_FILE, DEFAULT_CONFIG_CONTENT, ProtostarConfig
from .errors import (
    CommandExecutionError,
    ConfigurationError,
    ExecutionAbortedError,
    FileSystemError,
    MissingDependencyError,
    ProtostarError,
)
from .fs import atomic_write_text
from .metadata import resolve_auto_metadata
from .modules import (
    TOOLING_MODULES,
    BootstrapModule,
    PythonCore,
    SystemWorkspaceModule,
)
from .orchestrator import Orchestrator
from .presets import (
    PRESETS,
    PresetModule,
)
from .wizard import (
    resolve_missing_variables,
    run_init_wizard,
)

console = Console()


def handle_init(args: argparse.Namespace) -> None:
    """Handles the 'init' subcommand to scaffold environments.

    Dynamically constructs the environment manifest by evaluating flags mapped
    to the respective OS, IDE, and preset registries.
    """
    override_target = getattr(args, "from_path", None)
    template_name = getattr(args, "template_name", None)
    template_context = getattr(args, "template_context", {})

    if override_target and template_name:
        raise ConfigurationError(
            "Cannot use both '--template' and '--from' simultaneously."
        )

    if template_name:
        target = importlib.resources.files("protostar.templates").joinpath(
            f"{template_name}.toml"
        )
        if not target.is_file():
            raise ConfigurationError(f"Built-in template '{template_name}' not found.")
        # We can cast it to str because we know Protostar isn't typically zip-safe,
        # but if we wanted to be perfectly robust we could use as_file().
        override_target = str(target)

    config = ProtostarConfig.load(
        override_target=override_target,
        template_context=template_context,
        variable_resolver=resolve_missing_variables,
    )

    modules: list[BootstrapModule] = []
    presets: list[PresetModule] = []

    # 1. Universal System Layer
    modules.append(SystemWorkspaceModule())

    # 2. Mandatory Python Core
    python_core = PythonCore(
        python_version=getattr(args, "python_version", None),
    )
    modules.append(python_core)

    # 3. Preset Layers
    for preset in PRESETS:
        is_active = preset.config_key in config.active_presets

        if preset.cli_flags:
            cli_override = getattr(args, preset.__class__.__name__, None)
            if cli_override is not None:
                is_active = cli_override

        if is_active:
            presets.append(preset)

    # 4. Tooling Layers
    for mod in TOOLING_MODULES:
        is_active = False

        # Evaluate global configuration defaults
        if getattr(config, mod.config_key, False):
            is_active = True

        # Explicit CLI flags override local configuration omissions and defaults.
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

    # 5. Undocumented Crash Test Injection
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
    for preset in presets:
        required_keys.update(preset.required_metadata)

    resolved_metadata = resolve_auto_metadata(required_keys)

    # Execute
    engine = Orchestrator(
        modules,
        config,
        presets,
        docker=args.docker,
        force_merge=getattr(args, "force_merge", False),
        force_replace=getattr(args, "force_replace", False),
        metadata=resolved_metadata,
    )
    engine.run()


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
    base_parser = argparse.ArgumentParser(add_help=False)
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

    parser = argparse.ArgumentParser(
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
        epilog="[bold]Example:[/bold]\n  protostar init --astro --mypy",
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
        dest="template_name",
        help="Name of a built-in template to apply (e.g., 'astro', 'cli').",
        metavar="NAME",
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
        help="Specify the Python version to scaffold (e.g., 3.12). Overrides global configuration.",
        dest="python_version",
        metavar="VERSION",
    )

    # Dynamically mount Preset flags
    preset_group = init_parser.add_argument_group("Python Dependency Presets")
    for preset in PRESETS:
        if preset.cli_flags:
            preset_group.add_argument(
                *preset.cli_flags,
                action=argparse.BooleanOptionalAction,
                help=preset.cli_help,
                dest=preset.__class__.__name__,
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

            config = ProtostarConfig.load()
            modules = selections["modules"]
            presets = selections["presets"]

            # Inject mandatory universal layers implicitly
            modules.insert(0, SystemWorkspaceModule())
            modules.insert(1, PythonCore())

            engine = Orchestrator(
                modules,
                config,
                presets,
                docker=selections["docker"],
                force_merge=False,
                force_replace=False,
                metadata=selections.get("project_metadata"),
            )
            engine.run()
            sys.exit(0)


def configure_logging() -> None:
    """Injects Rich tracebacks and debug handlers into the global logger."""
    logger = logging.getLogger("protostar")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(RichHandler(console=console, markup=True, rich_tracebacks=True))


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


def main() -> None:
    """Main execution pipeline for the Protostar CLI."""
    parser = build_parser()

    try:
        intercept_interactive_wizards(parser)
        args, unknown = parser.parse_known_args()

        if unknown and (
            getattr(args, "command", None) != "init"
            or not getattr(args, "from_path", None)
        ):
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")

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
        if getattr(e, "hint", None):
            body += f"\n\n[dim]Hint: {e.hint}[/dim]"

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
        if isinstance(e, ConfigurationError):
            sys.exit(os.EX_CONFIG)  # 78: Malformed configuration tables
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
