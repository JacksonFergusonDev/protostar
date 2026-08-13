"""Module exports for the Protostar manifest execution engine."""

from .base import BootstrapModule
from .lang_layer import PythonCore
from .system_layer import SystemWorkspaceModule
from .tooling_layer import (
    CodecovModule,
    CommitizinModule,
    DirenvModule,
    MarkdownLintModule,
    MypyModule,
    PreCommitModule,
    PrekModule,
    PyreflyModule,
    PytestModule,
    RenovateModule,
    RuffModule,
    TyModule,
    ZensicalModule,
)

TOOLING_MODULES: tuple[BootstrapModule, ...] = (
    DirenvModule(),
    MarkdownLintModule(),
    RuffModule(),
    MypyModule(),
    TyModule(),
    PyreflyModule(),
    PytestModule(),
    PreCommitModule(),
    PrekModule(),
    CommitizinModule(),
    RenovateModule(),
    CodecovModule(),
    ZensicalModule(),
)

__all__ = [
    "TOOLING_MODULES",
    "BootstrapModule",
    "CodecovModule",
    "CommitizinModule",
    "DirenvModule",
    "MarkdownLintModule",
    "MypyModule",
    "PreCommitModule",
    "PrekModule",
    "PyreflyModule",
    "PytestModule",
    "PythonCore",
    "RenovateModule",
    "RuffModule",
    "SystemWorkspaceModule",
    "TyModule",
    "ZensicalModule",
]
