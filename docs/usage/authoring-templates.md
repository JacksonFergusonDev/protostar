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

Non-TOML appends use a stable named record containing exactly one string `content` field. Keep the record ID unchanged when its payload changes. The engine namespaces template IDs by their canonical source identity and module IDs by module identity. Merge initialization preserves an existing unowned named region and warns when its desired content differs. Once owned, a region merges its desired updates line by line with local edits inside it, and keeps the local block whole when they overlap; explicit overwrite replaces only that region while retaining surrounding bytes. Delimiters use subtle editor-folding comments (`# region: protostar <tag>` and `# endregion: protostar <tag>`) with deterministic 8-character hex tags, while the expanded logical identity and each region's last applied text are preserved in `protostar.lock`.

Anonymous strings/arrays under `[appends]`, TOML append regions, append regions targeting a structurally merged YAML file (`.pre-commit-config.yaml`, `.github/codecov.yml`, `.readthedocs.yaml`, and the generated `.github/workflows/ci.yml` and `release.yml`, under any other name their tool reads them from), and the `__replace__`/`__remove__` control keys are rejected. Do not combine `[files]` with structured configuration or named regions targeting the same path. `protostar.lock` is reserved for engine state; `uv.lock` belongs to the resolver. Neither filename nor its descendants can be a template target.

Dependency declarations belong in `dependencies`, `[dev].dev_dependencies`, and `docs_dependencies`. Keep `docs_dependencies` for a documentation toolchain: `uv sync` installs the `dev` group by default but not `docs`, so anything else placed there (notebook tooling, for example) is removed by the next sync. Put development tooling in `[dev].dev_dependencies`. Generic TOML payloads cannot write `project.dependencies`, `project.optional-dependencies`, `dependency-groups`, or `tool.uv.sources`. Declare supported group wiring explicitly at the root:

```toml
dependency_includes = [{ group = "dev", include = "docs" }]
```

Includes support the `dev` and `docs` groups and reject cycles. Execution applies them before `uv add`; include-only changes declare a conditional `uv lock` action. Dependency resolver writes are bounded to `pyproject.toml` and `uv.lock` and journaled before invocation. Ordinary dependency additions need no extra lock action.

Templates may declare an informational root `version` string. CLI and wizard resolution retain the origin, canonical locator, and SHA-256 of the selected TOML bytes before interpolation. Built-in locators are stable IDs, local locators are normalized TOML paths, and remote locators retain the canonical resolved download URL rather than temporary extraction paths. Remote source URLs must omit credentials and query parameters so provenance cannot persist secrets. Recognizable immutable commit locators also retain their source revision. Display aliases are descriptive; trust authorization and interpolation answers are excluded from serialized provenance. State and three-way reconciliation are subsequent milestones.

### Tool-Bound Payloads & Dependencies

A payload that configures a tool should say which one. Write it as a table with `content` and `requires`, and Protostar injects it only while that tool is enabled:

```toml
[dev.pyproject.linting]
requires = "ruff"
content = '''
[tool.ruff.lint]
extend-select = ["I", "UP", "B"]
'''
```

With this, `protostar init --template my-template --no-ruff` writes no `[tool.ruff]` at all, instead of leaving configuration behind for a tool that isn't installed. A project's recipe opt-out treats the payload the same way it treats the tool's own configuration.

Plain string payloads are always injected. Use them for configuration that no tool toggle should remove, such as a `[build-system]` table. The valid `requires` names are the tool keys in the [Tooling & Flags Matrix](./tooling-matrix.md) (for example `ruff`, `mypy`, `pytest`), and an unknown name is rejected when the template loads. In TOML, put the plain string payloads before any `[dev.pyproject.<name>]` sub-tables.

Dev packages that only one tool needs belong in `[dev.tool_dependencies]`, keyed by the tool. They are installed only while that tool is enabled:

```toml
[dev.tool_dependencies]
pytest = ["pytest-cov", "httpx"]
```

With this, `--no-pytest` does not install `pytest-cov` or `httpx`. Packages in `[dev].dev_dependencies` are always installed, so keep that list for tools no toggle should remove. The tool names are validated the same way as `requires`.

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
| `unbound-tool-package` | A tool's package, such as `pytest-cov`, installed unconditionally instead of under `[dev.tool_dependencies]` |

The check exits `1` when the template has errors, and also on warnings with `--strict`. If the template can't be retrieved at all (a wrong path, a network failure, an HTTP error such as 404), nothing is checked: it prints the retrieval error and exits with that error's [exit code](cli-reference.md#posix-exit-codes), such as `65` or `75`, so a failure to download is never mistaken for a broken template. `--json` returns the findings as a JSON payload.

The check covers a default `init`. Tool-bound content that only applies when a user turns on a tool the template leaves off is not planned, so still try the combinations you expect your users to choose.

To check a template in its own repository's CI, add a step such as:

```yaml
- uses: actions/checkout@v7
- uses: astral-sh/setup-uv@v10
- run: uvx protostar check-template --strict
```

### Local Testing

When authoring a template, you do not need to commit and push to a remote repository to test its execution. You can point the `--from` flag directly at your local template directory:

```bash
# From within an empty target directory
protostar init --from ~/Developer/templates/my-custom-template
```

### Distribution & URL Translation

Once your template is ready, push it to your organization's version control platform. Protostar automatically translates standard web UI URLs into raw downloadable endpoints or archive targets for all major hosting providers (GitHub, GitLab, Bitbucket, Codeberg, and Sourcehut).

You can invoke your template directly:

```bash
protostar init --from https://github.com/YourOrg/data-science-template
```

Or, you can register it as a global alias in your `~/.config/protostar/config.toml` to access it natively in your interactive wizard:

```toml
[templates]
org-ds-base = "https://github.com/YourOrg/data-science-template"
```

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

- **[Templates](./templates.md):** Learn about CLI options, URL translation, and template consumption.
- **[Global Configuration](./configuration.md):** Register your custom templates under `[templates]` in your `config.toml`.
- **[Extending Protostar](../developer/extending-protostar.md):** Implement custom Python bootstrap modules if your project requires engine-level integrations.
