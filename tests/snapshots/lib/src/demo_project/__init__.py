"""demo-project."""

import contextlib
import importlib.metadata

from demo_project.core import greet

__all__ = ["greet"]

__version__ = "unknown"
with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    __version__ = importlib.metadata.version("demo-project")
