---
description: "The pure three-way merge kernel: how Protostar decides which values it owns, keeps, applies, or reports as conflicts."
---

# Kernel and Ownership

`protostar.merge.reconcile()` is the format-neutral heart of every structured merge. It accepts decoded semantic `base`, `local`, and `remote` values plus a `MergeLocation` and a `MergePolicy`.

- **Base** is the owned baseline: what Protostar last applied.
- **Local** is what the file holds now.
- **Remote** is what Protostar wants now.

Format adapters keep the local AST and apply accepted decisions to it, so user documents are never regenerated. The kernel does no filesystem access, runs no subprocess, and prints nothing. Inputs and returned mutable collections share no objects.

## Values

`MISSING` represents absence; `None` represents a present null. Equality checks semantic types, including boolean versus integer and native TOML date/time values. Cyclic, unsupported, and excessively nested values fail with domain errors.

## Results

`MergeResult` returns:

- The semantic value.
- The composite owned baseline.
- An aggregate decision: `KEEP_LOCAL`, `APPLY_REMOTE`, or `CONFLICT`.
- The concrete file, key, and record conflicts.

An aggregate conflict may still contain accepted sibling changes, so adapters must inspect the returned values rather than discard everything on a conflict. No diagnostic strings or prompts belong to this interface.

## Decision Rules

- Omitted remote values retain local values and previous ownership, unless the policy is `complete`.
- Missing unowned values may be added and owned. Existing equal values remain unowned, because equality is insufficient for adoption.
- Owned convergence advances the baseline without requiring a write.
- Unchanged remote intent preserves local edits and deletions without warning.
- An unchanged local owned value can accept a changed remote value.
- Divergence, incompatible types, and changed intent under a deleted owned ancestor preserve local content and previous ownership, with a conflict.

## Mappings

Mapping reconciliation retains foreign siblings and local insertion order while advancing only successful owned children. A deleted or incompatible owned mapping protects its entire subtree.

An adapter operating directly on a child of a protected file or record must set `protected_ancestor`, because it cannot infer ancestor ownership from that child alone.

The following belong to adapters or execution, not to the kernel:

- Initializer-output exceptions.
- The overwrite strategy.
- Keyed identities.
- Diagnostic presentation.

## Sequences

Sequences are atomic by default, including arrays of tables. An adapter can declare set-like key paths in `MergePolicy`. A set-like sequence:

- Accepts unique scalars only.
- Retains local order and user deletions.
- Retains omitted baseline members.
- Appends new accepted members in desired order.

Existing foreign equal members never become owned. Policy validation examines all inputs before any truth-table shortcut, including lists inside unchanged mappings. Keyed record sequences are declared per YAML document; see [YAML document specs](documents.md#yaml-document-specs).

## Complete Documents and Retraction

A policy with `complete` set treats the remote value as one generator's complete document. An owned mapping key it no longer declares is retracted instead of retained:

| Local state of the retracted content | Outcome |
| :--- | :--- |
| Unedited | Removed from the value and the baseline. |
| Already deleted by the user | Leaves the baseline only. |
| Differs from its baseline, including foreign keys added inside it | Kept with its previous ownership and a `retracted` conflict. |

Retraction happens once, at the highest key that disappeared, so a partly edited record is never reduced to a fragment. The exception is a `namespace_paths` mapping, whose keys are separate units retracted one at a time while foreign keys stay.

`retained_paths` names owned paths that another writer manages; these are never retracted.

The complete-document adapters are GitHub Actions workflows, `.pre-commit-config.yaml`, `.readthedocs.yaml`, and `pyproject.toml`. A hook configuration retracts each hook by `id` and each repository by `repo`, and a repository's pin leaves `protostar.lock` with it. For `pyproject.toml`, the aggregated contributions of its producers are the complete declaration: `[tool]` is its namespace, and its seed paths and `dependency-groups` (which the include writer owns) are retained. Every other adapter keeps the no-pruning default.

### Documents Nothing Declares Any More

A document can lose every producer, because its tool or template option is switched off or its template stops contributing to it. It is still visited: `Reconciliation._release_undeclared_documents` reconciles every owned TOML, YAML, and JSONC record that no declared document reads against an empty declaration, under its own spec with `complete` set. "Declared" is `EnvironmentManifest.declared_documents`, expanded through each document's locations.

- Seed paths and retained paths are retracted too, and guards are off, because nothing is wanted.
- Explicit overwrite covers declared targets only, so an edited unit is always a decision.
- A document is declared while any producer contributes to it, even when this run holds it, so a held document is never retracted.

Once no owned content is left and no `retracted` conflict is open, the record is dropped along with its hook pins. A file whose decoded value is then empty is deleted, and one with foreign keys stays as the user's. A file the user already deleted is forgotten.

Generated text files and append regions are released by the same idea; see [text files and regions](formats.md#generated-files-seeds-and-regions).
