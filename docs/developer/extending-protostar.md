---
description: "Learn how to extend Protostar's architecture by adding new modules, tools, or domain workflows without altering core execution."
---
<!-- markdownlint-disable -->
# Extending Protostar

Protostar's architecture strictly isolates state definition from execution. This guarantees that you can add entirely new languages, tools, or domain workflows without altering the core orchestrator or the system executor.

<div class="grid cards" markdown>

-   :material-rocket-launch: __Bootstrap Modules__

    <hr>

    Define the foundational environment footprint (languages, core tooling). Evaluated during `protostar init`.

    [:octicons-arrow-right-24: Learn more](#building-a-custom-bootstrap-module)

</div>

---

## Building a Custom Bootstrap Module

Bootstrap modules define the structural environment footprint. To create a new module, subclass `BootstrapModule` from `protostar.modules.base`.

You must define its CLI flags, a human-readable name, and the `build` method. You can also optionally define `pre_flight` checks, `collision_markers`, and `required_languages` to enforce strict footprint constraints.

!!! tip "Dynamic CLI Registration"
    The CLI parser dynamically reads the `cli_flags` and `cli_help` attributes at runtime. Once you append your module to the `TOOLING_MODULES` tuple in `protostar/modules/__init__.py`, it will automatically appear in the `protostar init --help` output.

Here is a complete example of a module that scaffolds a `justfile` (a modern `Makefile` alternative):

=== "Example Implementation"
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
                raise RuntimeError("Missing dependency: 'just' is not installed.")

        def build(self, manifest: EnvironmentManifest) -> None:
            content = """default:
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

??? abstract "Deep Dive: Pre-flight vs Build"
    - **`pre_flight()`**: Executes before *any* state changes occur. If `shutil.which("just")` fails here, the orchestrator immediately halts, guaranteeing the environment remains untouched.
    - **`build()`**: Only queues state changes. Notice how we use `manifest.filesystem.add_file_injection()` instead of `Path("justfile").write_text()`.

---

## The Manifest API

!!! danger "No Direct Disk I/O"
    Never call `subprocess.run` or write to disk inside a module's `build()` method. Modules must strictly communicate via the `EnvironmentManifest` to ensure the Orchestrator maintains atomicity.

The manifest exposes the following methods across its domain slices to queue state changes:

| Method Signature | Execution Behavior |
| --- | --- |
| `manifest.dependencies.add(package: str)` | Queues a standard package for resolution. |
| `manifest.dependencies.add_dev(package: str)` | Queues a development or tooling package. |
| `manifest.dependencies.add_docs(package: str)` | Queues a documentation dependency for installation. |
| `manifest.filesystem.add_directory(path: str)` | Queues a relative directory path to be scaffolded. |
| `manifest.filesystem.add_file_injection(path: str, content: str)` | Queues a complete file write. Fails if the file exists unless explicitly marked for overwrite. |
| `manifest.filesystem.add_file_append(path: str, content: str)` | Queues a string payload for late-binding concatenation or TOML AST deep-merging. |
| `manifest.filesystem.add_vcs_ignore(path: str)` | Appends a tracking exclusion entry to the version control ignore manifest (e.g., `.gitignore`). |
| `manifest.tasks.add_system_task(command: list[str], timeout: int | None = 30, description: str | None = None)` | Queues a subprocess command to execute *after* the disk scaffolding phase is complete. Allows an optional execution timeout and UI description. |
| `manifest.tasks.add_post_install_task(command: list[str], timeout: int | None = 30, description: str | None = None)` | Queues a subprocess command to execute *after* all dependencies have been installed. Allows an optional execution timeout and UI description. |
