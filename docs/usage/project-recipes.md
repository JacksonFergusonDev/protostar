---
description: "What Protostar records in [tool.protostar], how tools, variables, options, and tiers are stored, and how to enroll or eject a project."
---

# Project recipes

A successful `protostar init` records what you asked for in `[tool.protostar]` inside `pyproject.toml`. This table is the project's **recipe**. Commit it alongside `protostar.lock`.

The two files answer different questions:

| File | Records |
| :--- | :--- |
| Recipe (`[tool.protostar]`) | What you request: the template, tools, variables, and other choices. |
| `protostar.lock` | What was actually applied: the contributions accepted by [reconciliation](../developer/reconciliation/kernel.md). |

A conflict can therefore leave the recipe ahead of what was applied. The lock's ownership ledger stays at schema v1.

## What the recipe records

A schema-v1 recipe captures:

- The resolved template origin and locator, or an explicit `mode = "tooling-only"`.
- For a repository template, its `path` inside the repository and the `ref` it follows (see [template versions](templates.md#template-versions)).
- The Python version, Docker selection, IDE, and the original tooling fallbacks.
- The built-in rendering context, template variable values, the chosen tier, and non-secret project metadata.

Template aliases are resolved when a project is enrolled, so the recipe records the exact source rather than the alias. Local relative locators resolve against the project directory. Unknown fields, versions, tools, and unsafe source paths are rejected.

`[tool.protostar.tools]`, `[tool.protostar.metadata]`, `[tool.protostar.variables]`, and `[tool.protostar.options]` are written only while they have entries, and an absent table means empty. `fallback` and `context` are always present.

### Where it lives

In a `pyproject.toml` that Protostar creates, the recipe is the last section, under its own `# ---- Protostar ---- #` header, like every other tool's configuration. Everything that is not tool configuration sits above the `# Tool Configuration` banner:

- `[project]`
- `[build-system]`
- `[dependency-groups]`
- Build-backend tables such as `[tool.hatch...]`

A `pyproject.toml` you already had keeps your own order.

### Where values come from

For a new uv project, the captured project name uses uv normalization (`Demo_Project` becomes `demo-project`) while the package identifier remains `demo_project`. This keeps early file rendering and later TOML rendering consistent.

In a project that had no recipe, the Python version, author, and year come from the project itself where it states them (see [existing projects](init.md#existing-projects)), and from your configuration otherwise.

### What owns the table

The recipe belongs to the project. Templates and modules cannot contribute to, replace, or own any part of `tool.protostar`. Use structured TOML contributions for `pyproject.toml`: free-form replacement is rejected even with `--force-replace`.

Recipe edits use round-trip TOML manipulation, which preserves unrelated content and comments. Recipe and ownership updates share one filesystem transaction, so a late write failure rolls both back, including original bytes and modes. `init --dry-run` remains a manifest preview and writes neither file.

## One-shot and eject

`init --one-shot` uses the recipe and ownership decisions only during the run. It writes neither the recipe nor `protostar.lock`, so lifecycle commands cannot update that scaffold. It still generates the separate `uv.lock` dependency lockfile.

`protostar eject` takes a tracked project out of the lifecycle. It removes the recipe and `protostar.lock` in one transaction and keeps `uv.lock` and every other project file.

- The CLI shows the pending changes and asks for confirmation.
- `--dry-run` previews the `pyproject.toml` diff.
- `--yes` confirms a noninteractive run.

After ejection, `status`, `diff`, and `sync` are unavailable for that project.

## Tool selections

`[tool.protostar.tools]` records the tools you turned on or off yourself.

- `true` turns a tool on.
- `false` turns it off, and removes what it added.

### Which choice wins

Each tool is decided by the first of these that says anything about it:

1. **The project's own choice:** an entry in `[tool.protostar.tools]`. A `--<tool>` or `--no-<tool>` flag on `init` writes one, and so does switching a tool in the recipe editor away from the template's choice.
1. **The template's tier:** the tool's flag in `[tiers.<tier>]`, for the tier the project follows.
1. **The template:** the tool's flag at the template's root.
1. **Your defaults when the project was set up:** your [global configuration](configuration.md)'s tool settings, recorded in the recipe's `fallback` at `init`. Changing your configuration later never changes an existing project.

So a template's later release can change a tool the project never chose, and an entry in `[tool.protostar.tools]` stays fixed until you edit it. `sync --tier` changes which tier the template's opinions come from, and never removes your own entries.

An opt-out affects that module only: an independent template or another module can still contribute to the same file or dependency group. Disabling a tool also retracts what it contributed. Unedited files, dependencies, configuration tables, and regions are removed, and edited ones become `retracted` conflicts.

The table is omitted while it has no entries, so a new project has none. To record a diversion, add the table:

```toml
[tool.protostar.tools]
mypy = true
renovate = false
```

!!! warning "Don't list every tool"
    Leave a tool out unless you mean to override the template. Absence lets template opinions evolve, while an entry pins your choice.

Later explicit initialization flags update their corresponding entries, and unspecified flags preserve existing diversions. `--docker` and `--no-docker` explicitly change Docker intent. Metadata and `CURRENT_YEAR` are captured, so repeat initialization keeps the same rendering context even when Git settings, global defaults, or the clock change.

## Enrolling a project without a recipe

A project scaffolded before recipes existed has a lock but no recipe. Rerun the original explicit selection with safe merging:

```bash
protostar init --template cli --force-merge
```

This establishes a recipe without reconstructing the original command from the lock and without adopting equal foreign content. Template identity checks still apply. Afterwards, use `status`, `diff`, and `sync`; see the [lifecycle walkthrough](lifecycle.md).

## Template variables

A template's custom variables (every `<% NAME %>` placeholder that isn't a built-in) get their values when you initialize, and the recipe records them:

=== "Command"

    ```bash
    protostar init --from ./blueprint.toml --var REGION=eu-west-1 --var TIER=gold
    ```

=== "Recipe"

    ```toml
    [tool.protostar.variables]
    REGION = "eu-west-1"
    TIER = "gold"
    ```

### Where values come from

Each source overrides the one before it:

1. The recipe from an earlier `init`.
1. `--var NAME=VALUE` flags.
1. In an interactive terminal, a prompt for anything still missing.

A `--var` that names no variable of the template is an error, and so is a mistyped flag. Values the template no longer uses are dropped the next time you run `init`.

### Missing values

Without a terminal, including under `--json`, a missing value stops `init` before anything is written. The `MissingTemplateVariablesError` names every missing variable at once (`error.missing_variables` in JSON).

When a template gains a variable, `sync` asks for its value in a terminal, and otherwise takes `--var NAME=VALUE`; without either, it stops before writing anything. You can also add the value under `[tool.protostar.variables]` yourself.

### Variables are not secrets

Template variables are non-secret by definition, because the recipe is committed.

- Each newly entered value passes the [secret guard](authoring-templates.md#variables-are-not-secrets). A value that looks like a credential is held back until you confirm it isn't a secret.
- Recorded values are not checked again.
- Keep secrets in the environment the project reads at runtime.
- Trust permissions and command lines are never serialized.

!!! note
    Generated project files and ownership baselines contain rendered content. Diffs are not a secret-redaction system.

## Template options

A template's [options](authoring-templates.md#template-options) record only the values a project chose. Every value passed with `--option` is recorded as given. From the recipe editor, only values that differ from the template's defaults are recorded.

=== "Command"

    ```bash
    protostar init --from ./blueprint.toml --option database=postgres
    ```

=== "Recipe"

    ```toml
    [tool.protostar.options]
    database = "postgres"
    ```

An option the table leaves out follows the template's default, the way an omitted tool follows the template's opinion. A template that changes a default therefore changes those projects on their next `sync`.

- `sync --option NAME=VALUE` changes a value and records it.
- A value for an option the template no longer offers is dropped on the next `sync`.
- A value the option no longer offers stops `sync` with an `InvalidOptionValueError` naming the values it does offer (`error.values` in JSON).

## Template tier

A template that declares [tiers](authoring-templates.md#template-tiers) lets a project follow its `workbench` or `production` tool opinions. The recipe records the tier only when it was passed with `--tier` (even when that is the template's default), or chosen in the recipe editor away from the template's default.

=== "Command"

    ```bash
    protostar init --from ./blueprint.toml --tier production
    ```

=== "Recipe"

    ```toml
    [tool.protostar]
    tier = "production"
    ```

Without a recorded tier, a project follows the template's default tier, so a template that changes its default changes those projects on their next `sync`. Tool diversions in `[tool.protostar.tools]` are measured against the tier's opinions and still win over them.

- `sync --tier NAME` changes the tier and records it.
- A recorded tier is dropped on the next `sync` once the template stops declaring tiers.
- A tooling-only recipe never holds one.
