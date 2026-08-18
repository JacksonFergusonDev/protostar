"""Module exports for the Protostar manifest execution engine."""

from .base import BootstrapModule
from .ci_layer import CIModule, ReleaseModule
from .lang_layer import LICENSE_MAP, PythonCore
from .system_layer import SystemWorkspaceModule
from .tooling_layer import (
    CodecovModule,
    CommitizenModule,
    DirenvModule,
    JustModule,
    MarkdownLintModule,
    MypyModule,
    PreCommitModule,
    PrekModule,
    PyreflyModule,
    PytestModule,
    ReadTheDocsModule,
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
    CommitizenModule(),
    RenovateModule(),
    CodecovModule(),
    ZensicalModule(),
    ReadTheDocsModule(),
    CIModule(),
    ReleaseModule(),
    JustModule(),
)

__all__ = [
    "LICENSE_MAP",
    "TOOLING_MODULES",
    "BootstrapModule",
    "CIModule",
    "CodecovModule",
    "CommitizenModule",
    "DirenvModule",
    "JustModule",
    "MarkdownLintModule",
    "MypyModule",
    "PreCommitModule",
    "PrekModule",
    "PyreflyModule",
    "PytestModule",
    "PythonCore",
    "ReadTheDocsModule",
    "ReleaseModule",
    "RenovateModule",
    "RuffModule",
    "SystemWorkspaceModule",
    "TyModule",
    "ZensicalModule",
]
