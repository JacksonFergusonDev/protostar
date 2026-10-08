---
description: "How reconciliation runs inside a transaction: state ordering, dependency resolution, shared review preparation, and the acceptance suite."
---

# Execution and Review

Reconciliation is pure, but it runs inside the [executor's](../../mechanics/executor.md) transaction. This page covers the rules that connect the two: what is read before mutation, in what order things are written, how dependencies are resolved, and how review and apply share one preparation.

## Execution Boundary

- Read and validate state before any mutation.
- Filesystem node safety and the workspace jail stay the executor's responsibility. A pure string codec cannot inspect symlinks or ancestor workspaces.
- Missing state must never adopt existing content.
- Pass only applied owned contributions to the snapshot encoder.

## Execution Order

This is the one description of the order execution runs in; the mechanics pages link here. `SystemExecutor.execute()` runs everything inside one transaction, and prepares its decisions in batches named by `PreparationPhase`. Each batch is prepared only once the files it reads exist, so a batch that merges into `pyproject.toml` runs after `uv init` creates it.

### `init`

1. **`BEFORE_INITIALIZERS`**: migrations, released content, directories, and whole files no command creates. The CLI shows this as "Writing project files".
1. **System tasks**: the initializers `git init` and `uv init` when the project lacks them, then the template's `system_tasks`.
1. **`BEFORE_RESOLVER`**: merged configuration, append regions, and dependency selection, then the resolver: one `uv add` per dependency group, or a single `uv lock` when only metadata or include edges changed. Every `uv add` but the last passes `--no-sync`: each still resolves and locks, so a bad requirement fails at its own command, and the last installs the whole environment once instead of once per group. By this point every choice the change review made must have matched a decision, or execution raises `StaleReviewError`.
1. **`AFTER_RESOLVER`**: ignore rules, container files, and editor settings, which depend on the resolved project.
1. **Post-install tasks**, such as a hook install, then the editor extension probe.
1. **`RECIPE`**: the recipe in `pyproject.toml`, written after everything it records. A one-shot run skips it.
1. **State**: `protostar.lock` is written last, then the journal commits.

The change review shows what can be known before any command runs: `review_phase()` returns `BEFORE_COMMANDS`, both batches before the resolver, when no initializer creates a file the second batch reads (as in a project that already has its `pyproject.toml`), and `BEFORE_INITIALIZERS` otherwise. Files later batches create are listed as "after setup".

### `sync`

A lifecycle run has no initializer between batches, so `prepare_review()` prepares `COMPLETE`, every batch at once, before anything runs. Execution applies that review's edits, runs only its accepted resolver requests, converges git hooks, and writes `protostar.lock`, then commits. It runs no system task, post-install task, or editor probe.

### Write Rules

1. Apply accepted changes through format ASTs and `TransactionAwareFS`.
1. Stage composite baselines in a candidate.
1. Write state only after all declared writes and resolver actions succeed.
1. Skip writes when the resulting bytes already match.
1. Commit state before the journal commit, so a failure restores exact original file and state bytes and modes.

Any exception terminates managed processes and rolls the journal back; see [Rollback Internals](../../mechanics/rollback.md).

## Conflict Diagnostics

Expected merge conflicts preserve the affected values and become structured warnings, while malformed state stays fatal. The executor aggregates module contributions in declared sequence order, then applies template opinions once. Unclassified conflicting producers fail before any mutation.

Conflict diagnostics carry the file, key path, optional identity, and an enum reason in `ExecutionResult.to_dict()`. Safe siblings can apply despite other conflicts, and existing equal values remain unowned.

A tracked deleted file cannot be recreated by initializer tasks, new dependency requests, include-group wiring, or newly requested tooling. The executor captures a deleted tracked `pyproject.toml` before running `uv init`, including projects tracked only through dependency records. Explicit overwrite can still initialize that file again.

## Dependency Selection

Selection is per group, canonical package name, and normalized marker. Extras, bounds, and direct references remain requirement values.

- Unchanged declared dependency intent skips `uv add`, even when the materialized requirement gained resolver bounds or the user later edited or deleted it.
- Changed intent needs an unchanged materialized baseline.
- Unowned existing constraints, duplicate identities, known version regressions, and ambiguous constraint changes are preserved with warnings.
- Converged previously owned intent advances its record without a resolver call.
- Only accepted requests invoke `uv add`. A successful request records both the declared intent and the actual materialized requirement, and matching foreign entries remain unowned.

### Requirements in Other Groups

Before adding an unowned requirement to an empty destination, selection checks the other dependency groups (including custom groups), project dependencies, and optional dependencies for the same normalized package and marker. An existing entry produces a `different-group` conflict in both review and execution.

- Keeping the current placement acknowledges the absent destination entry.
- Taking the update adds to the requested group without moving or adopting the existing entry.
- Include records do not hide the entries in their source groups.
- Explicit overwrite still authorizes the addition.

## Resolver

System tasks establish the local project first (`uv init` when needed). Structured TOML and accepted typed include edges then apply before any dependency resolver.

Accepted `requires-python` or include-edge writes mark resolution dirty. A later accepted `uv add` resolves the final metadata and clears that flag. Otherwise one `uv lock` runs after all relevant writes, and identical repeats run neither command.

Include ownership records only managed edges, and groups created for them, in the owned TOML baseline. Foreign requirements and include records are never copied into ownership.

- Deleted owned edges and groups stay deleted, including when a new requirement would otherwise recreate their group.
- Ambiguous include identities preserve local content with a conflict.
- A resolver needs a local project and a footprint containing both `pyproject.toml` and `uv.lock`. Ancestor workspace ownership is rejected.

Both resolver paths are journaled before invocation. Failures and timeouts are fatal, and an interrupt terminates managed processes before rollback restores the exact original project, lock, and state bytes and modes. `.venv` and global caches remain outside the rollback boundary.

There is no AST dependency rewrite, no implicit upgrade, and no redundant lock after an ordinary dependency addition.

## Shared Preparation

`protostar.preparation.prepare_review()` computes, from a manifest and captured workspace inputs:

- Immutable accepted file bytes.
- Conflicts and preserved local deviations.
- Candidate ownership.
- Resolver requests.

It uses the TOML, YAML, keyed-hook, region, and text adapters through `Reconciliation`. Preparation writes only to an in-memory byte sink and never runs initializers, package managers, template tasks, IDE probes, or registry acquisition.

Tool selection resolves project overrides, current template opinions, and the captured fallback before effective modules declare their executables or contributions. Producer attribution survives into the review, so opting out of one producer does not suppress another producer contributing to the same target.

### Applying a Review

The caller supplies one acquired hook revision snapshot. A `SystemExecutor` constructed with `review=review` consumes that snapshot and the exact accepted bytes without acquiring pins again.

The lifecycle policy skips every declared system and post-install task and the IDE extension probe. It applies direct edits and only accepted resolver requests, materializes dependency ownership from actual resolver output, and writes the ownership ledger last within the same transaction. Resolver output stays unknown in review data: there is no simulated dependency rewrite and no fabricated `uv.lock` diff.

`init` keeps its own policy and prepares successive batches around actual initializer and resolver execution. Original transaction presence still distinguishes eligible initializer-created values from pre-existing user values. The recipe refresh stays after post-install tasks and inside the state transaction.

### Stale Reviews

Captured inputs are the exact bytes, existence, POSIX modes, relevant ancestors, `pyproject.toml`, `protostar.lock`, and declared resolver paths. Unsupported nodes fail during preparation.

Immediately before applying a batch, execution checks the desired manifest and all captured inputs. A stale review fails before that batch mutates anything, and fatal failures terminate managed processes and roll back exact journaled bytes and modes.

!!! note
    This protects the interval between preparation and application. It does not exclude concurrent writers during a transaction.

## Safe Reinitialization

`init --force-merge` is safe reinitialization, not an update product. It requires the same selected template identity for a tracked project and reconciles only recorded contributions. It does not:

- Adopt pre-existing files on its own. Only a `local` resolution of an `unowned` conflict adopts one.
- Restore user-deleted content.
- Switch templates.
- Reconstruct or rerun a request from the lock state.

Omitted contributions are retracted exactly as `sync` retracts them. Updating a tracked project is `sync`'s job; see the [lifecycle guide](../../usage/lifecycle.md).

## Acceptance Suite

Broad end-to-end evidence is kept apart from focused synthetic-revision cases.

`tests/test_template_repeatability.py`
:   Executes every built-in template in an isolated workspace, then performs two identical merge runs. It asserts byte-identical workspace and lock state, no managed mutations on either repeat, and exact-byte agreement between every persisted whole-file text baseline and its generated artifact.

Synthetic revisions
:   `tests/test_reconciliation_execution.py`, `tests/test_codecov_execution.py`, `tests/test_pre_commit_reconciliation.py`, `tests/test_generated_execution.py`, and `tests/test_resolver_execution.py` provide synthetic v1-to-v2 revisions plus conflict and failure cases. They cover non-overlapping edits, scalar, keyed, and sequence conflicts, deletion protection, state-write rollback, resolver rollback, and generated and region baseline advancement.

Rejected input
:   `tests/test_sync_state.py`, `tests/test_yaml_ast.py`, and `tests/test_intent.py` reject invalid state, unsupported YAML structures, unsafe paths, duplicate identities, reserved targets, and unsupported control keys before any execution mutation.
