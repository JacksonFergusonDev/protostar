# Protostar Stage 1: Safe Semantic Reconciliation

Status: PR-A through PR-C complete; PR-D is next.
Updated: 2026-09-16.
Primary audience: LLM implementation and review agents.
Secondary audience: human maintainers.

## 1. Mission and authority

Make repeated `protostar init --force-merge` safe and useful on an existing project, establishing the reconciliation foundation for a future `sync` command. Preserve user intent, not merely comments. Never implement a whole-tree text merge.

This plan supersedes the earlier "Semantic Merge Foundation" draft. Read the repository's `AGENTS.md` before implementation; its architectural and verification rules remain authoritative. Reinspect the current tree before each PR because this document records a starting point, not permanent line-number references.

Protostar is pre-1.0 with no external users. Break APIs and template schemas cleanly when required. Do not introduce compatibility aliases, legacy marker adoption, state-file migrations, or fallback shims. Conversely, do not refactor unrelated code or invent a general-purpose merge framework.

### Settled decisions

- Reconciliation of existing free-form `[files]` content is out of scope for Stage 1.
- Add `ruamel.yaml` to Protostar itself for round-trip YAML editing, not to scaffolded projects.
- Structured configuration needs semantic three-way reconciliation using prior applied contributions.
- Keep state in `.protostar.lock.toml`, separate from `pyproject.toml`.
- Omit timestamps. State and no-op execution must be deterministic.
- Do not automatically prune removed template contributions.
- Safely updating an unchanged managed scalar is allowed; "additive" does not mean every scalar is immutable.
- Defer both migration-directive syntax and its runner until a real migration exists.
- Defer `sync`, `adopt`, restoration/pruning flags, and interactive conflict review.
- Use checksum-gated regeneration for Renovate in Stage 1. Do not build a JSON/JSONC merge adapter now.
- Managed non-TOML append regions are distinct from free-form files: give them stable IDs and checksum-gated replacement, not textual three-way merging.

### Current-tree facts to preserve

- CI/release workflow collision gating already landed in commit `b6285be` and has executor tests. The old draft's PR-1 is complete; do not reimplement it.
- Dependency installation currently calls `uv add`, which already updates `pyproject.toml`, `uv.lock`, and the environment. An additional `uv lock` after those calls is redundant.
- `SystemExecutor._install_dependencies()` pre-journals `pyproject.toml` and `uv.lock`.
- Execution installs dependencies before `_append_files()`. Direct dependency-affecting TOML edits therefore require special attention to ordering.
- Template locators are resolved in CLI/wizard code but are not durably represented in `InitRequest`/`EnvironmentManifest`.
- `deep_merge_tomlkit()` overwrites declared scalars, appends arrays of tables without deduplication, and has path-specific overwrite behavior. Do not treat it as an already-correct universal merge policy.
- Generic append markers currently derive identity from payload content. Changed payloads create new identities and can duplicate old contributions.
- Dockerfile collision gating currently also skips `.dockerignore` processing. Decouple these paths so a preserved Dockerfile does not prevent additive ignore updates.

### Implementation status

This checklist records implementation progress, including the completed PR-C
implementation submitted for review. It is limited to this plan; a completed
milestone does not imply that later reconciliation behavior is available.

| Milestone | Status | Landed scope | Verification |
| --- | --- | --- | --- |
| PR-A: Typed intent, identity, and schema boundaries | **Complete** | Template provenance through CLI/wizard request and manifest serialization; typed structured TOML contributions; stable named append regions; seed-only personal metadata; typed dependency-group includes and resolver footprints; reserved-path and unsafe-injection validation; built-in templates, schema, fixtures, and documentation updated. | Merged implementation commit `be0be97`; targeted tests and commit/pre-push hooks passed. |
| PR-B: State codec and pure reconciliation kernel | **Complete** | Deterministic schema-v1 codec and frozen candidate state; owned TOML document snapshots; generated/seed/region/dependency/hook-pin records; identity/path/schema validation; pure three-way decisions, explicit set-like policy, deletion protection, and composite baselines. Executor integration remains PR-C; YAML snapshots require PR-D’s adapter. | `uv run pytest tests/test_merge.py tests/test_sync_state.py tests/test_intent.py tests/test_toml_ast.py`: 201 passed; separate read-only milestone review and regression fixes. |
| PR-C: Transactional state integration and TOML reconciliation | **Complete** | Transactional state loading/final candidate writes; owned-only TOML AST reconciliation; module/template aggregation; seed metadata and deletion protection; structured conflicts; guarded dependency selection and accepted requirement capture. Complete resolver ordering/include reconciliation remains PR-G. | Implementation commit `71e0547`; fixture/documentation alignment `efd8dfd`; nine-file targeted suite: 346 passed; commit hooks passed; separate read-only boundary review found no remaining blockers. |
| PR-D through PR-H | Planned | — | — |

