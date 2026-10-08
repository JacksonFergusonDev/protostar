---
description: "How the TOML, YAML, JSONC, and text engines apply accepted merge decisions while preserving the user's comments, layout, and bytes."
---

# Format Engines

The [kernel](kernel.md) decides what changes. A format engine applies that decision to the user's own document, patching the local AST or byte spans instead of regenerating the file.

No engine knows a file by name. Each reconciles whatever spec it is handed; see [Managed documents](documents.md).

| Engine | Module | Backing library |
| :--- | :--- | :--- |
| TOML | `toml_ast.py` | `tomlkit` |
| YAML | `yaml_ast.py` | `ruamel.yaml` |
| JSONC | `jsonc_ast.py` | Standard library only |
| Free-form text | `text_merge.py` | Standard library only |

All of them share the same execution guarantees. Accepted content is written through `TransactionAwareFS`, candidate state is committed only at transaction completion, and a failure restores exact bytes and POSIX modes.

## TOML

The TOML adapter keeps semantic intent separate from a desired `tomlkit` AST. The kernel decides ownership using plain values, while accepted nodes keep the authored comments, array layout, and inline-table style from that AST.

- Set-like additions retain existing local member nodes and their comments before desired-node replacement is considered.
- The adapter patches the existing local AST and does not globally format an existing document, even when adding a new tool to semantically unchanged managed configuration.
- Newly initialized `pyproject.toml` files keep the standard tool banner and section markers.
- Explicit overwrite owns declared values while retaining undeclared siblings.
- Personal project fields are seed-only in merge mode. Defaults written by a journaled initializer are eligible for initial ownership, while pre-existing user metadata is preserved.

## YAML

