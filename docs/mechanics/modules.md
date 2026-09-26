# The Module Architecture

Protostar is built around modular plugins. When you run a command, Protostar turns your CLI flags into an ordered list of tool modules.

These modules act as autonomous, stateless plugins that interact strictly with the `EnvironmentManifest`. They do not inspect sibling modules, do not read the host filesystem, and do not execute system commands directly.

## The Layering Model

If multiple modules touch the same configuration space, the Orchestrator relies on sequence order to determine precedence.

```mermaid
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

A tooling module's configuration is a __baseline tuned for casual projects__: it should never make a small script painful. Strict settings such as `mypy`'s `strict = true` belong in the templates whose shape calls for them, not in the module. See [Built-in Templates](../developer/built-in-templates.md#baseline-in-modules-delta-in-templates).

## The Module Contract

### `executables`

The binaries the module's tool runs, such as `direnv`. Before any module builds, planning records each one missing from `$PATH` in `manifest.missing_tools`; it never fails. The module still writes the tool's files, and skips only the steps that run the binary. The binaries Protostar itself runs, `uv` and `git`, are checked by the engine instead, and are the only ones that fail a run.

### `build(manifest: EnvironmentManifest)`

The aggregation phase. Modules receive the mutable manifest object and register dependencies, directory structures, ignored files, and AST payloads.

```python
# Example: A simplified tool implementation
class MyPyModule(BootstrapModule):
    def build(self, manifest: EnvironmentManifest) -> None:
        # Register the dependency
        manifest.dependencies.add_dev("mypy")

        # Inject the AST payload for pyproject.toml. Keep it a casual baseline;
        # templates that want strict mode add it themselves.
        manifest.filesystem.add_structured("pyproject.toml", """
[tool.mypy]
check_untyped_defs = true
warn_return_any = true
        """, producer="module:MyPyModule")
```

## API Reference

??? abstract "Core Interface: `BootstrapModule`"
    ::: protostar.modules.base.BootstrapModule
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true
            members_order: source

## Next Steps & Developer Guides

- __[Built-in Modules](https://github.com/JacksonFergusonDev/protostar/tree/main/src/protostar/modules):__ Browse the source code for official implementations.
- __[Extending Protostar](../developer/extending-protostar.md):__ Step-by-step guide to implementing your own custom `BootstrapModule`.
- __[The Environment Manifest](./manifest.md):__ Full breakdown of the manifest namespaces and mutation methods used during `build()`.
- __[Testing Architecture & Philosophy](../developer/testing.md):__ Learn how to test modules in-memory with strict subprocess mocking.
