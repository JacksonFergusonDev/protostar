"""High-velocity, zero-friction Python environment scaffolding."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    __version__: str
    from .errors import (
        AggregatedDependencyError,
        CommandExecutionError,
        CommandTimeoutError,
        ConfigurationError,
        FileSystemError,
        MissingDependencyError,
        NetworkFetchError,
        ProtostarError,
        SecurityViolationError,
        TemplateResolutionError,
        WorkspaceCollisionError,
    )
    from .fs import ArchiveFormat
    from .ide import IDEType
    from .intent import DependencyGroup
    from .manifest import DiagnosticPhase, EnvironmentManifest, Severity
    from .metadata import LicenseType, MetadataKey, PromptType
    from .models import ExecutionResult, InitRequest
    from .modules.base import BootstrapModule
    from .network import GitHost
    from .security import SafelistBinary
    from .workflows import CIFlag, TargetOS
    from .workspace import PackageName, ProjectName, PythonVersion
from typing import Any

# Neutralize the logger before any runtime execution to prevent stderr leakage
logging.getLogger("protostar").addHandler(logging.NullHandler())

_MODULE_LOOKUP: dict[str, str] = {
    "AggregatedDependencyError": ".errors",
    "ArchiveFormat": ".fs",
    "BootstrapModule": ".modules.base",
    "CIFlag": ".workflows",
    "CommandExecutionError": ".errors",
    "CommandTimeoutError": ".errors",
    "ConfigurationError": ".errors",
    "DependencyGroup": ".intent",
    "DiagnosticPhase": ".manifest",
    "EnvironmentManifest": ".manifest",
    "ExecutionResult": ".models",
    "FileSystemError": ".errors",
    "GitHost": ".network",
    "IDEType": ".ide",
    "InitRequest": ".models",
    "LicenseType": ".metadata",
    "MetadataKey": ".metadata",
    "MissingDependencyError": ".errors",
    "NetworkFetchError": ".errors",
    "PackageName": ".workspace",
    "ProjectName": ".workspace",
    "PromptType": ".metadata",
    "ProtostarError": ".errors",
    "PythonVersion": ".workspace",
    "SafelistBinary": ".security",
    "SecurityViolationError": ".errors",
    "Severity": ".manifest",
    "TargetOS": ".workflows",
    "TemplateResolutionError": ".errors",
    "WorkspaceCollisionError": ".errors",
}

__all__ = [
    "AggregatedDependencyError",
    "ArchiveFormat",
    "BootstrapModule",
    "CIFlag",
    "CommandExecutionError",
    "CommandTimeoutError",
    "ConfigurationError",
    "DependencyGroup",
    "DiagnosticPhase",
    "EnvironmentManifest",
    "ExecutionResult",
    "FileSystemError",
    "GitHost",
    "IDEType",
    "InitRequest",
    "LicenseType",
    "MetadataKey",
    "MissingDependencyError",
    "NetworkFetchError",
    "PackageName",
    "ProjectName",
    "PromptType",
    "ProtostarError",
    "PythonVersion",
    "SafelistBinary",
    "SecurityViolationError",
    "Severity",
    "TargetOS",
    "TemplateResolutionError",
    "WorkspaceCollisionError",
    "__version__",
]


def __getattr__(name: str) -> Any:
    """Lazy evaluation for module attributes."""
    if name == "__version__":
        import contextlib
        import importlib.metadata

        with contextlib.suppress(importlib.metadata.PackageNotFoundError):
            return importlib.metadata.version("protostar")
        return "unknown"
    if name in _MODULE_LOOKUP:
        import importlib

        module = importlib.import_module(_MODULE_LOOKUP[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Returns sorted attribute list including lazily evaluated exports."""
    return sorted(list(globals().keys()) + __all__)
