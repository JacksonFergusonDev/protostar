---
description: "Author custom single-file blueprints and multi-file repository templates for Protostar."
---

# Authoring Custom Templates

Protostar templates allow platform engineers, team leads, and open-source maintainers to define reusable, declarative environment blueprints. By abstracting away the boilerplate of configuring linters, type checkers, and directory hierarchies, templates ensure that new projects adhere to organizational standards from initialization.

Templates scale gracefully from a single declarative TOML file to complex, multi-file repository archives.

## Level 1: The Single-File Blueprint

At its simplest, a template is a single TOML file containing the configuration state. You can host this file remotely or keep it on your local machine.

### The Template Schema

Below is the complete annotated schema for a Protostar template. It defines how to declare dependencies, scaffold directories, and override base tooling opinions.

```toml
--8<-- "template_schema.toml"
```

??? tip "Exporting the JSON Schema (`protostar export-schema`)"
    Protostar can generate the official JSON Schema for template files. You can use this for automated validation in external pipelines or configure IDE plugins like VS Code's *Even Better TOML* to get real-time autocompletion and linting:

    ```bash
    # Print formatted schema to terminal:
    protostar export-schema

    # Export machine-readable JSON schema to a file:
    protostar export-schema --json > protostar-template.schema.json
    ```

### Template Metadata (`name` & `description`)

Templates can declare self-documenting metadata at the root of the file:

```toml
# Display name of the template
name = "Enterprise FastAPI"

# Brief explanation of the stack and purpose
description = "FastAPI web application scaffold with Uvicorn, Pydantic, and Docker"
```

Protostar's zero-network template discovery engine reads these top-level fields locally to populate `protostar init --list-templates`, shell autocompletion hints, and interactive wizard options.

### AST Injections & Appends

Declare named TOML payloads under `[dev.pyproject]`. Tooling and build configuration are managed contributions; personal project fields such as description, authors, license, classifiers, keywords, and repository URLs are seed-only during merge initialization. Existing free-form `[files]` content is preserved unless explicit overwrite is selected.

```toml
[dev.pyproject]
linting = '''
[tool.ruff.lint]
extend-select = ["I", "UP", "B"]
'''

[appends.".envrc".project_environment]
content = "export PROJECT=example"
```

