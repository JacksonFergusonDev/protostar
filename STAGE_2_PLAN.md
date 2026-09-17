# Stage 2: Developer-facing lifecycle commands

## Mission and authority

Turn Stage 1's reconciliation foundation into a repeatable project lifecycle:
inspect pending changes, review accepted updates and conflicts, and apply safe
updates without reconstructing the original `init` invocation.

**Preserve user intent, not merely comments. Never implement a whole-tree text
merge.** Stage 2 reuses the Stage 1 ownership rules; it does not relax them.

This document is the implementation contract for Stage 2 agents. Decisions marked
settled are requirements, not invitations to explore alternative products. Each PR
must satisfy its acceptance gates before its dependents proceed. If a requirement
proves incompatible with an existing invariant, report the specific conflict and
revise this plan explicitly before implementing a different behavior. Do not
silently expand scope. Repository `AGENTS.md` remains authoritative for engineering
conventions and transactional, headless, and machine-mode invariants.

## Starting point

Stage 1 is complete, as documented in
[semantic reconciliation contracts](docs/development/semantic-reconciliation.md).
Relevant implementation boundaries are:

- `sync_state.py`: schema-v1 `.protostar.lock.toml`, applied ownership baselines,
  dependency materialization, hook provenance, and template identity checks.
- `merge.py` and format/file adapters: semantic three-way decisions, round-trip
  structured edits, checksum gates, seeds, and named regions.
- `orchestrator.py`: manifest-first planning and headless execution boundary.
- `executor.py`: reconciliation currently interleaved with transactional writes,
  dependency resolution, initialization, and post-install tasks.
- `cli/main.py`: resolves templates, global defaults, tooling flags, interpolation,
  metadata, and trust before building an `InitRequest`.

The lock is evidence of successful contributions, **not a replayable request**.
The current `init --dry-run` displays a manifest, not the changes reconciliation
would accept. A lifecycle command must not simply call today's `init` handler with
inferred flags, nor run the executor in a temporary directory to simulate a preview.

## Settled decisions and scope boundaries

### Command surface

Stage 2 adds exactly three project commands:

| Command | Contract |
| --- | --- |
| `protostar status` | Read-only summary of applicable updates, conflicts, preserved local deviations, and baseline-only advancement. |
| `protostar diff` | Read-only review of accepted file edits plus separate conflict details and proposed resolver actions. |
| `protostar sync` | Apply accepted updates transactionally; preserve conflicting local content and report partial completion. |
| `protostar sync --dry-run` | Produce the same review data as `diff`, without executing anything. |
| `protostar sync --check` | Read-only CI check: fail if accepted work or conflicts remain. |

All commands support `--json` and existing global verbosity/help conventions.
They operate on the current directory as the explicit project root. Do not search
ancestor directories, introduce `--project`, or infer an ancestor uv workspace.
`sync --dry-run` and `sync --check` are mutually exclusive.

There are no template, tooling, merge, overwrite, upgrade, or trust override flags
on these commands. Desired selection changes are deliberate edits to
`[tool.protostar]`. `init` keeps its existing creation and explicit reinitialization role.
Its existing manifest dry-run remains a distinct documented operation.

### Project recipe versus applied state

Add a versioned, human-editable `[tool.protostar]` table in `pyproject.toml` as the
project recipe. Keep `.protostar.lock.toml` as the separate machine ownership
ledger. Both belong in version control. The recipe table is user space: templates,
modules, and generic structured contributions are strictly prohibited from
injecting or mutating it. It is external input to `plan()`, never a template
opinion, and entirely excluded from three-way reconciliation and owned baselines.

The table records complete effective project selection: resolved template source
identity or explicit tooling-only mode; resolved Python, Docker, and IDE choices;
explicit tooling overrides; and non-secret built-in rendering context needed for
deterministic generation. Freeze metadata and `CURRENT_YEAR` at recipe
establishment; lifecycle runs must not consult the clock, Git author settings, or
changed global defaults to regenerate content.

