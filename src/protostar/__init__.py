"""High-velocity, zero-friction environment scaffolding."""

import contextlib
import importlib.metadata
import logging

__version__ = "unknown"
with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    __version__ = importlib.metadata.version("protostar")

from .manifest import EnvironmentManifest
from .modules.base import BootstrapModule
from .presets.base import PresetModule

# Neutralize the logger before any runtime execution to prevent stderr leakage
logging.getLogger("protostar").addHandler(logging.NullHandler())

__all__ = [
    "BootstrapModule",
    "EnvironmentManifest",
    "PresetModule",
]
