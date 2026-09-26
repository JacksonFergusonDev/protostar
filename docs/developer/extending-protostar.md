---
description: "Learn how to extend Protostar's architecture by adding new modules, tools, or domain workflows without altering core execution."
---

# Extending Protostar

Protostar's architecture strictly isolates state definition from execution. This guarantees that you can add entirely new languages, tools, or domain workflows without altering the core orchestrator or the system executor.

## Building a Custom Bootstrap Module

Bootstrap modules define the structural environment footprint. To create a new module, subclass `BootstrapModule` from `protostar.modules.base`.

You must define its CLI flags, a human-readable name, and the `build` method. Declare the binaries your tool runs in `executables`.

!!! tip "Dynamic CLI Registration"
    The CLI parser dynamically reads the `cli_flags` and `cli_help` attributes at runtime. Once you append your module to the `TOOLING_MODULES` tuple in `protostar/modules/__init__.py`, it will automatically appear in the `protostar init --help` output.

Here is a complete example of a module that scaffolds a `justfile` (a modern `Makefile` alternative):

=== "Example Implementation"
    ```python
    from protostar.modules import BootstrapModule, PathSignal
    from protostar.manifest import EnvironmentManifest
    from protostar.system_deps import GlobalExecutable

    class JustModule(BootstrapModule):
        """Configures a justfile for project task execution."""

        cli_flags = ("--just",)
        cli_help = "Scaffold a standard justfile for project tasks"
        config_key = "just"
        # What shows an existing project already uses this tool.
        signals = (PathSignal("justfile"), PathSignal("Justfile"))
        # Binaries the tool runs; planning reports each missing one.
        executables = (GlobalExecutable.JUST,)

        @property
        def name(self) -> str:
            return "Just"

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

=== "Base API"
    !!! abstract "Core Interface: `BootstrapModule`"
        ::: protostar.modules.base.BootstrapModule
            options:
                show_source: true
                show_bases: true
                show_root_heading: true
                show_root_toc_entry: true
                separate_signature: true

??? abstract "Deep Dive: Executables vs Build"
    - **`executables`**: Never blocks a run. Before any module builds, planning records each one missing from `$PATH` in `manifest.missing_tools`, so `build()` can skip a step that runs it (`manifest.is_missing(...)`) and record why in `manifest.diagnostics`. Only the binaries Protostar itself runs (`system_deps.REQUIRED`: `uv` and `git`) fail planning.
    - **`build()`**: Only queues state changes. Notice how we use `manifest.filesystem.add_file_injection()` instead of `Path("justfile").write_text()`.

## Signals: Recognizing an Existing Project

`signals` tells `init` that a project it has never touched already uses the module's tool, so the recipe editor can start with it switched on. A module lists every signal that holds for its tool:

- `PathSignal(path)`: a file or directory, matched with its exact spelling.
- `TableSignal(keys)`: a table in `pyproject.toml`, such as `("tool", "ruff")`.
- `SectionSignal(path, section)`: a section of an INI file, such as `("setup.cfg", "mypy")`.
- `RequirementSignal(name)`: a package in any of the project's dependency lists.

A module that manages a document builds its path signals from that document's locations in `protostar.documents`, so every name the tool reads counts. Analysis knows no tool by name: it reads only what modules declare, and every tooling module must declare at least one signal.

## The Manifest API

!!! danger "No Direct Disk I/O"
    Never call `subprocess.run` or write to disk inside a module's `build()` method. Modules must strictly communicate via the `EnvironmentManifest` to ensure the Orchestrator maintains atomicity.

!!! tip "Automated Collision Detection"
    Modules do not need to register collision markers manually. Any files queued via `manifest.filesystem.add_file_injection()`, `manifest.filesystem.add_structured()`, `manifest.filesystem.add_region()`, or manifest tooling flags are automatically derived by `EnvironmentManifest.target_files()` for workspace collision detection.

The manifest exposes the following methods across its domain slices to queue state changes:

| Method Signature | Execution Behavior |
| --- | --- |
| `manifest.dependencies.add(package: str)` | Queues a standard package for resolution. |
| `manifest.dependencies.add_dev(package: str)` | Queues a development or tooling package. |
| `manifest.dependencies.add_docs(package: str)` | Queues a documentation dependency for installation. |
| `manifest.filesystem.add_directory(path: str)` | Queues a relative directory path to be scaffolded. |
| `manifest.filesystem.add_file_injection(path: str, content: str)` | Queues a complete file write. Fails if the file exists unless explicitly marked for overwrite. |
| `manifest.filesystem.add_structured(path: str, content: str, *, producer: str)` | Queues typed TOML contributions, separating personal metadata seeds from managed configuration. |
| `manifest.filesystem.add_region(path: str, content: str, *, identity: str)` | Queues one uniquely named non-TOML text region. Use a stable module namespace. |
| `manifest.dependencies.add_include(group: DependencyGroup, include: DependencyGroup)` | Declares an include edge between dev/docs groups and its resolver footprint. |
| `manifest.filesystem.add_vcs_ignore(path: str)` | Appends a tracking exclusion entry to the version control ignore manifest (e.g., `.gitignore`). |
| `manifest.tasks.add_system_task(command: list[str], timeout: int | None = 30, description: str | None = None)` | Queues a subprocess command to execute *after* the disk scaffolding phase is complete. Allows an optional execution timeout and UI description. |
| `manifest.tasks.add_post_install_task(command: list[str], timeout: int | None = 30, description: str | None = None)` | Queues a subprocess command to execute *after* all dependencies have been installed. Allows an optional execution timeout and UI description. |

## Next Steps

- **[Testing Architecture & Philosophy](./testing.md):** Best practices for writing isolated unit tests and mocking subprocesses.
- **[The Module Architecture](../mechanics/modules.md):** Deep dive into the layering model and module resolution sequence.
- **[API Reference](./api-reference.md):** Complete class documentation for `BootstrapModule` and `EnvironmentManifest`.
