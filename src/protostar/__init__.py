"""High-velocity, zero-friction environment scaffolding."""

import contextlib
import importlib.metadata
import logging

__version__ = "unknown"
with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    __version__ = importlib.metadata.version("protostar")

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

# Neutralize the logger before any runtime execution to prevent stderr leakage
logging.getLogger("protostar").addHandler(logging.NullHandler())

__all__ = [
    "BootstrapModule",
    "CommandExecutionError",
    "CommandTimeoutError",
    "ConfigurationError",
    "EnvironmentManifest",
    "FileSystemError",
    "MissingDependencyError",
    "NetworkFetchError",
    "ProtostarError",
    "SecurityViolationError",
    "TemplateResolutionError",
]
