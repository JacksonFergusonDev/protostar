<!-- markdownlint-disable -->
# Extending Protostar

Protostar's architecture strictly isolates state definition from execution. This guarantees that you can add entirely new languages, tools, or domain workflows without altering the core orchestrator or the system executor.

<div class="grid cards" markdown>

-   :material-rocket-launch: __Bootstrap Modules__

    <hr>

    Define the foundational environment footprint (languages, core tooling). Evaluated during `protostar init`.

    [:octicons-arrow-right-24: Learn more](#building-a-custom-bootstrap-module)

-   :material-layers-triple: __Preset Modules__

    <hr>

    Lighter wrappers that inject domain-specific dependencies and directories onto a bootstrap foundation.

    [:octicons-arrow-right-24: Learn more](#building-a-custom-domain-preset)

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
            manifest.add_file_injection("justfile", content)
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

!!! info "Enforcing Language Constraints"
    If your custom tool is language-specific (like a Python linter or a Rust formatter), declare the `required_languages` tuple as a class attribute (e.g., `required_languages = ("PythonModule",)`). This guarantees that the CLI will dynamically intercept invalid combinations—preventing developers from attempting chaotic anomalies like forcefully shoving Ruff into a strict Node.js environment—by safely dropping the invalid flag and surfacing a terminal warning.

??? abstract "Deep Dive: Pre-flight vs Build"
    - **`pre_flight()`**: Executes before *any* state changes occur. If `shutil.which("just")` fails here, the orchestrator immediately halts, guaranteeing the environment remains untouched.
    - **`build()`**: Only queues state changes. Notice how we use `manifest.add_file_injection()` instead of `Path("justfile").write_text()`.

---

## Building a Custom Domain Preset

Presets sit on top of the base language footprint. They inherit from `PresetModule` in `protostar.presets.base` and strictly define arrays of dependencies and directory structures.

=== "Example Implementation"
    ```python
    from protostar.presets import PresetModule

    class DataEngineeringPreset(PresetModule):
        """Injects ETL and data pipeline dependencies."""

        cli_flags = ("--data-eng",)
        cli_help = "Inject data engineering dependencies"

        @property
        def name(self) -> str:
            return "Data Engineering"

        @property
        def default_dependencies(self) -> list[str]:
            return ["polars", "pyarrow", "duckdb", "dbt-core"]

        @property
        def default_directories(self) -> list[str]:
            return ["pipelines", "data/raw", "data/processed", "tests/data"]

        @property
        def default_ignores(self) -> list[str]:
            return ["*.parquet", "*.duckdb", "dbt_packages/"]

    ```

=== "Preset API"
    !!! abstract "Domain-Specific Dependencies: `PresetModule`"
        ::: protostar.presets.base.PresetModule
            options:
                show_source: true
                show_bases: true
                show_root_heading: true
                show_root_toc_entry: true
                separate_signature: true

!!! info "Configuration Overrides"
    Register your preset in `protostar/presets/__init__.py`. Protostar automatically handles merging any user-defined overrides for these defaults found in their global `config.toml`.

---

## The Manifest API

!!! danger "No Direct Disk I/O"
    Never call `subprocess.run` or write to disk inside a module's `build()` method. Modules must strictly communicate via the `EnvironmentManifest` to ensure the Orchestrator maintains atomicity.

The manifest exposes the following methods to queue state changes:

| Method Signature | Execution Behavior |
| --- | --- |
| `add_dependency(package: str)` | Queues a standard package for resolution. |
| `add_dev_dependency(package: str)` | Queues a development or tooling package. |
| `add_file_injection(path: str, content: str)` | Queues a complete file write. Fails if the file exists unless explicitly marked for overwrite. |
| `add_file_append(path: str, content: str)` | Queues a string payload for late-binding concatenation or TOML AST deep-merging. |
| `add_system_task(command: list[str], timeout: int | None = 30)` | Queues a subprocess command to execute *after* the disk scaffolding phase is complete. Allows an optional execution timeout. |
| `add_post_install_task(command: list[str], timeout: int | None = 30)` | Queues a subprocess command to execute *after* all dependencies have been installed. Allows an optional execution timeout. |
| `add_vcs_ignore(path: str)` | Appends a tracking exclusion entry to the version control ignore manifest (e.g., `.gitignore`). |
