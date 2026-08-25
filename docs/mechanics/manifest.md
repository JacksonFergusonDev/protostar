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

Rather than storing all state in a monolithic structure, `EnvironmentManifest` delegates state management to specialized domain classes: `DependencyManifest`, `FilesystemManifest`, `ToolingManifest`, and `TaskManifest`.

During the `build()` phase, modules route their state declarations through these explicit domain namespaces (e.g., `manifest.dependencies`, `manifest.filesystem`, `manifest.tooling`, `manifest.tasks`). This composition allows the `SystemExecutor` to cleanly apply topological sorting to disk writes and execution tasks.

=== "Dependency Resolution (`manifest.dependencies`)"
    Managed by `DependencyManifest`. Holds the required packages for the active footprint. These are routed to the configured package manager (e.g., `uv`, `pip`, `npm`) at the very end of the execution lifecycle to maximize network concurrency and prevent fragmented lockfiles.

    * `dependencies`: Core application or scientific libraries (`manifest.dependencies.add()`).
    * `dev_dependencies`: Tooling, linters, and testing frameworks (`manifest.dependencies.add_dev()`).
    * `docs_dependencies`: Documentation toolchains and themes (`manifest.dependencies.add_docs()`).

=== "Filesystem Operations (`manifest.filesystem`)"
    Managed by `FilesystemManifest`. Manages physical directory scaffolding, file injections, AST appends, and ignore configurations.

    * `directories`: A mathematical set of directories to be scaffolded via `mkdir -p` (`manifest.filesystem.add_directory()`).
    * `file_injections`: A 1:1 mapping of exact file paths to their raw string contents (e.g., dropping a `.markdownlint-cli2.yaml` file via `manifest.filesystem.add_file_injection()`).
    * `file_appends`: A mapping of file paths to lists of configuration blocks used primarily for late-binding AST deep-merges into files like `pyproject.toml` (`manifest.filesystem.add_file_append()`).
    * `vcs_ignores`: Deduplicated patterns for `.gitignore` and `.dockerignore` (`manifest.filesystem.add_vcs_ignore()`).
    * `workspace_hides`: Patterns hidden from IDE workspace file explorers (`manifest.filesystem.add_workspace_hide()`).

=== "Tooling & CI Configuration (`manifest.tooling`)"
    Managed by `ToolingManifest`. Configures development tools, CI/CD pipeline steps, pre-commit hooks, and IDE extension recommendations.

    * `pre_commit_hooks` / `pre_commit_local_hooks`: Hook configurations registered via `manifest.tooling.add_pre_commit_hook()` and `manifest.tooling.add_pre_commit_local_hook()`.
    * `ci_steps` / `ci_flags`: Continuous integration steps and workflow flags (`manifest.tooling.add_ci_step()`, `manifest.tooling.add_ci_flag()`).
    * `ide_extensions`: Recommended IDE extensions queued for workspace configuration (`manifest.tooling.add_ide_extension()`).

=== "System Execution (`manifest.tasks`)"
    Managed by `TaskManifest`. Maintains ordered queues of `SystemTask` objects for imperative shell execution, combining commands with explicit timeout boundaries.

    * `system_tasks`: Pre-installation shell commands executed after filesystem scaffolding (e.g., `git init`, `uv init` queued via `manifest.tasks.add_system_task()`).
    * `post_install_tasks`: Commands that strictly require the virtual environment or installed dependencies to be present (e.g., `pre-commit install` queued via `manifest.tasks.add_post_install_task()`).

=== "Root Settings"
    Attributes directly bound to the root `EnvironmentManifest` instance.

    * `metadata`: Structured `ProjectMetadata` dictionary defining author, licensing, and package specs.
    * `ide_settings`: Key-value dictionaries mapped directly to local IDE workspace configs via `manifest.add_ide_setting()`.
    * `collision_strategy`: Active `CollisionStrategy` (`MERGE`, `OVERWRITE`, `ABORT`).

---

## State Serialization

Every sub-manifest (`DependencyManifest`, `FilesystemManifest`, `ToolingManifest`, `TaskManifest`) as well as the root `EnvironmentManifest` implements a deterministic `.to_dict()` serialization method.

This method enables machine interfaces (such as `protostar init --dry-run --json`) and external tooling to inspect the full planned environment state:

- __Sets $\to$ Sorted Lists:__ Unordered set collections (such as `directories`, `vcs_ignores`, `workspace_hides`) are sorted alphabetically for deterministic JSON output.
- __Ordered Lists Preserved:__ Sequential task queues and dependency lists maintain their exact insertion order.
- __Enums & Objects:__ Enums (such as `CollisionStrategy`) are emitted as string values, and `SystemTask` objects are serialized as structured dictionaries (`command`, `description`, `timeout`).

Below is an example JSON representation of an aggregate state during a dry-run of `protostar init --template astro --dry-run --json`:

```json
--8<-- "manifest_state.json"
```

!!! tip "Deduplication & Order"
    Notice how lists are utilized for task ordering (which must be executed sequentially), while sets are utilized internally for structural artifacts (like ignores and directories) to prevent redundant I/O requests.

---

## Collision Strategies

When the Orchestrator detects that a collision marker (e.g., an existing `pyproject.toml`) is present in the target workspace, it alters the manifest's `collision_strategy` attribute based on user input or `--force-merge` / `--force-replace` flags.

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

Head over to __[Extending Protostar](../mission-control/extending-protostar.md)__ for more information.
