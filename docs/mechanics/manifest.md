# The Environment Manifest

The `EnvironmentManifest` is the critical boundary between declarative intent and imperative execution. It acts as an isolated, centralized state object that guarantees atomicity during environment scaffolding.

By strictly prohibiting modules from mutating the host operating system directly, Protostar isolates side-effects to a single, easily testable execution phase. Think of it as a strict idempotency boundary: side-effects (disk writes, network calls, shell executions) are contained entirely within the Orchestrator's final realization phase.

<div class="grid cards" markdown>

- :material-atom: __Atomicity__

    If a pre-flight check fails or an invalid configuration is evaluated in the final loaded module, the process aborts cleanly. No partial directories are created; no half-written `.toml` files are left behind.

- :material-test-tube: __Testability__

    Because modules only append to this object, the entire scaffolding pipeline can be tested declaratively in memory without mocking the filesystem or performing expensive `subprocess.run` calls.

- :material-merge: __Collision Safety__

    The manifest aggregates all requested files, ignores, and configuration injections in one place, allowing the Orchestrator to detect and resolve target collisions before any destructive operations occur.

</div>

---

## State Architecture

During the `build()` phase, modules utilize the manifest's unified API to register their requirements. The state is structurally categorized to allow the `SystemExecutor` to apply topological sorting to the disk writes.

=== "Dependency Resolution"
    Holds the required packages for the active footprint. These are routed to the configured package manager (e.g., `uv`, `pip`, `npm`) at the very end of the execution lifecycle to maximize network concurrency and prevent fragmented lockfiles.

    * `dependencies`: Core application or scientific libraries.
    * `dev_dependencies`: Tooling, linters, and testing frameworks.

=== "File Operations"
    Manages physical file scaffolding.

    * `directories`: A mathematical set of directories to be scaffolded via `mkdir -p`.
    * `file_injections`: A 1:1 mapping of exact file paths to their raw string contents (e.g., dropping a `.markdownlint.yaml` file).
    * `file_appends`: A mapping of file paths to lists of configuration blocks. Used primarily for late-binding AST deep-merges into files like `pyproject.toml`.

=== "Exclusions & IDE Context"
    Manages visibility across different sub-systems.

    * `vcs_ignores`: Deduplicated patterns for `.gitignore` and `.dockerignore`.
    * `ide_settings`: Key-value dictionaries mapped directly to local IDE workspace configs (e.g., Python interpreter paths).

=== "System Execution"
    Ordered queues of `SystemTask` objects for imperative shell execution, combining commands with explicit timeout boundaries.

    * `system_tasks`: Pre-installation shell commands (e.g., `git init`, `uv init`).
    * `post_install_tasks`: Commands that strictly require the virtual environment or node modules to be present (e.g., `pre-commit install`).

---

## State Serialization

To understand the decoupling, it is helpful to visualize the manifest's internal state. Below is a dynamically generated JSON representation of the aggregate state just before execution, simulating a user running `protostar init --python --astro --ruff`.

--8<-- "manifest_state.md"

!!! tip "Deduplication & Order"
    Notice how lists are utilized for task ordering (which must be executed sequentially), while sets are utilized internally for structural artifacts (like ignores and directories) to prevent redundant I/O requests.

---

## Collision Strategies

When the Orchestrator detects that a collision marker (e.g., an existing `pyproject.toml`) is present in the target workspace, it alters the manifest's `collision_strategy` attribute based on user input or `--force` flags.

The `SystemExecutor` reads this enum to govern its AST mutation logic:

- __`MERGE` (Default):__ Safely injects missing configurations. If a user has a custom line-length defined in their `pyproject.toml`, it is preserved. Missing arrays are appended, but existing scalar values are respected.
- __`OVERWRITE`:__ Forces Protostar's configuration onto the AST. Keys conflicting with Protostar's payload will be updated to match the tool's baseline.
- __`ABORT`:__ Halts execution completely.

---

## API Reference

If you are extending Protostar with custom domains or tooling layers, your `BootstrapModule` will interact directly with the `EnvironmentManifest` instance passed into its `build()` method.

??? abstract "Core Interface: `EnvironmentManifest`"
    ::: protostar.manifest.EnvironmentManifest
        options:
            show_source: true
            show_bases: true
            show_root_heading: false
            show_root_toc_entry: false
            separate_signature: true
            members_order: source

Head over to __[Extending Protostar](../5_mission-control/extending-protostar.md)__ for more information.
