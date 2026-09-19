---
description: "Review and apply recipe-driven project updates while preserving local intent."
---

# Review and synchronize a project

After `init`, commit `pyproject.toml` and `.protostar.lock.toml`. The
[project recipe](../development/project-recipe.md) records desired selection; the
lock records accepted ownership. Run lifecycle commands from that project's root.
Protostar uses the current directory and never searches ancestors for a project.

## Review, apply, repeat

```bash
protostar init --template cli
protostar status
protostar diff
protostar sync --dry-run
protostar sync
protostar sync --check
```

`status` summarizes accepted updates, conflicts, preserved edits/deletions, and
ownership advancement. `diff` and `sync --dry-run` show the same accepted byte
changes. Conflicts appear separately with file/key/identity diagnostics; a
conflicted file can still have independent accepted edits. Resolver actions list
accepted requirements and their `pyproject.toml`/`uv.lock` footprint. Their output
is unknown until application, so previews do not invent a resulting lockfile diff.

`sync` applies safe edits and composite ownership state transactionally. It never
reruns project initialization, Git initialization, hook installation, arbitrary
template tasks, or IDE extension probes. It is not an environment reinstall or a
package upgrade command. An unchanged repeat writes nothing and runs no subprocess.

Built-in templates come from the installed Protostar version. Local templates use
the recorded locator; remote templates use the exact recorded source. A revision
at the same identity can update the project. Changing template identity, switching
to tooling-only mode, or retargeting an alias is not a supported lifecycle update.
Missing sources fail visibly rather than falling back to cached content.

## Preserve local intent and handle partial updates

Suppose a template changes two settings and you independently edited one of them.
Inspection reports the divergent setting as a conflict and the other as accepted.
`sync` commits the safe setting while retaining your conflicting content and its
previous applied baseline. It returns exit `1` with a partial result; this is a
committed update, not a failed transaction.

```bash
protostar sync --json > sync-result.json
# Exit 1 with status "partial": inspect review.conflicts in sync-result.json.
protostar diff
```

Resolve the desired setting deliberately in your project or same-source template,
then review again. If local content already equals new desired content, Protostar
can advance its baseline without rewriting that content. This still counts as
pending work until `sync` records the advancement.

Local edits or deletions with unchanged desired intent are preserved and do not
make checks fail. Deleted managed files stay deleted. Omitted template
contributions retain their existing files and ownership; sync never prunes them.
Equal foreign content remains unowned.

## Edit the recipe deliberately

Edit entries in `[tool.protostar]` using the
[recipe rules](../development/project-recipe.md). For example:

```toml
[tool.protostar.tools]
renovate = false
mypy = true
```

The `tools` table is left out of `pyproject.toml` until it has an entry, so add it when you need it.

An omitted tool follows current template opinion, then the fallback captured on
initialization. Current global defaults cannot change project selection. An opt-out
suppresses only that tool's contributions and warnings, retaining its previous
files, dependencies, and ownership. Other producers sharing a target still apply.
Re-enabling a tool resumes reconciliation against retained baselines; it does not
restore deleted files or adopt foreign content. Filesystem edits never implicitly
write a recipe opt-out. Captured metadata and year keep rendering repeatable.

## Enroll an existing project

A Stage 1 project needs an explicit recipe. Rerun its original selection:

```bash
protostar init --template cli --force-merge
```

Include the original tooling choices and source as appropriate. Protostar does not
reconstruct a request from the ownership lock. Enrollment preserves existing
ownership and does not adopt equal foreign content. Custom interpolation requires
[environment bindings](../development/project-recipe.md#custom-interpolation).
Missing recipes, malformed state, and missing bindings fail before mutation.

## Use checks in CI

```bash
protostar sync --check --json > review.json
```

| Invocation/outcome | Exit code |
| --- | --- |
| Valid status, diff, or dry-run review, including conflicts | `0` |
| Sync completes with no conflicts, including a no-op | `0` |
| Sync commits safe work and retains conflicts | `1` |
| Check finds accepted edits, resolver work, state advancement, or conflicts | `1` |
| Check finds only preserved local deviations or no work | `0` |
| Fatal error | Domain-specific code; interruption uses `130` |

`--check` and `--dry-run` are mutually exclusive. Check never applies work. All
commands accept `--json` without prompts: stdout contains one deterministic JSON
envelope; diagnostics and subprocess output go to stderr. Check includes
`check_passed`; review uses `status: "reviewed"`; application uses `"success"` or
`"partial"`. See the [machine interface](agent-interface.md) for generated examples
and schema discovery.

## Security and rollback boundaries

Inspection does not write workspace files, populate source caches, run subprocesses,
or prompt. Remote acquisition can access the network outside pure planning and
holds source data in memory. Each invocation captures one source revision and hook
registry snapshot; apply uses those captured decisions without a second fetch.
Trust is not inherited from the recipe or lock. Initialization-only tasks remain
excluded even for trusted external templates.

Custom environment values resolve in memory; bindings record environment names,
not values. Generated files and review diffs contain project content, so diffs are
not a secret-redaction system. Keep credentials out of rendered configuration.

Before mutation, sync checks captured bytes, existence, and modes. Changed inputs
abort as a stale review before the first write. This protects the review/apply
interval, not arbitrary concurrent writes during execution. Symlinks and special
filesystem nodes are rejected for transaction-managed targets.

Fatal resolver failures, timeouts, interrupts, and late state-write failures trigger
[automatic rollback](rollback.md). Managed processes are terminated and reaped
before journaled files are restored to exact original bytes and POSIX modes.
Direct edits, ownership state, and declared resolver `pyproject.toml`/`uv.lock`
paths are covered. `.venv` and global caches remain outside that guarantee.
