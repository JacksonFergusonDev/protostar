---
description: "Learn how to use protostar init to safely construct and manage your Python project architecture."
---

# Environment Initialization

The `init` command is Protostar's primary command. It sets up folder structures, wires together tools, and configures dependencies in seconds.

Protostar is designed to be run on Day 1 to build your repository foundation. On
an already initialized workspace, `--force-merge` safely reconciles contributions
that Protostar previously recorded. It can apply unchanged-local template updates
and additive tooling, while preserving user edits, deletions, and unowned content.
It does not adopt existing configuration, switch templates, prune removed template
content. After initialization, use the [project lifecycle](lifecycle.md) commands
`status`, `diff`, and `sync` to review and apply the recorded recipe.

<div class="grid cards" markdown>

- :material-shield-check: __Safe Merging__

    Protostar doesn't blindly overwrite files. In merge mode it uses recorded ownership baselines for supported TOML and YAML configuration (including GitHub Actions workflows, merged by job and step), line-by-line three-way merges for other generated files, and deduplicated ignore additions. Existing content without state remains unowned.

- :material-clock-fast: __Instant & Repeatable__

    Instead of manually copying boilerplate from old repositories or relying on fragile shell scripts, Protostar creates a clean, consistent environment in fractions of a second.

</div>

## Built-in Templates

While Protostar is fully modular, you often want a vetted, turnkey environment without selecting individual flags manually. Protostar ships with built-in templates that bundle domain-specific tools, directories, and AST configurations. Each one is a project *shape* (a command-line app, a web service, an analysis workbench), not a fixed stack of libraries.

The shapes come in two kinds of default. __Product__ templates (`cli`, `api`, `lib`) start with the full quality gate: strict typing, tests, CI, and commit hooks. __Workbench__ templates (`astro`, `ml`) start lean, with just Ruff, direnv, and `just`, so exploratory work isn't buried in opinions on day one. Either kind is only a starting point: every tool can be overridden with the tri-state flags below.

To scaffold from a template headlessly, pass `--template` (or `-t`):

```bash
# Scaffold from a built-in template (e.g., astro, cli, ml, api)
protostar init --template astro
```

### Tri-State CLI Toggles

Every tooling option supports tri-state evaluation. You can load a template's baseline and explicitly override any tool: passing `--<tool>` forces it on, while passing `--no-<tool>` forces it off:

```bash
# Scaffold the astro template with direnv disabled and mypy enabled
protostar init -t astro --no-direnv --mypy
```

To explore all built-in templates, load remote team standards (`--from`), supply dynamic parameters, or register global aliases, see the complete __[Templates Guide](./templates.md)__.

## Example Setups

To understand how Protostar interprets your flags, observe what happens when we execute different workflows in an empty directory.

!!! note "IDE Configurations"
    The following repository tree examples assume you have configured an IDE in your global settings (e.g., `ide = "vscode"`) in addition to enabling direnv. If your config remains set to the default `None`, the `.vscode/settings.json` file will not be generated, though the universal `.vscode/` exclusion will still be safely appended to your `.gitignore`.

=== "The CLI Application (Tooling Focus)"
    __Command:__ `protostar init --template cli`

    This example demonstrates Protostar's ability to wire complex tooling together automatically.

    ```text
    --8<-- "tree_cli.txt"
    ```

    ??? abstract "Inspect Generated Files"
        === "pyproject.toml"
            ```toml
            --8<-- "cli/pyproject.toml"
            ```
        === ".pre-commit-config.yaml"
            ```yaml
            --8<-- "cli/pre-commit-config.fixture.yaml"
            ```
        === ".gitignore"
            ```gitignore
            --8<-- "cli/.gitignore"
            ```

    __What Protostar sets up:__

    - __Dependency Locking:__ Protostar locks `typer` and `rich` from the CLI template.
    - __AST Configuration:__ It constructs the TOML Abstract Syntax Tree (AST), configuring `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`, and `[tool.rumdl]` alongside development dependency groups.
    - __Local Toolchain Hooks:__ In `.pre-commit-config.yaml`, Protostar scaffolds local toolchain hooks (`ruff-check`, `ruff-format`, `mypy`, `rumdl-check`, `rumdl-fmt`) that execute directly in your project environment via `uv run`, so each runs the version locked in `uv.lock`. `mypy` checks the whole project, as CI does, because checking only the staged files misses errors they cause elsewhere. Workflows are linted with `actionlint`, and the Renovate and Read the Docs configurations are validated against their schemas with `check-jsonschema`, wherever those files live.
    - __Hook Stages:__ `default_install_hook_types` always includes `pre-commit`. Commitizen adds `commit-msg`, and Pytest adds `pre-push`: the test suite runs before a push that changes `src/`, `tests/`, `pyproject.toml`, or `uv.lock`, rather than on every commit. `default_stages` is `pre-commit`, so every other hook runs at commit time.

