"""demo_project."""

import contextlib
import importlib.metadata

__version__ = "unknown"
with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    __version__ = importlib.metadata.version("demo_project")
