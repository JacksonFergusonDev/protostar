---
description: "The EnvironmentManifest: the one object every module declares into while planning, and the executor reads to make the changes."
---

# The Environment Manifest

The `EnvironmentManifest` is the plan. While planning, each module declares into it what its tool needs: files, settings, dependencies, hooks, CI steps, and commands. Modules never write a file or run a command themselves. The `SystemExecutor` then reads the manifest and makes every change, in one place that rollback covers.

<div class="grid cards" markdown>

- :material-atom: __A failed plan changes nothing__

    Nothing is written while planning, so a plan that fails, because `uv` or `git` is missing or a template is invalid, leaves the project exactly as it was.

- :material-test-tube: __Planning is tested in memory__

    Modules only add to this object, so a test can plan any combination of tools without a filesystem or a subprocess.

- :material-merge: __Existing files are found first__

    Every file the plan writes is in one place, so the orchestrator lists them with `manifest.target_files()` and finds the ones that already exist before anything is written.

- :material-play-speed: __A dry run reads the real plan__

    `--dry-run` and `--dry-run --json` show this object, the same one a real run executes.

</div>

## What the Manifest Holds

The manifest is split into four parts, each its own class: `manifest.dependencies` (`DependencyManifest`), `manifest.filesystem` (`FilesystemManifest`), `manifest.tooling` (`ToolingManifest`), and `manifest.tasks` (`TaskManifest`). A module's `build()` declares into whichever parts its tool needs, and the `SystemExecutor` reads each part at its step in the [execution order](../developer/reconciliation/execution.md#execution-order).

=== "Dependency Resolution (`manifest.dependencies`)"
    Managed by `DependencyManifest`. Holds the packages the project needs, by group. Execution adds them with uv, one `uv add` per group, after the merged configuration is written, so uv resolves them against the final `pyproject.toml` and writes `uv.lock` itself. Only the last `uv add` installs into the environment; the earlier ones just resolve and lock, so a run updates the environment once.

    * `dependencies`: Core application or scientific libraries (`manifest.dependencies.add()`).
    * `dev_dependencies`: Tooling, linters, and testing frameworks (`manifest.dependencies.add_dev()`).
    * `docs_dependencies`: Documentation toolchains and themes (`manifest.dependencies.add_docs()`).
    * `includes`: One dependency group including another, such as `dev` including `docs` (`manifest.dependencies.add_include()`). The files uv writes are declared separately, by `resolver_footprint`.

=== "Filesystem Operations (`manifest.filesystem`)"
    Managed by `FilesystemManifest`. Holds the folders to create, whole files, TOML contributions, named text blocks, and ignore patterns.

    * `directories`: The set of directories to create, each through `TransactionAwareFS` so rollback removes it again (`manifest.filesystem.add_directory()`).
    * `file_injections`: Whole files, by path, with their contents, such as `.readthedocs.yaml` (`manifest.filesystem.add_file_injection()`).
    * `structured`: TOML contributions by path, each with a stable producer name and its content (`manifest.filesystem.add_structured()`). Which paths are seed-only is the target document's policy, not the contribution's. Dependency-affecting metadata declares a resolver footprint.
    * `regions`: Named text blocks appended to files that aren't TOML, by path, each with a stable id and its content (`manifest.filesystem.add_region()`). The id stays the same when the content changes.
    * `vcs_ignores`: Deduplicated patterns for `.gitignore` and `.dockerignore` (`manifest.filesystem.add_vcs_ignore()`).
    * `workspace_hides`: Patterns the editor's file explorer hides (`manifest.filesystem.add_workspace_hide()`).

=== "Tooling & CI Configuration (`manifest.tooling`)"
    Managed by `ToolingManifest`. Holds commit hooks, CI steps, and editor extension recommendations.

    * `pre_commit_hooks` / `pre_commit_local_hooks` / `pre_commit_install_hook_types`: Hooks, and the git hook types to install them for (such as `commit-msg`), added with `manifest.tooling.add_pre_commit_hook()`, `manifest.tooling.add_pre_commit_local_hook()`, and `manifest.tooling.add_pre_commit_hook_type()`.
    * `ci_steps` / `ci_flags`: CI workflow steps and flags (`manifest.tooling.add_ci_step()`, `manifest.tooling.add_ci_flag()`).
    * `ide_extensions`: Editor extensions to recommend (`manifest.tooling.add_ide_extension()`).
    * `wants_docker`: Whether to write the `Dockerfile` and `.dockerignore`.

