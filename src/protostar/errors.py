"""Domain-specific exceptions for Protostar."""

from __future__ import annotations

import os
from enum import IntEnum
from pathlib import Path


class ExitCode(IntEnum):
    """Standardized cross-platform exit codes."""

    OK = getattr(os, "EX_OK", 0)
    USAGE = getattr(os, "EX_USAGE", 64)
    DATAERR = getattr(os, "EX_DATAERR", 65)
    UNAVAILABLE = getattr(os, "EX_UNAVAILABLE", 69)
    SOFTWARE = getattr(os, "EX_SOFTWARE", 70)
    OSERR = getattr(os, "EX_OSERR", 71)
    IOERR = getattr(os, "EX_IOERR", 74)
    TEMPFAIL = getattr(os, "EX_TEMPFAIL", 75)
    NOPERM = getattr(os, "EX_NOPERM", 77)
    CONFIG = getattr(os, "EX_CONFIG", 78)


DOCS_BASE_URL = "https://protostar.readthedocs.io/en/stable/"


class ProtostarError(Exception):
    """Base class for all expected operational errors in Protostar."""

    def __init__(
        self, message: str, *, hint: str | None = None, docs_path: str | None = None
    ) -> None:
        super().__init__(message)
        self.hint = hint
        self.docs_path = docs_path

    @property
    def docs_url(self) -> str | None:
        """Returns the full URL to the documentation page, or None if not set."""
        if self.docs_path is None:
            return None
        return f"{DOCS_BASE_URL}{self.docs_path.lstrip('/')}"


