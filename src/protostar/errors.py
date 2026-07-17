"""Domain-specific exceptions for Protostar."""


class ProtostarError(Exception):
    """Base class for all expected operational errors in Protostar."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class ConfigurationError(ProtostarError):
    """Raised when a configuration file is malformed, invalid, or missing requirements."""

    pass


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


class CommandTimeoutError(ProtostarError):
    """Raised when a managed subprocess exceeds its allocated runtime window."""

    def __init__(self, command: list[str], timeout: int) -> None:
        message = f"Command timed out after {timeout} seconds: {' '.join(command)}"
        hint = "This is often caused by a stalled network request or an unresponsive registry."
        super().__init__(message, hint=hint)
        self.command = command
        self.timeout = timeout


class FileSystemError(ProtostarError):
    """Raised when a local disk mutation (write, read, mkdir) fails via an OSError."""

    def __init__(self, operation: str, path: str, original: OSError) -> None:
        err_msg = original.strerror or str(original)
        message = f"Failed to {operation} '{path}': {err_msg}"
        super().__init__(message)
        self.operation = operation
        self.path = path
        self.original = original
