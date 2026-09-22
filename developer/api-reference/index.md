# API Reference

The engine strictly isolates state definition from imperative execution. Rather than executing disjointed setup scripts, the Orchestrator evaluates a polymorphic array of `BootstrapModule` objects interacting exclusively with a centralized state object: the `EnvironmentManifest`.

Think of the `EnvironmentManifest` as the nucleus of the scaffolding process. All modules revolve around this state object, mutating its properties and injecting AST payloads during their respective `build()` phases.

```
classDiagram
    direction LR

    class EnvironmentManifest {
        +DependencyManifest dependencies
        +FilesystemManifest filesystem
        +ToolingManifest tooling
        +TaskManifest tasks
        +ProjectMetadata metadata
        +CollisionStrategy collision_strategy
        +add_ide_setting(key: IDESettingKey, value: Any)
    }

    class DependencyManifest {
        +list[str] dependencies
        +list[str] dev_dependencies
        +list[str] docs_dependencies
        +add(package: str)
        +add_dev(package: str)
        +add_docs(package: str)
    }

    class FilesystemManifest {
        +set[str] directories
        +dict[str, str] file_injections
        +dict[str, list[str]] file_appends
        +set[str] vcs_ignores
        +add_directory(path: str)
        +add_file_injection(path: str, content: str)
        +add_file_append(path: str, content: str)
    }

    class TaskManifest {
        +list[SystemTask] system_tasks
        +list[SystemTask] post_install_tasks
        +add_system_task(command: list[str], timeout: int, description: str)
        +add_post_install_task(command: list[str], timeout: int, description: str)
    }

    class ToolingManifest {
        +bool wants_pre_commit
        +bool wants_ci
        +add_pre_commit_hook(payload: str)
        +add_ci_step(step_yaml: str)
    }

    class BootstrapModule {
        <<Abstract>>
        +tuple cli_flags
        +str config_key
        +pre_flight()*
        +build(manifest: EnvironmentManifest)*
    }

    EnvironmentManifest *-- DependencyManifest : contains
    EnvironmentManifest *-- FilesystemManifest : contains
    EnvironmentManifest *-- TaskManifest : contains
    EnvironmentManifest *-- ToolingManifest : contains
    BootstrapModule ..> EnvironmentManifest : Mutates state via build()
```

## Class Definitions

Telemetry & Error Handling: `protostar.errors`

Strictly typed operational errors that halt the execution pipeline safely and return POSIX-compliant exit codes.

## protostar.errors.ProtostarError

Bases: `Exception`

Base class for all expected operational errors in Protostar.

Source code in `src/protostar/errors.py`

```python
class ProtostarError(Exception):
    """Base class for all expected operational errors in Protostar."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        docs_path: DocsPage | str | None = None,
        docs_anchor: str | None = None,
    ) -> None:
        super().__init__(message)
        self.hint = hint
        self.docs_path = docs_path
        self.docs_anchor = docs_anchor

    @property
    def docs_url(self) -> str | None:
        """Returns the full URL to the documentation page, or None if not set."""
        path = self.docs_path
        if path is None or path == "":
            path = DocsPage.GETTING_STARTED.value
        elif isinstance(path, DocsPage):
            path = path.value

        base = DOCS_BASE_URL if DOCS_BASE_URL.endswith("/") else f"{DOCS_BASE_URL}/"
        url = urllib.parse.urljoin(base, path.lstrip("/"))
        if self.docs_anchor:
            url = f"{url}#{self.docs_anchor.lstrip('#')}"
        return url
```

### docs_url `property`

```python
docs_url
```

Returns the full URL to the documentation page, or None if not set.

## protostar.errors.ConfigurationError

Bases: `ProtostarError`

Raised when a configuration file is malformed, invalid, or missing requirements.

Source code in `src/protostar/errors.py`

```python
class ConfigurationError(ProtostarError):
    """Raised when a configuration file is malformed, invalid, or missing requirements."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        docs_path: DocsPage | str | None = DocsPage.CONFIGURATION,
    ) -> None:
        super().__init__(message, hint=hint, docs_path=docs_path)
```

## protostar.errors.NetworkFetchError

Bases: `ProtostarError`

Raised when fetching a remote template or archive fails due to network or protocol issues.

Source code in `src/protostar/errors.py`

```python
class NetworkFetchError(ProtostarError):
    """Raised when fetching a remote template or archive fails due to network or protocol issues."""

    def __init__(
        self,
        url: str,
        original: Exception | None = None,
        *,
        message: str | None = None,
        hint: str | None = None,
        docs_path: DocsPage | str | None = DocsPage.TEMPLATES,
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
```

## protostar.errors.TemplateResolutionError

Bases: `ProtostarError`

Raised when a template is found but cannot be parsed, extracted, or resolved.

Source code in `src/protostar/errors.py`

```python
class TemplateResolutionError(ProtostarError):
    """Raised when a template is found but cannot be parsed, extracted, or resolved."""

    def __init__(
        self,
        target: str,
        detail: str,
        *,
        hint: str | None = None,
        docs_path: DocsPage | str | None = DocsPage.AUTHORING_TEMPLATES,
    ) -> None:
        message = f"Failed to resolve template '{target}': {detail}"
        super().__init__(message, hint=hint, docs_path=docs_path)
        self.target = target
        self.detail = detail
```

