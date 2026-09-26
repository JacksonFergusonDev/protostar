"""Domain-specific exceptions for Protostar."""

from __future__ import annotations

import os
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError

from protostar.docs_registry import DocsPage
from protostar.system_deps import GlobalExecutable, InstallCommand

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


class UnmatchedResolutionError(ConfigurationError):
    """Raised when a resolution names no conflict in the current review.

    A conflict's identity covers its content, so a conflict that changed since
    it was reviewed no longer matches.
    """

    def __init__(self, selectors: tuple[str, ...]) -> None:
        """Initializes the error with every selector that matched nothing.

        Args:
            selectors: Conflict identities or file paths, in the order given.
        """
        super().__init__(
            f"No conflict matches: {', '.join(selectors)}.",
            hint="Review the project again and resolve the conflicts it lists.",
            docs_path=DocsPage.RESOLVE_CONFLICTS,
        )
        self.selectors = selectors

    def details(self) -> dict[str, Any]:
        """Returns the selectors that matched no conflict."""
        return {"unmatched_resolutions": list(self.selectors)}


class UnsupportedResolutionError(ConfigurationError):
    """Raised when a conflict cannot be settled by the choice made for it."""

    def __init__(self, selector: str, choice: str, choices: tuple[str, ...]) -> None:
        """Initializes the error with the choices the conflict does offer.

        Args:
            selector: The conflict identity or file path the choice was made for.
            choice: The unsupported choice.
            choices: The choices the conflict offers, empty when it must be
                resolved by hand.
        """
        super().__init__(
            f"Cannot resolve {selector} with '{choice}'.",
            hint=f"Choose one of: {', '.join(choices)}."
            if choices
            else "Edit the file by hand, then review the project again.",
            docs_path=DocsPage.RESOLVE_CONFLICTS,
        )
        self.selector = selector
        self.choice = choice
        self.choices = choices

    def details(self) -> dict[str, Any]:
        """Returns the rejected choice and the choices offered instead."""
        return {
            "resolution": {"selector": self.selector, "choice": self.choice},
            "choices": list(self.choices),
        }


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
        if isinstance(original, HTTPError):
            default_hint = (
                f"The server answered HTTP {original.code}. Check that the URL, "
                "including its branch, tag, or commit, exists and is public."
                if 400 <= original.code < 500
                else f"The server answered HTTP {original.code}. Try again later."
            )
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


class TemplateEncodingError(TemplateResolutionError):
    """Raised when a file in an acquired template is not UTF-8 text.

    Everything Protostar reads from a template is interpolated as text, so an
    undecodable file is a defect of the template itself, not a failure to
    retrieve it.
    """

    def __init__(self, target: str, path: str) -> None:
        """Initializes the error for one undecodable file.

        Args:
            target: The template being loaded.
            path: The file's POSIX path within the template.
        """
        super().__init__(
            target,
            f"{path} is not UTF-8 text.",
            hint="Template files are interpolated as text, so binary files such as "
            "images are not supported. Remove the file or save it as UTF-8.",
        )
        self.path = path


class TemplateRefNotFoundError(TemplateResolutionError):
    """Raised when a remote template's repository has no such tag, branch, or commit."""

    def __init__(self, target: str, ref: str, releases: tuple[str, ...]) -> None:
        """Initializes the error for one unknown ref.

        Args:
            target: The template's repository.
            ref: The ref that names nothing in the repository.
            releases: The repository's release tags, newest first.
        """
        super().__init__(
            target,
            f"The repository has no tag, branch, or commit named '{ref}'.",
            hint=f"Its newest release tags are: {', '.join(releases[:5])}."
            if releases
            else "It has no release tags; name a branch or a full commit SHA.",
            docs_path=DocsPage.TEMPLATES,
        )
        self.ref = ref


class UnversionedTemplateError(ConfigurationError):
    """Raised when a revision is requested for a template that has none."""

    def __init__(self) -> None:
        """Initializes the error."""
        super().__init__(
            "This project's template has no revisions to move between.",
            hint="Only templates in a GitHub, GitLab, Bitbucket, Codeberg, or "
            "Sourcehut repository have versions. Built-in templates follow the "
            "installed Protostar, and local templates follow their files.",
            docs_path=DocsPage.TEMPLATES,
        )


