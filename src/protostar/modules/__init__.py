"""Module exports for the Protostar manifest execution engine."""

from .base import (
    BootstrapModule,
    PathSignal,
    RequirementSignal,
    SectionSignal,
    Signal,
    TableSignal,
    ToolInfo,
    ToolModule,
)
from .ci_layer import CIModule, ReleaseModule
from .community_layer import CommunityModule
from .docker import DOCKER_INFO, DOCKER_NAME, DockerModule
from .lang_layer import LICENSE_MAP, PythonCore, declare_readme
from .system_layer import SystemWorkspaceModule
from .tooling_layer import (
    AGENTS_TARGET,
    AgentsModule,
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
    RumdlModule,
    TyModule,
    ZensicalModule,
)

TOOLING_MODULES: tuple[ToolModule, ...] = (
    DirenvModule(),
    MarkdownLintModule(),
    RumdlModule(),
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
    DockerModule(),
    JustModule(),
    AgentsModule(),
    CommunityModule(),
)


def _check_tool_alignment() -> None:
    from protostar.recipe import Tool

    tool_values = {t.value for t in Tool}
    module_keys = {m.config_key for m in TOOLING_MODULES}
    if tool_values != module_keys:
        missing_in_modules = tool_values - module_keys
        missing_in_tools = module_keys - tool_values
        reasons = []
        if missing_in_modules:
            reasons.append(
                f"Tools defined in Tool enum but missing from TOOLING_MODULES: {sorted(missing_in_modules)}"
            )
        if missing_in_tools:
            reasons.append(
                f"Modules in TOOLING_MODULES with config_key missing from Tool enum: {sorted(missing_in_tools)}"
            )
        raise RuntimeError(f"Tool alignment mismatch: {'; '.join(reasons)}")


_check_tool_alignment()

__all__ = [
    "AGENTS_TARGET",
    "DOCKER_INFO",
    "DOCKER_NAME",
    "LICENSE_MAP",
    "TOOLING_MODULES",
    "AgentsModule",
    "BootstrapModule",
    "CIModule",
    "CodecovModule",
    "CommitizenModule",
    "CommunityModule",
    "DirenvModule",
    "DockerModule",
    "JustModule",
    "MarkdownLintModule",
    "MypyModule",
    "PathSignal",
    "PreCommitModule",
    "PrekModule",
    "PyreflyModule",
    "PytestModule",
    "PythonCore",
    "ReadTheDocsModule",
    "ReleaseModule",
    "RenovateModule",
    "RequirementSignal",
    "RuffModule",
    "RumdlModule",
    "SectionSignal",
    "Signal",
    "SystemWorkspaceModule",
    "TableSignal",
    "ToolInfo",
    "ToolModule",
    "TyModule",
    "ZensicalModule",
    "declare_readme",
]