## 2. Scope and per-artifact policy

| Artifact | Stage 1 policy | State needed |
| --- | --- | --- |
| Managed tooling/build configuration in `pyproject.toml` | Semantic three-way reconciliation through `tomlkit` | Prior applied managed contributions |
| Personal project metadata in `pyproject.toml` | Seed only; preserve thereafter | Ownership/initialization records |
| Dependencies | Requirement-aware reconciliation followed by `uv add` only for accepted changes | Declared requirement and actual materialized requirement |
| `.github/codecov.yml` | Semantic three-way YAML reconciliation | Prior applied managed contributions |
| `.pre-commit-config.yaml` | Repository/hook identity-aware reconciliation | Prior managed repository/hook fields and resolved pins |
| `.github/renovate.json` | Whole-file checksum gate | Last successfully written SHA-256 |
| CI/release workflows, Dockerfile, justfile | Whole-file checksum gate | Last successfully written SHA-256 |
| `.gitignore`, `.dockerignore` | Append missing patterns; preserve existing content/order | No ownership claims or removal tracking required |
| `uv.lock` | Resolver-owned derived artifact; never merge/edit directly | Declared transaction footprint, not a template snapshot |
| Existing free-form `[files]` content | Never reconcile in merge mode | Seeded-path ledger prevents recreation after deletion |
| Managed non-TOML `[appends]` | Stable region identity; checksum-gated replacement | Region ID and last applied region digest |

No source-code AST merge, universal ordered-list merge, JSONC editor, or generic migration DSL ships in this stage.

## 3. Architectural boundaries

### Planning and execution

- `plan()` is read-only: no writes and no subprocesses. Reading workspace/state is allowed under existing repository rules.
- Modules declare desired contributions and possible resolver/task footprints in the manifest. They do not apply merges.
- Template fetching/loading stays at the existing template-resolution boundary, outside reconciliation. Do not add new fetches to the merge kernel.
- Pure helpers accept content/models and return merge results. They never read files, invoke processes, or emit terminal output.
- The executor realizes the declared operations and conditional resolver actions. It does not resolve templates, request user choices, or mutate the task manifest opportunistically.
- All file/directory mutations, including state-file writes, route through `TransactionAwareFS` and `MutationJournal`.
- All subprocesses route through `ProcessRunner`; their supported footprint is declared and journaled before invocation.
- Resolve external hook revisions once per run and carry the resolved values/provenance into execution. Reconciliation must not refetch them.

### Headless results and machine mode

- Represent outcomes with flat frozen dataclasses and enums, including `KEEP_LOCAL`, `APPLY_REMOTE`, and `CONFLICT` or equivalent names.
- Include concrete file/key/identity information in a conflict record. Do not rely on an English warning string as the internal API.
- Expected merge conflicts preserve the affected local value/region/file and emit warning diagnostics. Safe non-conflicting contributions may still apply.
- Explicit `--force-merge` authorizes this non-blocking preserve-and-warn policy, including in `--json` mode. Report warnings structurally; never request additional prompts.
- If the caller has not selected a collision strategy, retain the current domain-exception/CLI collision-resolution boundary.
- Malformed state/configuration and unsafe paths are fatal domain errors, not soft merge conflicts. Abort before mutations where possible; rollback otherwise.
- `--json` stdout remains exclusively the JSON payload. Diagnostics and human output go to stderr.

### Minimal implementation shape

Use a small pure decision kernel, file-specific policies, format-specific AST adapters, and one state codec. Suggested homes are `merge.py`, `sync_state.py`, and `yaml_ast.py`; exact module names are not contracts.

Do not build adapter registries, plugin factories, strategy inheritance trees, or a second orchestrator. Do not convert the local AST to plain dictionaries and regenerate it just to reuse the kernel. AST trivia and mutation remain in the adapter; semantic decisions remain in the kernel/policy.

## 4. Reconciliation contract

### Three inputs and explicit absence

For each managed semantic leaf or keyed record:

- `base`: the contribution Protostar last successfully applied.
- `local`: current workspace content.
- `remote`: the resolved desired contribution for this run.

Distinguish missing from a present null value. Equality must be type-aware: a YAML boolean must not compare equal to an integer. Preserve semantic types supported by the codec; do not force TOML dates/times into JSON or use lossy string conversion.

The baseline is not a snapshot of the entire workspace. It contains only owned/applied contributions. User-added siblings and custom hooks must never become managed merely because the executor reads or rewrites their containing file.

### Scalar decision rules

Apply these rules in the listed order:

