import argparse
import importlib.metadata
import logging
import sys
from collections.abc import Iterable
from typing import Any, cast

import argcomplete
from rich import box
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich_argparse import RawTextRichHelpFormatter

from .config import ProtostarConfig
from .generators import GENERATOR_REGISTRY
from .modules import (
    LANG_MODULES,
    TOOLING_MODULES,
    BootstrapModule,
    DirenvModule,
    JetBrainsModule,
    LinuxModule,
    MacOSModule,
    MarkdownLintModule,
    MypyModule,
    PreCommitModule,
    PytestModule,
    PythonModule,
    RuffModule,
    VSCodeModule,
)
from .orchestrator import Orchestrator
from .presets import (
    PRESETS,
    PresetModule,
)
from .wizard import run_discovery_wizard, run_generate_wizard, run_init_wizard

console = Console()


class LazyTargetHelp:
    """Delays boilerplate target table generation until help is explicitly rendered.

    This prevents unnecessary terminal rendering overhead during standard execution
    and ensures the table dimensions evaluate the terminal width at render-time,
    preventing overflow on resized terminal windows.
    """

    def __str__(self) -> str:
        """Evaluates the terminal context and renders the table string dynamically.

        Returns:
            A formatted string containing the generated table and header.
        """
        # color_system=None strips ANSI codes. This prevents argparse
        # from counting invisible styling bytes as characters during column alignment.
        capture_console = Console(
            width=Console().width - 32,
            color_system=None,
        )

        target_table = Table(
            show_header=False,
            box=box.ROUNDED,
            show_lines=True,
            padding=(0, 1),
            pad_edge=False,
        )
        target_table.add_column("Target", no_wrap=True)
        target_table.add_column("Description")

        for key, generator in GENERATOR_REGISTRY.items():
            desc = generator.__doc__.strip().split("\n")[0] if generator.__doc__ else ""
            target_table.add_row(key, desc)

        with capture_console.capture() as capture:
            capture_console.print(target_table)

        return f"The boilerplate target to evaluate and generate:\n{capture.get()}"

    def __mod__(self, params: dict[str, Any]) -> str:
        """Intercepts argparse's string interpolation to trigger deferred evaluation.

        Args:
            params: The dictionary of formatting parameters provided by argparse.

        Returns:
            The fully evaluated and formatted help string.
        """
        return self.__str__() % params

    def __getattr__(self, name: str) -> Any:
        """Delegates missing string methods (like .strip()) to the evaluated string.

        This prevents crashes when external formatters attempt to manipulate
        the proxy object as if it were a native string.
        """
        return getattr(str(self), name)


def get_os_module() -> BootstrapModule:
    """Detects the host OS and returns the corresponding bootstrap layer."""
    if sys.platform == "darwin":
        return MacOSModule()
    return LinuxModule()


def get_ide_module(ide_preference: str) -> BootstrapModule | None:
    """Returns the IDE module based on the user's global configuration.

    Dynamically resolves the target module by evaluating the aliases declared
    on each IDE class.
    """
    ide = ide_preference.lower()

    # Iterate over supported IDE modules to find an alias match
    for ide_class in (VSCodeModule, JetBrainsModule):
        instance = ide_class()
        if ide in instance.aliases:
            return instance

    return None


def handle_init(args: argparse.Namespace) -> None:
    """Handles the 'init' subcommand to scaffold environments.

    Dynamically constructs the environment manifest by evaluating flags mapped
    to the respective language, OS, IDE, and preset registries.
    """
    config = ProtostarConfig.load()
    modules: list[BootstrapModule] = []
    presets: list[PresetModule] = []

    # 1. Base OS Layer
    modules.append(get_os_module())

    # 2. Language Layers
    has_language = False
    for mod in LANG_MODULES:
        if mod.cli_flags and getattr(args, mod.__class__.__name__, False):
            if isinstance(mod, PythonModule) and getattr(args, "python_version", None):
                mod.python_version = args.python_version

            modules.append(mod)
            has_language = True

    if not has_language:
        console.print(
            "[yellow]Please specify at least one language flag (e.g., --python, --rust).[/yellow]"
        )
        console.print("Run [bold cyan]protostar init --help[/bold cyan] for options.")
        sys.exit(1)

    # 3. Preset Layers
    for preset in PRESETS:
        if preset.cli_flags and getattr(args, preset.__class__.__name__, False):
            presets.append(preset)

    # 4. IDE Layer
    if ide_mod := get_ide_module(config.ide):
        modules.append(ide_mod)

    # 5. Tooling Layers
    has_python = any(isinstance(m, PythonModule) for m in modules)

    for mod in TOOLING_MODULES:
        is_active = False

        # Evaluate global configuration defaults, ensuring language-specific
        # tools only activate if their parent language is present in the stack.
        if (
            isinstance(mod, DirenvModule)
            and getattr(config, "direnv", False)
            or isinstance(mod, PreCommitModule)
            and getattr(config, "pre_commit", False)
            or isinstance(mod, MarkdownLintModule)
            and getattr(config, "markdownlint", False)
            or has_python
            and (
                isinstance(mod, RuffModule)
                and getattr(config, "ruff", False)
                or isinstance(mod, MypyModule)
                and getattr(config, "mypy", False)
                or isinstance(mod, PytestModule)
                and getattr(config, "pytest", False)
            )
        ):
            is_active = True

        # Explicit CLI flags override local configuration omissions and defaults.
        # argparse.BooleanOptionalAction evaluates to True, False, or None.
        if mod.cli_flags:
            cli_override = getattr(args, mod.__class__.__name__, None)
            if cli_override is not None:
                is_active = cli_override

        if is_active:
            modules.append(mod)

    # Execute
    engine = Orchestrator(modules, presets, docker=args.docker)
    engine.run()


