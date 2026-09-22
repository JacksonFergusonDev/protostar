# Extending Protostar

Protostar's architecture strictly isolates state definition from execution. This guarantees that you can add entirely new languages, tools, or domain workflows without altering the core orchestrator or the system executor.

______________________________________________________________________

## Building a Custom Bootstrap Module

Bootstrap modules define the structural environment footprint. To create a new module, subclass `BootstrapModule` from `protostar.modules.base`.

You must define its CLI flags, a human-readable name, and the `build` method. You can also optionally define `pre_flight` checks, `collision_markers`, and `required_languages` to enforce strict footprint constraints.

Dynamic CLI Registration

The CLI parser dynamically reads the `cli_flags` and `cli_help` attributes at runtime. Once you append your module to the `TOOLING_MODULES` tuple in `protostar/modules/__init__.py`, it will automatically appear in the `protostar init --help` output.

Here is a complete example of a module that scaffolds a `justfile` (a modern `Makefile` alternative):

```python
from pathlib import Path
from protostar.modules import BootstrapModule
from protostar.manifest import EnvironmentManifest

class JustModule(BootstrapModule):
    """Configures a justfile for project task execution."""

    cli_flags = ("--just",)
    cli_help = "Scaffold a standard justfile for project tasks"
    config_key = "just"

    @property
    def name(self) -> str:
        return "Just"

    @property
    def collision_markers(self) -> list[Path]:
        return [Path("justfile")]

    def pre_flight(self) -> None:
        import shutil
        if not shutil.which("just"):
            from protostar.errors import MissingDependencyError
            raise MissingDependencyError("just", purpose="task runner", hint="Install: brew install just")

    def build(self, manifest: EnvironmentManifest) -> None:
        content = r"""default:
\t@just --list

lint:
\tuv run ruff check .
\tuv run ruff format --check .

test:
\tuv run pytest
"""
        manifest.filesystem.add_file_injection("justfile", content)
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

Deep Dive: Pre-flight vs Build

- **`pre_flight()`**: Executes before *any* state changes occur. If `shutil.which("just")` fails here, the orchestrator immediately halts, guaranteeing the environment remains untouched.
- **`build()`**: Only queues state changes. Notice how we use `manifest.filesystem.add_file_injection()` instead of `Path("justfile").write_text()`.

______________________________________________________________________

## The Manifest API

No Direct Disk I/O

Never call `subprocess.run` or write to disk inside a module's `build()` method. Modules must strictly communicate via the `EnvironmentManifest` to ensure the Orchestrator maintains atomicity.

The manifest exposes the following methods across its domain slices to queue state changes:

| Method Signature                                                        | Execution Behavior                                                                              |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `manifest.dependencies.add(package: str)`                               | Queues a standard package for resolution.                                                       |
| `manifest.dependencies.add_dev(package: str)`                           | Queues a development or tooling package.                                                        |
| `manifest.dependencies.add_docs(package: str)`                          | Queues a documentation dependency for installation.                                             |
| `manifest.filesystem.add_directory(path: str)`                          | Queues a relative directory path to be scaffolded.                                              |
| `manifest.filesystem.add_file_injection(path: str, content: str)`       | Queues a complete file write. Fails if the file exists unless explicitly marked for overwrite.  |
| `manifest.filesystem.add_file_append(path: str, content: str)`          | Queues a string payload for late-binding concatenation or TOML AST deep-merging.                |
| `manifest.filesystem.add_vcs_ignore(path: str)`                         | Appends a tracking exclusion entry to the version control ignore manifest (e.g., `.gitignore`). |
| \`manifest.tasks.add_system_task(command: list[str], timeout: int       | None = 30, description: str                                                                     |
| \`manifest.tasks.add_post_install_task(command: list[str], timeout: int | None = 30, description: str                                                                     |

______________________________________________________________________

## Next Steps

- **[Testing Architecture & Philosophy](.././testing/):** Best practices for writing isolated unit tests and mocking subprocesses.
- **[The Module Architecture](../../mechanics/modules/):** Deep dive into the layering model and module resolution sequence.
- **[API Reference](.././api-reference/):** Complete class documentation for `BootstrapModule` and `EnvironmentManifest`.