`[tool.protostar.tools]` is the living diversion ledger. An omitted tool follows
the current same-source template opinion, then the captured fallback. `true` is an
explicit request; `false` is an explicit opt-out that suppresses that tool's future
contributions and related warnings. Do not write all tools as booleans during
initialization: absence is meaningful, because it permits same-source template
evolution. Capture original global defaults as a fixed fallback. Resolution
precedence is explicit project overrides, current template opinions, then captured
fallback; never current global defaults. Model these layers and contribution
attribution explicitly rather than flattening away their provenance.

Do not persist arbitrary interpolation answers, secrets, trust authorization,
rendered whole-template snapshots, or the original command line. Templates needing
custom interpolation must use explicit variable-to-environment-name bindings in
`[tool.protostar]`. Resolve values in memory; missing bindings or values fail with an
actionable domain error and never prompt. Do not echo values into recipe, lock,
logs, or error messages. File diffs inherently contain project content; do not
promise that review output is a secret-redaction system.

Use `tomlkit` for recipe-table edits, strict typed models for discrete choices, and
reject unknown versions, fields, identities, and unsafe paths. Reserve the complete
`tool.protostar` subtree against template contributions, including ancestor-table
replacement and explicit overwrite. Preserve all foreign `pyproject.toml` content,
comments, and table layout through round-trip AST edits. Keep ownership state schema
v1 unless an actual ownership requirement demands a separately reviewed schema
change. Moving project intent into `pyproject.toml` is not a reason to rename or
migrate the ownership ledger.

Successful non-dry-run `init` establishes or refreshes the recipe table from the
explicit request. Unspecified init flags preserve existing explicit entries; an
explicit CLI selection updates only its corresponding entry. The recipe table and
ownership state commit inside the same filesystem transaction. On a tracked
project, recipe refresh must still pass the existing template identity guard.
Conflicts can commit desired recipe changes with composite applied baselines:
the table means requested intent; the lock means what was actually accepted.

A Stage 1 project without a recipe is not automatically reconstructed. Lifecycle
commands fail with a hint to rerun the original explicit selection through
`init --force-merge`. That run establishes replayable intent without adopting
existing equal content. This is explicit enrollment, not a compatibility shim.
If custom interpolation cannot be expressed through environment bindings, fail
recipe establishment before mutation and explain how to configure bindings.

### Template revisions, source identity, and acquisition

Built-ins resolve from the installed Protostar version. Local sources resolve
from their recorded locator; recipe-local relative paths resolve against the
project root and are normalized into the existing identity contract. External
sources retain the existing resolver's file/directory/archive behavior. Remote
sources are fetched through the existing acquisition boundary, before pure
planning, using the exact recorded source rather than re-resolving an alias.

A changed digest at the same identity is an ordinary update. Switching templates,
alias retargeting, changing source identity, and tooling/template transitions fail.
Do not invent a version-selection, channel, upgrade, migration, or template cache
product. Missing sources and acquisition failures fail visibly; never silently
use an old or unrelated template.

Read-only means no workspace or recipe/state mutations, no subprocesses, and no
cache population by lifecycle inspection. Network acquisition is allowed only
outside `plan()` and uses in-memory source data for inspection. Capture one source
revision and one hook registry snapshot per invocation. Preview and execution use
those same bytes and pins; no refetch between review and apply. Pin fallback and
regression guards remain unchanged. Trust is never inherited from the recipe or
lock; source acquisition retains existing security checks.

### Shared preview and execution

Extract read-only preparation from executor mutation methods. One shared
reconciliation path must compute accepted edits, conflicts, composite candidate
baselines, and accepted resolver requests for preview and execution. Do not fork a
second merge implementation for `status` or `diff`.

Keep `plan() -> EnvironmentManifest` read-only. Add a separate headless preparation
boundary over the manifest, validated ownership state, and workspace inputs; it
returns immutable typed review data. Execution consumes the prepared decisions
through `SystemExecutor` and `TransactionAwareFS`. No UI, shell commands, resolver,
initializer, hooks, or IDE probes run during preparation.

Review data distinguishes:

- Accepted direct file edits, including creates and independent region edits.
- Conflicts with existing file/key/identity/reason diagnostics.
- Preserved local edits or deletions with unchanged desired intent; these are
  informational, not conflicts or pending work.
