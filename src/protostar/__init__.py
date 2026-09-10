"""High-velocity, zero-friction Python environment scaffolding."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    __version__: str

from .dependencies import DependencyGroup
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
from .manifest import DiagnosticPhase, EnvironmentManifest, Severity
from .metadata import LicenseType, MetadataKey, PromptType
from .models import ExecutionResult, InitRequest
from .modules.base import BootstrapModule
from .network import GitHost
from .security import SafelistBinary
from .wizard import WizardSelections
from .workflows import CIFlag, TargetOS
from .workspace import PackageName, ProjectName, PythonVersion

# Neutralize the logger before any runtime execution to prevent stderr leakage
logging.getLogger("protostar").addHandler(logging.NullHandler())

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
    "WizardSelections",
    "WorkspaceCollisionError",
    "__version__",
]


def __getattr__(name: str) -> str:
    """Lazy evaluation for module attributes."""
    if name == "__version__":
        import contextlib
        import importlib.metadata

        with contextlib.suppress(importlib.metadata.PackageNotFoundError):
            return importlib.metadata.version("protostar")
        return "unknown"
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