=== "The Reusable Library (Package Focus)"
    __Command:__ `protostar init --template lib`

    This template scaffolds a clean, reusable Python library package ready for distribution.

    ```text
    --8<-- "tree_lib.txt"
    ```

    ??? abstract "Inspect Generated Files"
        === "pyproject.toml"
            ```toml
            --8<-- "lib/pyproject.toml"
            ```
        === "src/demo_project/__init__.py"
            ```python
            --8<-- "lib/src/demo_project/__init__.py"
            ```
        === ".pre-commit-config.yaml"
            ```yaml
            --8<-- "lib/pre-commit-config.fixture.yaml"
            ```
        === ".gitignore"
            ```gitignore
            --8<-- "lib/.gitignore"
            ```

    __What Protostar sets up:__

    - __PEP 561 Typing:__ Injects `py.typed` to signal inline type annotations to downstream type checkers like Mypy and Pyright.
    - __Package Packaging:__ Configures the `hatchling` build backend with a standard `src/` layout for wheel and sdist builds.
    - __Public API Architecture:__ Scaffolds `__init__.py` with explicit `__all__` re-exports and dynamic `__version__` lookup via `importlib.metadata`.
    - __Strict Typing & Quality:__ Enables strict Mypy checking, docstring linting (`D`), and `TC` (flake8-type-checking) to keep type-only imports from becoming runtime transitive dependencies.

=== "The Astrophysics Pipeline (Data Focus)"
    __Command:__ `protostar init --template astro`

    This template focuses on managing dataset files and preventing repository bloat.

    ```text
    --8<-- "tree_astro.txt"
    ```

    ??? abstract "Inspect Generated Files"
        === "pyproject.toml"
            ```toml
            --8<-- "astro/pyproject.toml"
            ```
        === ".gitattributes"
            ```gitattributes
            --8<-- "astro/.gitattributes"
            ```
        === ".gitignore"
            ```gitignore
            --8<-- "astro/.gitignore"
            ```

    __What Protostar sets up:__

    - __Directory Scaffolding:__ It injects `data/catalogs` and `data/fits`, isolating dataset files from source code.
    - __Binary Safety:__ It generates a `.gitattributes` file explicitly marking `*.fits` files as binary, and configuring `*.ipynb` for clean text diffing.
    - __Notebook Diffing:__ It automatically configures `nbdime` at the git level, avoiding unreadable JSON diffs when tracking Jupyter Notebooks.
    - __Artifact Exclusions:__ The `.gitignore` is populated with `*.fits`, `*.csv`, and `*.parquet`, preventing accidental commits of large data files.

=== "The Machine Learning Stack (Artifact Focus)"
    __Command:__ `protostar init --template ml --docker`

    This template focuses on containerization and excluding model artifacts.

    ```text
    --8<-- "tree_ml.txt"
    ```

    ??? abstract "Inspect Generated Files"
        === "Dockerfile"
            ```dockerfile
            --8<-- "ml/Dockerfile"
            ```
        === ".dockerignore"
            ```dockerignore
            --8<-- "ml/.dockerignore"
            ```
        === "pyproject.toml"
            ```toml
            --8<-- "ml/pyproject.toml"
            ```

    __What Protostar sets up:__

    - __Container Scaffolding:__ Passing `--docker` (or using a template that declares `docker = true`, such as `api`; `--no-docker` overrides it) generates a multi-stage `Dockerfile` and optimized `.dockerignore`. The `Dockerfile` leverages `uv` layer caching, non-root user execution (`appuser`), and minimal runtime images.
    - __Model Checkpoints:__ The ML template injects ignores for tensor weights (`*.pth`, `*.pt`, `*.onnx`, `*.safetensors`) and experiment tracking directories (`wandb/`, `mlruns/`).