`yaml_ast.py` isolates `ruamel.yaml` typing and round-trip AST operations. The runtime dependency is `ruamel.yaml>=0.19.1,<0.20`, used through the [instance API](https://yaml.dev/doc/ruamel.yaml/api/) in pure-Python round-trip mode, without C extras or custom constructors.

### Accepted Input

YAML 1.2 is the default, and explicit 1.1 directives are rejected instead of silently reinterpreted. A document needs:

- One mapping root and unique string keys.
- JSON-like scalar types.
- Finite, acyclic collections.

Timestamp, binary, set, and custom tags, and multiple documents, fail with a domain error. Input is bounded to 1 MB, 100 nesting levels, and 10,000 expanded nodes. Graph validation precedes construction, so recursive aliases are rejected.

### Ownership and Conflicts

Owned baselines use the `structured-yaml` policy and are serialized canonically from owned values only, never from the local round-trip document.

The three-way kernel controls scalar ownership and mapping recursion. Changed local targets are preserved with structured warnings, and unchanged remote intent stays silent. Deleted tracked files and subtrees stay deleted, equal pre-existing content is not adopted, and overwrite targets declared values while retaining foreign siblings.

Shared alias nodes and merge-key mappings are protected whenever an edit could change foreign content. Their previous ownership is retained and a `shared-structure` conflict is emitted, even under overwrite. Independent sibling changes can still apply.

### Preserving the File

The adapter patches accepted nodes in the local AST, and comments, quotes, flow and block styles, and anchors are retained where the [round-trip implementation](https://yaml.dev/doc/ruamel.yaml/detail/) supports it.

- A semantic no-op returns the original bytes without dumping.
- A missing file that accepts the whole desired document receives the desired text verbatim, so its comments survive.
- A changed document is emitted in the block indentation detected from the local file (nested mapping indent, sequence dash offset, item indent, and indentless sequences), with no line-width limit, so untouched long lines are never folded.
- New mapping keys and records are inserted after their nearest earlier desired sibling that exists locally, otherwise before their nearest later one, otherwise at the end.

!!! warning "Byte preservation is not universal"
    The emitter applies one style per document. A file that mixes indentation styles, or uses non-default flow spacing such as `[ a ]`, can be normalized outside the edited values.

When the local file does not end with a blank line, an emitted document ends with exactly one newline. Removing a trailing item would otherwise leave its separator blank line behind on the item before it.

### Keyed Records

Pre-commit configuration uses exact `repo` identities and `(repo, id)` hook identities, including `repo: local`. The adapter presents keyed semantic values to the kernel and then patches accepted fields on the original sequence records, so repository and hook order, comments, and foreign fields remain in the local AST. Owned snapshots stay ordinary YAML with `repos` and `hooks` sequences and never contain copied foreign hooks.

- Repository revisions are owned independently of hook fields. Adding a managed hook to an existing repository adopts neither its revision nor its other hooks.
- Duplicate local repository blocks or hook IDs preserve the entire ambiguous repository with a `duplicate-identity` conflict. Independent repositories can still change.
- Duplicate desired or state identities and malformed shapes are fatal domain errors.
- Alias and merge-key protection also applies to keyed records and sequences.

Generation declares `default_install_hook_types` and `default_stages` on every run, including their defaults. A clean runner or install-type change can then update owned top-level fields instead of leaving stale values through omission. User changes to these atomic sequences still win in merge mode.

### Hook Pins

The executor captures one frozen registry snapshot before execution starts. Planning performs no network requests, and reconciliation never refetches pins.

- Each automatic revision carries registry or fallback provenance.
- A fallback cannot replace a previously applied pin, even when its version appears newer.
- A comparable regressive version, or a changed unorderable automatic revision, preserves the local pin with an `unsafe-pin` conflict.
- Explicit opaque revisions use the ordinary three-way policy.
- Pin state advances only when an owned revision is accepted or converged, and identical fallback responses do not relabel registry provenance.

## JSONC

`jsonc_ast.py` is a pure, standard-library-only codec, editor, and reconciliation adapter for `.github/renovate.json` and `.vscode/settings.json`. It has no dependency beyond the merge kernel and domain errors, performs no I/O, and never touches a terminal.

### Dialect

JSONC means `//` and `/* */` comments and trailing commas over one object root with unique string keys. JSON5 (single quotes, unquoted keys, hexadecimal numbers) is unsupported, so the `.json5` Renovate locations are [competitors](documents.md#document-locations), never edited.

Duplicate keys, non-finite numbers, lone surrogates, and non-object roots are domain errors. Input is bounded to 1 MB, 100 nesting levels, and 10,000 nodes. Owned baselines use the strict subset (no comments or trailing commas) with deterministic key order, and they preserve null values.

### Editing by Span

The parser records source spans instead of rebuilding text, and every edit is a set of replacements over those spans. Every byte outside an accepted edit is identical, including comments, key order, quoting, number spellings, CRLF or LF line endings, and a leading BOM.

- Inserted members copy the indentation, separator style, and trailing-comma style of their neighbors, and stay compact inside single-line containers.
- Accepted array replacements are applied by position, so unchanged leading elements keep their comments. Arrays stay atomic for ownership.
- Comments on their own lines above a removed item are retained.
- A semantic no-op returns the original bytes.
- Blank or comment-only files gain a root object after their existing trivia.

### Ownership

The kernel controls ownership as usual. Existing equal content is not adopted, missing unowned keys may be added and owned, local edits and deletions are preserved with structured conflicts, and explicit overwrite owns declared leaves while retaining foreign siblings. Conflicts are reported at key level. A missing file receives the desired bytes verbatim, so template comments and layout survive.

### Renovate and IDE Settings

Renovate declarations arrive through the file-injection channel, so a template `[files]` entry for `.github/renovate.json` follows the same path as the built-in module. A Renovate configuration at another location Renovate reads is merged in place when it is JSONC and held as a competitor when it is JSON5. A malformed generated or existing Renovate document fails before any workspace mutation.

IDE settings reconcile the flat `python.*` preference keys as literal top-level keys (not nested paths) and indent new content with four spaces. Existing user values are preserved with a warning. A settings file that is not a valid JSONC object is an editor convenience: it is skipped with a warning and never aborts the run.

## Text Merge

`text_merge.py` merges free-form text line by line, for managed files that have no structured format to reconcile. It is pure, with no subprocess, filesystem access, or terminal output, so planning and change review call it like the semantic kernel.

!!! note "Why not `git merge-file` or merge3?"
    `git merge-file` was rejected because the merge must run during planning, where no subprocess may run, and tests could only mock it. merge3 was rejected for its GPL license.

### Algorithm

`merge_text(base, local, remote)` is diff3 (Khanna, Kunal & Pierce, 2007) over patience-diff alignments.

- Stretches with no line unique to both sides fall back to `difflib` alignment within a bounded cost. Past the bound a stretch counts as wholly changed, which can only coarsen hunks into a conflict, never produce a wrong merge.
- Lines split on `\n` alone and keep their terminators, so a missing final newline is an edit.
- When the local text uses one newline style throughout, base and remote texts that consistently use the other are converted first. A checkout that rewrites line endings is therefore not an edit, and the merged text keeps the local style.

### Hunks and Conflicts

A hunk changed by one side takes that side, and identical changes on both sides merge. Overlapping and adjacent edits conflict, as in git. Lines both sides added identically at the edges of a conflict leave it (git's `zdiff3` refinement), so a `TextConflict` spans only disagreeing lines.

A `TextConflict` holds its zero-based `start` in the local text and the base, local, and remote lines. Its `lines` property converts that to the `LineSpan` a `MergeLocation` carries into diagnostics and review JSON: a one-based `start` and a `count`, numbered like a unified diff hunk header, so a zero `count` sits after line `start`.

A conflicted merge returns no text. Two hunks of one generator change can depend on each other, so adapters keep the local file whole or accept the merged file whole and never write a partial merge.

### Agreement with Git

Clean merges match `git merge-file` byte for byte. Where the two disagree on whether a merge is clean (a fraction of a percent of randomized cases), the cause is ambiguous placement among repeated lines, where patience and Myers alignments legitimately differ. `scripts/compare_text_merge.py` reruns that comparison.

## Generated Files, Seeds, and Regions

### Generated Files

The Dockerfile and justfile record the text Protostar last applied and reconcile through `reconcile_text`.

| Local state | Outcome |
| :--- | :--- |
| Never-owned and absent | Created. |
| Owned and unchanged | Takes the desired text exactly. |
| Owned and converged | The baseline advances without rewriting the file. |
| Existing and unowned | Never adopted, even when its bytes equal the desired output. |
| Owned and deleted | Stays deleted. |
| Owned and edited | Merged three ways against the baseline. |

In a three-way merge, non-overlapping edits combine and the baseline advances to the desired text. Overlapping edits keep the whole local file and the previous baseline, with one `diverged` conflict per overlap carrying its `LineSpan`. Local bytes that are not UTF-8 count as edited.

An unchanged desired contribution does not warn merely because the user edited or deleted it. Explicit overwrite can replace a declared generated target and own its text. A record from before text baselines (digest-only `checksum`) is rejected as an unknown policy, with no migration. Dockerfile preservation does not prevent additive `.dockerignore` updates.

**Releasing a generated file.** A generated file whose tool is switched off (`EnvironmentManifest.generated_files` no longer lists it) and that receives no declared region is released by `Reconciliation._release_undeclared_generated`:

- Deleted when its text matches the whole-file baseline.
- Forgotten when already deleted.
- Otherwise a `retracted` conflict for the whole file, where `local` keeps it as the user's and `desired` deletes it.

Generated text has no units to keep apart, so this decision is never split into hunks.

### Seeds

Free-form files record only the paths actually seeded. Existing files remain unowned and untouched in merge mode, regardless of extension, and deleted seeded files stay absent. New never-seeded paths can still be created.

### Regions

Named append regions use the same `reconcile_text` gate per stable identity. Delimiters are subtle, editor-folding-compatible comments carrying a deterministic 8-character hex tag derived from the region identity:

```text
# region: protostar <tag>
# endregion: protostar <tag>
```

`protostar.lock` preserves the tag, the full logical ID, and the last applied framed text. That text spans the begin marker through the end marker, including the payload and internal line endings, and excludes the newline following the end marker. Replacement preserves all bytes outside that interval.

| Region state | Outcome |
| :--- | :--- |
| Existing and unowned | Stays unowned. |
| Edited | Merged line by line. Overlapping edits keep the local block whole and its previous text, with one `diverged` conflict per overlap. The `LineSpan` is numbered in the final file, after other regions' accepted updates. |
| Deleted | Stays deleted. Deleting an owned region file protects newly introduced regions too. |
| Owned, no longer declared | Removed when unedited (with the blank line appending put before it), kept with a `retracted` conflict when edited, forgotten when already deleted. |

Duplicate, nested, or malformed boundaries raise domain errors, including boundaries injected by a new payload. A record from before region texts (digest-only) is rejected as an unknown field.

**With a generated target.** A target with declared append regions, such as a template's justfile appends, records the complete desired text and also retains each region's text. If overlapping edits prevent the whole-file merge, clean region updates can still apply independently. A pre-existing unowned target can own a newly appended region without acquiring whole-file ownership. A target where Protostar owns only regions (the `regions` policy) is left to the region step.

When a previously managed region is omitted, the generated writer retracts it before regenerating, so the file converges in the same run:

- An unedited region is removed from the file and cut from the whole-file baseline.
- A region the user already deleted is forgotten.
- A settled region is taken or kept.
- A region kept with its local edit is the user's, so it sits out the three-way merge (a generated line changed next to it would otherwise overlap) and is appended after the merged text.

While an edited omitted region waits for its decision, the writer leaves the file alone and the region step reports it. The file regenerates in the run that settles it.