- Baseline/provenance advancement without a content write.
- Resolver actions and their declared `pyproject.toml`/`uv.lock` footprint.

Unified textual diffs are a presentation of already accepted byte changes only.
They are never a merge algorithm. Structured conflicts identify semantic paths;
checksum conflicts identify files/regions. Do not manufacture whole-file remote
replacements for conflicted files. Omitted contributions remain owned and retained.

Do not pretend to know resolver output in advance. Show accepted requirements and
conditional lock actions; mark derived output as unknown until execution. No
preview `uv add`, `uv lock`, dependency AST rewrite, or fabricated lock diff.

Validate relevant inputs before mutation. Record exact bytes/existence/modes and
reject unsupported nodes for read targets, recipe, and state. Immediately before
execution, revalidate the captured inputs; a mismatch aborts before mutation with a
stale-review domain error. This protects the prepare/apply interval; it is not a
promise of protection against arbitrary concurrent writers during a transaction.
Persisted/exported executable plans and cross-process locks are outside Stage 2.

### Lifecycle side effects

`sync` updates declared configuration, generated artifacts, named regions,
additive ignores, accepted dependencies, and applied state. Never rerun `uv init`,
`git init`, hook installation, arbitrary template system/post-install tasks, or IDE
extension probes. Task declarations are excluded by explicit lifecycle policy and
reported as initialization-only; never classify task safety by command-string
heuristics. A deleted project or managed file stays deleted under Stage 1 rules.
New managed paths may be added only when those same rules permit them.

Removing a tool or omitting a contribution stops requesting it; it does not remove
old files, dependencies, hooks, groups, or ownership records. `sync` is not `uv sync`
and is not an environment reinstall or a dependency upgrade command.

An explicit tool opt-out applies only to contributions attributed to that tool. It
cannot suppress another producer that shares a file, dependency group, hook
repository, or generated target. It does not infer itself from deletion or editing:
filesystem drift remains protected implicit intent until a user deliberately edits
`[tool.protostar.tools]`. Re-enabling a tool resumes ordinary reconciliation against
the retained baseline; it never restores deleted content, adopts foreign content,
or resets ownership.

Resolver failures/timeouts remain fatal. Terminate managed subprocesses before
rollback. Journal direct mutations and declared resolver paths before mutation;
write state last, before journal commit. Restore exact original bytes and POSIX
modes on failure. `.venv` and global caches remain outside the rollback guarantee.
A fully unchanged repeat writes nothing and runs no subprocess.

### Outcomes and machine contract

Use one deterministic review model for human rendering and JSON serialization.
Sort sets and paths; emit relative POSIX paths. Preserve existing structured domain
error envelopes and POSIX error codes. JSON stdout contains exactly one envelope;
all progress, diagnostics, and subprocess output use stderr. No lifecycle prompts.

| Outcome | Exit code |
| --- | --- |
| Read-only inspection with a valid review, including conflicts | `0` |
| `sync` completes without conflicts, including a no-op | `0` |
| `sync` commits safe changes but retains conflicts | `1` |
| `sync --check` finds accepted work, state-only advancement, or conflicts | `1` |
| `sync --check` finds only intentionally preserved local deviations | `0` |
| Fatal error | Existing domain-specific exit code |

JSON review outcomes use `status: "reviewed"`; application outcomes use
`"success"` or `"partial"`; fatal errors use `"error"`. Check mode includes an
explicit `check_passed` boolean. Partial application is a committed result, not a
rollback error. Baseline-only changes count as work because state still needs to
advance. Version the CLI schema explicitly when publishing these new envelopes;
update schema discovery and fixtures together. Do not retain obsolete API aliases.

### Explicitly excluded work

Do not add adoption/import, pruning/uninstall, restore/reset, template switching,
state repair, historical state migrations, interactive conflict resolution,
whole-tree text merging, semantic Renovate/JSONC editing, new format adapters,
package upgrades, task replay, daemon/watch mode, or a general plugin framework.
Do not add a project-config editor command. Existing generated Renovate output
continues to use Stage 1's checksum gate. Any such capability needs a separate
stage and decision document.

