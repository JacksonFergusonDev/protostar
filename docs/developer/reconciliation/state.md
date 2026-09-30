---
description: "The schema-v1 ownership state stored in protostar.lock: records, file policies, dependencies, hook pins, and validation."
---

# Ownership state

`protostar.sync_state.SyncState` is a frozen candidate/committed model, serialized to `protostar.lock`. It holds:

- Producer provenance.
- An optional template reference.
- Tuples of file, dependency, and hook-pin records.

`with_file()` returns a new candidate and retains the other records. It never modifies committed state, and candidate updates are neither writes nor transaction commits.

## Serialization

`serialize_state()` and `deserialize_state()` operate on TOML strings with `tomlkit`.

- Paths and record identities sort deterministically.
- Owned baseline mapping keys sort recursively, while sequence order remains meaningful.
- No clock values, trust authorization, interpolation answers, or whole-workspace snapshots are recorded.
- Template provenance describes the latest successful transaction attempt. File baselines remain authoritative after partial conflicts.

## File policies

Each file record carries a policy that says what its stored baseline means:

| File policy | Stored ownership |
| :--- | :--- |
| `structured-toml` | TOML document string containing only applied contributions |
| `structured-yaml` | Validated YAML 1.2 document string containing only applied contributions |
| `structured-jsonc` | Strict JSON object string containing only applied contributions, including nulls |
| `text` | Last applied generated text, plus optional managed-region texts |
| `seed-only` | Path actually seeded; retained after deletion |
| `regions` | Delimited 8-hex tags, stable logical IDs, and last applied framed region texts |

TOML and YAML snapshots are validated by their own codecs, and unknown policies fail rather than accepting opaque documents. YAML snapshots preserve null values. The kernel's null values cannot be persisted through TOML, so its snapshot encoder rejects them explicitly. Native TOML scalars, arrays, and arrays of tables round trip without conversion through JSON or a tagged cross-format value system.

## Dependencies and hook pins

A dependency record keeps its identity (path, group, canonical name, normalized marker) plus the exact declared and materialized requirement strings. The codec validates PEP 508 syntax and that both requirements match the stored identity. Extras, specifiers, and direct references remain values.

A hook-pin record keeps the exact repository identity, the revision, and the registry, template, or fallback provenance. Hook fields need the YAML adapter's owned baseline, so a pin record never causes adoption.

## Validation

These are fatal `ConfigurationError` failures:

- Unknown fields, policies, or versions.
- Malformed snapshots and duplicate identities.
- Invalid digests.
- Noncanonical or escaping paths.

Paths must be relative POSIX workspace paths. They reject Windows drives and backslashes, and exclude engine state and resolver-owned `uv.lock` targets.

Missing state is a caller-level absence, not an empty or corrupt state document.

## Template identity

`check_template_identity()` allows a changed digest at the same source while rejecting template switching, alias retargeting, and tooling/template transitions. `Orchestrator.plan()` runs it through `check_workspace_identity()`, so every caller rejects a switch before it asks the user anything.
