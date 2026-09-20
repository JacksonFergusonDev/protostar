# Semantic reconciliation contracts

PR B provides the pure kernel and schema-v1 state codec. PR C connects them to
transactional execution and TOML AST application, with early dependency selection
guards. PR D adds the YAML codec and validated YAML snapshots. PR E adds keyed
pre-commit reconciliation and guarded hook pin provenance.

## Kernel and ownership

`protostar.merge.reconcile()` accepts decoded semantic `base`, `local`, and
`remote` values plus a `MergeLocation` and `MergePolicy`. Format adapters keep
local ASTs and apply accepted decisions without regenerating user documents.
The kernel does no filesystem access, subprocess execution, or terminal output.
Inputs and returned mutable collections share no objects.

`MISSING` represents absence; `None` represents a present null. Equality checks
semantic types, including boolean versus integer and native TOML date/time values.
Cyclic, unsupported, and excessively nested values fail with domain errors.

`MergeResult` returns the semantic value, composite owned baseline, aggregate
`KEEP_LOCAL`/`APPLY_REMOTE`/`CONFLICT` decision, and concrete file/key/record
conflicts. An aggregate conflict may contain accepted sibling changes. Adapters
must inspect the returned values rather than discard all changes on conflict.
No diagnostic strings or prompts belong to this interface.

- Omitted remote values retain local values and previous ownership.
- Missing unowned values may be added and owned. Existing equal values remain
  unowned; equality is insufficient for adoption.
- Owned convergence advances the baseline without requiring a write.
- Unchanged remote intent preserves local edits/deletions without warning.
- An unchanged local owned value can accept a changed remote value.
- Divergence, incompatible types, and changed intent under a deleted owned
  ancestor preserve local content and previous ownership, with a conflict.

Mapping reconciliation retains foreign siblings and local insertion order while
advancing only successful owned children. A deleted/incompatible owned mapping
protects its entire subtree. An adapter operating directly on a child of a
protected file/record must set `protected_ancestor`; it cannot infer ancestor
ownership from that child alone. Initializer-output exceptions, overwrite
strategy, keyed identities, and diagnostic presentation belong to adapters or
execution, not this merge interface.

Sequences are atomic by default, including arrays of tables. Adapters explicitly
enumerate set-like key paths in `MergePolicy`. These accept unique scalars only,
retain local order and user deletions, retain omitted baseline members, and append
new accepted members in desired order. Existing foreign equal members do not
become owned. Policy validation examines all inputs before truth-table shortcuts,
including lists inside unchanged mappings. Pre-commit supplies its file-specific keyed repository/hook policy in PR E.

## State schema v1

`protostar.sync_state.SyncState` is a frozen candidate/committed model. It contains
producer provenance, an optional template reference, and tuples of file,
dependency, and hook-pin records. `with_file()` returns a new candidate, retaining
other records; it does not modify committed state. Candidate updates are neither
writes nor transaction commits.

`serialize_state()` and `deserialize_state()` operate on TOML strings with
`tomlkit`. Paths and record identities sort deterministically. Owned baseline
mapping keys sort recursively, while sequence order remains meaningful. No
clock values, trust authorization, interpolation answers, or whole-workspace
snapshots are recorded. Template provenance describes the latest successful
transaction attempt; file baselines remain authoritative after partial conflicts.

| File policy | Stored ownership |
| --- | --- |
| `structured-toml` | TOML document string containing only applied contributions |
| `structured-yaml` | Validated YAML 1.2 document string containing only applied contributions |
| `structured-jsonc` | Strict JSON object string containing only applied contributions, including nulls |
| `checksum` | Last applied lowercase SHA-256 hex digest, plus optional managed-region digests |
| `seed-only` | Path actually seeded; retained after deletion |
| `regions` | Delimited 8-hex tags, stable logical IDs, and last applied SHA-256 digests |

TOML and YAML snapshots are validated by their respective codecs; unknown policies
fail rather than accepting opaque documents. YAML snapshots preserve null values.
Kernel null values cannot be persisted through TOML: its snapshot encoder rejects
them explicitly.
Native TOML scalars, arrays, and arrays of tables round trip without conversion
through JSON or a tagged cross-format value system.

