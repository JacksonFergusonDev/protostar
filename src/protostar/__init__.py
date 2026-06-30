"""High-velocity, zero-friction environment scaffolding."""

import contextlib
import importlib.metadata

from .manifest import EnvironmentManifest
from .modules.base import BootstrapModule
from .presets.base import PresetModule

__all__ = [
    "BootstrapModule",
    "EnvironmentManifest",
    "PresetModule",
]

__version__ = "unknown"
with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    __version__ = importlib.metadata.version("protostar")
