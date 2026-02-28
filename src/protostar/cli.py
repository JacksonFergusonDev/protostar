import argparse
import sys
from collections.abc import Iterable

from rich import box
from rich.console import Console
from rich.table import Table

from protostar.generators import GENERATOR_REGISTRY

from .config import ProtostarConfig
from .modules import (
    LANG_MODULES,
    TOOLING_MODULES,
    BootstrapModule,
    DirenvModule,
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

console = Console()


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
    for mod in TOOLING_MODULES:
        if isinstance(mod, DirenvModule) and getattr(config, "direnv", False):
            modules.append(mod)
            continue

        if mod.cli_flags and getattr(args, mod.__class__.__name__, False):
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


class ProtoHelpFormatter(argparse.RawTextHelpFormatter):
    """Custom help formatter for Protostar CLI.

    Inherits from RawTextHelpFormatter to respect explicit line breaks
    in docstrings/descriptions and argument help strings.
    """

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

                parts.append(f"\n  {group_name}:\n")
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
    parser = argparse.ArgumentParser(
        description="A modular CLI tool for quickly scaffolding software environments. ",
        epilog="Run 'proto help <command>' or 'proto <command> --help' for detailed options.",
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
                action="store_true",
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

    # Enable show_lines for horizontal separators between rows
    target_table = Table(
        show_header=False,
        box=box.ROUNDED,
        show_lines=True,
        padding=(0, 1),
        pad_edge=False,
    )
    target_table.add_column("Target", style="cyan", no_wrap=True)
    target_table.add_column("Description")

    # Dynamically populate from the registry
    for key, generator in GENERATOR_REGISTRY.items():
        # Grabs the first line of the class docstring
        desc = generator.__doc__.strip().split("\n")[0] if generator.__doc__ else ""
        target_table.add_row(key, desc)

    # Capture the output buffer
    with console.capture() as capture:
        # Buffer increased slightly to handle the extra border characters
        console.print(target_table, width=console.width - 32)

    target_help = "The boilerplate target to evaluate and generate:\n" + capture.get()

    target_group.add_argument(
        "target",
        choices=list(GENERATOR_REGISTRY.keys()),
        metavar="TARGET",
        help=target_help,
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

    # Dynamic dispatch based on the invoked subparser
    args = parser.parse_args()

    # Graceful fallback if the user executes `proto` with no arguments
    if not getattr(args, "command", None):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
