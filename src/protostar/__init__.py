"""High-velocity, zero-friction environment scaffolding."""

import contextlib
import importlib.metadata
import logging

__version__ = "unknown"
with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    __version__ = importlib.metadata.version("protostar")

from .dependencies import DependencyGroup
from .errors import (
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
]