def handle_generate(args: argparse.Namespace) -> None:
    """Handles the 'generate' subcommand for post-setup file scaffolding.

    Dynamically routes the execution to the corresponding TargetGenerator.
    """
    config = ProtostarConfig.load()

    generator = GENERATOR_REGISTRY.get(args.target)
    if not generator:
        console.print(
            f"[bold red]Generation Aborted:[/bold red] Unknown target '{args.target}'."
        )
        return

    try:
        out_paths = generator.execute(args.name, config)
        for path in out_paths:
            console.print(f"[bold green]Generated:[/bold green] {path}")
    except (FileExistsError, ValueError) as e:
        console.print(f"[bold red]Generation Aborted:[/bold red] {e}")


def handle_config(args: argparse.Namespace) -> None:
    """Handles the 'config' subcommand to manage global CLI settings."""
    ProtostarConfig.open_in_editor()


class ProtoHelpFormatter(RawTextRichHelpFormatter):
    """Custom help formatter for Protostar CLI using rich-argparse.

    Inherits from RawTextRichHelpFormatter to leverage native rich styling
    while respecting explicit line breaks in docstrings and argument parameters.
    """

    # Establish global syntactic styling identifiers
    styles = {
        "argparse.args": "cyan",
        "argparse.groups": "bold blue",
        "argparse.help": "default",
        "argparse.metavar": "dark_orange",
    }

    def _format_action(self, action: argparse.Action) -> str:
        """Overrides the default action formatting to group subcommands into logical clusters."""
        if isinstance(action, argparse._SubParsersAction):
            parts = []

            # Define logical command clusters
            groups = {
                "Environment Lifecycle": ["init"],
                "Boilerplate Generation": ["generate"],
                "System Management": ["config"],
                "General": ["help"],
            }

            subactions = list(self._iter_indented_subactions(action))

            for group_name, commands in groups.items():
                group_actions = [a for a in subactions if a.dest in commands]
                if not group_actions:
                    continue

                parts.append(
                    f"\n  [bold]{group_name}[/bold]:\n"
                )  # Inject explicit rich markup
                self._indent()
                for subaction in group_actions:
                    parts.append(self._format_action(subaction))
                self._dedent()

            return self._join_parts(parts)

        return super()._format_action(action)

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


