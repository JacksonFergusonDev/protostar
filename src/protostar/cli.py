import argparse
import importlib.metadata
import logging
import os
import shlex
import shutil
import subprocess
import sys
import types
from collections.abc import Iterable
from typing import Any, ClassVar, cast

import argcomplete
from rich import box
from rich.console import Console, Group
from rich.logging import RichHandler
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich_argparse import RawTextRichHelpFormatter

from .config import CONFIG_FILE, DEFAULT_CONFIG_CONTENT, ProtostarConfig
from .generators import GENERATOR_REGISTRY
from .modules import (
    LANG_MODULES,
    TOOLING_MODULES,
    BootstrapModule,
    JetBrainsModule,
    LinuxModule,
    MacOSModule,
    PythonModule,
    VSCodeModule,
)
from .orchestrator import Orchestrator
from .presets import (
    PRESETS,
    PresetModule,
)
from .wizard import run_discovery_wizard, run_generate_wizard, run_init_wizard

console = Console()


class LazyTargetHelp(str):
    """A str subclass that embeds a Rich-rendered target table as its string value.

    Inheriting from str ensures full compatibility with argparse and rich-argparse
    regardless of whether they use duck-typing or isinstance checks internally.
    The get_renderable() method provides a native Rich renderable for the custom
    print_table_help formatter, preserving styled terminal output.
    """

    def __new__(cls) -> "LazyTargetHelp":
        """Constructs the instance with the rendered table as its string value.

        Evaluates the terminal width at construction time and captures a
        ANSI-stripped Rich table render as the underlying str value. ANSI codes
        are stripped via color_system=None to prevent argparse from counting
        invisible styling bytes during column alignment.

        Returns:
            A LazyTargetHelp instance whose string value is the rendered table.
        """
        return super().__new__(cls, cls._build_string())

    @staticmethod
    def _build_string() -> str:
        """Renders the generator registry as a plain-text table string.

        Uses a width-constrained, color-stripped console to produce a string
        safe for argparse's internal help formatting logic.

        Returns:
            A formatted string containing the target table and its header.
        """
        # Subtract 32 columns to account for argparse's indentation and
        # decoration overhead, preventing table overflow in the help output.
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

    def get_renderable(self) -> Any:
        """Provides a native Rich renderable for the custom print_table_help formatter.

        Constructs a styled Rich table with column colouring and a descriptive
        header, used exclusively by print_table_help() when rendering the
        help output directly to the terminal via a Rich Console.

        Returns:
            A Rich Group containing a header Text and a styled Table.
        """
        target_table = Table(
            show_header=False,
            box=box.ROUNDED,
            show_lines=False,
            padding=(0, 1),
            pad_edge=False,
        )
        target_table.add_column("Target", style="cyan", no_wrap=True)
        target_table.add_column("Description")

        for key, generator in GENERATOR_REGISTRY.items():
            desc = generator.__doc__.strip().split("\n")[0] if generator.__doc__ else ""
            target_table.add_row(key, desc)

        return Group(
            Text("The boilerplate target to evaluate and generate:\n"),
            target_table,
        )