class OutdatedProtostarError(ConfigurationError):
    """Raised when the installed Protostar is older than the one that wrote the lock.

    Built-in modules render whatever the installed release produces, so an
    older release would plan older output and accept it as an update.
    """

    def __init__(self, recorded: str, installed: str) -> None:
        """Initializes the error for one version pair.

        Args:
            recorded: The version that last wrote ``protostar.lock``.
            installed: The version running now.
        """
        super().__init__(
            f"protostar.lock was written by Protostar {recorded}, "
            f"but Protostar {installed} is installed.",
            hint=f"Upgrade Protostar to {recorded} or newer (for example, "
            "`uv tool upgrade protostar`), then run the command again.",
            docs_path=DocsPage.VERSION_SKEW,
        )
        self.recorded = recorded
        self.installed = installed

    def details(self) -> dict[str, Any]:
        """Returns both versions."""
        return {"recorded_version": self.recorded, "installed_version": self.installed}


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
                "Pass each with `--var NAME=VALUE`, or add them under "
                "[tool.protostar.variables] in pyproject.toml."
            ),
            docs_path=DocsPage.RECIPE_VARIABLES,
        )
        self.variables = variables

    def details(self) -> dict[str, Any]:
        """Returns the missing variable names."""
        return {"missing_variables": list(self.variables)}


class InvalidOptionValueError(ConfigurationError):
    """Raised when a template option is given a value it does not offer."""

    def __init__(self, option: str, value: str, values: tuple[str, ...]) -> None:
        """Initializes the error with the option and the values it offers.

        Args:
            option: The option's name.
            value: The value given.
            values: Every value the option offers.
        """
        super().__init__(
            f"Option {option!r} has no value {value!r}.",
            hint=f"Choose one of: {', '.join(values)}, as `--option {option}=VALUE`.",
        )
        self.option = option
        self.values = values

    def details(self) -> dict[str, Any]:
        """Returns the option and the values it offers."""
        return {"option": self.option, "values": list(self.values)}


class MissingDependencyError(ProtostarError):
    """Raised when an executable Protostar itself needs is not on ``PATH``.

    Only ``system_deps.REQUIRED`` executables raise this; a selected tool's
    missing executable is reported as ``EnvironmentManifest.missing_tools``.
    """

    def __init__(
        self,
        missing: tuple[GlobalExecutable, ...],
        install: InstallCommand | None,
        *,
        docs_path: DocsPage | None = DocsPage.TROUBLESHOOTING_DEPS,
    ) -> None:
        """Initializes the error with the executables and how to install them.

        Args:
            missing: The missing executables, sorted.
            install: The commands that install them, or None when none is known.
            docs_path: Where the installation instructions live.
        """
        names = " and ".join(executable.value for executable in missing)
        them, are = ("it", "is") if len(missing) == 1 else ("them", "are")
        if install is None:
            hint = f"Install {names}, then run the command again."
        else:
            commands = "\n".join(f"    {line}" for line in install.lines)
            hint = f"Install {them} with:\n{commands}"
            if install.reload_shell:
                hint += f"\n\nThen open a new terminal so your shell finds {them}."
        super().__init__(
            f"Protostar needs {names}, which {are} not installed.",
            hint=hint,
            docs_path=docs_path,
        )
        self.missing = missing
        self.install = install

    def details(self) -> dict[str, Any]:
        """Returns the missing executables, and the commands that install them."""
        record: dict[str, Any] = {
            "missing_executables": [executable.value for executable in self.missing]
        }
        if self.install is not None:
            record["install_commands"] = list(self.install.lines)
        return record


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
    """Raised when newly entered template variable values look like credentials.

    Carries the flagged variable names and the rules they matched, never the
    values themselves. The user can confirm a flagged value per variable.
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
                "at runtime. If a flagged value isn't a secret, keep it with "
                "--allow-secret NAME."
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
