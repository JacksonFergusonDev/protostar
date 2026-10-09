---
description: "Write your own template, from a single TOML file to a repository with starter files, options, tiers, and variables."
---

# Authoring Custom Templates

A template describes one kind of project: the tools it turns on, its dependencies, the settings that differ from each tool's defaults, and its starter files. Protostar writes everything else those tools need, and keeps every project made from the template current as you release new versions.

A template starts as a single TOML file, and grows into a directory or repository when its starter files get big.

## Level 1: A Single TOML File

At its simplest, a template is one TOML file. Keep it on your machine, or host it anywhere `--from` can reach.

### The Template Schema

The complete annotated schema shows every key a template can set in one file. The sections below explain each part.

??? abstract "The complete annotated schema"
    ```toml
    --8<-- "template_schema.toml"
    ```

??? tip "Exporting the JSON Schema (`protostar export-schema`)"
    Protostar prints the JSON Schema for template files. Use it to validate templates in CI, or point your editor at it for completion and checking as you type ([editor setup](troubleshooting.md#editor-schema-setup-for-custom-templates)):

    ```bash
    # Highlighted, for reading:
    protostar export-schema

    # Plain JSON, saved to a file:
    protostar export-schema --json > protostar-template.schema.json
    ```

### Name and Description

```toml
name = "Enterprise FastAPI"
description = "FastAPI service with the team's quality gate"
```

`protostar init --list-templates`, shell completion, and the recipe editor's template picker show both. `check-template` warns when either is missing.

### `pyproject.toml` Settings (`[dev.pyproject]`)

Settings for `pyproject.toml` go in named payloads under `[dev.pyproject]`. Each is a TOML string, merged into the project's `pyproject.toml` key by key:

```toml
[dev.pyproject]
build_system = '''
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
'''
```

Protostar keeps a payload's keys current: when a later release changes one, projects that haven't edited it take the change, and projects that have keep their edit. A payload that configures a tool should say so with `requires`, so it leaves with the tool; see [Optional Content](#optional-content). Name each payload once and keep the name, since that is how a project's record finds it again.

Project fields such as `description`, `authors`, `license`, `classifiers`, `keywords`, and the repository URLs are different: a payload writes them once, when the project doesn't have them, and they belong to the project from then on. A payload can't set dependencies, `dependency-groups`, `tool.uv.sources`, or `[tool.protostar]`.

### Text Blocks in Other Files (`[appends]`)

To add text to a file that isn't TOML, such as `.envrc`, `AGENTS.md`, or the `justfile`, declare a named block:

```toml
[appends.".envrc".project_environment]
content = "export PROJECT=example"
```

Protostar writes the block between two marker comments, `# region: protostar <tag>` and `# endregion: protostar <tag>`, and leaves the rest of the file alone. A later release that changes `content` updates the block, merging line by line with any edits the project made inside it, and keeps the project's version when they overlap. As with payloads, keep the block's name when its content changes. A block takes `requires` beside its `content`.

Blocks can't go into TOML files, which merge key by key instead, or into the files Protostar merges as YAML: the hook configuration, `.github/codecov.yml`, `.readthedocs.yaml`, and the generated `ci.yml` and `release.yml` workflows. To add ignore patterns, use `vcs_ignores`.

### Starter Files (`[files]`)

```toml
[files]
"src/<% PACKAGE_NAME %>/main.py" = '''
"""Entry point for <% PROJECT_NAME %>."""
'''
```

A starter file is written once, when the project doesn't have it, and then belongs to the project: later releases never change it. To move or retire one in a later release, declare a [migration](releasing-templates.md#migrations). A path can't be both a starter file and a target of payloads or blocks. No file may be written to `protostar.lock`, `uv.lock`, or anywhere inside `.git/`.

### Dependencies

```toml
dependencies = ["fastapi", "uvicorn"]
docs_dependencies = ["zensical"]

[dev]
dev_dependencies = ["ipython"]
```

Protostar adds each list with `uv add`, which resolves current versions and writes `uv.lock`, so templates name packages without version pins. `dependencies` are the project's own requirements; `dev_dependencies` go in the `dev` group, and `docs_dependencies` in the `docs` group. Keep `docs` for a documentation toolchain: `uv sync` installs the `dev` group by default but not `docs`. A package only one tool needs, such as `pytest-cov`, goes in an [`[[optional]]`](#optional-content) block that requires the tool, so `--no-pytest` doesn't install it.

To have `dev` include `docs`, so `uv sync` installs both, declare it at the root:

```toml
dependency_includes = [{ group = "dev", include = "docs" }]
```

### Commands (`system_tasks` and `post_install_tasks`)

```toml
system_tasks = [["git", "lfs", "install", "--local"]]
post_install_tasks = [
  { command = ["uv", "run", "nbdime", "config-git", "--enable"], owned_files = [".git/config"] },
]
```

Each command is a list of arguments, never a shell string. `system_tasks` run once the project's files are written, after Protostar's own `git init` and `uv init`, and before dependencies are installed. `post_install_tasks` run after dependencies are installed, so they can use the project's packages through `uv run`.

When a command creates or changes files in the project, write it as a table and list them in `owned_files`, by their path from the project root. Protostar records each one before the command runs, so if the run fails later, it puts them back exactly as they were, or removes them if the command created them. The files also appear in the change review and `--dry-run`, except those inside `.git/`. A command written as a plain list declares nothing, and whatever it writes stays behind after a failed run.

- Commands run only during `init`. `sync` never runs them.
- Each command's program must be one of `uv`, `git`, `npm`, `yarn`, `pnpm`, `pre-commit`, `prek`, `direnv`, or `just`.
- Unless your template is trusted, the user confirms every command first; see [Trusting a Template](templates.md#trusting-a-template).
- Files a command writes without listing them in `owned_files` appear in no preview and stay behind if the run fails and rolls back.

Prefer a tool flag, a payload, or a starter file wherever one can do the job: they show up in every preview, work the same on every platform, and need no confirmation.

### Version and Identity

A template may declare a root `version`, such as `"1.2.0"`. It's informational unless the template declares [migrations](releasing-templates.md#migrations), which require it.

A project records which template it follows: the built-in name, the local file's path, or the repository and the path inside it. The release or commit it applied is recorded separately, so moving to a new release never makes it a different template, and a project can never switch to a different one. A template URL may not contain credentials or a query string.

### Optional Content

Content that only applies sometimes says when with `requires`. A condition names what must hold:

- a tool key, such as `"ruff"` or `"pytest"`, which holds while that tool is enabled (the keys are listed in the [Tooling & Flags Matrix](./tooling-matrix.md));
- a bool option, such as `"compose"`, which holds while the option is on;
- `"option=value"`, such as `"database=postgres"`, which holds while a choice option has that value;
- `"tier=workbench"` or `"tier=production"`, which holds while the project follows that [tier](#template-tiers);
- or an array of them, such as `["pytest", "database=postgres"]`, which holds while all of them do.

There is no "or" and no "not". To ship something for either of two choices, list it once for each. A question with two answers that each ship content is a choice option, not a bool.

A payload that configures a tool should say which one. Write it as a table with `content` and `requires`, and Protostar injects it only while the condition holds:

```toml
[dev.pyproject.linting]
requires = "ruff"
content = '''
[tool.ruff.lint]
extend-select = ["I", "UP", "B"]
'''
```

With this, `protostar init --template my-template --no-ruff` writes no `[tool.ruff]` at all, instead of leaving configuration behind for a tool that isn't installed. Plain string payloads are always injected. Use them for configuration that no toggle should remove, such as a `[build-system]` table. In TOML, put the plain string payloads before any `[dev.pyproject.<name>]` sub-tables. A named append region takes `requires` the same way, beside its `content`.

Dependencies and files that apply only sometimes go in `[[optional]]` blocks. Each block has a `requires` and any of `dependencies`, `dev_dependencies`, `docs_dependencies`, and `files`:

```toml
[[optional]]
requires = "pytest"
dev_dependencies = ["pytest-cov", "httpx"]

[[optional]]
requires = "database=postgres"
dependencies = ["psycopg[binary]"]
files = ["src/<% PACKAGE_NAME %>/db.py", "migrations/"]
```

With this, `--no-pytest` does not install `pytest-cov` or `httpx`. Packages in `dependencies` and `[dev].dev_dependencies` are always installed, so keep those lists for what no toggle should remove. `files` lists template files by their path in `template/` or `[files]`, or every file under a path ending in `/`. A file no block lists always ships; one several blocks list ships while any of them holds. Listing a path the template doesn't ship, or naming an unknown tool or option, stops the template from loading.

When a condition stops holding in an existing project, `protostar sync` takes back what it added: an unedited file, dependency, payload, or region is removed, and one you edited is kept as a `retracted` conflict for you to settle. Turning a tool off works the same way.

### Template Options

Options let a template ask for choices instead of text. Declare each in an `[options]` table:

```toml
[options.database]
description = "The database the service uses."
choices = ["none", "postgres", "sqlite"]
default = "none"

[options.compose]
description = "Ship a compose.yaml for local services."
default = false
```

An option with `choices` is a choice option: it needs at least two distinct values, made of letters, digits, dots, dashes, and underscores, and a `default` among them. An option without `choices` is a bool option with a `true` or `false` default. `description` is optional and appears beside the option when it is chosen. Every option must be named by some `requires`, and may not share a name with a tool, a variable, or `tier`.

An option only chooses what the template includes. It never renders into text: `<% database %>` is a variable, and a template can't use the same name for both. Content that differs by choice is listed per choice, whole files at a time, with `[[optional]]`, payloads, and regions.

Users choose with `--option`, on `init` and on `sync`:

```bash
protostar init --template my-template --option database=postgres --option compose=true
protostar sync --option compose=false
```

The recipe editor shows a switch for each bool option and a choice for each choice option. The project recipe records the values in `[tool.protostar.options]`: every value passed with `--option`, and from the editor only those that differ from the template's default. A project that never chose follows the template, so a template that changes a default changes those projects on their next `sync`. A recorded value for an option the template no longer offers is dropped on `sync`; one the option no longer offers stops `sync` with an error naming the values it does.

### Template Tiers

A template describes a project's shape: its structure, dependencies, and files. How much tooling that shape starts with is a separate choice, and a template can offer it as two tiers:

- `workbench`, for exploring and analyzing: lean tooling that stays out of the way.
- `production`, for building something to publish: the full quality gate.

Declare the tier a project starts with as `tier` at the root, and both tiers as tables of tool flags:

```toml
ruff = true
direnv = true
tier = "workbench"

[tiers.workbench]
mypy = false
pytest = false
ci = false

[tiers.production]
mypy = true
pytest = true
ci = true
```

A tier's flags are laid over the root flags. Set a tool at the root when both tiers agree, and in both tiers when they differ: each tier must set the same tools, and a tool set in the tiers can't also be set at the root. A tier may set any tool flag. Declare both tiers or neither; a template without tiers offers no tier to choose.

Configuration follows the tools, so a payload with `requires = "mypy"` already arrives with production and leaves with workbench. Content that belongs to a tier rather than to one tool, such as a smoke test that production's `pytest` needs, requires the tier:

```toml
[[optional]]
requires = "tier=production"
files = ["tests/test_smoke.py"]
```

Users choose with `--tier`, on `init` and on `sync`:

```bash
protostar init --template my-template --tier production
protostar sync --tier workbench
```

An explicit tool flag still wins over either tier, so `--tier production --no-ci` is production without CI; see [which choice wins](project-recipes.md#which-choice-wins). The project recipe records the tier as `tier` in `[tool.protostar]` when it was passed with `--tier`, or chosen in the recipe editor away from the template's default, so a project that never chose follows the template's default. A recorded tier is dropped on `sync` once the template stops declaring tiers.

## Level 2: A Folder or Repository

`[files]` suits small starter files, such as a `main.py`. Larger ones, such as a full FastAPI service or a PyTorch training pipeline, are easier to write as real files. Put them in a folder:

- **`protostar.toml`** holds everything a single-file template would.
- **`template/`**, beside it, holds the starter files. Each file is copied to the same path in the project.

Point `--from` at the folder, or at a repository that holds it.

### Example Repository Structure

```text
my-org-fastapi-template/
├── README.md
├── protostar.toml       # The template's settings
└── template/            # Starter files, copied into the project
    ├── src/
    │   └── <% PACKAGE_NAME %>/
    │       ├── __init__.py
    │       ├── core/
    │       │   └── config.py
    │       └── main.py
    └── tests/
        ├── conftest.py
        └── test_api.py
```

Protostar skips `pycache` folders and `.DS_Store` files in `template/`.

Every file in `template/` must be UTF-8 text, because Protostar fills in placeholders in each one. A binary file such as an image stops the template from loading with an error naming the file.

Every entry in `template/` must also be a regular file or directory. A symbolic link stops the template from loading: it would copy whatever it points at, such as a credentials file, into the project. No template file may land inside `.git/`, in any spelling, because Git runs what that directory configures. A remote template's archive may be at most 64 MiB and unpack to at most 256 MiB, and a raw `protostar.toml` at most 1 MiB.

## Level 3: Variables

A placeholder such as `<% VARIABLE_NAME %>` is replaced with its value wherever it appears: in `protostar.toml`, in `[files]` strings, and in the files under `template/`. Placeholders only insert values; there are no conditions or loops.

### Built-in Variables

Protostar fills these in itself, from the project folder, your configuration, and Git:

- `<% PROJECT_NAME %>`: the project's name, such as `my-cool-app`.
- `<% PACKAGE_NAME %>`: the name to import it by, made a valid Python identifier, such as `my_cool_app`.
- `<% PYTHON_VERSION %>`: the project's Python version, such as `3.13`.
- `<% CURRENT_YEAR %>`: the current year, for copyright lines.
- `<% AUTHOR_NAME %>`: your name, from your Protostar configuration or `git config user.name`.

### Your Own Variables

Any other placeholder is a variable the user supplies. A template that deploys to a region might write:

```python
# template/src/<% PACKAGE_NAME %>/settings.py
DEFAULT_REGION = "<% DEFAULT_REGION %>"
```

Users supply the value with `--var`:

```bash
protostar init --from https://github.com/Org/template --var DEFAULT_REGION=eu-west-1
```

If they leave it out, Protostar asks for it in a terminal before writing anything. Without a terminal, it stops with an error naming the variable. The value is recorded in the project recipe, so later runs of `init` and `sync` reuse it. Variable names are identifiers: a letter or underscore, then letters, digits, or underscores.

### Describing Variables

Protostar labels each field with the variable's name. To explain what a value should be, declare the variable in an optional `[variables]` table:

```toml
[variables.DEFAULT_REGION]
description = "Deployment region, e.g. eu-west-1"
```

The description appears under the field when Protostar asks for the value. Declarations are optional, and `description` is the only key. Declare only placeholders the template uses; declaring an unused or built-in variable stops the template from loading.

### Variables Are Not Secrets

A template's variables are never secret: their values are saved in the project's recipe in `pyproject.toml` and written into the project's files, all of which get committed. If a value must stay out of the repository, it isn't a template variable. Have the generated code read it from the environment at runtime, and ship a `.env.example` in `template/` that names it.

Protostar checks for mistakes, but the check is a safety net, not a guarantee:

- **Names:** a placeholder named like a credential, such as `<% API_KEY %>`, `<% DB_PASSWORD %>`, or `<% GITHUB_TOKEN %>`, draws a warning beside its field and in the terminal. Rename it, or better, read the secret from the environment instead.
- **Values:** each newly entered value is checked against [gitleaks](https://github.com/gitleaks/gitleaks)' default rules, at the version Protostar pins for the gitleaks hook it sets up. A value that looks like a credential, such as a GitHub token or a private key, is held back until the user confirms it isn't a secret, for that variable only: a checkbox beside the field, or `--allow-secret NAME` on the command line. The error names the variable and the matching rule, never the value. Values are limited to 1,024 characters.

Values already recorded in the recipe are not checked again, so a confirmed value never blocks a later `init` or `sync`. The guard misses secrets gitleaks has no rule for, such as a password inside a database URL, so it never replaces keeping secrets out of variables. See [Template Variables That Look Like Credentials](troubleshooting.md#template-variables-that-look-like-credentials).

## Best Practices

- **State only what differs.** Each tool already comes with sensible settings. Put only what is specific to your project in `[dev.pyproject]`, and prefer a tool's additive keys (for example Ruff's `extend-select`) over redefining a list. A list merges as a whole, so redefining `select` replaces Protostar's list instead of adding to it, and stops following it when it changes. Protostar's own built-in templates follow this rule; see [Built-in Templates](../developer/built-in-templates.md#baseline-in-modules-delta-in-templates).
- **Start with one file.** A single TOML file covers tools, dependencies, directories, configuration, and small starter files in `[files]`. Move to a directory with a `template/` folder when your starter files are big enough that writing them inside TOML strings gets in the way. CI, hooks, and tool configuration never need one: the tool flags bring them.
- **Name variables clearly.** Protostar asks for a missing value by the variable's name, so `<% AWS_REGION %>` explains itself where `<% REG %>` doesn't. Add a [description](#describing-variables) for anything a name can't say.
- **Use few commands.** A command in `system_tasks` or `post_install_tasks` may behave differently on Windows, and users of an untrusted template must confirm each one.
- **Check, then try it.** Run [`protostar check-template --strict`](releasing-templates.md#checking-a-template) on every change, and try the template in an empty folder (`protostar init --from ./path/to/template`) before you publish it.

## Next Steps

- **[Checking & Releasing Templates<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./releasing-templates.md):** Check a template in CI, publish versioned releases, and migrate the projects that follow it.
- **[Templates<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./templates.md):** How people use your template: repository URLs, versions, and trust.
- **[Global Configuration<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./configuration.md):** Give your templates short names under `[templates]`.
- **[Extending Protostar<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](../developer/extending-protostar.md):** Add support for a new tool to Protostar itself, when no template setting can do the job.