1. If `remote` is absent, preserve `local`; do not prune. Retain any previous ownership baseline so a later reintroduction does not erase evidence of a user deletion/edit.
1. If no ownership baseline exists:
   - If `local` is absent and no owned ancestor was deleted or changed incompatibly, add `remote` and establish its baseline.
   - If `local` already equals `remote`, leave it unchanged and unowned. Equality alone is not adoption.
   - Otherwise preserve `local` and report a conflict.
1. With an ownership baseline:
   - If `local == remote`, keep the local representation and accept the converged value as the new baseline.
   - If `remote == base`, preserve `local`, including a user deletion. Keep the old baseline.
   - If `local == base`, apply `remote` and advance that contribution's baseline.
   - Otherwise preserve `local`, report a conflict, and retain its previous baseline.

A user-deleted owned table, record, region, or file protects its subtree: do not resurrect it indirectly by adding a new child. Type mismatches protect the affected subtree and produce a conflict.

For newly created files in this transaction, distinguish initializer output from pre-existing user content. Applying declared initial contributions to `uv init` defaults is initialization, not adoption. Never let this exception cover a pre-existing `pyproject.toml`.

### Mapping and sequence policies

- Recursively reconcile managed mapping entries while retaining foreign siblings and local key order.
- Use set-like sequence reconciliation only for explicitly enumerated paths such as known lint-selection/ignore lists and classifiers. Preserve local order and append genuinely new accepted members in desired order.
- A previously applied member deleted by the user stays deleted. Template omission never removes a local member. Do not re-add every absent remote member through naive union.
- Keyed records require a file-specific identity function; see pre-commit and dependency sections.
- Unknown sequences, ordered sequences, and unknown TOML arrays of tables are atomic values. Compare/reconcile the whole value rather than guessing identity or silently deduplicating it.
- Reject duplicate identities where an identity-based policy cannot choose a unique target.
- Keep separate tests for format trivia and file-specific policies. Do not require all formats/files to share identical behavior.

### Explicit replacement/removal directives

Remove the existing `__replace__` control sentinel from the supported template payload schema and reject its use with an actionable `ConfigurationError`. Do not add `__remove__`.

Template configuration payloads contain configuration, not an embedded operation language. Future explicit migrations/replacements require a separately designed typed schema. Never leak a control key into a workspace file or mutate a shared desired payload during reconciliation.

### Collision strategies

- `MERGE`: use the policies in this document; preserve conflicts without blocking.
- `OVERWRITE`: remains explicit destructive authorization for declared targets/contributions, not an inferred default. Replace declared generated files/regions and explicitly targeted managed configuration, while preserving unrelated siblings and undeclared paths. Do not automatically prune omitted contributions or edit `uv.lock` directly.
- `ABORT`: no mutations when collisions are unresolved.

State metadata is engine-owned and updated transactionally; the mere existence of `.protostar.lock.toml` is not a user-file collision. Invalid state is nevertheless fatal. Do not let a template inject or append to the reserved state path.

## 5. Template identity and persistent state

### Template reference

Carry a frozen typed reference from both CLI and wizard resolution through request and manifest models. It should record:

- Origin kind: built-in, external local file, or external remote source.
- Canonical locator: stable built-in identifier, normalized local path, or resolved remote locator. Never persist a temporary extraction path or package-install absolute path as built-in identity.
- Optional display name/global alias, which is descriptive rather than authoritative.
- SHA-256 of the selected template TOML bytes before interpolation, not of an entire remote archive.
- Optional declared template version and immutable source revision when available. Versions are informational in Stage 1; do not implement migration ordering.

An alias that changes its underlying locator is a template identity change. A changed digest at the same locator is a normal template revision. On an existing tracked project, reject a different template identity in Stage 1 with a domain error and a hint; do not invent template switching or adoption.

Support tooling-only initialization without a template. Keep its state distinct from a tracked template project. Reconciliation of a tracked template project requires the same explicitly selected template; automatic reconstruction of a request from state belongs to Stage 2.

Do not persist trust authorization, credentials, arbitrary interpolation answers, or secret metadata. State does not authorize replaying external template tasks.

### State schema v1

Use `tomlkit` for parsing and deterministic serialization, but use a dedicated state codec, not pyproject merging/visual formatting. Store:

- `schema_version = 1` and producer version for provenance.
- Template reference when applicable.
- Per-file policy identifier and last successful applied state.
- Structured baselines containing only applied managed contributions.
- Whole-file digests for generated checksum-gated artifacts.
- Seeded free-form paths and managed region IDs/digests.
- Dependency declared/materialized requirement records and applied hook pins/provenance.

