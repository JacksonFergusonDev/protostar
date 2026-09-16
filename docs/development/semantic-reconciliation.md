# Semantic reconciliation contracts

PR B provides the pure kernel and schema-v1 state codec. PR C connects them to
transactional execution and TOML AST application, with early dependency selection
guards. PR D adds the YAML codec and validated YAML snapshots.

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
including lists inside unchanged mappings. File-specific keyed sequence policies
remain downstream.

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
| `checksum` | Last applied lowercase SHA-256 hex digest |
| `seed-only` | Path actually seeded; retained after deletion |
| `regions` | Stable region IDs and last applied SHA-256 digests |

Only TOML snapshots are supported at this milestone. YAML policy and snapshot
validation arrive together with PR D's format adapter; unknown policies fail
rather than accepting opaque unvalidated documents. Kernel null values cannot
be persisted through TOML: the TOML snapshot encoder rejects them explicitly.
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
AST. It patches the existing local AST and does not globally format an existing
document. Newly initialized `pyproject.toml` files retain the standard tool
banner and section markers. Explicit overwrite owns declared values
while retaining undeclared siblings. Personal project fields are seed-only in
merge mode; defaults written by a journaled initializer are eligible for initial
ownership, while pre-existing user metadata is preserved.

Conflict diagnostics include file, key path, optional identity, and an enum reason
in `ExecutionResult.to_dict()`. Safe siblings can apply despite other conflicts.
Existing equal values remain unowned. A tracked deleted file cannot be recreated
by new dependency requests or include-group wiring.

Unchanged declared dependency intent skips `uv add`, even when the materialized
requirement gained resolver bounds or the user later edited/deleted it. Changed
intent needs an unchanged materialized baseline; unowned existing constraints,
duplicate identities, known version regressions, and ambiguous constraint changes
are preserved with warnings. Converged previously owned intent advances its
record without a resolver call. Resolver failures remain fatal and restore the
journaled project, lock, and state bytes and modes.

PR G still owns complete include-group reconciliation and final TOML/resolver
ordering. YAML, generated-file digests, free-form seed ledgers, and managed-region
checksum application remain the later adapter milestones. This boundary adds no
adoption, pruning, migration layer, or new command.
