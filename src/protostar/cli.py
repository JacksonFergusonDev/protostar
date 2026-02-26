import argparse
import sys
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


def main() -> None:
    """Main entry point for the Protostar CLI."""
    parser = argparse.ArgumentParser(
        description="High-velocity environment scaffolding."
    )

    # Language flags
    parser.add_argument(
        "--python", action="store_true", help="Scaffold a Python (uv) environment"
    )
    parser.add_argument(
        "--rust", action="store_true", help="Scaffold a Rust (cargo) environment"
    )
    parser.add_argument(
        "--node", action="store_true", help="Scaffold a Node.js environment"
    )
    parser.add_argument(
        "--cpp", action="store_true", help="Scaffold a C/C++ environment footprint"
    )
    parser.add_argument(
        "--latex", action="store_true", help="Scaffold a LaTeX environment footprint"
    )

    # Presets
    parser.add_argument(
        "--scientific",
        action="store_true",
        help="Inject scientific computing dependencies (Python)",
    )

    args = parser.parse_args()

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
                """Appends core Python settings and scientific dependencies."""
                original_build(manifest)
                for pkg in SCIENTIFIC_PACKAGES:
                    manifest.add_dependency(pkg)

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
        console.print("Run [bold cyan]protostar --help[/bold cyan] for options.")
        sys.exit(1)

    # 3. IDE Layer
    if ide_mod := get_ide_module(config.ide):
        modules.append(ide_mod)

    # Execute
    engine = Orchestrator(modules)
    engine.run()


if __name__ == "__main__":
    main()