Represent structured baseline snapshots as TOML/YAML document strings inside the lockfile, decoded by their existing format adapter. This avoids a speculative cross-format tagged-value serialization system. Snapshots contain owned configuration only, not copied user documents. Partial success produces a composite baseline: advance successful/converged owned entries; retain previous entries on conflict/deletion/omission.

Models must be typed and flat. Use one schema version and fail on unsupported versions; there is no legacy state migration. Sort path-keyed state deterministically and serialize workspace paths as relative POSIX strings. Omit timestamps and execution-dependent trivia.

The top-level template digest identifies the latest committed reconciliation attempt, not proof that every file reached that revision. Per-file/contribution baselines remain authoritative after partial conflict handling. Do not add a misleading global `fully_synced` claim.

### Missing state and transactional lifecycle

1. Read and validate the state before mutation. Enforce path jail and reject symlinks/special nodes for transaction-managed targets and state paths.
1. Missing state is allowed for initial/ordinary merge execution, but existing content is unowned. Fill missing structured values conservatively; never infer whole-file ownership.
1. Stage candidate baseline updates in memory during execution.
1. For any skipped file/region, keep its prior digest/baseline. Never record the user's edited bytes as the last generated bytes.
1. After all declared writes and relevant subprocesses succeed, serialize the candidate state through `TransactionAwareFS`, before journal commit.
1. On failure/interrupt, terminate managed processes first and rollback files plus state to exact pre-transaction bytes/modes.

A no-op run must not rewrite the state or workspace files. If serialized bytes are unchanged, skip the write so `ExecutionResult.mutated_paths` stays accurate.

## 6. Artifact-specific implementation rules

### TOML and project metadata

- Keep `tomlkit` AST mutation in `toml_ast.py`; remove overwrite/scalar/array behavior that contradicts the new policies rather than wrapping it with compatibility behavior.
- Aggregate desired contributions before reconciling against local content. Retain the existing documented module/template precedence for intentional overrides; reject ambiguous conflicting producers with no defined precedence.
- Reconcile managed tooling and explicitly declared build configuration with the three-way rules.
- Treat personal project metadata such as name, version, description, authors, repository URLs, and initial license selection as seed-only in merge mode. Do not reset them from module defaults on rerun. Explicit overwrite remains separate authorization.
- Readme/source/license free-form files remain seed-only, even if referenced from TOML.
- Do not purge unmatched tool scalars simply because they are absent from the new payload.
- Avoid global reformatting of a pre-existing project. Mutate accepted nodes and preserve comments/trivia; no-op means byte-identical input.

### YAML codec and Codecov pilot

- Add `ruamel.yaml>=0.19.1,<0.20` using its instance API and pure-Python round-trip mode. Recheck the tested compatible release when implementation starts; document any changed bound.
- Do not add optional C extras. Isolate third-party typing at the codec boundary; do not spread `Any` across the merge models.
- Preserve quotes, scalar/collection styles, comments, anchors, and foreign content supported by round-trip editing.
- Default to YAML 1.2 interpretation. Do not silently reinterpret explicit 1.1 directives; handle them consistently or reject them with a domain error if unsupported by the file policy.
- Reject duplicate keys, multi-document input, non-mapping configuration roots, unsupported semantic shapes, and unsafe custom constructors. Bound parser traversal and detect cyclic aliases.
- If a proposed mutation touches shared alias/merge-key structure whose effects cannot be confined to managed paths, preserve the affected subtree and report a conflict. Do not mutate foreign nodes indirectly through shared objects.
- Round-trip support is not a promise of universal byte preservation. Avoid dumping on semantic no-ops; document/test unavoidable formatting normalization when accepted edits require serialization.
- Pilot the three-way contract with Codecov: changed managed target, preserved user target, custom ignore entry, user-deleted ignore member, and preserved comments.

### Pre-commit identities and ownership

- Repository identity is the exact `repo` value; do not normalize arbitrary URLs speculatively.
- Hook identity is `(repo, id)`. `repo: local` uses the same rule, not a blanket "all local hooks are foreign" rule.
- Repository `rev` belongs to the repository record, not each hook. Preserve user-added hooks in the same repository.
- Membership in `RemoteHook` identifies supported upstream repositories, not ownership of every matching local repository/hook. Only the applied baseline establishes management.
- Add missing planned repositories/hooks; never duplicate existing identities. Reconcile managed fields using the three-way contract, preserving foreign fields, args, stages, files patterns, and additional dependencies.
- Treat duplicate repository blocks or repeated hook IDs as an explicit ambiguity conflict for that repository. Do not silently consolidate/reorder user blocks.
- Capture resolved registry pin provenance. Offline fallback must not replace an already recorded pin. Do not automatically downgrade comparable version pins; preserve-and-warn on regressive or unorderable automatic pin changes. Opaque template-pinned revision changes use the normal explicit desired-value contract.
- Merge top-level managed hook-runner/install-hook-type configuration too; switching between pre-commit and prek must not leave stale managed runner fields.