Non-TOML appends use a stable named record containing a string `content` field and, optionally, a [`requires`](#optional-content) condition. Keep the record ID unchanged when its payload changes. The engine namespaces template IDs by their canonical source identity and module IDs by module identity. Merge initialization preserves an existing unowned named region and warns when its desired content differs. Once owned, a region merges its desired updates line by line with local edits inside it, and keeps the local block whole when they overlap; explicit overwrite replaces only that region while retaining surrounding bytes. Delimiters use subtle editor-folding comments (`# region: protostar <tag>` and `# endregion: protostar <tag>`) with deterministic 8-character hex tags, while the expanded logical identity and each region's last applied text are preserved in `protostar.lock`.

Anonymous strings/arrays under `[appends]`, TOML append regions, append regions targeting a structurally merged YAML file (`.pre-commit-config.yaml`, `.github/codecov.yml`, `.readthedocs.yaml`, and the generated `.github/workflows/ci.yml` and `release.yml`, under any other name their tool reads them from), and the `__replace__`/`__remove__` control keys are rejected. Do not combine `[files]` with structured configuration or named regions targeting the same path. `protostar.lock` is reserved for engine state; `uv.lock` belongs to the resolver. Neither filename nor its descendants can be a template target.

Dependency declarations belong in `dependencies`, `[dev].dev_dependencies`, and `docs_dependencies`. Keep `docs_dependencies` for a documentation toolchain: `uv sync` installs the `dev` group by default but not `docs`, so anything else placed there (notebook tooling, for example) is removed by the next sync. Put development tooling in `[dev].dev_dependencies`. Generic TOML payloads cannot write `project.dependencies`, `project.optional-dependencies`, `dependency-groups`, or `tool.uv.sources`. Declare supported group wiring explicitly at the root:

```toml
dependency_includes = [{ group = "dev", include = "docs" }]
```

Includes support the `dev` and `docs` groups and reject cycles. Execution applies them before `uv add`; include-only changes declare a conditional `uv lock` action. Dependency resolver writes are bounded to `pyproject.toml` and `uv.lock` and journaled before invocation. Ordinary dependency additions need no extra lock action.

Templates may declare an informational root `version` string. CLI and wizard resolution retain the origin, canonical locator, and SHA-256 of the selected TOML bytes before interpolation. Built-in locators are stable IDs, local locators are normalized TOML paths, and a repository template's locator is its canonical repository URL, with its path inside the repository alongside. The ref it was applied at and the commit that ref named are recorded separately, so they never change the template's identity. Remote source URLs must omit credentials and query parameters so provenance cannot persist secrets. Display aliases are descriptive; trust authorization and interpolation answers are excluded from serialized provenance.

### Optional Content

Content that only applies sometimes says when with `requires`. A condition names what must hold:

- a tool key, such as `"ruff"` or `"pytest"`, which holds while that tool is enabled (the keys are listed in the [Tooling & Flags Matrix](./tooling-matrix.md));
- a bool option, such as `"compose"`, which holds while the option is on;
- `"option=value"`, such as `"database=postgres"`, which holds while a choice option has that value;
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

An option with `choices` is a choice option: it needs at least two distinct values, made of letters, digits, dots, dashes, and underscores, and a `default` among them. An option without `choices` is a bool option with a `true` or `false` default. `description` is optional and appears beside the option when it is chosen. Every option must be named by some `requires`, and may not share a name with a tool or a variable.

An option only chooses what the template includes. It never renders into text: `<% database %>` is a variable, and a template can't use the same name for both. Content that differs by choice is listed per choice, whole files at a time, with `[[optional]]`, payloads, and regions.

Users choose with `--option`, on `init` and on `sync`:

```bash
protostar init --template my-template --option database=postgres --option compose=true
protostar sync --option compose=false
```

The recipe editor shows a switch for each bool option and a choice for each choice option. The project recipe records the values in `[tool.protostar.options]`: every value passed with `--option`, and from the editor only those that differ from the template's default. A project that never chose follows the template, so a template that changes a default changes those projects on their next `sync`. A recorded value for an option the template no longer offers is dropped on `sync`; one the option no longer offers stops `sync` with an error naming the values it does.

## Level 2: The Multi-File Repository

While the `[files]` table in a single TOML file is excellent for small injections (like a standard `LICENSE` or a minimal `main.py`), complex scaffolds—such as a full FastAPI architecture or a PyTorch training pipeline—require physical files.

When you point the `--from` flag at a remote repository or a local directory archive, Protostar utilizes the following resolution sequence:

1. **Locate the Manifest:** Protostar searches the root of the archive for a `protostar.toml` file to act as the primary configuration blueprint.
1. **Resolve the `template/` Directory:** If a directory named `template/` exists adjacent to the `protostar.toml` file, Protostar recursively maps its contents into the target workspace.

### Example Repository Structure

```text
my-org-fastapi-template/
├── README.md
├── protostar.toml       # The environment manifest
└── template/            # Files here are mapped to your root workspace
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

*Note: Protostar automatically ignores compilation artifacts (`__pycache__`) and `.DS_Store` files inside the `template/` directory during extraction.*

Every file in `template/` must be UTF-8 text, because Protostar interpolates placeholders in each one. A binary file such as an image stops the template from loading with an error naming the file.

## Level 3: Variable Interpolation

Protostar features a lightweight, regex-based templating engine that evaluates placeholders wrapped in `<% VARIABLE_NAME %>` delimiters. This interpolation runs across the `protostar.toml` manifest, inline `[files]` strings, and physical files housed within the `template/` directory.

### Built-in Variables

The execution engine automatically computes and injects the following variables based on your CLI inputs, Git configuration, and directory context:

- `<% PROJECT_NAME %>`: The human-readable project name (e.g., `my-cool-app`).
- `<% PACKAGE_NAME %>`: The PEP 8 sanitized Python module identifier (e.g., `my_cool_app`).
- `<% PYTHON_VERSION %>`: The resolved target Python version (e.g., `3.13`).
- `<% CURRENT_YEAR %>`: The current four-digit year (useful for copyright headers).
- `<% AUTHOR_NAME %>`: The author's name, resolved from the global Protostar config or `git config user.name`.

### Custom Variables & Interactive Prompts

You can define custom placeholders tailored to your domain footprint. For example, if your template deploys to a configurable region, you might include:

```python
# template/src/<% PACKAGE_NAME %>/settings.py
DEFAULT_REGION = "<% DEFAULT_REGION %>"
```

Users supply the value with `--var`:

```bash
protostar init --from https://github.com/Org/template --var DEFAULT_REGION=eu-west-1
```

If they omit it, Protostar detects the unresolved `<% DEFAULT_REGION %>` placeholder and asks for it in an interactive terminal before any disk mutations occur; without a terminal, it stops with an error naming the variable. The value is recorded in the project recipe, so later runs of `init` and `sync` reuse it. Variable names are identifiers: a letter or underscore, then letters, digits, or underscores.

### Describing Variables

Protostar labels each field with the variable's name. To explain what a value should be, declare the variable in an optional `[variables]` table:

```toml
[variables.DEFAULT_REGION]
description = "Deployment region, e.g. eu-west-1"
```

The description appears under the field when Protostar asks for the value. Declarations are optional, and `description` is the only key. Declare only placeholders the template uses; declaring an unused or built-in variable stops the template from loading.

### Variables Are Not Secrets

A template's custom variables are non-secret by definition: their values are saved in the project recipe in `pyproject.toml` and rendered into the project's files, all of which get committed. If a value must stay out of the repository, it isn't a template variable. Have the generated code read it from the environment at runtime, and ship a `.env.example` in `template/` that names it.

Protostar backs this up with a safety net, not a guarantee:

- **Names:** a placeholder named like a credential, such as `<% API_KEY %>`, `<% DB_PASSWORD %>`, or `<% GITHUB_TOKEN %>`, draws a warning beside its field and in the terminal. Rename it, or better, read the secret from the environment instead.
- **Values:** each newly entered value is checked against [gitleaks](https://github.com/gitleaks/gitleaks)' default rules, at the version Protostar pins for the gitleaks pre-commit hook it scaffolds. A value that looks like a credential, such as a GitHub token or a private key, is held back until the user confirms it isn't a secret, for that variable only: a checkbox beside the field, or `--allow-secret NAME` on the command line. The error names the variable and the matching rule, never the value. Values are limited to 1,024 characters.

Values already recorded in the recipe are not checked again, so a confirmed value never blocks a later `init` or `sync`. The guard misses secrets gitleaks has no rule for, such as a password inside a database URL, so it never replaces keeping secrets out of variables. See [Template Variables That Look Like Credentials](troubleshooting.md#template-variables-that-look-like-credentials).

## Level 4: Testing & Distribution

### Checking a Template

`protostar check-template` checks a template without scaffolding anything. Run it from the template's directory, or name a template directory, a template TOML file, or an HTTPS URL:

```bash
protostar check-template
protostar check-template ./templates/backend.toml
protostar check-template https://github.com/YourOrg/fastapi-template
```

It renders the template with a placeholder for each custom variable and plans a default `protostar init` of it into an empty scratch directory, using Protostar's built-in configuration rather than yours, so every machine gets the same result. It writes nothing, runs no commands, and ignores whatever the directory you run it from contains.

It reports two kinds of finding:

- **Errors** (`invalid-template`) are anything that stops `protostar init` from using the template: invalid TOML, a field of the wrong type, a forbidden or reserved target, an unknown tooling flag, or a file under `template/` that isn't UTF-8 text.
- **Warnings** break a practice the built-in templates follow. The template works, but its users get a worse result.

| Rule | What it reports |
| :--- | :--- |
| `unknown-key` | A root key Protostar ignores, such as a misspelled field, or a tooling flag whose value isn't `true` or `false` |
| `missing-metadata` | No `name` or `description`, which `--list-templates` and the wizard show |
| `undescribed-variable` | A custom variable with no `[variables]` description |
| `credential-variable` | A custom variable named like a credential |
| `restated-baseline` | A `[dev.pyproject]` payload that repeats a module's baseline value, or redefines a baseline list instead of using an additive key |
| `unbound-tool-config` | A payload that configures a tool without `requires` for that tool |
| `unbound-tool-package` | A tool's package, such as `pytest-cov`, installed unconditionally instead of in an `[[optional]]` block that requires the tool |
| `inconsistent-migration` | A migration that removes or renames away a file the template still ships, renames a file to one it doesn't ship, or renames a variable the template doesn't use under its new name |

The check exits `1` when the template has errors, and also on warnings with `--strict`. If the template can't be retrieved at all (a wrong path, a network failure, an HTTP error such as 404), nothing is checked: it prints the retrieval error and exits with that error's [exit code](cli-reference.md#posix-exit-codes), such as `65` or `75`, so a failure to download is never mistaken for a broken template. `--json` returns the findings as a JSON payload.

The check covers a default `init`, with every option at its default. Content that only applies when a user turns on a tool the template leaves off, or chooses another option value, is not planned, so still try the combinations you expect your users to choose.

Each finding names the file and line it concerns, such as `protostar.toml:12`, including a key inside a `[dev.pyproject]` payload. A finding about something the template doesn't contain, such as a missing `name`, names only the file.

### Checking in GitHub Actions

To check a template in its own repository's CI, add a step such as:

```yaml
- uses: actions/checkout@v7
- uses: astral-sh/setup-uv@v10
- run: uvx protostar check-template --strict --output-format github
```

With `--output-format github`, each finding becomes a workflow annotation: it shows on the pull request's changed files at its line, and in the run's summary. Paths are relative to the repository root (`GITHUB_WORKSPACE`), so the step works from any `working-directory`. A template that couldn't be retrieved gets one annotation saying so, and findings in a remote template annotate the run instead of a file. The step still fails the same way: exit `1` for a failed check, or the retrieval error's own exit code. `--output-format github` can't be combined with `--json`.

### Local Testing

When authoring a template, you do not need to commit and push to a remote repository to test its execution. You can point the `--from` flag directly at your local template directory:

```bash
# From within an empty target directory
protostar init --from ~/Developer/templates/my-custom-template
```

### Distribution & Releases

Once your template is ready, push it to a repository on GitHub, GitLab, Bitbucket, Codeberg, or Sourcehut. Protostar accepts the repository's web, raw, and archive URLs, and a path inside the repository, so one repository can hold several templates.

Publish releases as tags that are [PEP 440](https://peps.python.org/pep-0440/) versions, such as `v1.3.0`. A new project starts on your newest release, `protostar status` tells existing projects when a newer one exists, and `protostar sync --to v1.3.0` moves them to it with a three-way merge that keeps their local edits. Tag pre-releases as such (`v2.0.0rc1`): they are offered only to projects already on a pre-release. Never move a published tag. Projects stay on the commit they applied, and `status` reports the moved tag as an update.

You can invoke your template directly:

```bash
protostar init --from https://github.com/YourOrg/data-science-template
```

Or, you can register it as a global alias in your `~/.config/protostar/config.toml` to access it natively in your interactive wizard:

```toml
[templates]
org-ds-base = "https://github.com/YourOrg/data-science-template"
```

### Migrations

Most changes between your releases need nothing extra: `sync --to` merges each file three ways, so your changes arrive and your users' edits stay. A few changes can't be expressed that way, because they're about files and names rather than their contents. Declare those as migrations:

```toml
version = "2.0.0"

[[migrations]]
version = "2.0.0"
rename = [{ from = "src/<% PACKAGE_NAME %>/settings.py", to = "src/<% PACKAGE_NAME %>/config.py" }]
remove = ["setup.cfg"]
rename_variables = [{ from = "ORG", to = "ORGANIZATION" }]
```

A migration's `version` is the release that introduced the change. A project runs it when it moves from a release before that version to that version or later, and never again; a project that skips releases runs every migration in between, oldest first. A template with migrations must declare a [PEP 440](https://peps.python.org/pep-0440/) root `version`, and no migration may be newer than it. Keep every migration in later releases: the new release is the only one a project reads them from.

- **`rename`** moves a seeded file, including the user's edits to it, and Protostar's ownership with it. Ship the file under its new name. If something already exists at the new path, the file stays where it is and `status` says so. A file the user deleted stays deleted at its new path.
- **`remove`** retires a seeded file you no longer ship. An unedited copy is deleted. A copy with edits stays and becomes a `retracted` conflict until the user settles it: `local` keeps it as their own file, and `desired` deletes it.
- **`rename_variables`** moves a recorded variable value to its new name before anything renders, so users aren't asked for a value they already gave.

Migrations only touch what Protostar owns: a path it never seeded is left alone. They are declarative on purpose. `status` and `sync --dry-run` list each one before anything changes, and a failed `sync` rolls them back with everything else. Scripts would make both impossible, so migrations never run commands. A project can't move back to a release before a migration it has run, because the older release can't know how to reverse it.

Renaming or removing a dependency, or a module-generated file, isn't a migration yet.

### Security Considerations

Protostar enforces an **Informed Consent Security Model**. If your template defines `system_tasks` or `post_install_tasks` (executable shell commands), and you load it directly from an untrusted remote URL via `--from`, Protostar will halt execution and display an interactive security prompt.

Templates registered in your global `config.toml` aliases bypass this prompt. For a complete breakdown of how the runtime evaluates trust boundaries, see the [Remote Trust Model](templates.md#security-model-the-remote-trust-dialog).

## Best Practices

When building templates for your team or the open-source community, keep the following guidelines in mind:

- **State Only the Delta:** Each tool module already ships a sensible baseline configuration. Put only what is specific to your project in `[dev.pyproject]`, and prefer a tool's additive keys (for example Ruff's `extend-select`) over redefining a list. Lists merge atomically, so redefining `select` replaces the baseline instead of adding to it, and it will drift when the baseline changes. Protostar's own built-in templates follow this rule; see [Built-in Templates](../developer/built-in-templates.md#baseline-in-modules-delta-in-templates).
- **Choose the Right Complexity:** Start with a single-file blueprint (`protostar.toml`) if you only need to enforce tooling configurations (like Ruff or Pyright rules). Graduate to a multi-file repository only when you need to scaffold physical code, directories, or CI/CD pipelines.
- **Descriptive Variable Names:** Use clear, self-explanatory names for custom placeholders (e.g., `<% AWS_REGION %>` instead of `<% REG %>`). Since Protostar automatically generates interactive terminal prompts for unresolved variables, descriptive names provide a better user experience.
- **Minimize Shell Scripts:** Be cautious with `system_tasks` and `post_install_tasks`. Heavy reliance on shell commands can compromise cross-platform compatibility (e.g., failing on Windows). It also triggers the Informed Consent Security Model for remote URLs, which might alarm users.
- **Check, Then Test Locally:** Run `protostar check-template --strict` on every change, and try the template against an empty target directory (`protostar init --from ./path/to/template`) before publishing it to a remote version control platform.

## Next Steps

- **[Templates](./templates.md):** Learn about CLI options, repository URLs, template versions, and template consumption.
- **[Global Configuration](./configuration.md):** Register your custom templates under `[templates]` in your `config.toml`.
- **[Extending Protostar](../developer/extending-protostar.md):** Implement custom Python bootstrap modules if your project requires engine-level integrations.