## PR sequence and acceptance gates

Implement the following dependency chain. Each PR is independently reviewable and
must leave existing `init` behavior and Stage 1 acceptance tests passing. No PR
may advertise a command whose backend is still a stub.

### PR 1: `feat(recipe): persist project intent in pyproject`

**Purpose:** Make future updates reproducible without changing ownership rules.

- Introduce strict `[tool.protostar]` models, TOML codec, source/selection
  resolution, complete-subtree reservation, and environment-binding support.
- Refactor CLI selection assembly into shared typed helpers; capture override,
  template, fallback, and per-contribution attribution plus stable built-in context.
- Establish the recipe table transactionally during real `init`; dry-run writes
  neither the recipe table nor lock. Reinitialization preserves unspecified
  divergences and applies only explicit requested selections.
- Document enrollment for Stage 1 projects and custom-variable binding syntax.

**Acceptance:** Round trips are deterministic; malformed/unsafe recipes fail before
mutation; changing global defaults cannot change replayed selection; template
opinions evolve only beneath omitted entries. `true`/`false` overrides remain
authoritative and an opt-out does not suppress unrelated producers. Templates cannot
write, own, replace, or reconcile `tool.protostar`; foreign pyproject content and
formatting survive a recipe edit. Secrets and trust are not serialized. Failure
after either recipe-table or lock write restores both. Repeated identical
initialization has no new writes. No lifecycle command is exposed yet.

**Boundary:** No state reconstruction, ownership adoption, schema migration, or
new review/command behavior.

### PR 2: `refactor(reconcile): share read-only preparation with execution`

**Purpose:** Make review an accurate view of the decisions execution will consume.

- Extract pure decisions and byte preparation from adapters/executor into a flat,
  immutable prepared-review model, keeping the existing kernel and ownership rules.
- Make preparation resolve the diversion ledger before building desired
  contributions, and retain producer attribution so an opt-out only suppresses its
  own contributions in shared targets.
- Add explicit initialization versus lifecycle execution policy; filter tasks and
  probes by declaration/policy, not command text.
- Integrate prepared decisions into transactional execution; retain init-specific
  sequencing around initializers and resolver-materialized requirements.
- Add captured-input validation and stale-review rejection before mutations.
- Treat resolver outputs as execution-only and journal their declared footprint.

**Acceptance:** Preview has no writes, subprocesses, registry refetches, or prompts.
Accepted prepared bytes match applied direct edits with mocked resolvers. Test
safe siblings beside conflicts, deleted ancestors, keyed YAML, generated files,
regions, include edges, state-only convergence, explicit opt-outs in shared files,
and stale `pyproject.toml`/lock inputs.
Run existing Stage 1 focused execution suites and built-in repeatability tests.
Initialization still owns only eligible initializer-created values.

**Boundary:** No public lifecycle commands, new merge semantics, or speculative
executor framework. This PR must not force init through lifecycle task suppression.

### PR 3: `feat(cli): add project status and diff reviews`

**Purpose:** Give developers a usable, trustworthy inspection workflow first.

- Add `status` and `diff`, shared recipe/source loading, in-memory inspection
  acquisition, and one frozen registry snapshot.
- Add concise human summaries, accepted-change unified diffs, semantic conflict
  details, preservation information, state-only work, and unknown resolver output.
- Publish deterministic JSON review schema, schema discovery, help, completion,
  and command documentation in this PR.

**Acceptance:** Human and JSON modes agree on decisions. Missing recipe table/state,
invalid sources, missing variable values, and identity changes fail actionably.
Inspection preserves workspace bytes/modes and does not populate caches. All
conflict categories are addressable without showing an unsafe replacement as an
accepted edit. Shell/process spies prove zero subprocess execution. Review exits
follow the settled table.

**Boundary:** No application, trust prompts, plan export, or resolver simulation.

### PR 4: `feat(cli): apply safe lifecycle updates with sync`

**Purpose:** Complete the review-to-apply lifecycle with explicit partial outcomes.

