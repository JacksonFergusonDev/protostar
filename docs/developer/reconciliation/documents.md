---
description: "Where each managed document lives in the source, how Protostar finds the file a tool reads, and the per-document merge policies."
---

# Managed documents

The [format engines](formats.md) know no file by name. Everything specific to one file lives in its own module under `src/protostar/documents/`, and callers look it up through that package's registries.

## Document catalog

Each format engine reconciles a document under a spec it is handed: `TomlDocumentSpec` or `YamlDocumentSpec`. The YAML engine has one extension point for document policy, the `YamlGuard`. A TOML spec declares its policy as data (see [TOML document specs](#toml-document-specs)).

| Module | Owns |
| :--- | :--- |
| `pyproject` | `TARGET`, `SPEC` (set-like lint selections, personal metadata as seed paths, the `tool` super table, the canonical layout), the resolver footprint, and dependency-group includes. |
| `pyproject_layout` | The canonical `pyproject.toml` section order, banner, and headers. |
| `locations` | `DocumentLocations` and `resolve_location`, shared by every document. |
| `pre_commit` | `TARGET`, `SPEC` (repos by `repo`, hooks by `id`), `LOCATIONS` per hook runner, and `plan_hook_pins`, whose `HookPinPlan` guards unsafe automatic pins and advances pin provenance after the merge, moving it with a followed configuration. |
| `github_workflows` | `CI_TARGET`, `RELEASE_TARGET`, `SPEC`, `CI_LOCATIONS`, `RELEASE_LOCATIONS`, and `guard_workflow`. |
| `codecov` | `TARGET`, `SPEC` (set-like `ignore`), and `LOCATIONS`. |
| `readthedocs` | `TARGET`, `SPEC` (complete), `LOCATIONS`, and `guard_build`. |
| `zensical` | `TARGET`, `SPEC` (set-like `theme.features`, seed paths, the `project` root table), and `LOCATIONS` (the MkDocs competitors). |
| `renovate` | `TARGET` and `LOCATIONS`. |
| `vscode` | The settings target and its default indentation. |

The package's `__init__` assembles the registries callers look up by path:

- `YAML_DOCUMENTS`
- `YAML_CONTRIBUTION_TARGETS`
- `YAML_GUARDS`
- `LOCATIONS`
- `document_locations(target, hook_runner)`
- `yaml_spec(path)`
- `toml_spec(path)`, which returns `DEFAULT_TOML_SPEC` (plain tables, atomic arrays, tomlkit's own output) for any TOML file without a spec

Every YAML and JSONC document is applied through one path. `Reconciliation._locate` resolves the file, then `_reconcile_document` reads it, builds the guard from its path and the decoded desired, local, and owned values, reconciles, records the baseline (moving the record when the file was followed), and writes.

!!! tip "Adding a document"
    Adding a document means adding a module and a registry entry, not a branch in an engine.

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

**Aliases** are paths the tool reads as the same document, in a form Protostar edits. **Competitors** are configurations the tool may read instead, in a form Protostar does not edit: TOML where Protostar writes YAML, JSON5, or MkDocs.

Pre-commit ignores `.pre-commit-config.yml`, but a lone copy means the user's hooks are not running. It is therefore a competitor, not something Protostar silently creates a second configuration next to. `exclusive` records whether the tool reads a single configuration; GitHub Actions does not.

### Choosing the file to edit

`resolve_location` decides which file a run edits:

1. An owned file that exists is edited in place.
1. Otherwise a single existing editable file is adopted, like an existing canonical file, or followed when the ownership record names another path. Renames are followed in both directions, including `.yml` to `.yaml` and back. The record, its baseline, and pre-commit's pin provenance move to the new path, so edits made before the rename still merge three ways.
1. An owned file that no longer exists, with nothing to follow, keeps its record, and the merge keeps the deletion.

For an **exclusive** tool, every other configuration present next to the edited file is reported as `duplicate-identity` at that path, because either Protostar's file or the other one is being ignored. When several are present and none is owned, nothing is edited and each is reported, because Protostar cannot tell which one the tool reads. A competitor alone holds the document and reports `unowned` at the target.

A **non-exclusive** tool never conflicts. The owned file, else the target, else the single alias is edited, and a second workflow with the other extension is left alone.

### Where the resolver applies

Protostar never renames a user's file back to the canonical name. Ownership records stay keyed by the real path, so the lock file names the file that is owned.

`Reconciliation._locate` applies the resolver to every YAML, JSONC, and TOML document before its merge, under explicit overwrite too. The same locations also drive:

- The collision prompt (`EnvironmentManifest.colliding_files`), so an existing alias asks to merge or overwrite like the canonical file.
- The dry-run tree (`written_files`).
- Every lookup by recorded path (`documents.yaml_spec`, used by state validation, preserved deviations, and append-region rejection).

Existence probes during preparation capture each path, so a review goes stale when a competing copy appears or disappears.

## YAML document specs

Every YAML document the engine reconciles is described by a `YamlDocumentSpec`. It lives with its document in `src/protostar/documents/` and is registered by path in `documents.YAML_DOCUMENTS`. A spec:

- Names the document for domain errors.
- Supplies the kernel `MergePolicy` (Codecov's set-like `ignore`, for example).
- Declares its keyed sequences.

Nothing outside the catalog compares against YAML file names. State validation, preserved-deviation inspection, and append-region rejection look up the spec with `documents.yaml_spec(path)`, which knows every name the document may be edited under.

The structured contribution channel accepts only the targets in `documents.YAML_CONTRIBUTION_TARGETS` (`.github/codecov.yml` and `.readthedocs.yaml`), declared by their canonical path. It does not infer structured intent from free-form file extensions or expose arbitrary YAML template injections. Pre-commit and workflows arrive through their own generators, and TOML remains the default format.

### Keyed sequences

A `KeyedSequence` gives a path pattern in the keyed view and an identity field. In the keyed view each record is presented under its identity, so an enclosing keyed record appears in the path as its identity, and the `WILDCARD` sentinel matches exactly one segment. Pre-commit declares `repos` by `repo` and `repos.*.hooks` by `id`. Optional string fields (pre-commit's `rev`) must be non-empty strings whenever present.

- Desired and owned snapshots must identify every record exactly once. Anything else is a fatal domain error.
- A local record without an identity is foreign. It is left out of the keyed view, never owned, and stays at its position in the file.
- A repeated local identity is ambiguous. For a nested sequence the entry containing it is held (the repository owning duplicate hooks). For a top-level sequence only the repeated identity is held. Each hold reports one `duplicate-identity` conflict, and independent entries still merge.
- A new record is inserted after its nearest earlier desired sibling that exists locally, otherwise before its nearest later one, otherwise at the end. Consecutive new records keep desired order.

Append regions are rejected for every registered YAML document, because appended text cannot be merged by structure.

### Guards

Document policies pass a `YamlGuard` to `reconcile_yaml`. A guard receives the path of the file being reconciled, which may be an alias, so its conflicts name the real file. It returns keyed-view paths to hold, plus the conflicts the policy found, which are reported ahead of the merge's own.

A **hold** replaces the desired value at that path with the owned baseline value, or drops it when nothing there is owned. The kernel then sees unchanged intent, so local content and previous ownership stay, and the hold adds no conflict of its own. Explicit overwrite omits held paths instead of overlaying them.

The pre-commit pin guard holds `repos.<repo>.rev` instead of rewriting the desired document, so other additions keep their desired key order and styling.

A guard that depends only on the decoded documents is registered by path in `documents.YAML_GUARDS` (workflows and Read the Docs). Pre-commit's is planned per run from registry responses, so its caller passes it directly.

## TOML document specs

A `TomlDocumentSpec` lives with its document in `src/protostar/documents/` and is looked up with `documents.toml_spec(path)`. Besides the kernel `MergePolicy`, super tables, and layout, it declares document policy as data.

`seed_paths`
:   Written only while Protostar creates the document or explicit overwrite is selected. `reconcile_toml` holds every seed it has written at its owned value and drops every other seed. A seed never merges into an existing document, editing or deleting one never conflicts, and a changed seed default is never applied. A written seed stays owned, so deleting its table still reads as a deletion (the dependency guards rely on an owned `project` table). pyproject's personal metadata is declared this way.

`root_table`
:   Names the table that holds every setting Protostar declares, for tools that also accept settings at the top level. An existing document with settings but without that table is left alone and reported as `unowned` at the file, because adding the table would hide those settings from the tool.

`flat_names`
:   Names tables whose keys are dotted names a tool also accepts nested. Zensical hoists `pymdownx.*`, `pymdownx.blocks.*`, `zensical.*`, and `zensical.extensions.*` in `markdown_extensions` into extension names, so the quoted `"pymdownx.details"` and the nested `pymdownx.details` are one extension, and the nested spelling wins when both exist. `reconcile_toml` compares local, desired, and baseline values by name, so a respelled extension is no edit and overwrite never adds a second spelling. It writes each name back where the document keeps it: a new name follows the namespace's spelling in the document, then the desired one, and a new quoted table is written inline. A shadowed quoted spelling is left as it is. Only the listed namespaces flatten, so `toc.permalink` stays the extension `toc`.

Some rules apply to every TOML document:

- A table added inside a dotted-key table (`pymdownx.details = {}`) is written inline on its own dotted line, because tomlkit gives a table assigned there a wrong top-level header.
- `Reconciliation._append_files` checks `root_table` before the merge, under explicit overwrite too, because it protects what the tool reads rather than who owns a value.
- A document without a layout keeps its own end-of-file newlines. A desired table copied from the middle of a contribution would otherwise bring along the blank line that separated it from its next sibling.

## GitHub Actions workflows

`.github/workflows/ci.yml` and `release.yml` share one `github_workflows.SPEC`. There is no per-file behavior, only a different generator producing the desired document. Workflow files Protostar does not generate are never read or written.

- Mappings merge by key through the kernel, so user-added triggers, permissions, environment, jobs, and `with:` inputs are foreign siblings and are never touched.
- `jobs.*.steps` is keyed by step `name`. Every generated step is named, uniquely within its job, and a logical step keeps its name in every generator variant (`tests/test_workflows.py` enforces the exact set). Unnamed local steps are foreign and stay in place, and a renamed step reads as a deletion of the old name plus a foreign step.
- Every other sequence is atomic: branch filters, matrix axes, `include`, and `needs`.
- The policy is complete. When the generator stops emitting something (for example Codecov upload steps after Codecov is turned off), unedited copies are removed and edited ones are kept with a `retracted` conflict. Turning the CI tool off retracts the whole document the same way: an unedited workflow is deleted, and a top-level key the user edited or added stays.

`github_workflows.guard_workflow` builds the workflow's `YamlGuard` from two rules, both implemented as holds:

1. A job that exists locally but is not owned is held whole and reported as `unowned` at `jobs.<id>`, including under explicit overwrite. Protostar never grafts its steps into a job it did not create, though its other jobs are still added.
1. When an owned step's local `uses` names the same action as the owned baseline but a different ref, and the ref differs from the desired one too, the ref belongs to the user (a Renovate SHA pin, a manual bump or rollback). It is kept without a conflict and reported as a preserved deviation, so `sync --check` passes. If the local ref already equals the desired ref, ownership converges normally. Local (`./`) and `docker://` actions carry no ref and follow the ordinary rules, and a changed action path is an ordinary conflict.

Existing workflow files are parsed during preparation, before any batch mutates the workspace, so a malformed or unsupported workflow fails like any other structured YAML document.

## .readthedocs.yaml

The Read the Docs module declares `.readthedocs.yaml` as a structured YAML contribution. Its build jobs install uv, sync the `docs` group, and run `zensical build`. `documents.readthedocs.SPEC` encodes two facts about how Read the Docs reads the file, both verified against its source:

- Read the Docs loads the first file matching `^\.?readthedocs.ya?ml$` in directory-listing order, so `.readthedocs.yml`, `readthedocs.yaml`, and `readthedocs.yml` are aliases (see [Document locations](#document-locations)). A renamed configuration is followed, and a second one next to the managed file is reported, because the filesystem would choose between them.
- The policy is complete. The configuration is the module's whole output, so a job Protostar stops generating is retracted instead of lingering to override the build. Every sequence is atomic, because a job's commands are an ordered script.

Protostar's jobs are not settings added next to the user's. They replace build steps: `build.jobs.create_environment`, `install`, and `build.html` each skip the default step that the `sphinx`, `mkdocs`, `python`, and `conda` settings configure, and Read the Docs rejects `build.jobs` next to `build.commands`.

`readthedocs.guard_build` therefore holds `build.jobs` whenever the local configuration has a non-empty `build.commands` or any of those four settings, under explicit overwrite too, so Protostar never grafts its build onto one that already works another way. Other settings still merge by the ordinary rules.

The hold reports `unowned` at `build.jobs` only when it withholds a change, meaning the desired jobs differ from both the owned baseline and the local jobs. Adopting an existing Sphinx or MkDocs configuration reports it. A user who replaced Protostar's jobs with their own build after the scaffold is not warned, and `sync --check` passes, until a later Protostar release changes the jobs.

## zensical.toml

Zensical reads its settings from `[project]`, or from the top level when that table is absent, and prefers `zensical.toml` over `mkdocs.yml`. `documents.zensical.SPEC` splits the document by what Protostar can change without changing the user's site:

Managed
:   `project.theme.features`, merged by membership, and `project.plugins.mkdocstrings`, which configures the `mkdocstrings[python]` package the module installs.

Seeded
:   `site_name`, `site_description`, `nav`, `theme.palette`, `theme.font`, `markdown_extensions`, and `extra`. They are the site's identity, content, and look.

Root table
:   `project`. `mkdocs.yml` and `mkdocs.yaml` are competitors (see [Document locations](#document-locations)): Protostar does not create `zensical.toml` next to them and reports one that appears next to an owned site.

The extension table is seeded all or nothing. Listing extensions replaces Zensical's defaults, so adding entries to a document without the table would turn every other default off. Seeding it also keeps Protostar away from the two spellings Zensical accepts for one extension (dotted `pymdownx.details` and quoted `"pymdownx.details"`), which a key-level merge would duplicate.

The scaffold's extension list mirrors Zensical's `DEFAULT_MARKDOWN_EXTENSIONS`, spelled the way `zensical new` writes it, so a scaffolded site renders what a site without the table would. `tests/test_zensical_execution.py` compares the two whenever Zensical is installed.