=== "The API Service (FastAPI Focus)"
    __Command:__ `protostar init --template api`

    This template scaffolds a modern asynchronous web API service using FastAPI and Pydantic.

    ```text
    --8<-- "tree_api.txt"
    ```

    ??? abstract "Inspect Generated Files"
        === "pyproject.toml"
            ```toml
            --8<-- "api/pyproject.toml"
            ```
        === "justfile"
            ```just
            --8<-- "api/justfile"
            ```
        === "CHANGELOG.md"
            ```markdown
            --8<-- "api/CHANGELOG.md"
            ```

    __What Protostar sets up:__

    - __Modular API Architecture:__ Establishes a clean directory layout separating routers (`src/demo_project/api/routers`), core application settings (`src/demo_project/core/config.py`), database models, and schemas.
    - __Async Toolchain:__ Pre-configures `fastapi`, `uvicorn`, `pydantic-settings`, and asynchronous test infrastructure powered by `pytest-asyncio` and `httpx`.
    - __Semantic Versioning & Changelogs:__ Integrates Commitizen changelog tooling and automated release tracking out of the box.

## Task Runner Orchestration (`justfile`)

Every initialized repository includes a turnkey `justfile` generated from your active tooling configuration. Recipes dynamically adapt to your selected linters, test frameworks, and documentation engines:

```just
--8<-- "cli/justfile"
```

Running `just` in your project root provides standard developer workflows immediately:

- __`just format`__: Runs automated code formatting with Ruff and rumdl.
- __`just lint`__: Executes static analysis with Ruff and rumdl.
- __`just typecheck`__: Runs static type checking across the project source tree.
- __`just test` / `just test-cov`__: Executes the test suite with coverage reporting.
- __`just ci`__: Emulates the GitHub Actions CI pipeline locally.

## Recipe Editor & Metadata

When running `protostar init` without a `--template` flag in a terminal, Protostar opens the recipe editor. Pick a template, toggle tools, and fill in project details while a live preview shows the planned file tree.

![Protostar recipe editor](../assets/terminals/tui_recipe_editor.svg)

The editor is built for the keyboard; the mouse works too. Moving never changes a value; only `Space` and `Enter` do. The footer shows the keys for whatever has focus, each button shows its own key, and `F1` lists them all.

| Key | Action |
| --- | --- |
| `↑` `↓` | Move between rows. Lists move within, then continue to the next row. |
| `Space` | Toggle a checkbox, choose an option, or open a menu. |
| `Enter` | Same as `Space`; in a text field, accept it and move on. |
| `Tab` / `Shift+Tab` | Next or previous control; the tool checkboxes count as one stop. |
| `Ctrl+S` | Continue to the change review. |
| `Esc` | Cancel, after asking. |
| `Ctrl+C` | Quit immediately. |

__Continue__ opens the change review. It lists every planned path as new, modified, conflict, existing, or after setup, shows a diff for each file Protostar writes before running commands, and then the commands and packages that follow. Nothing runs until you choose __Apply__ (`A`). `↑` `↓` move between files, `PgUp` `PgDn` scroll the diff, and `Esc` goes back to the editor.

![Protostar change review](../assets/terminals/tui_change_review.svg)

The following metadata fields appear in the editor, pre-filled from your global configuration and git environment:

--8<-- "table_metadata.md"

## Execution Progress

Once planning succeeds, Protostar writes the project files and runs each subprocess
(`git init`, `uv init`, one `uv add` per dependency group, hook installation) as a
separate step. The running step animates in a spinner; each finished step leaves a
permanent `✔` line, so the completed work stays on screen:

![Protostar Init](../assets/terminals/cli_init.svg)

