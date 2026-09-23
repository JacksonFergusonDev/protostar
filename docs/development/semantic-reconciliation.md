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
including lists inside unchanged mappings. Keyed record sequences are declared per YAML document; see [YAML document specs](#yaml-document-specs).

A policy with `complete` set treats the remote value as one generator's complete document, so an owned mapping key it no longer declares is retracted rather than retained. Unedited owned content is removed from the value and the baseline; content the user already deleted only leaves the baseline; content that differs from its baseline, including foreign keys added inside it, is kept with its previous ownership and a `retracted` conflict. Retraction happens once, at the highest key that disappeared, so a partly edited record is never reduced to a fragment. Only complete-document adapters set it (GitHub Actions workflows and `.readthedocs.yaml`); every other adapter keeps the no-pruning default.

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
| `text` | Last applied generated text, plus optional managed-region digests |
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
The channel accepts one managed producer per target in
`documents.YAML_CONTRIBUTION_TARGETS` (`.github/codecov.yml` and `.readthedocs.yaml`); it does not infer
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
Semantic no-ops return the original bytes without dumping. A missing file that
accepts the whole desired document receives the desired text verbatim, so its
comments survive. A changed document is emitted in the block indentation detected
from the local file (nested mapping indent, sequence dash offset, and item indent,
including indentless sequences) with no line-width limit, so untouched long
lines are never folded. The emitter applies one style per document: a file mixing
indentation styles, or using non-default flow spacing such as `[ a ]`, can still
be normalized outside the edited values, so universal byte preservation is not
promised for changed documents.

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

## Document locations

Whether two paths hold the same configuration is a fact about the tool that reads them, not about the file format, so there is no rule that `.yml` and `.yaml` are interchangeable. Each document module declares its tool's locations as a `DocumentLocations` (`documents/locations.py`), verified against each tool's source:

| Document | Aliases (edited in place) | Competitors (never edited) | Tool reads |
| :--- | :--- | :--- | :--- |
| `.readthedocs.yaml` | `.readthedocs.yml`, `readthedocs.yaml`, `readthedocs.yml` | | one file, in directory-listing order |
| `.github/codecov.yml` | `codecov`/`.codecov` with `.yml`/`.yaml`, in the root, `.github/`, and `dev/` | | one file: the root first, then `dev/` or `.github/` |
| `.pre-commit-config.yaml` with prek | `.pre-commit-config.yml` | `prek.toml` | one file: `prek.toml`, then `.yaml`, then `.yml` |
| `.pre-commit-config.yaml` with pre-commit | | `.pre-commit-config.yml` | only the canonical name |
| `.github/workflows/ci.yml`, `release.yml` | the `.yaml` spelling | | every file, each as its own workflow |
| `.github/renovate.json` | `renovate.json`, `renovate.jsonc`, `.github/renovate.jsonc`, `.renovaterc`, `.renovaterc.json`, `.renovaterc.jsonc` | the `.json5` spellings | one file; `.gitlab/` is ignored on GitHub |
| `zensical.toml` | | `mkdocs.yml`, `mkdocs.yaml` | one configuration |

Aliases are paths the tool reads as the same document, in a form Protostar edits. Competitors are configurations the tool may read instead, in a form Protostar does not edit: TOML where Protostar writes YAML, JSON5, or MkDocs. Pre-commit ignores `.pre-commit-config.yml`, but a lone copy means the user's hooks are not running, so it is a competitor rather than something Protostar silently creates a second configuration next to. `exclusive` records whether the tool reads a single configuration; GitHub Actions does not.

`resolve_location` decides which file a run edits:

- An owned file that exists is edited in place.
- Otherwise a single existing editable file is adopted, like an existing canonical file, or followed when the ownership record names another path. Renames are followed in both directions, including `.yml` to `.yaml` and back. The record, its baseline, and pre-commit's pin provenance move to the new path, so edits made before the rename still merge three ways.
- An owned file that no longer exists, with nothing to follow, keeps its record, and the merge keeps the deletion.
- For an exclusive tool, every other configuration present next to the edited file is reported as `duplicate-identity` at that path: either Protostar's file or the other one is being ignored. When several are present and none is owned, nothing is edited and each is reported, because Protostar cannot tell which one the tool reads. A competitor alone holds the document and reports `unowned` at the target, as before.
- A non-exclusive tool never conflicts: the owned file, else the target, else the single alias is edited, and a second workflow with the other extension is left alone.

Protostar never renames a user's file back to the canonical name. Ownership records stay keyed by the real path, so the lock file names the file that is owned. `Reconciliation._locate` applies the resolver to every YAML, JSONC, and TOML document before its merge, under explicit overwrite too. The same locations drive the collision prompt (`EnvironmentManifest.colliding_files`, so an existing alias asks to merge or overwrite like the canonical file), the dry-run tree (`written_files`), and every lookup by recorded path (`documents.yaml_spec`, used by state validation, preserved deviations, and append-region rejection). Existence probes during preparation capture each path, so a review goes stale when a competing copy appears or disappears.

## YAML document specs

Every YAML document the engine reconciles is described by a `YamlDocumentSpec`. The spec lives with its document in `src/protostar/documents/` (see [Document catalog](#document-catalog)) and is registered by path in `documents.YAML_DOCUMENTS`. A spec names the document for domain errors, supplies the kernel `MergePolicy` (Codecov's set-like `ignore`), and declares its keyed sequences. Nothing outside the catalog compares against YAML file names: state validation, preserved-deviation inspection, and append-region rejection look up the spec with `documents.yaml_spec(path)`, which knows every name the document may be edited under. The structured contribution channel accepts only the targets in `documents.YAML_CONTRIBUTION_TARGETS` (Codecov and Read the Docs), declared by their canonical path, because pre-commit and workflows arrive through their own generators. Where each tool reads its document is declared separately (see [Document locations](#document-locations)).

A `KeyedSequence` gives a path pattern in the keyed view and an identity field. In the keyed view each record is presented under its identity, so an enclosing keyed record appears in the path as its identity, and the `WILDCARD` sentinel matches exactly one segment: pre-commit declares `repos` by `repo` and `repos.*.hooks` by `id`. Optional string fields (pre-commit's `rev`) must be non-empty strings whenever present.

- Desired and owned snapshots must identify every record exactly once; anything else is a fatal domain error.
- A local record without an identity is foreign. It is left out of the keyed view, never owned, and stays at its position in the file.
- A repeated local identity is ambiguous. For a nested sequence the entry containing it is held (the repository owning duplicate hooks); for a top-level sequence only the repeated identity is held. Each hold reports one `duplicate-identity` conflict, and independent entries still merge.
- A new record is inserted after its nearest earlier desired sibling that exists locally, otherwise before its nearest later one, otherwise at the end. Consecutive new records keep desired order.

New mapping keys are inserted after their nearest earlier desired sibling that exists locally, by the same rule as new records. When the local file does not end with a blank line, an emitted document ends with exactly one newline: removing a trailing item would otherwise leave its separator blank line behind on the item before it. Append regions are rejected for every registered YAML document, because appended text cannot be merged by structure.

Document policies pass a `YamlGuard` to `reconcile_yaml`. A guard policy receives the path of the file being reconciled, which may be an alias, so its conflicts name the real file: keyed-view paths to hold, plus the conflicts the policy found, which are reported ahead of the merge's own. A hold replaces the desired value at that path with the owned baseline value, or drops it when nothing there is owned, so the kernel sees unchanged intent: local content and previous ownership stay, and the hold adds no conflict of its own. Explicit overwrite omits held paths instead of overlaying them. The pre-commit pin guard holds `repos.<repo>.rev` rather than rewriting the desired document, so other additions keep their desired key order and styling. A guard that depends only on the decoded documents is registered by path in `documents.YAML_GUARDS` (the workflows and Read the Docs); pre-commit's is planned per run from registry responses, so its caller passes it directly.

## GitHub Actions workflows

`.github/workflows/ci.yml` and `release.yml` share one `github_workflows.SPEC`: there is no per-file behavior, only a different generator producing the desired document. Workflow files Protostar does not generate are never read or written.

- Mappings merge by key through the kernel, so user-added triggers, permissions, environment, jobs, and `with:` inputs are foreign siblings and never touched.
- `jobs.*.steps` is keyed by step `name`. Every generated step is named, uniquely within its job, and a logical step keeps its name in every generator variant (`tests/test_workflows.py` enforces the exact set). Unnamed local steps are foreign and stay in place. A renamed step reads as a deletion of the old name plus a foreign step.
- Every other sequence is atomic: branch filters, matrix axes, `include`, `needs`.
- The policy is complete, so when the generator stops emitting something (for example Codecov upload steps after Codecov is turned off) unedited copies are removed and edited ones are kept with a `retracted` conflict. Turning the CI tool off produces no document, so nothing is touched.

`github_workflows.guard_workflow` builds the workflow's `YamlGuard` from two rules, both implemented as holds:

- A job that exists locally but is not owned is held whole and reported as `unowned` at `jobs.<id>`, including under explicit overwrite. Protostar never grafts its steps into a job it did not create; its other jobs are still added.
- When an owned step's local `uses` names the same action as the owned baseline but a different ref, and the ref differs from the desired one too, the ref belongs to the user (a Renovate SHA pin, a manual bump or rollback). It is kept without a conflict, reported as a preserved deviation, and `sync --check` passes. If the local ref already equals the desired ref, ownership converges normally. Local (`./`) and `docker://` actions carry no ref and follow the ordinary rules; a changed action path is an ordinary conflict.

Existing workflow files are parsed during preparation, before any batch mutates the workspace, so a malformed or unsupported workflow fails like any other structured YAML document.

## .readthedocs.yaml

The Read the Docs module declares `.readthedocs.yaml` as a structured YAML contribution. Its build jobs install uv, sync the `docs` group, and run `zensical build`. `documents.readthedocs.SPEC` encodes two facts about how Read the Docs reads the file, both verified against its source:

- Read the Docs loads the first file matching `^\.?readthedocs.ya?ml$` in directory-listing order, so `.readthedocs.yml`, `readthedocs.yaml`, and `readthedocs.yml` are aliases (see [Document locations](#document-locations)). A renamed configuration is followed, and a second one next to the managed file is reported, because the filesystem would choose between them.
- The policy is complete. The configuration is the module's whole output, so a job Protostar stops generating is retracted instead of lingering to override the build. Every sequence is atomic: a job's commands are an ordered script.

Protostar's jobs are not settings added next to the user's; they replace build steps. `build.jobs.create_environment`, `install`, and `build.html` each skip the default step that the `sphinx`, `mkdocs`, `python`, and `conda` settings configure, and Read the Docs rejects `build.jobs` next to `build.commands`. `readthedocs.guard_build` therefore holds `build.jobs` whenever the local configuration has a non-empty `build.commands` or any of those four settings, under explicit overwrite too, so Protostar never grafts its build onto one that already works another way. Other settings still merge by the ordinary rules.

The hold reports `unowned` at `build.jobs` only when it withholds a change: the desired jobs differ from both the owned baseline and the local jobs. Adopting an existing Sphinx or MkDocs configuration reports it. A user who replaced Protostar's jobs with their own build after the scaffold is not warned, and `sync --check` passes, until a later Protostar release changes the jobs.

## TOML document specs

A `TomlDocumentSpec` lives with its document in `src/protostar/documents/` and is looked up with `documents.toml_spec(path)`. Besides the kernel `MergePolicy`, super tables, and layout, it declares document policy as data:

- `seed_paths` are written only while Protostar creates the document or explicit overwrite is selected. `reconcile_toml` holds every seed it has written at its owned value and drops every other seed, so a seed never merges into an existing document, editing or deleting one never conflicts, and a changed seed default is never applied. A written seed stays owned, so deleting its table still reads as a deletion (the dependency guards rely on an owned `project` table). pyproject's personal metadata is declared this way.
- `root_table` names the table that holds every setting Protostar declares, for tools that also accept settings at the top level. An existing document with settings but without that table is left alone and reported as `unowned` at the file, because adding the table would hide those settings from the tool.
`Reconciliation._append_files` checks `root_table` before the merge, under explicit overwrite too, because it protects what the tool reads rather than who owns a value. A document without a layout keeps its own end-of-file newlines: a desired table copied from the middle of a contribution would otherwise bring along the blank line that separated it from its next sibling.

## zensical.toml

Zensical reads its settings from `[project]`, or from the top level when that table is absent, and prefers `zensical.toml` over `mkdocs.yml`. `documents.zensical.SPEC` splits the document by what Protostar can change without changing the user's site:

- Managed: `project.theme.features`, merged by membership, and `project.plugins.mkdocstrings`, which configures the `mkdocstrings[python]` package the module installs.
- Seeded: `site_name`, `site_description`, `nav`, `theme.palette`, `theme.font`, `markdown_extensions`, and `extra`. They are the site's identity, content, and look. The extension table is all or nothing: listing extensions replaces Zensical's defaults, so adding entries to a document without the table would turn every other default off. Seeding it also keeps Protostar away from the two spellings Zensical accepts for one extension (dotted `pymdownx.details` and quoted `"pymdownx.details"`), which a key-level merge would duplicate.
- `root_table` is `project`. `mkdocs.yml` and `mkdocs.yaml` are competitors (see [Document locations](#document-locations)): Protostar does not create `zensical.toml` next to them and reports one that appears next to an owned site.

The scaffold's extension list mirrors Zensical's `DEFAULT_MARKDOWN_EXTENSIONS`, spelled the way `zensical new` writes it, so a scaffolded site renders what a site without the table would. `tests/test_zensical_execution.py` compares the two whenever Zensical is installed.

## Document catalog

The format engines (`toml_ast.py`, `yaml_ast.py`, `jsonc_ast.py`) know no file by name. Each one reconciles a document under a spec it is handed (`TomlDocumentSpec`, `YamlDocumentSpec`). The YAML engine exposes one extension point for document policy, the `YamlGuard`; a TOML spec declares its policy as data (see [TOML document specs](#toml-document-specs)). Everything specific to one file lives in its own module under `src/protostar/documents/`:

| Module | Owns |
| :--- | :--- |
| `pyproject` | `TARGET`, `SPEC` (set-like lint selections, personal metadata as seed paths, the `tool` super table, the canonical layout), the resolver footprint, dependency-group includes. |
| `pyproject_layout` | The canonical `pyproject.toml` section order, banner, and headers. |
| `locations` | `DocumentLocations` and `resolve_location`, shared by every document (see [Document locations](#document-locations)). |
| `pre_commit` | `TARGET`, `SPEC` (repos by `repo`, hooks by `id`), `LOCATIONS` per hook runner, and `plan_hook_pins`, whose `HookPinPlan` guards unsafe automatic pins and advances pin provenance after the merge, moving it with a followed configuration. |
| `github_workflows` | `CI_TARGET`, `RELEASE_TARGET`, `SPEC`, `CI_LOCATIONS`, `RELEASE_LOCATIONS`, and `guard_workflow`. |
| `codecov` | `TARGET`, `SPEC` (set-like `ignore`), and `LOCATIONS`. |
| `readthedocs` | `TARGET`, `SPEC` (complete), `LOCATIONS`, and `guard_build`. |
| `zensical` | `TARGET`, `SPEC` (set-like `theme.features`, seed paths, the `project` root table), and `LOCATIONS` (the MkDocs competitors). |
| `renovate` | `TARGET` and `LOCATIONS`. |
| `vscode` | The settings target and its default indentation. |

The package's `__init__` assembles the registries callers look up by path: `YAML_DOCUMENTS`, `YAML_CONTRIBUTION_TARGETS`, `YAML_GUARDS`, `LOCATIONS`, `document_locations(target, hook_runner)`, `yaml_spec(path)`, and `toml_spec(path)`, which returns `DEFAULT_TOML_SPEC` (plain tables, atomic arrays, tomlkit's own output) for any TOML file without a spec. Every YAML and JSONC document is applied through one path: `Reconciliation._locate` resolves the file, then `_reconcile_document` reads it, builds the guard from its path and the decoded desired, local, and owned values, reconciles, records the baseline (moving the record when the file was followed), and writes. Adding a document means adding a module and a registry entry, not a branch in an engine.

## PR F: Generated files, seeds, and regions

Dockerfile and justfile record the text Protostar last applied and reconcile
through `reconcile_text` (see [Text merge engine](#text-merge-engine)). An absent
never-owned target is created; an unchanged owned target takes the desired text
exactly. Convergence advances an existing baseline without rewriting the file.
Unowned existing files are never adopted, including when their bytes equal the
desired output. Deleted owned files stay deleted. An edited owned file merges
three ways against its baseline: non-overlapping edits combine and the baseline
advances to the desired text; overlapping edits keep the whole local file and the
previous baseline, with one `diverged` conflict per overlap carrying its
`LineSpan`. Local bytes that are not UTF-8 are treated as edited. An unchanged
desired contribution does not warn merely because the user edited or deleted it.
Explicit overwrite can replace a declared generated target and own its text. A
digest-only `checksum` record from before text baselines is rejected as an
unknown policy; there is no migration.

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

Generated targets with declared append regions (such as a template's justfile
appends) record the complete desired text and also retain individual region
digests. If overlapping edits prevent the whole-file merge, clean region updates
can still apply independently.
A pre-existing unowned generated target can own a newly appended region without
acquiring whole-file ownership. When a previously managed region is omitted, merge
mode skips whole-file regeneration, because regenerating without the region would
remove it and regions are never pruned; independently declared region updates
still apply.

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
hexadecimal numbers) is unsupported, so the `.json5` Renovate locations remain
untouched competitors. Duplicate keys, non-finite
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
module. A Renovate configuration at another location Renovate reads is merged in
place when it is JSONC and held as a competitor when it is JSON5 (see
[Document locations](#document-locations)). A malformed generated or existing
Renovate document fails before any workspace mutation.

IDE settings reconcile the flat `python.*` preference keys as literal top-level keys
(not nested paths), indenting new content with four spaces. Existing user values are
preserved with a warning rather than overwritten. A settings file that is not a
valid JSONC object is an editor convenience: it is skipped with a warning and never
aborts the run. Writes use the transaction-aware filesystem, candidate state is
committed only at transaction completion, and failures restore exact bytes and modes.

## Text merge engine

`text_merge.py` merges free-form text line by line, for managed files that have no
structured format to reconcile semantically. It is pure: no subprocess, filesystem
access, or terminal output, so planning and change review call it like the
semantic kernel. It depends only on the standard library. `git merge-file` was
rejected because the merge must run during planning, where no subprocess may run,
and tests could only mock it; merge3 was rejected for its GPL license.

`merge_text(base, local, remote)` is diff3 (Khanna, Kunal & Pierce, 2007) over
patience-diff alignments. Stretches with no line unique to both sides fall back to
`difflib` alignment within a bounded cost; past the bound a stretch is treated as
wholly changed, which can only coarsen hunks into a conflict, never produce a wrong
merge. Lines split on `\n` alone and keep their terminators, so a missing final
newline is an edit. When the local text uses one newline style throughout, base and
remote texts that consistently use the other are converted first: a checkout that
rewrites line endings is not an edit, and the merged text keeps the local style.

Hunks changed by one side take that side; identical changes on both sides merge.
Overlapping and adjacent edits conflict, as in git. Lines both sides added
identically at the edges of a conflict leave it (git's `zdiff3` refinement), so a
`TextConflict` spans only disagreeing lines: its zero-based `start` in the local
text and the base, local, and remote lines. Its `lines` property converts that to
the `LineSpan` a `MergeLocation` carries into diagnostics and review JSON: a
one-based `start` and a `count`, numbered like a unified diff hunk header, so a
zero `count` sits after line `start`. A conflicted merge returns no text.
Two hunks of one generator change can depend on each other, so adapters keep the
local file whole or accept the merged file whole; they never write a partial merge.

Clean merges match `git merge-file` byte for byte. Where the two disagree on
whether a merge is clean (a fraction of a percent of randomized cases), the cause is
ambiguous placement among repeated lines, where patience and Myers alignments
legitimately differ. `scripts/compare_text_merge.py` reruns that comparison.