### Checksum-gated generated files

Apply independently to Renovate, CI/release workflows, Dockerfile, and justfile:

1. Generate desired bytes purely from the resolved manifest/spec.
1. If the path has never been managed and is absent, create it and record its SHA-256.
1. If the current digest matches the last successful generated digest, write desired bytes only when different, then advance the digest.
1. If the current bytes already equal desired bytes and a prior ownership record exists, accept convergence without rewriting.
1. If content differs from the last applied bytes, preserve it. Warn only when the desired digest also differs from the recorded baseline and local content is not already converged. Keep the previous digest. A user edit alone is not a pending template update.
1. If an owned file was deleted, preserve the deletion; warn when the desired digest differs from the recorded baseline. Do not recreate it in merge mode.
1. If an existing file has no ownership record, preserve it even if it resembles generator output. No implicit adoption.

Hash exact bytes, not stripped text or normalized line endings. Renovate can contain JSONC comments even in `.json`; checksum gating deliberately avoids parsing/reformatting existing user Renovate content. New generated Renovate content is strict JSON and must be validated before writing. Alternative Renovate locations are not automatically adopted or managed in Stage 1; report a conflicting recognized configuration rather than creating a competing one.

Decouple `.dockerignore` additive processing from Dockerfile regeneration. Never remove existing ignore patterns under merge mode.

### Free-form files and managed append regions

For `[files]`, create a new absent, never-seeded path; leave existing content untouched. Record only paths actually created. A seeded path later deleted remains absent in merge mode. Do not parse/reconcile its contents even if its extension is Python, TOML, or YAML. Structured module contributions use the explicit structured manifest path, not extension-based inference from free-form `[files]`.

For non-TOML `[appends]`:

- Replace anonymous string lists with typed contributions carrying a stable ID and content. Template schema uses named records, for example `[appends.".envrc".project_environment]` with a `content` field. Module IDs are namespaced by module identity; template IDs by stable template identity, never version/digest/list position.
- Use a deterministic marker containing the stable ID and one matching end marker. Keep the ID stable when payload content changes.
- Append a new unique managed region if it does not collide with a user-deleted region/owned file.
- Replace an existing region only when its exact region bytes match the last applied digest, or an explicit overwrite was selected. Preserve surrounding bytes.
- Preserve edited/deleted regions and warn only when desired region bytes differ from the recorded baseline and local content is not already converged. Reject duplicate/nested/malformed boundaries rather than guessing.
- Never store a checksum of newly read user edits as the applied region baseline.
- Use no text merge and no legacy MD5 marker compatibility. Existing legacy blocks are not implicitly adopted; reject ambiguous updates with a domain error/hint rather than appending a duplicate.

TOML append payloads become structured contributions, not marker blocks. Template `[files]` and structured/region contributions must not target the same path ambiguously.

### Dependencies and `uv.lock`

Do not let an unchanged template dependency reset a user's specifier through repeated `uv add` calls.

- Parse PEP 508 requirements using `packaging.requirements.Requirement`; add `packaging` as a direct Protostar dependency if it is not already direct. Do not rely on a transitive install or invent a regex parser.
- Identity includes dependency group, canonical package name, and normalized marker expression. Extras, specifiers, and URL/source information are values, not ignorable decoration. Ambiguous multiple entries for one identity preserve-and-warn rather than guessing.
- Support declared main/dev/docs dependencies first. Preserve unrelated groups and include-group records.
- Store both the requested requirement and the actual requirement materialized by `uv add`, which may introduce a lower bound for a bare package. Capture only accepted managed identities after the resolver succeeds.
- If declared desired intent is unchanged, skip `uv add` for that identity even when the actual materialized requirement includes resolver-added bounds. A later user edit/deletion stays intact.
- For a changed desired requirement, compare local against the materialized baseline before accepting it. Preserve conflicts; never union two differing strings for the same package identity.
- Do not implement arbitrary version-range subset proofs. Known regressive exact/lower-bound version changes and ambiguous existing-constraint changes are preserve-and-warn in merge mode unless explicitly overwritten. Never run `--upgrade` implicitly.
- Journal `pyproject.toml` and the owning `uv.lock` before every accepted resolver action; failures/timeouts remain fatal.
- Prevent arbitrary TOML payloads from directly changing `project.dependencies`, `project.optional-dependencies`, `dependency-groups`, or `tool.uv.sources` outside the typed dependency path. Move built-in include-group wiring into typed declarations. Unsupported template use fails with a hint to use dependency fields, rather than silently bypassing the resolver.
- Declare a conditional lock action only for accepted non-`uv add` changes that invalidate resolution, such as typed include-group wiring or managed `requires-python` changes. Execute it after all relevant TOML writes if no later accepted `uv add` already reconciled the final metadata. Never run a redundant lock for an ordinary dependency addition.
- Identify the owning uv project/workspace before invocation. If its resolver-managed paths lie outside Protostar's transaction workspace, fail with a domain error; do not mutate an ancestor/sibling lockfile outside the journal boundary.
- `.venv` and global resolver caches remain outside the supported rollback boundary. Do not claim otherwise.

