---
description: "Understand the EnvironmentManifest: Protostar's central state object for guaranteeing atomicity during scaffolding."
---

# The Environment Manifest

The `EnvironmentManifest` is the critical boundary between declarative intent and imperative execution. It acts as an isolated, centralized state object that guarantees atomicity during environment scaffolding.

By preventing modules from writing to disk directly during planning, Protostar keeps side effects contained to a single, easily testable execution phase. All disk writes, package downloads, and shell commands are held until this final step.

<div class="grid cards" markdown>

- :material-atom: __Atomicity__

    Nothing is written while planning, so a plan that fails, because `uv` or `git` is missing or a template is invalid, leaves the project exactly as it was.

- :material-test-tube: __Testability__

    Because modules only append to this object, the entire scaffolding pipeline can be tested declaratively in memory without mocking the filesystem or performing expensive `subprocess.run` calls.

- :material-merge: __Collision Safety__

    The manifest aggregates all requested files, ignores, and configuration injections in one place, allowing the Orchestrator to dynamically derive planned file paths via `manifest.target_files()` and detect workspace collisions before any disk operations occur.

- :material-play-speed: __Deterministic Simulation__

    Enables side-effect-free execution simulations (`--dry-run`) and programmatic inspection of planned state ahead of disk mutation.

</div>

## State Architecture

Rather than storing all state in a monolithic structure, `EnvironmentManifest` delegates state management to specialized domain classes: `DependencyManifest`, `FilesystemManifest`, `ToolingManifest`, and `TaskManifest`.

During the `build()` phase, modules route their state declarations through these explicit domain namespaces (e.g., `manifest.dependencies`, `manifest.filesystem`, `manifest.tooling`, `manifest.tasks`). This structure allows the `SystemExecutor` to run setup tasks and write files in the correct dependency order.

=== "Dependency Resolution (`manifest.dependencies`)"
    Managed by `DependencyManifest`. Holds the packages the project needs, by group. Execution adds them with uv, one `uv add` per group, after the merged configuration is written, so uv resolves them against the final `pyproject.toml` and writes `uv.lock` itself. Only the last `uv add` installs into the environment; the earlier ones just resolve and lock, so a run updates the environment once.

    * `dependencies`: Core application or scientific libraries (`manifest.dependencies.add()`).
    * `dev_dependencies`: Tooling, linters, and testing frameworks (`manifest.dependencies.add_dev()`).
    * `docs_dependencies`: Documentation toolchains and themes (`manifest.dependencies.add_docs()`).
    * `includes`: Typed dev/docs group include edges (`manifest.dependencies.add_include()`). Resolver-owned files are declared by `resolver_footprint`.

=== "Filesystem Operations (`manifest.filesystem`)"
    Managed by `FilesystemManifest`. Manages physical directory scaffolding, seed-only file injections, structured contributions, named regions, and ignore configurations.

    * `directories`: The set of directories to create, each through `TransactionAwareFS` so rollback removes it again (`manifest.filesystem.add_directory()`).
    * `file_injections`: A 1:1 mapping of exact file paths to their raw string contents (e.g., dropping configuration files like `.readthedocs.yaml` via `manifest.filesystem.add_file_injection()`).
    * `structured`: Path-keyed typed TOML contributions with a stable producer and content (`manifest.filesystem.add_structured()`). Which paths are seed-only is the target document's policy, not the contribution's. Dependency-affecting metadata declares a resolver footprint.
    * `regions`: Path-keyed non-TOML append contributions with stable IDs and content (`manifest.filesystem.add_region()`). IDs remain unchanged across payload revisions.
    * `vcs_ignores`: Deduplicated patterns for `.gitignore` and `.dockerignore` (`manifest.filesystem.add_vcs_ignore()`).
    * `workspace_hides`: Patterns hidden from IDE workspace file explorers (`manifest.filesystem.add_workspace_hide()`).

=== "Tooling & CI Configuration (`manifest.tooling`)"
    Managed by `ToolingManifest`. Configures development tools, CI/CD pipeline steps, pre-commit hooks, and IDE extension recommendations.

    * `pre_commit_hooks` / `pre_commit_local_hooks` / `pre_commit_install_hook_types`: Hook configurations and Git lifecycle hook types (e.g., `commit-msg`) registered via `manifest.tooling.add_pre_commit_hook()`, `manifest.tooling.add_pre_commit_local_hook()`, and `manifest.tooling.add_pre_commit_hook_type()`.
    * `ci_steps` / `ci_flags`: Continuous integration steps and workflow flags (`manifest.tooling.add_ci_step()`, `manifest.tooling.add_ci_flag()`).
    * `ide_extensions`: Recommended IDE extensions queued for workspace configuration (`manifest.tooling.add_ide_extension()`).
    * `wants_docker`: Boolean flag indicating whether Docker containerization artifacts should be scaffolded.

