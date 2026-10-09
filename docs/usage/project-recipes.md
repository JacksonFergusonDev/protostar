---
description: "What a project's recipe in pyproject.toml records: its template, tools, variables, options, and tier, and which choice wins."
---

# Project Recipes

`protostar init` records what you asked for in `[tool.protostar]` in `pyproject.toml`. This table is the project's recipe: the template it follows and every choice you made. `protostar.lock` records what Protostar actually wrote; see [How Protostar Tracks Your Files](tracking.md). Commit both.

The recipe says what the project should be, so `status` and `sync` compare the project against it. You can edit it by hand, and `sync` applies the change.

## What the Recipe Records

This is the recipe of a new `cli` project:

```toml
[tool.protostar]
version = 1
mode = "template"
python = "3.13"
ide = "none"

[tool.protostar.source]
origin = "built-in"
locator = "cli"

[tool.protostar.fallback]
mypy = false
ruff = true
# ...one entry per tool

[tool.protostar.context]
PROJECT_NAME = "demo-project"
PACKAGE_NAME = "demo_project"
PYTHON_VERSION = "3.13"
CURRENT_YEAR = "2026"
AUTHOR_NAME = "your-name"

[tool.protostar.metadata]
supported_os = ["MacOS", "Linux", "Windows"]
```

| Key | What it holds |
| :--- | :--- |
| `version` | The recipe format's version. |
| `mode` | `template`, or `tooling-only` for a project set up with tools and no template. |
| `python`, `ide` | The Python version and editor the project was set up for. |
| `source` | The template: built-in, local, or a repository, with its `path` inside the repository and the `ref` it follows (see [template versions](templates.md#template-versions)). An alias is recorded as the template it named, so the recipe works on any machine. |
| `tools` | The tools you turned on or off yourself; see [below](#tool-selections). |
| `fallback` | Your configuration's tool defaults when the project was set up. |
| `context` | The values placeholders such as `<% PROJECT_NAME %>` rendered with. They're recorded so files render the same way later, even after your Git settings, your configuration, or the year change. |
| `metadata` | Project details such as the author email and supported systems. |
| `variables` | The template's custom variables; see [below](#template-variables). |
| `options`, `tier` | The template options and tier the project chose; see [below](#template-options). |

`tools`, `metadata`, `variables`, and `options` are left out until they have an entry. Unknown keys and tools are an error, so a typo never passes silently.

In a `pyproject.toml` Protostar creates, the recipe is the last section, under its own `# ---- Protostar ---- #` header, below every tool's settings; see [The pyproject.toml Layout](../developer/pyproject-layout.md). A `pyproject.toml` you already had keeps your own order.

The recipe belongs to the project: no template or tool can write to it. In a project that had no recipe, `init` fills the Python version, author, and year from what the project states (see [existing projects](init.md#existing-projects)), and from your configuration otherwise.

## Tool Selections

`[tool.protostar.tools]` records the tools you turned on or off yourself:

```toml
[tool.protostar.tools]
mypy = true
renovate = false
```

- `true` turns a tool on.
- `false` turns it off, and takes back what it added: what you never edited is removed, and what you edited becomes a conflict for you to settle.

!!! warning "Don't list every tool"
    Leave a tool out unless you mean to override the template. A tool you leave out follows the template as it evolves, while an entry fixes your choice.

### Which Choice Wins

Each tool is decided by the first of these that says anything about it:

1. **The project's own choice:** an entry in `[tool.protostar.tools]`. A `--<tool>` or `--no-<tool>` flag on `init` writes one, and so does switching a tool in the recipe editor away from the template's choice.
1. **The template's tier:** the tool's flag in `[tiers.<tier>]`, for the tier the project follows.
1. **The template:** the tool's flag at the template's root.
1. **Your defaults when the project was set up:** your [global configuration](configuration.md)'s tool settings, recorded in the recipe's `fallback` at `init`. Changing your configuration later never changes an existing project.

So a template's later release can change a tool the project never chose, while an entry in `[tool.protostar.tools]` stays fixed until you edit it. `sync --tier` changes which tier the template's choices come from, and never removes your own entries. A later `init` keeps the entries you don't pass a flag for.

Turning a tool off affects only what that tool added: a template or another tool can still write to the same file or dependency group.

## Template Variables

A template's custom variables, every `<% NAME %>` placeholder that isn't built in, get their values when you set up the project, and the recipe records them:

=== "Command"

    ```bash
    protostar init --from ./blueprint.toml --var REGION=eu-west-1 --var SERVICE=billing
    ```

=== "Recipe"

    ```toml
    [tool.protostar.variables]
    REGION = "eu-west-1"
    SERVICE = "billing"
    ```

Each source overrides the one before it:

1. The recipe, from an earlier run.
1. `--var NAME=VALUE` flags.
1. In a terminal, a screen asking for anything still missing.

A `--var` that names no variable of the template is an error. Values the template no longer uses are dropped the next time `init` writes the recipe.

Without a terminal, including under `--json`, a missing value stops the run before anything is written, with a `MissingTemplateVariablesError` naming every missing variable at once (`error.missing_variables` in JSON). When a template release adds a variable, `sync` asks for its value in a terminal, and otherwise takes `--var NAME=VALUE`. You can also add the value under `[tool.protostar.variables]` yourself.

### Variables Are Not Secrets

The recipe is committed, so variable values are never secret:

- Each newly entered value passes the [secret check](authoring-templates.md#variables-are-not-secrets). A value that looks like a credential is held back until you confirm it isn't a secret.
- Values already in the recipe are not checked again.
- Keep secrets in the environment the project reads when it runs.

Files a template renders contain their variables' values, and so do reviews and diffs of them.

## Template Options

The recipe records the [options](authoring-templates.md#template-options) a project chose. Every value passed with `--option` is recorded as given; from the recipe editor, only values that differ from the template's defaults are.

=== "Command"

    ```bash
    protostar init --from ./blueprint.toml --option database=postgres
    ```

=== "Recipe"

    ```toml
    [tool.protostar.options]
    database = "postgres"
    ```

An option the recipe leaves out follows the template's default, as a tool it leaves out follows the template. A template that changes a default changes those projects on their next `sync`.

- `sync --option NAME=VALUE` changes a value and records it.
- A value for an option the template no longer offers is dropped on the next `sync`.
- A value the option no longer offers stops `sync` with an `InvalidOptionValueError` naming the values it does offer (`error.values` in JSON).

### Template Tier

A template that declares [tiers](authoring-templates.md#template-tiers) lets a project follow its `workbench` or `production` tool choices. The recipe records the tier when it was passed with `--tier` (even if it's the template's default), or chosen in the recipe editor away from the template's default:

```toml
[tool.protostar]
tier = "production"
```

Without a recorded tier, a project follows the template's default tier, so a template that changes its default changes those projects on their next `sync`.

- `sync --tier NAME` changes the tier and records it.
- A recorded tier is dropped on the next `sync` once the template stops declaring tiers.
- A tooling-only recipe never has one.

## One-Shot and Eject

`init --one-shot` sets up a project without writing a recipe or `protostar.lock`, so `status`, `diff`, and `sync` can't update it later. It still writes `uv.lock`.

`protostar eject` stops tracking a project: it removes the recipe and `protostar.lock` together, and keeps every other file, including `uv.lock`. It shows the change and asks first; `--dry-run` previews the `pyproject.toml` diff, and `--yes` confirms without a terminal. A project whose recipe is missing but whose lock remains needs its recipe back before `sync` works; see [When the Recipe Is Missing](lifecycle.md#when-the-recipe-is-missing).