def main() -> None:
    """Main entry point for the Protostar CLI."""
    # Dynamically resolve the package version footprint
    try:
        __version__ = importlib.metadata.version("protostar")
    except importlib.metadata.PackageNotFoundError:
        __version__ = "unknown"

    parser = argparse.ArgumentParser(
        description="A modular CLI tool for quickly scaffolding software environments. ",
        epilog="Run 'protostar help <command>' or 'protostar <command> --help' for detailed options.",
        formatter_class=ProtoHelpFormatter,
        add_help=False,
        usage=argparse.SUPPRESS,
    )

    # Manually re-add the help flags but suppress them from the visual output
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the application's version and exit.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug output and rich tracebacks.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="Subcommands",
        metavar="<command>",
    )

    # --- Init Subparser ---
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new environment and aggregate manifest configurations.",
        description="Scaffolds base configurations, dependencies, and environment files.",
        formatter_class=ProtoHelpFormatter,
        usage=argparse.SUPPRESS,
    )

    # Dynamically mount Language flags
    lang_group = init_parser.add_argument_group("Language Footprints")
    for mod in LANG_MODULES:
        if mod.cli_flags:
            lang_group.add_argument(
                *mod.cli_flags,
                action="store_true",
                help=mod.cli_help,
                dest=mod.__class__.__name__,
            )

    # Add explicit python version override flag
    lang_group.add_argument(
        "--python-version",
        type=str,
        help="Specify the Python version to scaffold (e.g., 3.12). Overrides global configuration.",
        dest="python_version",
        metavar="VERSION",
    )

    # Dynamically mount Preset flags
    preset_group = init_parser.add_argument_group("Dependency Presets")
    for preset in PRESETS:
        if preset.cli_flags:
            preset_group.add_argument(
                *preset.cli_flags,
                action="store_true",
                help=preset.cli_help,
                dest=preset.__class__.__name__,
            )

    # Tooling Context
    tooling_group = init_parser.add_argument_group("Tooling & Context")
    tooling_group.add_argument(
        "--docker",
        action="store_true",
        help="Generate a .dockerignore based on the environment footprint",
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

    # --- Generate Subparser ---
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate boilerplate files and project scaffolding.",
        description="Generates boilerplate code or files based on the configured environment.",
        formatter_class=ProtoHelpFormatter,
        usage=argparse.SUPPRESS,
    )

    target_group = generate_parser.add_argument_group("Generation Target")

    # The string evaluation is now deferred to the LazyTargetHelp object
    target_group.add_argument(
        "target",
        choices=list(GENERATOR_REGISTRY.keys()),
        metavar="TARGET",
        help=cast(str, LazyTargetHelp()),
    )

    # Output Parameters remains standard
    param_group = generate_parser.add_argument_group("Output Parameters")
    param_group.add_argument(
        "name",
        nargs="?",
        metavar="NAME",
        help="The primary identifier or filename for the output.",
    )

    generate_parser.set_defaults(func=handle_generate)

    # --- Config Subparser ---
    config_parser = subparsers.add_parser(
        "config",
        help="Manage global Protostar configuration.",
        description="Opens the global configuration file in your system's default $EDITOR.",
        formatter_class=ProtoHelpFormatter,
        usage=argparse.SUPPRESS,
    )
    config_parser.set_defaults(func=handle_config)

    # --- Help Subparser ---
    help_parser = subparsers.add_parser(
        "help",
        help="Show this help message or a subcommand's manual.",
        description="Displays the CLI help manual.",
        formatter_class=ProtoHelpFormatter,
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

    # ==========================================
    # Interactive Wizard Interception Routing
    # ==========================================

    # 1. Intercept zero-argument invocation (Discovery Multiplexer)
    if len(sys.argv) == 1:
        action = run_discovery_wizard()
        if not action:
            parser.print_help()
            sys.exit(1)
        # Append the selected action to sys.argv to trick argparse into routing
        # to the correct subparser for further processing or wizard interception.
        sys.argv.append(action)

    # 2. Intercept parameter-less subcommands for interactive wizards
    if len(sys.argv) == 2:
        cmd = sys.argv[1]

        if cmd == "init":
            selections = run_init_wizard()
            if not selections:
                # Force argparse to dump the subcommand help if wizard is cancelled
                parser.parse_args(["init", "--help"])
                sys.exit(1)

            config = ProtostarConfig.load()
            modules = selections["modules"]
            presets = selections["presets"]

            # Inject mandatory OS and configured IDE layers implicitly
            modules.insert(0, get_os_module())
            if ide_mod := get_ide_module(config.ide):
                modules.append(ide_mod)

            engine = Orchestrator(modules, presets, docker=selections["docker"])
            engine.run()
            sys.exit(0)

        elif cmd == "generate":
            selections = run_generate_wizard()
            if not selections:
                parser.parse_args(["generate", "--help"])
                sys.exit(1)

            config = ProtostarConfig.load()
            target_generator = GENERATOR_REGISTRY.get(str(selections["target"]))

            if not target_generator:
                console.print(
                    f"[bold red]Generation Aborted:[/bold red] Unknown target '{selections['target']}'."
                )
                sys.exit(1)

            try:
                out_paths = target_generator.execute(selections["name"], config)
                for path in out_paths:
                    console.print(f"[bold green]Generated:[/bold green] {path}")
            except (FileExistsError, ValueError) as e:
                console.print(f"[bold red]Generation Aborted:[/bold red] {e}")
            sys.exit(0)

    # ==========================================
    # Standard CLI Execution
    # ==========================================

    # Dynamic dispatch based on the invoked subparser
    args = parser.parse_args()

    if getattr(args, "verbose", False):
        logger = logging.getLogger("protostar")
        logger.setLevel(logging.DEBUG)

        # Clear existing handlers to prevent duplicate stream outputs
        logger.handlers.clear()
        logger.addHandler(
            RichHandler(console=console, markup=True, rich_tracebacks=True)
        )

    # Graceful fallback if the user executes `proto` with no arguments
    if not getattr(args, "command", None):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