class ConfigurationError(ProtostarError):
    """Raised when a configuration file is malformed, invalid, or missing requirements."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        docs_path: str | None = "usage/configuration/",
    ) -> None:
        super().__init__(message, hint=hint, docs_path=docs_path)


class InvalidUsageError(ProtostarError):
    """Raised when the user provides unrecognized or invalid CLI arguments."""

    def __init__(self, message: str, *, docs_path: str | None = None) -> None:
        super().__init__(message, docs_path=docs_path)


class NetworkFetchError(ProtostarError):
    """Raised when fetching a remote template or archive fails due to network or protocol issues."""

    def __init__(
        self,
        url: str,
        original: Exception | None = None,
        *,
        message: str | None = None,
        hint: str | None = None,
        docs_path: str | None = "usage/templates/",
    ) -> None:
        default_message = (
            f"Network failure: Could not fetch remote configuration from '{url}'."
        )
        default_hint = "Ensure you have an active internet connection and that the URL requires HTTPS, not HTTP."
        super().__init__(
            message or default_message, hint=hint or default_hint, docs_path=docs_path
        )
        self.url = url
        self.original = original


class TemplateResolutionError(ProtostarError):
    """Raised when a template is found but cannot be parsed, extracted, or resolved."""

    def __init__(
        self,
        target: str,
        detail: str,
        *,
        hint: str | None = None,
        docs_path: str | None = "usage/authoring-templates/",
    ) -> None:
        message = f"Failed to resolve template '{target}': {detail}"
        super().__init__(message, hint=hint, docs_path=docs_path)
        self.target = target
        self.detail = detail


class MissingDependencyError(ProtostarError):
    """Raised during pre-flight checks when a system-level executable is absent."""

    def __init__(
        self,
        dependency: str,
        purpose: str,
        install_hint: str,
        *,
        docs_path: str | None = "getting-started/",
    ) -> None:
        message = f"Missing dependency: '{dependency}' is required for {purpose}."
        super().__init__(message, hint=install_hint, docs_path=docs_path)
        self.dependency = dependency
        self.purpose = purpose


class CommandExecutionError(ProtostarError):
    """Raised when a managed subprocess exits with a non-zero status code."""

    def __init__(
        self,
        command: list[str],
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        *,
        docs_path: str | None = None,
    ) -> None:
        message = f"Protostar failed to execute command: {' '.join(command)}"
        super().__init__(message, docs_path=docs_path)
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    @property
    def output_detail(self) -> str | None:
        """Formats captured stdout/stderr into a display-ready block, or None if empty."""
        blocks = []
        if self.stdout:
            blocks.append(f"--- STDOUT ---\n{self.stdout.strip()}")
        if self.stderr:
            blocks.append(f"--- STDERR ---\n{self.stderr.strip()}")
        return "\n\n".join(blocks) or None


class CommandTimeoutError(ProtostarError):
    """Raised when a managed subprocess exceeds its allocated runtime window."""

    def __init__(
        self,
        command: list[str],
        timeout: int,
        *,
        docs_path: str | None = "usage/templates/",
    ) -> None:
        message = f"Command timed out after {timeout} seconds: {' '.join(command)}"
        hint = "This is often caused by a stalled network request or an unresponsive registry."
        super().__init__(message, hint=hint, docs_path=docs_path)
        self.command = command
        self.timeout = timeout


class FileSystemError(ProtostarError):
    """Raised when a local disk mutation (write, read, mkdir) fails via an OSError or serialization fault."""

    def __init__(
        self,
        operation: str,
        path: str,
        original: Exception,
        *,
        docs_path: str | None = None,
    ) -> None:
        err_msg = getattr(original, "strerror", None) or str(original)
        message = f"Failed to {operation} '{path}': {err_msg}"
        super().__init__(message, docs_path=docs_path)
        self.operation = operation
        self.path = path
        self.original = original


class ExecutionAbortedError(ProtostarError):
    """Raised when the user explicitly aborts the execution via an interactive prompt."""

    def __init__(
        self,
        message: str = "Execution aborted by user.",
        *,
        hint: str | None = None,
        docs_path: str | None = None,
    ) -> None:
        super().__init__(message, hint=hint, docs_path=docs_path)


class PartialExecutionAbortedError(ExecutionAbortedError):
    """Raised when execution is interrupted after disk mutations have begun."""

    def __init__(
        self, touched_paths: frozenset[str], *, docs_path: str | None = None
    ) -> None:
        """Initializes the exception with the frozenset of paths modified before the interrupt.

        Args:
            touched_paths: Immutable set of file and directory paths touched on disk.
            docs_path: Optional path to relevant documentation.
        """
        if touched_paths:
            paths_bulleted = "\n".join(f"- {p}" for p in sorted(touched_paths))
            message = (
                "Execution was interrupted before Protostar could finish setting up the environment.\n\n"
                "The following paths were modified or created before the abort:\n"
                f"{paths_bulleted}\n\n"
                "Note: External commands (e.g., uv, git) may have also modified workspace files."
            )
        else:
            message = (
                "Execution was interrupted before Protostar could finish setting up the environment.\n\n"
                "Note: External commands (e.g., uv, git) may have also modified workspace files."
            )
        hint = "Inspect the modified paths or clean up the workspace before re-running Protostar."
        super().__init__(message, hint=hint, docs_path=docs_path)
        self.touched_paths = touched_paths


class WorkspaceCollisionError(ProtostarError):
    """Raised by plan() when collision markers exist and no force flag was provided.

    Carries a structured set of conflicting paths so callers can programmatically
    present the collision details or decide a resolution strategy without re-scanning
    the filesystem.
    """

    def __init__(self, paths: frozenset[Path]) -> None:
        """Initializes the error with the set of conflicting workspace paths.

        Args:
            paths: The set of existing collision-marker paths detected on disk.
        """
        bulleted = "\n".join(f"  - {p}" for p in sorted(paths))
        message = (
            "Orbital Collision Detected: existing configuration files found in the workspace:\n"
            f"{bulleted}\n"
            "Use --force-merge or --force-replace to bypass, or resolve interactively."
        )
        super().__init__(message)
        self.paths = paths


class SecurityViolationError(ProtostarError):
    """Raised when a template attempts an unauthorized system or filesystem operation."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        docs_path: str | None = "usage/templates/",
    ) -> None:
        super().__init__(message, hint=hint, docs_path=docs_path)
