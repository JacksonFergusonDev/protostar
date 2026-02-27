import argparse
import sys
from collections.abc import Iterable

from rich.console import Console

from protostar.generators import GENERATOR_REGISTRY

from .config import ProtostarConfig
from .modules import (
    BootstrapModule,
    CppModule,
    JetBrainsModule,
    LatexModule,
    LinuxModule,
    MacOSModule,
    NodeModule,
    PythonModule,
    RustModule,
    VSCodeModule,
)
from .orchestrator import Orchestrator
from .presets import (
    AstroPreset,
    DspPreset,
    EmbeddedPreset,
    PresetModule,
    ScientificPreset,
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

    Dynamically constructs the environment manifest by mapping user flags
    to the respective language, OS, IDE, and preset modules.
    """
    config = ProtostarConfig.load()
    modules: list[BootstrapModule] = []
    presets: list[PresetModule] = []

    # 1. Base OS Layer
    modules.append(get_os_module())

    # 2. Language Layers
    has_language = False
    if args.python:
        modules.append(PythonModule())
        has_language = True

    if args.rust:
        modules.append(RustModule())
        has_language = True

    if args.node:
        modules.append(NodeModule(package_manager=config.node_package_manager))
        has_language = True

    if args.cpp:
        modules.append(CppModule())
        has_language = True

    if args.latex:
        modules.append(LatexModule())
        has_language = True

    if not has_language:
        console.print(
            "[yellow]Please specify at least one language flag (e.g., --python, --rust).[/yellow]"
        )
        console.print("Run [bold cyan]protostar init --help[/bold cyan] for options.")
        sys.exit(1)

    # 3. Preset Layers
    if args.scientific:
        presets.append(ScientificPreset())

    if args.astro:
        presets.append(AstroPreset())

    if args.dsp:
        presets.append(DspPreset())

    if args.embedded:
        presets.append(EmbeddedPreset())

    # 4. IDE Layer
    if ide_mod := get_ide_module(config.ide):
        modules.append(ide_mod)

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


class ProtoHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom help formatter for Protostar CLI.

    Inherits from RawDescriptionHelpFormatter to respect explicit line breaks
    in docstrings/descriptions while overriding default verbose prefixes.
    """

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
        description="High-velocity environment scaffolding.",
        formatter_class=ProtoHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="Subcommands",
        metavar="<command>",
    )

    # --- Init Subparser ---
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new environment and aggregate manifest configurations.",
        description="Scaffolds base configurations, dependencies, and environment files.",
        formatter_class=ProtoHelpFormatter,
    )

    # Conceptual grouping for language footprints
    lang_group = init_parser.add_argument_group("Language Footprints")
    lang_group.add_argument(
        "-p", "--python", action="store_true", help="Scaffold a Python (uv) environment"
    )
    lang_group.add_argument(
        "-r", "--rust", action="store_true", help="Scaffold a Rust (cargo) environment"
    )
    lang_group.add_argument(
        "-n", "--node", action="store_true", help="Scaffold a Node.js environment"
    )
    lang_group.add_argument(
        "-c",
        "--cpp",
        action="store_true",
        help="Scaffold a C/C++ environment footprint",
    )
    lang_group.add_argument(
        "-l",
        "--latex",
        action="store_true",
        help="Scaffold a LaTeX environment footprint",
    )

    # Conceptual grouping for dependency injections
    preset_group = init_parser.add_argument_group("Dependency Presets")
    preset_group.add_argument(
        "-s",
        "--scientific",
        action="store_true",
        help="Inject scientific computing dependencies",
    )
    preset_group.add_argument(
        "-a",
        "--astro",
        action="store_true",
        help="Inject astrophysics and observational data dependencies",
    )
    preset_group.add_argument(
        "-d",
        "--dsp",
        action="store_true",
        help="Inject digital signal processing and audio analysis tools",
    )
    preset_group.add_argument(
        "-e",
        "--embedded",
        action="store_true",
        help="Inject host-side embedded hardware interface tools",
    )

    # Conceptual grouping for context artifacts
    context_group = init_parser.add_argument_group("Context Scaffolding")
    context_group.add_argument(
        "--docker",
        action="store_true",
        help="Generate a .dockerignore based on the environment footprint",
    )

    init_parser.set_defaults(func=handle_init)

    # --- Generate Subparser ---
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate boilerplate files and project scaffolding.",
        description="Generates boilerplate code or files based on the configured environment.",
        formatter_class=ProtoHelpFormatter,
    )

    # Expand the target choices dynamically using the registry keys
    generate_parser.add_argument(
        "target",
        choices=list(GENERATOR_REGISTRY.keys()),
        help="The boilerplate target to evaluate and generate.",
    )
    generate_parser.add_argument(
        "name",
        nargs="?",
        help="The primary identifier or filename for the output.",
    )

    generate_parser.set_defaults(func=handle_generate)

    # --- Config Subparser ---
    config_parser = subparsers.add_parser(
        "config",
        help="Manage global Protostar configuration.",
        description="Opens the global configuration file in your system's default $EDITOR.",
        formatter_class=ProtoHelpFormatter,
    )
    config_parser.set_defaults(func=handle_config)

    # Dynamic dispatch based on the invoked subparser
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