Dependencies retain path/group/canonical-name/normalized-marker identity plus
exact declared and materialized requirement strings. The codec validates PEP 508
syntax and that both requirements match the stored identity. Extras, specifiers,
and direct references remain values. PR C selects accepted resolver requests before `uv add`, captures uniquely
materialized accepted requirements, and guards known regressions and ambiguous
constraint changes. PR G completes resolver ordering and derived-artifact handling. Hook pins retain exact repository identity,
revision, and registry/template/fallback provenance; hook fields need the YAML
adapter's owned baseline, not adoption from a pin record.

Unknown fields/policies/versions, malformed snapshots, duplicate identities,
invalid digests, and noncanonical or escaping paths are fatal `ConfigurationError`
failures. Paths must be relative POSIX workspace paths, reject Windows drives and
backslashes, and exclude engine state and resolver-owned `uv.lock` targets.
`check_template_identity()` allows a changed digest at the same source while
rejecting template switching, alias retargeting, and tooling/template transitions.
Missing state is a caller-level absence, not an empty or corrupt state document.

## PR C execution boundary

Read and validate state before mutation. Filesystem node safety and the actual
workspace jail remain the executor's responsibility; a pure string codec cannot
inspect symlinks or ancestor workspaces. Missing state must never adopt existing
content. Pass only applied owned contributions to the snapshot encoder.

Apply accepted changes through format ASTs and `TransactionAwareFS`, stage
composite baselines in a candidate, and write state only after all declared writes
and resolver actions succeed. Skip writes when resulting bytes match. Commit
state before journal commit so failure restores exact original file/state bytes
and modes. Expected merge conflicts preserve affected values and become structured
warnings; malformed state remains fatal. The executor aggregates module contributions in declared sequence order, then
applies template opinions once. Unclassified conflicting producers fail before
mutations. The TOML adapter keeps semantic intent separate from a desired
`tomlkit` AST: the kernel decides ownership using plain values, while accepted
nodes retain authored comments, array layout, and inline-table style from that
AST. Set-like additions retain existing local member nodes and their comments
before considering desired-node replacement. It patches the existing local AST
and does not globally format an existing document, even when adding a new tool
to semantically unchanged managed configuration. Newly initialized `pyproject.toml` files retain the standard tool
banner and section markers. Explicit overwrite owns declared values
while retaining undeclared siblings. Personal project fields are seed-only in
merge mode; defaults written by a journaled initializer are eligible for initial
ownership, while pre-existing user metadata is preserved.

Conflict diagnostics include file, key path, optional identity, and an enum reason
in `ExecutionResult.to_dict()`. Safe siblings can apply despite other conflicts.
Existing equal values remain unowned. A tracked deleted file cannot be recreated
by initializer tasks, new dependency requests, include-group wiring, or newly
requested tooling. The executor captures a deleted tracked `pyproject.toml` before
running `uv init`, including projects tracked only through dependency records.
Explicit overwrite can still initialize that file again.

Unchanged declared dependency intent skips `uv add`, even when the materialized
requirement gained resolver bounds or the user later edited/deleted it. Changed
intent needs an unchanged materialized baseline; unowned existing constraints,
duplicate identities, known version regressions, and ambiguous constraint changes
are preserved with warnings. Converged previously owned intent advances its
record without a resolver call. Resolver failures remain fatal and restore the
journaled project, lock, and state bytes and modes.

PR G still owns complete include-group reconciliation and final TOML/resolver
ordering. Generated-file digests, free-form seed ledgers, and managed-region
checksum application remain the later adapter milestones. This boundary adds no
adoption, pruning, migration layer, or new command.

## PR D YAML and Codecov boundary