=== "System Execution (`manifest.tasks`)"
    Managed by `TaskManifest`. Holds the commands to run, in order, as `SystemTask` objects, each with its timeout.

    * `system_tasks`: Commands that run after the files are written and before dependencies install, such as `git init` and `uv init` (`manifest.tasks.add_system_task()`).
    * `post_install_tasks`: Commands that need the installed dependencies, such as `pre-commit install` (`manifest.tasks.add_post_install_task()`).

=== "On the Manifest Itself"
    Fields and methods of `EnvironmentManifest` itself.

    * `metadata`: The project's `ProjectMetadata`: author, license, and package details.
    * `ide_settings`: Editor settings, by key (`manifest.add_ide_setting()`).
    * `collision_strategy`: Chosen `CollisionStrategy` (`MERGE` or `OVERWRITE`), or `null` while a collision decision is pending.
    * `template_reference`: The template's identity (origin, locator, and the SHA-256 of its TOML), or `null` for a tooling-only run. Trust and variable values are never part of it.
    * `one_shot`: Whether the run skips writing the recipe and `protostar.lock`.
    * `collisions`: Files the plan writes that already exist.
    * `target_files()`: Every path Protostar itself writes: whole files, TOML targets, the `Dockerfile`, lockfiles, `.gitignore`, and template files. The orchestrator compares it with the project to find collisions.
    * `planned_files()`: Every file a run leaves behind: the files Protostar writes, plus each command's declared outputs, the resolver's `pyproject.toml` and `uv.lock`, and `protostar.lock`. The dry-run tree, the recipe editor's preview, the change review, and the dry-run JSON `entries` all read it, and `check-snapshots` fails when a scaffold differs from it.

## As JSON

The manifest and each of its four parts have a `.to_dict()` that `protostar init --dry-run --json` prints. The output is the same for the same plan:

- __Sets become sorted lists:__ `directories`, `vcs_ignores`, and `workspace_hides` are sorted alphabetically.
- __Ordered lists keep their order:__ commands and dependencies stay in the order they were declared.
- __Enums and objects become plain values:__ an enum such as `CollisionStrategy` becomes its string value, and each `SystemTask` becomes an object with its `command`, `description`, and `timeout`.

This is the manifest for `protostar init --template astro --dry-run --json`:

```json
--8<-- "manifest_state.json"
```

!!! tip "Lists for order, sets for everything else"
    Commands are lists because they run in order. Folders and ignore patterns are sets, so two modules declaring the same one write it once.

## Collision Strategies

The Orchestrator records existing files the plan would write in `manifest.collisions`, and `plan()` returns them even before any strategy is chosen. `--force-merge` and `--force-replace` choose one in advance; otherwise the recipe editor's Existing files panel does. `execute()` raises `WorkspaceCollisionError` before writing anything while collisions remain and no strategy is set.

- __`MERGE`:__ Reconciles each file against `protostar.lock`. Protostar's own content takes the update, the user's content stays, and each disagreement becomes a conflict, proposed change, or kept edit. Lists with set semantics, such as Ruff's rule lists, gain new members; other lists change as a whole. Project fields such as `description` are written only when missing. See [How Protostar Tracks Your Files](../usage/tracking.md).
- __`OVERWRITE`:__ Writes Protostar's version over each declared target.

Cancelling is a CLI outcome and leaves the project untouched.

## API Reference

A module you add declares into the `EnvironmentManifest` passed to its `build()` method.

??? abstract "Core Interface: `EnvironmentManifest`"
    ::: protostar.manifest.EnvironmentManifest
        options:
            show_source: true
            show_bases: true
            show_root_heading: false
            show_root_toc_entry: false
            separate_signature: true
            members_order: source

## Related Pages

- __[The Orchestrator<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./orchestrator.md):__ How `plan()` builds the manifest and `execute()` hands it on.
- __[The System Executor<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./executor.md):__ How the executor turns the manifest into writes and commands that roll back together.
- __[The Module Architecture<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./modules.md):__ How a module declares its dependencies, files, and settings.
- __[Extending Protostar<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](../developer/extending-protostar.md):__ Add a module for a new tool.
