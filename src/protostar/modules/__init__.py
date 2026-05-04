"""Module exports for the Protostar manifest execution engine."""

from .base import BootstrapModule
from .lang_layer import PythonCore
from .system_layer import SystemWorkspaceModule
from .tooling_layer import (
    DirenvModule,
    MarkdownLintModule,
    MypyModule,
    PreCommitModule,
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
)

__all__ = [
    "TOOLING_MODULES",
    "BootstrapModule",
    "DirenvModule",
    "MypyModule",
    "PreCommitModule",
    "PytestModule",
    "PythonCore",
    "RuffModule",
    "SystemWorkspaceModule",
]