`yaml_ast.py` isolates `ruamel.yaml` typing and round-trip AST operations. The
runtime dependency is `ruamel.yaml>=0.19.1,<0.20`, tested with 0.19.1 using the
[instance API](https://yaml.dev/doc/ruamel.yaml/api/) in pure-Python round-trip
mode, without C extras or custom constructors. YAML 1.2 is the default; explicit
1.1 directives are rejected rather than silently reinterpreted. One mapping
root, unique string keys, JSON-like scalar types, and finite acyclic collections
are required. Timestamp/binary/set/custom tags and multiple documents fail with a
domain error. Input is bounded to 1 MB, 100 nesting levels, and 10,000 expanded
nodes; graph validation precedes construction to reject recursive aliases.

Codecov declares `StructuredFormat.YAML` explicitly through `add_structured()`.
The pilot accepts one managed producer at `.github/codecov.yml`; it does not infer
structured intent from free-form file extensions or expose arbitrary YAML template
injections. TOML remains the default format. YAML baseline documents use the
`structured-yaml` file policy in schema v1 and are canonically serialized from
owned values only, never from the local round-trip document.

The existing three-way kernel controls scalar ownership and mapping recursion.
Only the root `ignore` list is set-like: retain custom members, preserve user
removals, and append newly accepted members in desired order. Other sequences
are atomic. Changed local targets are preserved with structured warnings;
unchanged remote intent stays silent. Deleted tracked files/subtrees stay deleted.
Equal pre-existing content is not adopted. Overwrite targets declared values and
retains foreign siblings.

The adapter patches accepted nodes in the local AST. Shared alias nodes and
merge-key mappings are protected when an edit could change foreign content:
retain their previous ownership and emit a `shared-structure` conflict, including
under overwrite. Independent sibling changes can still apply. Existing comments,
quotes, flow/block styles, and anchors are retained where supported by the
[round-trip implementation](https://yaml.dev/doc/ruamel.yaml/detail/).
Semantic no-ops return the original bytes without dumping. Accepted edits can
normalize indentation or other emitter formatting; universal byte preservation
is not promised for changed documents.

The executor validates YAML before workspace writes, applies accepted content
through `TransactionAwareFS`, and writes candidate state only at transaction
completion. Parse errors commit nothing; later failures restore exact YAML/state
bytes and POSIX modes. Acceptance tests use temporary workspaces and mocked
processes. Identity-aware pre-commit editing remains PR E.

## PR E pre-commit boundary

Pre-commit configuration now uses the YAML round-trip adapter with exact `repo`
identities and `(repo, id)` hook identities, including `repo: local`. The adapter
presents keyed semantic values to the existing three-way kernel, then patches
accepted fields on the original sequence records. Repository/hook order, comments,
and foreign fields remain in the local AST. Owned snapshots remain ordinary YAML
with `repos` and `hooks` sequences; they never contain copied foreign hooks.

Repository revisions are owned independently of hook fields. Adding a managed hook
to an existing repository does not adopt its revision or its other hooks. User
edits and deletions retain their previous baselines, omitted contributions are not
pruned, and explicit overwrite targets declared fields while preserving foreign
siblings. Duplicate local repository blocks or hook IDs preserve the entire
ambiguous repository with a `duplicate-identity` conflict; independent repositories
can still change. Duplicate desired/state identities and malformed shapes are
fatal domain errors. Existing alias and merge-key protection also applies to keyed
records and sequences.

The executor captures one frozen registry snapshot before execution starts. Planning
still performs no network requests, and reconciliation never refetches pins.
Each automatic revision carries registry/fallback provenance. A fallback cannot
replace a previously applied pin, even when its version appears newer. Comparable
regressive versions and changed unorderable automatic revisions also preserve the
local pin with an `unsafe-pin` conflict. Explicit opaque revisions use the ordinary
three-way policy. Pin state advances only when an owned revision is accepted or
converged, and identical fallback responses do not relabel registry provenance.

Generation explicitly declares `default_install_hook_types` and `default_stages`
every run, including their defaults. This allows clean runner/install-type changes
to update owned top-level fields instead of leaving stale values through omission.
User changes to these atomic sequences still take precedence in merge mode.
Switching runners can add a new repository identity; the general no-pruning policy
retains the old repository and hooks.

File and pin state are staged together and written through the transaction-aware
filesystem. Unchanged runs write nothing. Failures, including a failure after the
state write, restore exact configuration/state bytes and POSIX modes. Generated
file and append-region checksum gates remain PR F; this milestone adds neither
pruning nor a `sync` command.

## PR F: Generated files, seeds, and regions

CI/release workflows, Dockerfile, and justfile use one pure exact-byte
SHA-256 gate. An absent never-owned target is created; an unchanged owned target
can update. Convergence advances an existing baseline without rewriting the file.
Unowned existing files are never adopted, including when their bytes equal the
desired output. Edited or deleted owned files remain untouched. A pending desired
change emits a structured conflict; an unchanged desired contribution does not
warn merely because the user edited or deleted it. Explicit overwrite can replace
a declared generated target and establish its new digest.

Renovate configuration is no longer checksum-gated; it is reconciled as JSONC
(see the JSONC boundary below). Dockerfile preservation does not prevent additive
`.dockerignore` updates.

Free-form files record paths actually seeded. Existing files remain unowned and
untouched in merge mode, regardless of extension; deleted seeded files stay absent.
New never-seeded paths can still be created.

Named append regions use the same gate per stable identity. Delimiters use subtle,
editor-folding-compatible comments (`# region: protostar <tag>` and `# endregion: protostar <tag>`)
carrying a deterministic 8-character hex tag derived from the region identity, while `.protostar.lock.toml`
preserves the tag, full logical ID, and digest. The digest covers
UTF-8 bytes from the begin marker through the end marker, including the payload
and internal line endings, excluding the newline following the end marker.
Replacement preserves all bytes outside that interval. Existing unowned regions
remain unowned; edited/deleted regions retain their old digest. Deleting an owned
region file protects newly introduced regions too. Omitted region identities
retain their baselines without pruning. Duplicate, nested, or malformed
boundaries raise domain errors, including boundaries injected by a new payload.

Accepted digests and seeded paths enter the candidate state only, with final state
writes through the transactional filesystem. No-op runs write nothing; failures
restore exact file/state bytes and POSIX modes. Resolver completion and end-to-end
Stage 1 acceptance remain PR G and PR H.

Generated targets with declared append regions (such as a template's justfile appends) checksum
the complete desired file and also retain individual region digests. If user edits
prevent whole-file regeneration, clean region updates can still apply independently.
A pre-existing unowned generated target can own a newly appended region without
acquiring whole-file ownership. When a previously managed region is omitted, merge
mode conservatively skips whole-file regeneration because its digest cannot
reconstruct the omitted payload; independently declared region updates still apply.

## PR G resolver and derived-artifact boundary

System tasks establish the local project first (`uv init` when needed). Structured
TOML and accepted typed include edges then apply before any dependency resolver.
Requirement selection remains per group, canonical package name, and normalized
marker; extras, bounds, and direct references remain requirement values. Only
accepted requests invoke `uv add`; successful requests record both declared intent
and the actual materialized requirement. Matching foreign entries remain unowned.
Unchanged declared intent preserves resolver-added bounds and later user edits.

Accepted `requires-python` or include-edge writes mark resolution dirty. A later
accepted `uv add` resolves the final metadata and clears that flag. Otherwise one
`uv lock` runs after all relevant writes. Identical repeats run neither command.
Include ownership records only managed edges and groups created for them in the
owned TOML baseline; foreign requirements and include records are never copied
into ownership. Deleted owned edges/groups stay deleted, including when a new
requirement would otherwise recreate their group. Removed template edges are
not pruned. Ambiguous include identities preserve local content with a conflict.

Resolver invocation requires a local project and a footprint containing both
`pyproject.toml` and `uv.lock`. Ancestor workspace ownership remains rejected.
Both resolver paths are journaled before invocation. Failures/timeouts are fatal;
interrupts terminate managed processes before rollback restores exact original
project, lock, and state bytes and modes. `.venv` and global caches remain outside
the rollback boundary. No AST dependency rewrite, implicit upgrade, or redundant
lock after an ordinary dependency addition is introduced.

The snapshot table-placement changes are intentional: dependency groups created
by the resolver now follow tooling tables that must exist before resolution.
Requirement values are unchanged. The CLI snapshot additionally records its
managed dev-to-docs edge and the initially created docs group.

## PR H acceptance and operational boundary

Stage 1 is complete. The acceptance suite deliberately separates broad
end-to-end evidence from focused synthetic-revision cases:

- `tests/test_template_repeatability.py` executes every built-in template in an
  isolated workspace, then performs two identical merge runs. It asserts
  byte-identical workspace and lock state, no managed mutations on either
  repeat, and exact-byte agreement between every persisted whole-file digest and
  its generated artifact.
- `tests/test_reconciliation_execution.py`, `tests/test_codecov_execution.py`,
  `tests/test_pre_commit_reconciliation.py`, `tests/test_checksum_execution.py`,
  and `tests/test_resolver_execution.py` provide synthetic v1-to-v2 revisions
  and conflict/failure cases. They cover non-overlapping edits, scalar/keyed/
  sequence conflicts, deletion protection, state-write rollback, resolver
  rollback, and generated/region baseline advancement.
- `tests/test_sync_state.py`, `tests/test_yaml_ast.py`, and
  `tests/test_intent.py` reject invalid state, unsupported YAML structures,
  unsafe paths, duplicate identities, reserved targets, and unsupported control
  keys before any execution mutation.

`init --force-merge` is therefore safe reinitialization, not an update product.
It requires the same selected template identity for a tracked project and
reconciles only recorded contributions. It does not adopt pre-existing files,
restore user-deleted content, prune omitted contributions, switch templates, or
reconstruct/rerun a request from the lock state. Those capabilities, along with a
user-facing `sync` command, remain deferred.

## Stage 2 shared preparation boundary

`protostar.preparation.prepare_review()` computes immutable accepted file bytes,
conflicts, preserved local deviations, candidate ownership, and resolver requests
from a manifest and captured workspace inputs. It uses the existing TOML, YAML,
keyed-hook, region, and checksum adapters through `Reconciliation`. Preparation
writes only to an in-memory byte sink; it never runs initializers, package managers,
template tasks, IDE probes, or registry acquisition. This is a headless backend
boundary; no public lifecycle command ships with this refactor.

Tool selection resolves project overrides, current template opinions, and captured
fallback before effective modules run pre-flight checks or declare contributions.
Producer attribution survives into the review, so opting out of one producer does
not suppress another producer contributing to the same target.

The caller supplies one acquired hook revision snapshot. A `SystemExecutor`
constructed with `review=review` consumes that snapshot and the exact accepted
bytes without acquiring pins again. The lifecycle policy skips every declared
system/post-install task and IDE extension probe. It applies direct edits and only
accepted resolver requests, materializes dependency ownership from actual resolver
output, and writes the ownership ledger last within the same transaction. Resolver
output stays unknown in review data: there is no simulated dependency rewrite or
fabricated `uv.lock` diff.

Initialization retains its own policy and prepares successive batches around
actual initializer and resolver execution. Original transaction presence still
distinguishes eligible initializer-created values from pre-existing user values.
Recipe refresh remains after post-install tasks and inside the state transaction.

Captured inputs include exact bytes, existence, POSIX modes, relevant ancestors,
`pyproject.toml`, `.protostar.lock.toml`, and declared resolver paths. Unsupported
nodes fail during preparation. Immediately before applying a batch, execution
checks the desired manifest and all captured inputs; a stale review fails before
that batch mutates anything. Fatal failures terminate managed processes and roll
back exact journaled bytes/modes. This protects the preparation/application
interval, without promising exclusion of concurrent writers during a transaction.

## JSONC boundary

`jsonc_ast.py` is a pure-Python, standard-library-only codec, editor, and
reconciliation adapter for `.github/renovate.json` and `.vscode/settings.json`.
It has no dependency beyond the merge kernel and domain errors, performs no I/O,
and never touches a terminal.

The dialect is JSONC: `//` and `/* */` comments and trailing commas over one
object root with unique string keys. JSON5 (single quotes, unquoted keys,
hexadecimal numbers) is unsupported, so `renovate.json5` and the other Renovate
alternatives remain untouched foreign locations. Duplicate keys, non-finite
numbers, lone surrogates, and non-object roots are domain errors. Input is bounded
to 1 MB, 100 nesting levels, and 10,000 nodes. Owned baselines use the strict
subset (no comments or trailing commas), deterministic key order, and preserve
null values.

The parser records source spans rather than rebuilding text. Every edit is a set of
replacements over those spans, so all bytes outside an accepted edit, including
comments, key order, quoting, number spellings, CRLF or LF line endings, and a
leading BOM, are identical. Inserted members copy the indentation, separator
style, and trailing-comma style of their neighbors, and stay compact inside
single-line containers. Accepted array replacements are applied by position, so
unchanged leading elements keep their comments; arrays remain atomic for
ownership. Comments on their own lines above a removed item are retained. A
semantic no-op returns the original bytes.

The existing three-way kernel controls ownership. Existing equal content is not
adopted, missing unowned keys may be added and owned, local edits and deletions are
preserved with structured conflicts, and explicit overwrite owns declared leaves
while retaining foreign siblings. A missing file receives the desired bytes
verbatim, so template comments and layout survive. Conflicts are reported at key
level. Blank or comment-only files gain a root object after their existing trivia.

Renovate declarations still arrive through the file-injection channel, so a template
`[files]` entry for `.github/renovate.json` follows the same path as the built-in
module. Recognized alternative Renovate locations prevent creation of a competing
configuration and produce an `unowned` conflict. A malformed generated or existing
Renovate document fails before any workspace mutation.

IDE settings reconcile the flat `python.*` preference keys as literal top-level keys
(not nested paths), indenting new content with four spaces. Existing user values are
preserved with a warning rather than overwritten. A settings file that is not a
valid JSONC object is an editor convenience: it is skipped with a warning and never
aborts the run. Writes use the transaction-aware filesystem, candidate state is
committed only at transaction completion, and failures restore exact bytes and modes.
