"""Domain-specific exceptions for Protostar."""

from __future__ import annotations

import os
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from protostar.docs_registry import DocsPage
from protostar.system_deps import GlobalExecutable

if TYPE_CHECKING:
    from .journal import RollbackResult
    from .models import RollbackContext
    from .secret_guard import SecretFinding


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


class ProtostarError(Exception):
    """Base class for all expected operational errors in Protostar."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        docs_path: DocsPage | None = None,
        docs_anchor: str | None = None,
    ) -> None:
        super().__init__(message)
        self.hint = hint
        self.docs_path = docs_path
        self.docs_anchor = docs_anchor
        self.rollback_context: RollbackContext | None = None

    @property
    def docs_url(self) -> str | None:
        """Returns the full URL to the documentation page, or None if not set."""
        if not self.docs_path:
            return None
        return self.docs_path.build_url(self.docs_anchor)

    def details(self) -> dict[str, Any]:
        """Returns structured fields for the machine-readable error envelope.

        Returns:
            JSON-safe fields merged into the ``--json`` error object; empty
            unless a subclass carries data an agent can act on.
        """
        return {}


class ConfigurationError(ProtostarError):
    """Raised when a configuration file is malformed, invalid, or missing requirements."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        docs_path: DocsPage | None = DocsPage.CONFIGURATION,
    ) -> None:
        super().__init__(message, hint=hint, docs_path=docs_path)


class StaleReviewError(ConfigurationError):
    """Raised when workspace inputs change between preparation and execution."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"Review input changed: {path}.",
            hint="Prepare a new review against the current workspace before applying changes.",
        )


class InvalidUsageError(ProtostarError):
    """Raised when the user provides unrecognized or invalid CLI arguments."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        docs_path: DocsPage | None = DocsPage.CLI_REFERENCE,
    ) -> None:
        super().__init__(message, hint=hint, docs_path=docs_path)


class NetworkFetchError(ProtostarError):
    """Raised when fetching a remote template or archive fails due to network or protocol issues."""

    def __init__(
        self,
        url: str,
        original: Exception | None = None,
        *,
        message: str | None = None,
        hint: str | None = None,
        docs_path: DocsPage | None = DocsPage.TEMPLATES,
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
        docs_path: DocsPage | None = DocsPage.AUTHORING_TEMPLATES,
    ) -> None:
        message = f"Failed to resolve template '{target}': {detail}"
        super().__init__(message, hint=hint, docs_path=docs_path)
        self.target = target
        self.detail = detail


class MissingTemplateVariablesError(TemplateResolutionError):
    """Raised when a template needs variable values nobody supplied.

    Protostar never prompts from the engine. The CLI prompts in an interactive
    terminal; everywhere else, including ``--json`` and ``sync``, this error
    lists every missing name so a caller can supply them all at once.
    """

    def __init__(self, target: str, variables: tuple[str, ...]) -> None:
        """Initializes the error with every missing variable.

        Args:
            target: The template being rendered.
            variables: The variables without a value, sorted.
        """
        super().__init__(
            target,
            f"Template needs values for: {', '.join(variables)}.",
            hint=(
                "Pass them with `protostar init --var NAME=VALUE`, or add them "
                "under [tool.protostar.variables] in pyproject.toml."
            ),
            docs_path=DocsPage.RECIPE_VARIABLES,
        )
        self.variables = variables

    def details(self) -> dict[str, Any]:
        """Returns the missing variable names."""
        return {"missing_variables": list(self.variables)}


class MissingDependencyError(ProtostarError):
    """Raised during pre-flight checks when a system-level executable is absent."""

    def __init__(
        self,
        dependency: GlobalExecutable,
        purpose: str,
        *,
        docs_path: DocsPage | None = DocsPage.TROUBLESHOOTING_DEPS,
    ) -> None:
        message = f"Missing dependency: '{dependency.value}' is required for {purpose}."
        super().__init__(message, hint=None, docs_path=docs_path)
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
        docs_path: DocsPage | None = None,
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
        docs_path: DocsPage | None = DocsPage.TEMPLATES,
    ) -> None:
        message = f"Command timed out after {timeout} seconds: {' '.join(command)}"
        hint = "This is often caused by a stalled network request or an unresponsive registry."
        super().__init__(message, hint=hint, docs_path=docs_path)
        self.command = command
        self.timeout = timeout