If a step fails or you interrupt it, that step is marked `✖`, every tracked change
is rolled back, and the error report follows. Piped output omits the spinner but
keeps the checklist lines; `--json` suppresses the checklist entirely.

## Progressive Scaffolding & Collisions

When Protostar detects existing configuration files (like `pyproject.toml`), the change review marks them as conflicts and asks how to handle them under __Existing files__:

- __Merge__ (`M`) safely injects missing configs and preserves existing user data.
- __Overwrite__ (`O`) forces injection and updates existing keys to match Protostar.

Choosing either re-prepares the review with its diffs. Press __Cancel__ to exit without modifying the environment.

Selecting __Merge__ reconciles declared TOML configuration against
`.protostar.lock.toml`. A tracked project requires the same explicitly selected
template source; switching templates or adding a template to tracked tooling-only
state is unsupported.

The example below starts from a tracked ML workspace, adds representative
astronomy dependencies, ignore rules, and data directories as foreign local
content, then repeats the ML template with `--mypy --docker --force-merge`:

- Leaves the existing foreign dependencies, ignores, and directories untouched.
- Adds accepted new dependencies through `uv add`.
- Updates unchanged owned tooling values and preserves local edits/deletions with structured warnings.
- Appends new file patterns to `.gitignore` without duplicating existing rules.

    ??? abstract "See the injected changes"
        ```diff
        --8<-- "diff_ml_ml_merged_pyproject_toml.diff"
        --8<-- "diff_ml_ml_merged__gitignore.diff"
        ```

!!! tip "Headless Operations"
    In CI/CD environments where interactive prompts are impossible, pass `--force-merge` or `--force-replace` to bypass collision prompts deterministically.

## Advanced Flags

- __Dry-Run Simulation__: Append `--dry-run` to preview the planned filesystem structure, dependencies, and tasks without writing files or running shell commands (e.g., `protostar init --template cli --dry-run`).
    ![Protostar Dry Run](../assets/terminals/cli_dry_run.svg)
- __Machine-Readable Output__: Pass the position-independent `--json` flag to emit structured JSON envelopes to `stdout` and route logs to `stderr` (e.g., `protostar init --template cli --json`). See the __[Agent & Machine Interface](./agent-interface.md)__ for the full protocol specification.
- __Template Shorthand__: Use `-t` as shorthand for `--template` (e.g., `protostar init -t cli`).
- __List Available Templates__: Run `protostar init --list-templates` to view all built-in templates and registered global aliases.
- __Template Variables__: Supply a template's custom variables with `--var NAME=VALUE`, once per variable (e.g., `protostar init --from ./team.toml --var REGION=eu-west-1`). In a terminal, Protostar asks for any you leave out; elsewhere, including under `--json`, a missing value is an error. Values are saved in the project recipe, so never pass secrets. A value that looks like a credential stops init; if it isn't a secret, keep it with `--allow-secret NAME`. See [Template variables](../development/project-recipe.md#template-variables).
- __Python Version Overrides__: Override the default Python version for a single run using `--python-version` (e.g., `protostar init --template cli --python-version 3.13`).
- __Verbose Output__: Append `--verbose` (or `-v`) to enable debug logs and full tracebacks.

## The Capabilities Matrix

To view all supported subcommands and flags in your terminal, run `protostar help init`.

![Protostar Help Init](../assets/terminals/cli_init_help.svg)

## Next Steps

- __[Templates](./templates.md):__ Learn how to create and share custom TOML blueprints, fetch remote templates, and interpolate variables.
- __[Tooling & Flags Matrix](./tooling-matrix.md):__ Explore all supported linters, formatters, type checkers, and test runners.
- __[Global Configuration](./configuration.md):__ Customize your default Python version, licenses, and template aliases.
- __[Troubleshooting & FAQ](./troubleshooting.md):__ Resolve missing binary dependencies, workspace collisions, and editor configuration issues.

## Persisted project intent

Successful initialization records `[tool.protostar]` in `pyproject.toml` alongside
the separate ownership ledger. Unspecified flags preserve recorded diversions on
reinitialization. See [project recipes](../development/project-recipe.md) for
enrollment, selection precedence, and template variables.