=== "System Execution (`manifest.tasks`)"
    Managed by `TaskManifest`. Maintains ordered queues of `SystemTask` objects for imperative shell execution, combining commands with explicit timeout boundaries.

    * `system_tasks`: Pre-installation shell commands executed after filesystem scaffolding (e.g., `git init`, `uv init` queued via `manifest.tasks.add_system_task()`).
    * `post_install_tasks`: Commands that strictly require the virtual environment or installed dependencies to be present (e.g., `pre-commit install` queued via `manifest.tasks.add_post_install_task()`).

=== "Root Settings & Footprint"
    Attributes and inspection methods directly bound to the root `EnvironmentManifest` instance.

    * `metadata`: Structured `ProjectMetadata` dictionary defining author, licensing, and package specs.
    * `ide_settings`: Key-value dictionaries mapped directly to local IDE workspace configs via `manifest.add_ide_setting()`.
    * `collision_strategy`: Chosen `CollisionStrategy` (`MERGE` or `OVERWRITE`), or `null` while a collision decision is pending.
    * `template_reference`: The template's identity (origin, locator, and the SHA-256 of its TOML), or `null` for a tooling-only run. Trust and variable values are never part of it.
    * `one_shot`: Whether execution omits the recorded recipe and Protostar ownership state after scaffolding.
    * `collisions`: Existing workspace paths that intersect planned file writes.
    * `target_files()`: Pure method returning the complete set of concrete `Path` objects Protostar intends to create or mutate (file injections, TOML targets, Dockerfiles, lockfiles, `.gitignore`, and templated blueprint files). Used by the Orchestrator for dynamic collision detection.
    * `planned_files()`: Every file a run leaves behind: the files Protostar writes, plus each command's declared outputs, the resolver's `pyproject.toml` and `uv.lock`, and `protostar.lock`. The dry-run tree, the recipe editor's preview, the change review, and the dry-run JSON `entries` all read it, and `check-snapshots` fails when a scaffold differs from it.

## State Serialization

Every sub-manifest (`DependencyManifest`, `FilesystemManifest`, `ToolingManifest`, `TaskManifest`) as well as the root `EnvironmentManifest` implements a deterministic `.to_dict()` serialization method.

This method enables machine interfaces (such as `protostar init --dry-run --json`) and external tooling to inspect the full planned environment state:

- __Sets Become Sorted Lists:__ Unordered set collections (such as `directories`, `vcs_ignores`, `workspace_hides`) are sorted alphabetically for deterministic JSON output.
- __Ordered Lists Preserved:__ Sequential task queues and dependency lists maintain their exact insertion order.
- __Enums & Objects:__ Enums (such as `CollisionStrategy`) are emitted as string values, and `SystemTask` objects are serialized as structured dictionaries (`command`, `description`, `timeout`).

Below is an example JSON representation of an aggregate state during a dry-run of `protostar init --template astro --dry-run --json`:

```json
--8<-- "manifest_state.json"
```

!!! tip "Deduplication & Order"
    Notice how lists are utilized for task ordering (which must be executed sequentially), while sets are utilized internally for structural artifacts (like ignores and directories) to prevent redundant I/O requests.

## Collision Strategies

The Orchestrator records existing files the plan would write in `manifest.collisions`, and `plan()` returns them even before any strategy is chosen. `--force-merge` and `--force-replace` choose one in advance; otherwise the recipe editor's Existing files panel does. `execute()` raises `WorkspaceCollisionError` before writing anything while collisions remain and no strategy is set.

- __`MERGE`:__ Reconciles each file against `protostar.lock`. Protostar's own content takes the update, the user's content stays, and each disagreement becomes a conflict, proposed change, or kept edit. Lists with set semantics, such as Ruff's rule lists, gain new members; other lists change as a whole. Project fields such as `description` are written only when missing. See [How Protostar Tracks Your Files](../usage/tracking.md).
- __`OVERWRITE`:__ Writes Protostar's version over each declared target.

Cancelling is a CLI outcome and leaves the project untouched.

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

## Related Mechanics & Guides

- __[The Orchestrator<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./orchestrator.md):__ Learn how the engine coordinates the planning and execution phases using the manifest.
- __[The System Executor<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./executor.md):__ Discover how the manifest is transformed into atomic disk mutations and managed subprocesses.
- __[The Module Architecture<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./modules.md):__ Understand how modules declare dependencies, file injections, and AST appends.
- __[Extending Protostar<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](../developer/extending-protostar.md):__ Build custom bootstrap modules that interact directly with `EnvironmentManifest`.