Do not introduce a blanket "write all dependencies via AST, then uv sync" rewrite in this stage. Keep the existing `uv add` ownership path and narrowly fix its reconciliation and ordering.

## 7. PR sequence and gates

Use one bounded implementation PR at a time until the kernel/state contracts land. Every PR includes tests and any affected documentation/schema/fixture changes. The bullets below are implementation gates, not permission to commit or push without the maintainer's authorization.

### PR-A: Typed intent, identity, and schema boundaries — **Complete**

Goal: declare what can be managed without introducing side effects.

- Introduce template references at CLI and wizard boundaries and preserve them through request/manifest serialization.
- Introduce typed structured contributions, stable append IDs, and possible dependency-affecting resolver footprints.
- Separate seed-only personal metadata/free-form files from managed tooling configuration.
- Replace/reject legacy control sentinels and anonymous append schema; update built-in templates, schema export, fixtures, and docs directly.
- Move dependency table/include-group contributions into the typed dependency model; reject unsafe generic injections.

Gate: **Complete.** Targeted config/schema/manifest/orchestrator/CLI/wizard tests prove stable identities, deterministic serialization, reserved-path checks, clear errors, and zero planning mutations/subprocesses. Built-in templates and the exported schema use the new typed declarations; newly supported declarations are applied or rejected explicitly. Merged implementation commit `be0be97` contains the implementation and verification updates.

### PR-B: State codec and pure reconciliation kernel — **Complete**

Depends on PR-A.

- Add state schema v1, validation, deterministic serialization, and typed in-memory candidate state.
- Implement scalar/missing/type decision rules, explicit set-like membership policy, composite baseline advancement, and deletion protection.
- Add pure tests for every truth-table branch, unknown/atomic sequences, foreign ownership, and partial conflicts.
- Do not wire an unsafe two-way adapter as a temporary executor implementation.

Gate: **Complete.** State round trips supported TOML baseline values, rejects corrupt/unsupported/escaping records, has no timestamps, and remains byte-stable. Kernel is filesystem/subprocess/UI-free and does not mutate its desired/base inputs. Set-like identity validation runs before no-op shortcuts, including through unchanged ancestor mappings. Persisted dependencies validate PEP 508 syntax and stored name/marker identity using direct `packaging`; resolver acceptance remains downstream. See [PR-B contracts](docs/development/semantic-reconciliation.md) for the PR-C handoff.

### PR-C: Transactional state integration and TOML reconciliation — **Complete**

Depends on PR-B.

- Integrate state loading/candidate writes into execution and rewrite managed TOML application through the three-way policy.
- Preserve personal metadata, unmatched keys, comments, user deletions, and no-op bytes.
- Aggregate producer contributions once and enforce precedence/collision rules.
- Add dependency requirement selection guards early enough that existing `uv add` calls cannot bypass TOML ownership safety. PR-G completes resolver ordering, not an excuse to leave reset behavior until later.