- Add `sync`, `--dry-run`, and `--check` using the same preparation and renderers.
- Execute lifecycle policy only, apply safe siblings, retain conflicting baselines,
  and commit candidate state atomically with direct changes.
- Add application/partial JSON schemas, exit handling, rollback reporting, and
  command help/completion/docs together.

**Acceptance:** Preview/direct-apply parity holds for a captured revision. Safe
changes commit beside conflicts with exit `1`; fatal failures restore the entire
transaction. Check mode is read-only and distinguishes pending work from preserved
user intent. Changed dependencies invoke only accepted resolver requests;
metadata-only changes resolve once; unchanged repeats run no resolver or task.
Deleted tracked files remain absent. Initialization-only tasks and IDE probes never
run, including tasks from trusted external templates.

**Boundary:** No force/overwrite mode, pruning, task execution escape hatch, or
implicit dependency upgrades.

### PR 5: `test(lifecycle): verify stage 2 acceptance and publish workflows`

**Purpose:** Prove the complete developer workflow and its operational boundaries.

- Add end-to-end lifecycle acceptance using isolated workspaces and mocked process,
  network, and registry boundaries; extend existing fixture generators deliberately.
- Exercise every built-in template: initialize, inspect, sync, then repeat twice.
- Exercise synthetic same-source v1-to-v2 changes with user edits and deletions,
  accepted sibling updates, dependencies, keyed hooks, checksum files, and regions.
- Complete lifecycle walkthroughs, enrollment guidance, partial/check exit examples,
  recipe editing rules, security notes, and rollback-boundary documentation.
- Update generated CLI schemas, help SVGs, snapshots, and doc navigation using the
  repository's generators; inspect expected drift rather than accepting it blindly.

**Acceptance:** The matrix below passes; coverage remains at least 85%; applicable
fixture/documentation checks pass. Let commit/push hooks run their assigned checks
without redundant manual lint/CI runs. No host writes or live package-manager
commands are allowed in tests.

**Boundary:** Documentation must describe shipped behavior, not propose deferred
features. Earlier PRs include their own focused tests and docs; this PR is not a
place to postpone correctness.

## Final Stage 2 acceptance matrix

| Scenario | Required result |
| --- | --- |
| Same recipe/source/inputs repeated | No direct/state writes; no subprocesses; check passes. |
| Current global defaults differ | Effective project selection is unchanged. |
| `[tool.protostar.tools]` omits a tool | Same-source template opinion may evolve for that tool. |
| `[tool.protostar.tools].renovate = false` | Renovate contributions and warnings are suppressed; existing files and ownership are retained. |
| User edits/deletes a managed target without a recipe entry | Preserve implicit drift; never infer an opt-out. |
| User re-enables an opted-out tool | Resume reconciliation against retained baseline; do not restore or adopt content. |
| Same source gains safe new intent | Status/diff expose it; sync applies only accepted contributions. |
| User edits/deletes; desired intent unchanged | Preserve silently during apply; inspection may explain; check passes. |
| User and template diverge | Preserve conflict; apply safe siblings; partial exit `1`. |
| Owned values already converge | Advance baseline without rewriting their content; check fails until advancement commits. |
| Template omits a prior contribution | No pruning; previous ownership survives. |
| Foreign content happens to equal desired | No adoption. |
| Resolver output cannot be predicted | Preview reports actions, not invented resulting requirements/lock bytes. |
| Resolver failure, timeout, interrupt, or late state failure | Reap processes; restore journaled bytes/modes; no partial committed state. |
| Input changes after preparation | Abort before first mutation. |
| Recipe table/state missing or malformed | Fail before mutation with concrete enrollment/correction hint. |
| Alias retargeting or source/template transition | Reject identity change. |
| External template contains arbitrary tasks | Never execute those tasks during inspection or sync. |
| Machine invocation | One deterministic JSON envelope; stderr diagnostics; zero prompts. |

Stage 2 is complete only when the three commands share one decision path, a project
can replay its declared selection independently of global defaults, and these
acceptance gates pass. Completing the CLI parser alone does not complete the stage.