## protostar.errors.MissingDependencyError

Bases: `ProtostarError`

Raised during pre-flight checks when a system-level executable is absent.

Source code in `src/protostar/errors.py`

```python
class MissingDependencyError(ProtostarError):
    """Raised during pre-flight checks when a system-level executable is absent."""

    def __init__(
        self,
        dependency: GlobalExecutable,
        purpose: str,
        *,
        docs_path: DocsPage | str | None = DocsPage.TROUBLESHOOTING_DEPS,
    ) -> None:
        message = f"Missing dependency: '{dependency.value}' is required for {purpose}."
        super().__init__(message, hint=None, docs_path=docs_path)
        self.dependency = dependency
        self.purpose = purpose
```

## protostar.errors.CommandExecutionError

Bases: `ProtostarError`

Raised when a managed subprocess exits with a non-zero status code.

Source code in `src/protostar/errors.py`

```python
class CommandExecutionError(ProtostarError):
    """Raised when a managed subprocess exits with a non-zero status code."""

    def __init__(
        self,
        command: list[str],
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        *,
        docs_path: DocsPage | str | None = None,
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
```

### output_detail `property`

```python
output_detail
```

Formats captured stdout/stderr into a display-ready block, or None if empty.

## protostar.errors.CommandTimeoutError

Bases: `ProtostarError`

Raised when a managed subprocess exceeds its allocated runtime window.

Source code in `src/protostar/errors.py`

```python
class CommandTimeoutError(ProtostarError):
    """Raised when a managed subprocess exceeds its allocated runtime window."""

    def __init__(
        self,
        command: list[str],
        timeout: int,
        *,
        docs_path: DocsPage | str | None = DocsPage.TEMPLATES,
    ) -> None:
        message = f"Command timed out after {timeout} seconds: {' '.join(command)}"
        hint = "This is often caused by a stalled network request or an unresponsive registry."
        super().__init__(message, hint=hint, docs_path=docs_path)
        self.command = command
        self.timeout = timeout
```

## protostar.errors.FileSystemError

Bases: `ProtostarError`

Raised when a local disk mutation (write, read, mkdir) fails via an OSError or serialization fault.

Source code in `src/protostar/errors.py`

```python
class FileSystemError(ProtostarError):
    """Raised when a local disk mutation (write, read, mkdir) fails via an OSError or serialization fault."""

    def __init__(
        self,
        operation: str,
        path: str,
        original: Exception,
        *,
        docs_path: DocsPage | str | None = None,
    ) -> None:
        err_msg = getattr(original, "strerror", None) or str(original)
        message = f"Failed to {operation} '{path}': {err_msg}"
        super().__init__(message, docs_path=docs_path)
        self.operation = operation
        self.path = path
        self.original = original
```

## protostar.errors.SecurityViolationError

Bases: `ProtostarError`

Raised when a template attempts an unauthorized system or filesystem operation.

Source code in `src/protostar/errors.py`

```python
class SecurityViolationError(ProtostarError):
    """Raised when a template attempts an unauthorized system or filesystem operation."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        docs_path: DocsPage | str | None = DocsPage.TROUBLESHOOTING_SECURITY,
    ) -> None:
        super().__init__(message, hint=hint, docs_path=docs_path)
```

## protostar.errors.ExecutionAbortedError

Bases: `ProtostarError`

Raised when the user explicitly aborts the execution via an interactive prompt.

Source code in `src/protostar/errors.py`

```python
class ExecutionAbortedError(ProtostarError):
    """Raised when the user explicitly aborts the execution via an interactive prompt."""

    def __init__(
        self,
        message: str = "Execution aborted by user.",
        *,
        hint: str | None = None,
        docs_path: DocsPage | str | None = None,
    ) -> None:
        super().__init__(message, hint=hint, docs_path=docs_path)
```

## protostar.errors.PartialExecutionAbortedError

Bases: `ExecutionAbortedError`

Raised when execution is interrupted after disk mutations have begun.

Source code in `src/protostar/errors.py`

```python
class PartialExecutionAbortedError(ExecutionAbortedError):
    """Raised when execution is interrupted after disk mutations have begun."""

    def __init__(
        self, touched_paths: frozenset[str], *, docs_path: DocsPage | str | None = None
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
```

### __init__

```python
__init__(touched_paths, *, docs_path=None)
```

Initializes the exception with the frozenset of paths modified before the interrupt.

Parameters:

| Name            | Type             | Description                                                | Default    |
| --------------- | ---------------- | ---------------------------------------------------------- | ---------- |
| `touched_paths` | `frozenset[str]` | Immutable set of file and directory paths touched on disk. | *required* |
| `docs_path`     | \`DocsPage       | str                                                        | None\`     |

Source code in `src/protostar/errors.py`

```python
def __init__(
    self, touched_paths: frozenset[str], *, docs_path: DocsPage | str | None = None
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
```

## protostar.errors.WorkspaceCollisionError

Bases: `ProtostarError`

Raised by plan() when collision markers exist and no force flag was provided.

Carries a structured set of conflicting paths so callers can programmatically present the collision details or decide a resolution strategy without re-scanning the filesystem.

Source code in `src/protostar/errors.py`

```python
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
            "Workspace collision detected: existing configuration files found in the workspace:\n"
            f"{bulleted}\n"
            "Use --force-merge or --force-replace to bypass, or resolve interactively."
        )
        super().__init__(message, docs_path=DocsPage.TROUBLESHOOTING_COLLISIONS)
        self.paths = paths
```

### __init__

```python
__init__(paths)
```

Initializes the error with the set of conflicting workspace paths.

Parameters:

| Name    | Type              | Description                                                  | Default    |
| ------- | ----------------- | ------------------------------------------------------------ | ---------- |
| `paths` | `frozenset[Path]` | The set of existing collision-marker paths detected on disk. | *required* |

Source code in `src/protostar/errors.py`

```python
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
```

Core Interface: `BootstrapModule`

## protostar.modules.base.BootstrapModule

Bases: `ABC`

Appends module-specific requirements to the environment manifest.

Source code in `src/protostar/modules/base.py`

```python
class BootstrapModule(abc.ABC):
    """Appends module-specific requirements to the environment manifest."""

    cli_flags: ClassVar[tuple[str, ...]] = ()
    """The CLI flags to trigger this module (e.g., ('-p', '--python'))."""

    cli_help: ClassVar[str] = ""
    """The help description for the CLI flag."""

    config_key: ClassVar[str] = ""
    """The global configuration key used to evaluate if this module is active."""

    required_metadata: ClassVar[tuple[MetadataKey | str, ...]] = ()
    """The metadata keys that MUST be resolved for this module to function."""

    optional_metadata: ClassVar[tuple[MetadataKey | str, ...]] = ()
    """The metadata keys that are nice to have but not strictly required."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Returns the human-readable identifier for the module."""
        pass

    @property
    def collision_markers(self) -> list[Path]:
        """Returns a list of critical filesystem paths to evaluate for collisions during pre-flight.

        Returns:
            A list of Path objects representing critical configuration files or directories
            managed by this module. Defaults to an empty list.
        """
        return []

    def pre_flight(self) -> None:  # noqa: B027
        """Verifies system prerequisites before manifest building begins.

        Raises:
            RuntimeError: If a critical dependency (e.g., 'uv', 'cargo') is missing.
        """
        pass

    @abc.abstractmethod
    def build(self, manifest: EnvironmentManifest) -> None:
        """Appends module-specific requirements to the environment manifest.

        Args:
            manifest (EnvironmentManifest): The centralized state object.
        """
        pass
```

### cli_flags `class-attribute`

```python
cli_flags = ()
```

The CLI flags to trigger this module (e.g., ('-p', '--python')).

### cli_help `class-attribute`

```python
cli_help = ''
```

The help description for the CLI flag.

### config_key `class-attribute`

```python
config_key = ''
```

The global configuration key used to evaluate if this module is active.

### required_metadata `class-attribute`

```python
required_metadata = ()
```

The metadata keys that MUST be resolved for this module to function.

### optional_metadata `class-attribute`

```python
optional_metadata = ()
```

The metadata keys that are nice to have but not strictly required.

### name `abstractmethod` `property`

```python
name
```

Returns the human-readable identifier for the module.

### collision_markers `property`

```python
collision_markers
```

Returns a list of critical filesystem paths to evaluate for collisions during pre-flight.

Returns:

| Type         | Description                                                                     |
| ------------ | ------------------------------------------------------------------------------- |
| `list[Path]` | A list of Path objects representing critical configuration files or directories |
| `list[Path]` | managed by this module. Defaults to an empty list.                              |

### pre_flight

```python
pre_flight()
```

Verifies system prerequisites before manifest building begins.

Raises:

| Type           | Description                                                |
| -------------- | ---------------------------------------------------------- |
| `RuntimeError` | If a critical dependency (e.g., 'uv', 'cargo') is missing. |

Source code in `src/protostar/modules/base.py`

```python
def pre_flight(self) -> None:  # noqa: B027
    """Verifies system prerequisites before manifest building begins.

    Raises:
        RuntimeError: If a critical dependency (e.g., 'uv', 'cargo') is missing.
    """
    pass
```

### build `abstractmethod`

```python
build(manifest)
```

Appends module-specific requirements to the environment manifest.

Parameters:

| Name       | Type                  | Description                   | Default    |
| ---------- | --------------------- | ----------------------------- | ---------- |
| `manifest` | `EnvironmentManifest` | The centralized state object. | *required* |

Source code in `src/protostar/modules/base.py`

```python
@abc.abstractmethod
def build(self, manifest: EnvironmentManifest) -> None:
    """Appends module-specific requirements to the environment manifest.

    Args:
        manifest (EnvironmentManifest): The centralized state object.
    """
    pass
```