class ProcessTerminationError(ProtostarError):
    """Raised when a managed process cannot be terminated and reaped safely."""

    def __init__(self, process_id: int, detail: str) -> None:
        message = f"Failed to terminate managed process tree {process_id}: {detail}"
        hint = (
            "Stop the reported process tree before modifying or retrying the workspace."
        )
        super().__init__(message, hint=hint)
        self.process_id = process_id
        self.detail = detail


class FileSystemError(ProtostarError):
    """Raised when a local disk mutation (write, read, mkdir) fails via an OSError or serialization fault."""

    def __init__(
        self,
        operation: str,
        path: str,
        original: Exception,
        *,
        docs_path: DocsPage | None = None,
    ) -> None:
        err_msg = getattr(original, "strerror", None) or str(original)
        message = f"Failed to {operation} '{path}': {err_msg}"
        super().__init__(message, docs_path=docs_path)
        self.operation = operation
        self.path = path
        self.original = original


class UnsupportedFilesystemNodeError(ProtostarError):
    """Raised when a transaction targets a symlink or special filesystem node."""

    def __init__(
        self,
        path: Path,
        node_type: str,
        *,
        docs_path: DocsPage | None = DocsPage.ROLLBACK,
    ) -> None:
        message = f"Cannot transactionally mutate unsupported {node_type}: {path}"
        hint = (
            "Replace the node with a regular file or directory and run Protostar again."
        )
        super().__init__(message, hint=hint, docs_path=docs_path)
        self.path = path
        self.node_type = node_type


class TransactionStateError(ProtostarError):
    """Raised when a transaction operation is invalid for its lifecycle state."""

    def __init__(self, operation: str, state: str) -> None:
        super().__init__(
            f"Cannot {operation} a transaction while it is {state}.",
            hint="Create a new executor for each execution attempt.",
        )
        self.operation = operation
        self.state = state


class ExecutionAbortedError(ProtostarError):
    """Raised when the user explicitly aborts the execution via an interactive prompt."""

    def __init__(
        self,
        message: str = "Execution aborted by user.",
        *,
        hint: str | None = None,
        docs_path: DocsPage | None = None,
    ) -> None:
        super().__init__(message, hint=hint, docs_path=docs_path)


class ExecutionInterruptedError(ProtostarError):
    """Raised when the user interrupts execution (Ctrl+C) and rollback succeeds."""

    def __init__(
        self,
        rollback_context: RollbackContext,
        *,
        docs_path: DocsPage | None = None,
    ) -> None:
        """Initializes the exception with the structured rollback metadata.

        Args:
            rollback_context: The structured context detailing paths restored and tasks run.
            docs_path: Optional path to relevant documentation.
        """
        super().__init__(
            "Execution interrupted by user.", hint=None, docs_path=docs_path
        )
        self.rollback_context = rollback_context


class WorkspaceCollisionError(ProtostarError):
    """Raised before execution when collisions lack a chosen strategy.

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
            "Workspace collision detected: existing configuration files found in the workspace:\n"
            f"{bulleted}\n"
            "Use --force-merge or --force-replace to bypass, or resolve interactively."
        )
        super().__init__(message, docs_path=DocsPage.TROUBLESHOOTING_COLLISIONS)
        self.paths = paths

    def details(self) -> dict[str, Any]:
        """Returns the colliding paths as sorted strings."""
        return {"paths": sorted(str(p) for p in self.paths)}


class SecurityViolationError(ProtostarError):
    """Raised when a template attempts an unauthorized system or filesystem operation."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        docs_path: DocsPage | None = DocsPage.TROUBLESHOOTING_SECURITY,
    ) -> None:
        super().__init__(message, hint=hint, docs_path=docs_path)