Gate: **Complete.** Initial/merge/repeat/conflict/failure tests show exact file+state rollback, accurate touched paths, no adoption, seed-only metadata, and no live package-manager calls. The targeted command `uv run pytest tests/test_reconciliation_execution.py tests/test_executor.py tests/test_toml_ast.py tests/test_dependencies.py tests/test_merge.py tests/test_sync_state.py tests/test_orchestrator.py tests/test_intent.py tests/test_workspace.py -q` passed **346 tests**. Commit and pre-push hooks passed. A final package-name/extra-spelling regression verifies normalized unchanged intent stays silent. `uv run python scripts/generate_doc_fixtures.py` regenerated all seven scenarios successfully; the same-template rerun example and snapshots are committed in `efd8dfd`. A separate read-only review challenged ownership, deleted/incompatible ancestors, dependency guards, and state transactionality; its final review of `71e0547` found no remaining concrete blockers. See [execution contracts](docs/development/semantic-reconciliation.md#pr-c-execution-boundary). Downstream generated/YAML/region policies and complete resolver ordering remain their later milestones.

### PR-D: YAML codec and Codecov pilot

Depends on PR-C.

- Add the tested ruamel dependency and isolated codec.
- Implement Codecov managed three-way reconciliation and explicit ignore-list policy.
- Add comments/styles/alias safety fixtures and malformed-input tests.

Gate: untouched old target updates; user-edited target survives with a structured warning; custom/deleted ignore members survive; semantic no-op is byte-identical; parser failures cause no committed changes.

### PR-E: Identity-based pre-commit reconciliation

Depends on PR-D.

- Implement keyed repositories/hooks and top-level managed fields.
- Carry registry resolution/provenance once per run; guard fallback/regressive updates.
- Preserve custom local/remote hooks and user-modified managed fields.

Gate: one run adds a managed hook and safely changes a managed pin while retaining custom hooks/comments. Test same-repo foreign hooks, runner changes, duplicates, user pin edits/deletions, and offline fallback.

### PR-F: Generated-file and append-region checksum gates

Depends on PR-C; implement after PR-E by default to avoid simultaneous executor edits.

- Introduce one small reusable whole-file gate for Renovate/workflows/Dockerfile/justfile.
- Implement stable managed-region replacement using the existing comment-syntax helper where appropriate.
- Add seeded-path deletion handling for `[files]` and decouple `.dockerignore`.

Gate: test every artifact for initial creation, unchanged repeat, clean update, local edit, convergence, missing baseline, and user deletion. Assert exact digest correspondence and preservation of surrounding region bytes. Existing commented Renovate config is never parsed or rewritten.

### PR-G: Resolver ordering and derived-artifact completion

Depends on PR-C and relevant artifact integration.

- Complete requested/materialized requirement tracking and per-identity resolver acceptance.
- Order typed TOML/dependency-affecting contributions before the resolver action that must observe them, respecting initial `uv init` prerequisites.
- Add conditional lock-only actions for supported metadata changes not handled by a later `uv add`.
- Validate resolver workspace ownership and preserve fatal failure/interrupt/process cleanup behavior.

Gate: unchanged requirements invoke no redundant `uv add`/`uv lock`; user constraints are not reset; additions resolve once through the existing path; include-group/requires-python changes leave the mocked lock up to date; failures restore original pyproject/lock/state bytes and modes.

### PR-H: End-to-end acceptance, documentation, and cleanup

Depends on all previous PRs.

- Add the complete Stage 1 scenario matrix below across built-in templates and representative synthetic revisions.
- Rewrite the "run exactly once" documentation to describe safe reinitialization and its ownership limitations without advertising an unimplemented `sync` command.
- Remove superseded merge paths and obsolete parameters outright. Update fixture snapshots and domain-error documentation links.
- Verify coverage remains at least 85% through the repository's coverage target.

Gate: all Stage 1 acceptance cases pass; maintainers can explain why each surviving merge path exists. No deferred migration/adoption/JSONC machinery has slipped into the implementation.

## 8. Stage 1 acceptance matrix

One byte-identical rerun test is necessary but insufficient. Cover:

1. For every built-in template: initial execution, identical merge, and a second identical merge produce identical managed bytes/state. Freeze template inputs, metadata, producer version, registry responses, clock-dependent rendering, and resolver outputs.
1. A clean v1-to-v2 tooling/config/generated-file change applies and advances only its successful baseline/digest.
1. Non-overlapping user/template edits both survive.
1. Overlapping scalar, keyed-record, and atomic-sequence edits preserve local content and produce machine-readable diagnostics.
1. User-deleted owned members/subtrees/files/regions stay deleted; newly introduced never-owned paths can be created.
1. Existing seed-only source files and personal project metadata are never reset in merge mode.
1. Foreign keys/hooks and same-repository custom hooks never become owned through serialization.
1. Existing content without state is never implicitly adopted; template switching/alias retargeting is rejected.
1. Malformed TOML/YAML/state, duplicate identities, reserved targets, unsafe nodes, cycles, and unsupported schema versions have no committed effects.
1. Failure after any managed write, during resolution, or during the state write rolls back exact original bytes/POSIX modes and leaves no advanced state.
1. Interrupt cleanup terminates/reaps processes before rollback; rollback-failure reporting remains intact.
1. All recorded generated/region digests match the bytes Protostar last successfully applied, not necessarily edited current workspace bytes.
1. A no-op run writes nothing and reports no false mutations. Foreign/gitignored execution-dependent artifacts are excluded through an explicit bounded manifest-derived path list, not a broad directory exclusion.
1. JSON stdout contains only the envelope; selected merge mode never prompts, and conflict warnings name the affected file/key/identity.
1. Dependency requirements normalize correctly across package-name spelling, extras, markers, groups, and direct references; ambiguous identities conflict safely.
1. Offline fallback cannot regress an already managed pin; identical pinned registry responses are deterministic.

Automated tests use `tmp_path` and mocked subprocess/network behavior. Extend in-process integration helpers rather than invoking live `uv`, `git`, or package managers. Optional real smoke checks use `just sandbox`/`just sandbox-linux` separately, never ordinary automated tests on the host.

## 9. Agent implementation workflow

### Work unit

Start with PR-A, not all of Stage 1. Give each implementation agent:

- This plan and `AGENTS.md`.
- Exactly one PR/milestone objective, allowed scope, prerequisites, and acceptance gate.
- A requirement to inspect current code/status before editing and preserve unrelated changes.
- A requirement to add regression tests with the change and record exact verification commands/results.
- A stop condition: hand off when the bounded gate is met, or report a genuine contract blocker. Do not silently redesign ownership semantics or implement deferred features.

Suggested kickoff prompt:

```text
Read AGENTS.md and SEMANTIC_MERGE_PLAN.md completely. Implement PR-A only.
Inspect the current tree and relevant request/config/manifest/CLI/wizard tests
before editing. Preserve unrelated changes. Follow the plan's ownership and
transaction boundaries; do not implement downstream adapters or sync/adopt.
Add targeted tests and update affected schema/docs/fixtures. Do not commit or
push. Finish with changed files, exact checks/results, unresolved risks, and
the next PR's contract handoff. Ask before changing a settled policy.
```

### Review and coordination

- Prefer one implementation owner for shared executor/manifest/state code.
- Use a separate read-only reviewer after each milestone, especially PR-C and PR-G. Its task is to challenge the ownership truth table, deletion protection, baseline advancement, resolver footprint, and tests, not implement more features.
- Parallel agent implementation is optional only after PR-C's contracts are accepted, and only for independent bounded adapters/tests on isolated branches/worktrees. Do not have agents concurrently mutate the executor/state models in a shared checkout.
- Integrate/rebase and rerun targeted acceptance tests after every parallel contribution. Parallel completion does not establish integration correctness.
- Review architecture/contract changes with the maintainer before dependent PRs proceed.

### Verification and historical record

- During development, run targeted commands such as `uv run pytest tests/test_toml_ast.py tests/test_executor.py`; choose the actual relevant files for that PR.
- Follow `AGENTS.md`: do not redundantly run ruff/mypy/rumdl/`just lint`/`just ci` immediately before committing/pushing. Let `prek` hooks perform their configured gates once commit/push is authorized.
- Fix hook failures, inspect formatter changes, and restage explicitly. Never bypass failing hooks to declare completion.
- Commit/PR titles use Conventional Commits. PR descriptions explain the problem, decisions, rejected alternatives, and meaningful architectural invariants rather than listing a diff.
- Handoff includes milestone status, tests, state/schema contracts, conflict semantics, and known limitations. Do not call the overall plan complete until PR-H's gate is satisfied.

## 10. Readiness and deferred work

The plan is clear to begin implementation at PR-A. There are no unresolved product decisions required to start. Names and flat model layout may be refined within these contracts; do not treat those details as a reason to build speculative abstractions.

This is readiness for incremental implementation, not assurance that the entire redesign can land unreviewed. The first critical checkpoint is PR-C: validate ownership and state transactionality before extending the engine to more files.

Deferred work includes `sync`/`update`, request reconstruction from stored template inputs, adoption/template switching, user-requested restoration, pruning/removal directives, migration syntax/version ordering, semantic Renovate/JSONC updates, arbitrary ordered-sequence identities, and reconciliation of existing free-form source files. Build these against real use cases after Stage 1 is trusted.

## 11. Primary references

- [ruamel.yaml instance API and round-trip loader](https://yaml.dev/doc/ruamel.yaml/api/): use the instance API; the round-trip loader does not construct arbitrary Python objects without explicitly added constructors.
- [ruamel.yaml round-trip details and limitations](https://yaml.dev/doc/ruamel.yaml/detail/): comments/styles are retained where supported; inconsistent indentation may normalize on serialization.
- [ruamel.yaml package and compatible release history](https://pypi.org/project/ruamel.yaml/).
- [uv add and lock CLI contracts](https://docs.astral.sh/uv/reference/cli/): `uv add` already updates the lock/environment; lock-only actions address separate accepted metadata changes.
- [uv lock/sync behavior](https://docs.astral.sh/uv/concepts/projects/sync/).
- [PEP 508 requirement parsing in packaging](https://packaging.pypa.io/en/stable/requirements.html): use a standards parser rather than string splitting.
- [Renovate configuration formats](https://docs.renovatebot.com/configuration-options/): `.json` configuration can contain JSONC comments, motivating Stage 1 checksum gating.
