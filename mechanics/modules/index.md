# The Module Architecture

Protostar is built around modular plugins. When you run a command, Protostar turns your CLI flags into an ordered list of tool modules.

These modules act as autonomous, stateless plugins that interact strictly with the `EnvironmentManifest`. They do not inspect sibling modules, do not read the host filesystem, and do not execute system commands directly.

______________________________________________________________________

## The Layering Model

If multiple modules touch the same configuration space, the Orchestrator relies on sequence order to determine precedence.

```
graph TD
    %% Styling
    classDef layer fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff,font-weight:bold;
    classDef base fill:#0f172a,stroke:#00e5ff,stroke-width:3px,color:#fff;

    subgraph Stack [ ]
        direction TB

        L1[1. System Layer]:::base
        L2[2. Language Layer]:::layer
        L3[3. Tooling Layer]:::layer

        %% Relationships showing precedence flow
        L1 --> L2 --> L3
    end

    %% Annotations
    Note1["**Foundation**<br/>Universal Hygiene"] -- Initialized first --> L1

    style Stack fill:transparent,stroke:#475569,stroke-dasharray: 5 5
```

The stack is resolved in the following strict order:

### 1. System Layer

Configures universal environment artifacts and workspace hygiene. The `SystemWorkspaceModule` ignores standard host artifacts (`.DS_Store`), IDE directories (`.idea/`, `.vscode/`), and credentials (`.env`).

### 2. Language Layer

The core runtime environment (`PythonCore`). Establishes the primary package manager (`uv`), initializes project metadata (`pyproject.toml`), and binds IDE settings.

### 3. Tooling Layer

Ancillary development tools. Tools like `ruff`, `mypy`, `pytest`, and `prek` evaluate the manifest to inject configuration blocks into the project files.

______________________________________________________________________

## The Module Contract

### `pre_flight()`

Pre-flight checks. If a module requires external binaries (e.g., `git`, `uv`), it verifies their presence in `$PATH`. If the check fails, an exception is raised before any files or directories are created.

### `build(manifest: EnvironmentManifest)`

The aggregation phase. Modules receive the mutable manifest object and register dependencies, directory structures, ignored files, and AST payloads.

```python
# Example: A simplified tool implementation
class MyPyModule(BootstrapModule):
    def build(self, manifest: EnvironmentManifest) -> None:
        # Register the dependency
        manifest.dependencies.add_dev("mypy")

        # Inject the AST payload for pyproject.toml
        manifest.filesystem.add_file_append("pyproject.toml", """
[tool.mypy]
strict = true
warn_return_any = true
        """)
```

## API Reference

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

______________________________________________________________________

## Next Steps & Developer Guides

- **[Built-in Modules](https://github.com/JacksonFergusonDev/protostar/tree/main/src/protostar/modules):** Browse the source code for official implementations.
- **[Extending Protostar](../../developer/extending-protostar/):** Step-by-step guide to implementing your own custom `BootstrapModule`.
- **[The Environment Manifest](.././manifest/):** Full breakdown of the manifest namespaces and mutation methods used during `build()`.
- **[Testing Architecture & Philosophy](../../developer/testing/):** Learn how to test modules in-memory with strict subprocess mocking.
