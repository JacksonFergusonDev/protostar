"""Domain-specific exceptions for Protostar."""


class ProtostarError(Exception):
    """Base class for all expected operational errors in Protostar."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class ConfigurationError(ProtostarError):
    """Raised when a configuration file is malformed, invalid, or missing requirements."""

    pass


class NetworkFetchError(ProtostarError):
    """Raised when fetching a remote template or archive fails due to network or protocol issues."""

    def __init__(
        self,
        url: str,
        original: Exception | None = None,
        *,
        message: str | None = None,
        hint: str | None = None,
    ) -> None:
        default_message = (
            f"Network failure: Could not fetch remote configuration from '{url}'."
        )
        default_hint = "Ensure you have an active internet connection and that the URL requires HTTPS, not HTTP."
        super().__init__(message or default_message, hint=hint or default_hint)
        self.url = url
        self.original = original


class TemplateResolutionError(ProtostarError):
    """Raised when a template is found but cannot be parsed, extracted, or resolved."""

    def __init__(self, target: str, detail: str, *, hint: str | None = None) -> None:
        message = f"Failed to resolve template '{target}': {detail}"
        super().__init__(message, hint=hint)
        self.target = target
        self.detail = detail


class MissingDependencyError(ProtostarError):
    """Raised during pre-flight checks when a system-level executable is absent."""

    def __init__(self, dependency: str, purpose: str, install_hint: str) -> None:
        message = f"Missing dependency: '{dependency}' is required for {purpose}."
        super().__init__(message, hint=install_hint)
        self.dependency = dependency
        self.purpose = purpose


class CommandExecutionError(ProtostarError):
    """Raised when a managed subprocess exits with a non-zero status code."""

    def __init__(
        self, command: list[str], returncode: int, stdout: str = "", stderr: str = ""
    ) -> None:
        message = f"Protostar failed to execute command: {' '.join(command)}"
        super().__init__(message)
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

    def __init__(self, command: list[str], timeout: int) -> None:
        message = f"Command timed out after {timeout} seconds: {' '.join(command)}"
        hint = "This is often caused by a stalled network request or an unresponsive registry."
        super().__init__(message, hint=hint)
        self.command = command
        self.timeout = timeout


class FileSystemError(ProtostarError):
    """Raised when a local disk mutation (write, read, mkdir) fails via an OSError or serialization fault."""

    def __init__(self, operation: str, path: str, original: Exception) -> None:
        err_msg = getattr(original, "strerror", None) or str(original)
        message = f"Failed to {operation} '{path}': {err_msg}"
        super().__init__(message)
        self.operation = operation
        self.path = path
        self.original = original


class ExecutionAbortedError(ProtostarError):
    """Raised when the user explicitly aborts the execution via an interactive prompt."""

    def __init__(self, message: str = "Execution aborted by user.") -> None:
        super().__init__(message)


class SecurityViolationError(ProtostarError):
    """Raised when a template attempts an unauthorized system or filesystem operation."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