class GenerateEpilogTable:
    """Delays and structures the generate command epilog as a native Rich table."""

    def __str__(self) -> str:
        """Fallback string representation."""
        return "How NAME is evaluated:"

    def __mod__(self, params: dict[str, Any]) -> str:
        """Intercepts argparse's string interpolation."""
        return self.__str__() % params

    def __getattr__(self, name: str) -> Any:
        """Delegates missing string methods to the evaluated string."""
        return getattr(str(self), name)

    def get_renderable(self) -> Any:
        """Provides a native Rich table for the custom help renderer."""
        from rich.table import Table

        table = Table(
            title="How NAME is evaluated:",
            box=box.ROUNDED,
            show_lines=False,
            show_header=False,
            padding=(0, 1),
            title_justify="left",
            title_style="bold blue",
        )
        table.add_column("Target", style="cyan", no_wrap=True)
        table.add_column("Description")
        table.add_column("Example", style="dim")

        table.add_row(
            "tex", "The output filename", "(e.g., proto generate tex report.tex)"
        )
        table.add_row(
            "cpp-class",
            "The class identifier",
            "(e.g., proto generate cpp-class Engine)",
        )
        table.add_row(
            "pio", "The board target ID", "(e.g., proto generate pio esp32dev)"
        )
        table.add_row("cmake", "Ignored automatically", "(e.g., proto generate cmake)")
        table.add_row(
            "circuitpython",
            "Ignored automatically",
            "(e.g., proto generate circuitpython)",
        )

        return table


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
        if getattr(config, mod.config_key, False) and (
            not mod.requires_python or has_python
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
    engine = Orchestrator(
        modules,
        config,
        presets,
        docker=args.docker,
        force=getattr(args, "force", False),
    )
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

    for group in self._action_groups:
        # Filter out explicitly suppressed arguments and the default HelpAction
        actions = [
            a
            for a in group._group_actions
            if a.help != argparse.SUPPRESS and not isinstance(a, argparse._HelpAction)
        ]

        if not actions:
            continue

        table = Table(
            show_header=False,
            title=group.title,
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
        epilog="[bold]Example:[/bold]\n  protostar init --python --astro --mypy",
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
    preset_group = init_parser.add_argument_group("Python Dependency Presets")
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

    # The force flag for collision bypass
    tooling_group.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Bypass interactive prompts and force a merge on file collisions.",
    )

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
    init_parser.print_help = types.MethodType(print_table_help, init_parser)  # type: ignore[method-assign]

    # --- Generate Subparser ---
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate boilerplate files and project scaffolding.",
        description="Generates boilerplate code or files based on the configured environment.",
        formatter_class=ProtoHelpFormatter,
        usage=argparse.SUPPRESS,
        epilog=cast(str, GenerateEpilogTable()),
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
    generate_parser.print_help = types.MethodType(print_table_help, generate_parser)  # type: ignore[method-assign]

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

    return parser


def intercept_interactive_wizards(parser: argparse.ArgumentParser) -> None:
    """Evaluates sys.argv to route execution to TUI wizards if parameters are omitted."""
    if len(sys.argv) == 1:
        action = run_discovery_wizard()
        if not action:
            parser.print_help()
            sys.exit(1)
        sys.argv.append(action)

    # Intercept parameter-less subcommands for interactive wizards
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

            engine = Orchestrator(
                modules, config, presets, docker=selections["docker"], force=False
            )
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

    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(DEFAULT_CONFIG_CONTENT)
        console.print(
            f"[bold green]Initialized default configuration at {CONFIG_FILE}[/bold green]"
        )

    editor_env = os.environ.get("EDITOR", "nano")
    editor_cmd = shlex.split(editor_env)

    if not editor_cmd:
        console.print(
            "[bold red]Configuration Error:[/bold red] The $EDITOR environment variable is empty."
        )
        sys.exit(1)

    if not shutil.which(editor_cmd[0]):
        console.print(
            f"[bold red]Configuration Error:[/bold red] Could not resolve editor executable '{editor_cmd[0]}'.\n"
            "Ensure your $EDITOR environment variable is set to a valid binary in your PATH."
        )
        sys.exit(1)

    editor_cmd.append(str(CONFIG_FILE))

    try:
        subprocess.run(editor_cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(
            f"[bold red]Editor Error:[/bold red] Editor '{editor_env}' exited with non-zero status: {e}"
        )
        sys.exit(1)


def main() -> None:
    """Main execution pipeline for the Protostar CLI."""
    parser = build_parser()

    try:
        intercept_interactive_wizards(parser)

        args = parser.parse_args()

        if getattr(args, "verbose", False):
            configure_logging()

        if not getattr(args, "command", None):
            parser.print_help()
            sys.exit(1)

        args.func(args)

    except ValueError as e:
        # Gracefully handle the TOML syntax errors bubbled up from ProtostarConfig
        console.print(f"\n[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
