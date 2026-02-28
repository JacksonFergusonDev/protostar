"""Module exports for the Protostar manifest execution engine."""

from .base import BootstrapModule
from .ide_layer import JetBrainsModule, VSCodeModule
from .lang_layer import CppModule, LatexModule, NodeModule, PythonModule, RustModule
from .os_layer import LinuxModule, MacOSModule
from .tooling_layer import DirenvModule, MarkdownLintModule

LANG_MODULES: tuple[BootstrapModule, ...] = (
    PythonModule(),
    RustModule(),
    NodeModule(),
    CppModule(),
    LatexModule(),
)

TOOLING_MODULES: tuple[BootstrapModule, ...] = (
    DirenvModule(),
    MarkdownLintModule(),
)

__all__ = [
    "BootstrapModule",
    "MacOSModule",
    "LinuxModule",
    "VSCodeModule",
    "JetBrainsModule",
    "LANG_MODULES",
    "TOOLING_MODULES",
]
