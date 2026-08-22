"""High-velocity, zero-friction environment scaffolding."""

import contextlib
import importlib.metadata
import logging

__version__ = "unknown"
with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    __version__ = importlib.metadata.version("protostar")

from .enums import (
    ArchiveFormat,
    CIFlag,
    DependencyGroup,
    DiagnosticPhase,
    GitHost,
    IDEType,
    LicenseType,
    MetadataKey,
    PromptType,
    SafelistBinary,
    TargetOS,
)
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
)
from .manifest import EnvironmentManifest
from .modules.base import BootstrapModule
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
    "FileSystemError",
    "GitHost",
    "IDEType",
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
    "TargetOS",
    "TemplateResolutionError",
]