class SecretDetectedError(SecurityViolationError):
    """Raised when template variable values look like credentials.

    Carries the flagged variable names and the rules they matched, never the
    values themselves.
    """

    def __init__(self, findings: tuple[SecretFinding, ...]) -> None:
        """Initializes the error with one finding per flagged variable.

        Args:
            findings: The flagged variables, sorted by name.
        """
        listed = "\n".join(
            f"  - {finding.variable} (gitleaks rule {finding.rule})"
            for finding in findings
        )
        super().__init__(
            f"Template variable values look like credentials:\n{listed}",
            hint=(
                "Template variables are saved to pyproject.toml and rendered into "
                "project files, so they must not hold secrets. Enter a non-secret "
                "value, and have the project read the secret from the environment "
                "at runtime."
            ),
            docs_path=DocsPage.TEMPLATE_VARIABLES,
        )
        self.findings = findings

    def details(self) -> dict[str, Any]:
        """Returns each flagged variable and the rule it matched."""
        return {
            "findings": [
                {"variable": finding.variable, "rule": finding.rule}
                for finding in self.findings
            ]
        }


class AggregatedDependencyError(ProtostarError):
    """Raised when multiple pre-flight executable checks fail."""

    def __init__(
        self,
        errors: tuple[MissingDependencyError, ...],
        *,
        docs_path: DocsPage | None = DocsPage.TROUBLESHOOTING_DEPS,
    ) -> None:
        if not errors:
            raise ValueError("AggregatedDependencyError requires at least one error.")

        message = (
            f"Missing {len(errors)} system dependencies required for this environment."
        )

        import sys

        package_names = [e.dependency.package_name for e in errors]

        if sys.platform == "darwin":
            unified = f"Install missing tools via Homebrew:\n    brew install {' '.join(package_names)}"
        elif sys.platform == "win32":
            unified = f"Install missing tools via Winget:\n    winget install {' '.join(package_names)}"
        else:
            unified = f"Install missing tools via your system package manager (e.g. apt, pacman):\n    sudo apt install {' '.join(package_names)}"

        import os

        if sys.platform == "win32":
            reload_hint = "Note: Please close and reopen your terminal for the PATH changes to take effect."
        else:
            shell = os.environ.get("SHELL", "")
            if "zsh" in shell:
                reload_cmd = "source ~/.zshrc"
            elif "bash" in shell:
                reload_cmd = (
                    "source ~/.bash_profile"
                    if sys.platform == "darwin"
                    else "source ~/.bashrc"
                )
            elif "fish" in shell:
                reload_cmd = "source ~/.config/fish/config.fish"
            else:
                reload_cmd = "source ~/.bashrc  # (or your shell's equivalent)"

            reload_hint = f"Note: Reload your shell profile for the PATH changes to take effect:\n    {reload_cmd}"

        hint = f"{unified}\n\n{reload_hint}"

        super().__init__(message, hint=hint, docs_path=docs_path)
        self.errors = errors


class RollbackFailedError(ProtostarError):
    """Raised when an interrupted execution fails to cleanly rollback to its original state."""

    def __init__(
        self,
        rollback_result: RollbackResult,
        original_error: BaseException,
        *,
        docs_path: DocsPage | None = DocsPage.ROLLBACK,
    ) -> None:
        failed_list = "\n".join(
            f"- {failure.path}: {failure.detail}" for failure in rollback_result.errors
        )
        message = (
            "Protostar execution failed and the automated rollback was only partially successful.\n\n"
            "The following paths could not be restored to their original state:\n"
            f"{failed_list}\n\n"
            f"Original execution error: {original_error}"
        )
        hint = (
            "Manual intervention is required to restore the workspace to a clean state."
        )
        super().__init__(message, hint=hint, docs_path=docs_path)
        self.rollback_result = rollback_result
        self.original_error = original_error
