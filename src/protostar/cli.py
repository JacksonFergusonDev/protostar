import argparse
import sys
from collections.abc import Iterable
from typing import TYPE_CHECKING

from rich.console import Console

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
from .presets.scientific import SCIENTIFIC_PACKAGES

if TYPE_CHECKING:
    from .manifest import EnvironmentManifest

console = Console()


def get_os_module() -> BootstrapModule:
    """Detects the host OS and returns the corresponding bootstrap layer."""
    if sys.platform == "darwin":
        return MacOSModule()
    return LinuxModule()


def get_ide_module(ide_preference: str) -> BootstrapModule | None:
    """Returns the IDE module based on the user's global configuration."""
    ide = ide_preference.lower()
    if ide in ("vscode", "cursor"):
        return VSCodeModule()
    elif ide == "jetbrains":
        return JetBrainsModule()
    return None


def handle_init(args: argparse.Namespace) -> None:
    """Handles the 'init' subcommand to scaffold environments.

    Dynamically constructs the environment manifest by mapping user flags
    to the respective language, OS, and IDE bootstrap modules.
    """
    config = ProtostarConfig.load()
    modules: list[BootstrapModule] = []

    # 1. Base OS Layer
    modules.append(get_os_module())

    # 2. Language Layers
    has_language = False
    if args.python:
        python_mod = PythonModule()
        if args.scientific:
            # We intercept the build phase slightly to inject the preset
            # without requiring a dedicated preset module class.
            original_build = python_mod.build

            def hooked_build(manifest: "EnvironmentManifest") -> None:
                """Appends core Python settings, scientific dependencies, and pipeline directories."""
                original_build(manifest)

                for pkg in SCIENTIFIC_PACKAGES:
                    manifest.add_dependency(pkg)

                # Scaffold standard data analysis pipeline directories
                for directory in ["data", "notebooks", "src"]:
                    manifest.add_directory(directory)

                # Ignore large or binary data files common in analysis pipelines
                for artifact in ["*.csv", "*.parquet", "*.nc"]:
                    manifest.add_vcs_ignore(artifact)

            python_mod.build = hooked_build  # type: ignore

        modules.append(python_mod)
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

    # 3. IDE Layer
    if ide_mod := get_ide_module(config.ide):
        modules.append(ide_mod)

    # Execute
    engine = Orchestrator(modules)
    engine.run()


def handle_generate(args: argparse.Namespace) -> None:
    """Handles the 'generate' subcommand for post-setup file scaffolding."""
    config = ProtostarConfig.load()

    if args.target == "tex":
        from .modules.lang_layer import generate_latex_boilerplate

        filename = args.name or "main.tex"
        preset = config.presets.get("latex", "minimal")

        try:
            out_path = generate_latex_boilerplate(filename, preset)
            console.print(f"[bold green]Generated:[/bold green] {out_path}")
        except FileExistsError as e:
            console.print(f"[bold red]Generation Aborted:[/bold red] {e}")
    elif args.target == "cpp-class":
        from .modules.lang_layer import generate_cpp_class

        if not args.name:
            console.print(
                "[bold red]Generation Aborted:[/bold red] A class name is required "
                "(e.g., `proto generate cpp-class DataIngestor`)."
            )
            return

        try:
            out_paths = generate_cpp_class(args.name)
            for path in out_paths:
                console.print(f"[bold green]Generated:[/bold green] {path}")
        except (FileExistsError, ValueError) as e:
            console.print(f"[bold red]Generation Aborted:[/bold red] {e}")

    elif args.target == "cmake":
        from .modules.lang_layer import generate_cmake

        project_name = args.name or "ProtostarApp"
        try:
            out_path = generate_cmake(project_name)
            console.print(f"[bold green]Generated:[/bold green] {out_path}")
        except FileExistsError as e:
            console.print(f"[bold red]Generation Aborted:[/bold red] {e}")

    else:
        console.print(
            f"[red]Generator target '{args.target}' is not yet implemented.[/red]"
        )


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
        help="Inject scientific computing dependencies (Python)",
    )

    init_parser.set_defaults(func=handle_init)

    # --- Generate Subparser ---
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate boilerplate files and project scaffolding.",
        description="Generates boilerplate code or files based on the configured environment.",
        formatter_class=ProtoHelpFormatter,
    )

    generate_parser.add_argument(
        "target",
        choices=["tex", "cpp-class", "cmake"],
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
