"""Module exports for the Protostar manifest execution engine."""

from .base import BootstrapModule
from .lang_layer import PythonCore
from .system_layer import SystemWorkspaceModule
from .tooling_layer import (
    DirenvModule,
    MarkdownLintModule,
    MypyModule,
    PreCommitModule,
    PrekModule,
    PytestModule,
    RuffModule,
)

TOOLING_MODULES: tuple[BootstrapModule, ...] = (
    DirenvModule(),
    MarkdownLintModule(),
    RuffModule(),
    MypyModule(),
    PytestModule(),
    PreCommitModule(),
    PrekModule(),
)

__all__ = [
    "TOOLING_MODULES",
    "BootstrapModule",
    "DirenvModule",
    "MypyModule",
    "PreCommitModule",
    "PrekModule",
    "PytestModule",
    "PythonCore",
    "RuffModule",
    "SystemWorkspaceModule",
]
