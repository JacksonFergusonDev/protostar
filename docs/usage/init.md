# Environment Initialization

The `init` command is the core engine of Protostar. It is a deterministic state-machine designed to safely aggregate configurations, wire development tooling together, and construct robust directory architectures in seconds.

Protostar is designed to be run on Day 1 to build your repository foundation, but it is safe to re-run on Day 50 to inject a forgotten dependency or adopt a new static analysis tool.

<div class="spacer-2"></div>

<div class="grid cards" markdown>

- :material-shield-check: __State-Aware Aggregation__

    Protostar doesn't blindly overwrite files. It parses ASTs, deduplicates `.gitignore` entries, and safely deep-merges configurations. It is safe to execute on pre-existing codebases.

- :material-clock-fast: __Deterministic Velocity__

    Instead of manually copying boilerplate from old repositories or relying on fragile shell scripts, Protostar guarantees a consistent, idempotent environment in fractions of a second.

</div>

---

## Opinionated Templates

While Protostar is modular, you often want a vetted, turnkey environment without selecting a dozen flags manually. Protostar ships with built-in __Opinionated Templates__ that bundle specific tools, directories, and AST overrides.

You can select a template in the interactive wizard (`protostar init`), or trigger it headlessly:

```bash
# Scaffold from a built-in template
protostar init --template astro

# Scaffold from a remote team standard
protostar init --from https://github.com/YourOrg/standards/blob/main/backend.toml
```

### Tri-State CLI Toggles

Every tooling option in Protostar supports tri-state evaluation. Passing `--<tool>` forces it on, while passing `--no-<tool>` forces it off, overriding template opinions:

```bash
# Use the astro template but disable direnv and enable mypy
protostar init --template astro --no-direnv --mypy
```

For custom authoring, variable interpolation, global aliases, and security mechanics, see the complete __[Templates & Portable Configurations Guide](./templates.md)__.

---

## Execution Footprints

To understand how Protostar interprets your flags, observe what happens when we execute different workflows in an empty directory.

!!! note "IDE Configuration Footprints"
    The following repository tree examples assume you have configured an IDE in your global settings (e.g., `ide = "vscode"`) in addition to enabling direnv. If your config remains set to the default `None`, the `.vscode/settings.json` file will not be generated, though the universal `.vscode/` exclusion will still be safely appended to your `.gitignore`.

=== "The CLI Application (Tooling Focus)"
    __Command:__ `protostar init --template cli`

    This footprint demonstrates Protostar's ability to wire complex tooling together automatically.

    --8<-- "cli_tree.md"

    ??? abstract "See the generated `.gitignore`"
        --8<-- "cli_gitignore.md"

    ??? abstract "See the generated `.markdownlint-cli2.yaml`"
        --8<-- "cli_markdownlint-cli2yaml.md"

    ??? abstract "See the generated `.pre-commit-config.yaml`"
        --8<-- "cli_pre-commit-configyaml.md"

    ??? abstract "See the generated `pyproject.toml`"
        --8<-- "cli_pyprojecttoml.md"

    **The Intelligence:**

    - **Dependency Locking:** Protostar locks `typer` and `rich` from the CLI template.
    - **AST Configuration:** It constructs the TOML Abstract Syntax Tree (AST), configuring `[tool.ruff]`, `[tool.mypy]`, and `[tool.pytest.ini_options]` alongside development dependency groups.
    - **Local Toolchain Hooks:** In `.pre-commit-config.yaml`, Protostar scaffolds local Python toolchain hooks (`ruff-check`, `ruff-format`, `mypy`) that execute directly in your project environment via `uv run`. This eliminates isolated virtualenv overhead and version discrepancies.

=== "The Astrophysics Pipeline (Data Focus)"
    __Command:__ `protostar init --template astro`

    This footprint focuses on managing serialized data assets and preventing repository bloat.

    --8<-- "astro_tree.md"

    ??? abstract "See the generated `.gitattributes`"
        --8<-- "astro_gitattributes.md"

    ??? abstract "See the generated `.gitignore`"
        --8<-- "astro_gitignore.md"

    ??? abstract "See the generated `pyproject.toml`"
        --8<-- "astro_pyprojecttoml.md"

    **The Intelligence:**

    - **Directory Scaffolding:** It injects `data/catalogs` and `data/fits`, isolating telemetry from source code.
    - **Binary Safety:** It generates a `.gitattributes` file explicitly marking `*.fits` files as binary, and configuring `*.ipynb` for clean text diffing.
    - **Notebook Diffing:** It automatically configures `nbdime` at the git level, avoiding unreadable JSON diffs when tracking Jupyter Notebooks.
    - **Artifact Exclusions:** The `.gitignore` is populated with `*.fits`, `*.csv`, and `*.parquet`, preventing accidental commits of massive telemetry files.

=== "The Machine Learning Stack (Artifact Focus)"
    __Command:__ `protostar init --template ml --docker`

    This footprint focuses on containerization and strictly excluding model artifacts.

    --8<-- "ml_tree.md"

    ??? abstract "See the generated `Dockerfile`"
        --8<-- "ml_Dockerfile.md"

    ??? abstract "See the generated `.dockerignore`"
        --8<-- "ml_dockerignore.md"

    ??? abstract "See the generated `.gitignore`"
        --8<-- "ml_gitignore.md"

    ??? abstract "See the generated `pyproject.toml`"
        --8<-- "ml_pyprojecttoml.md"

    **The Intelligence:**

    - **Container Scaffolding:** Passing `--docker` generates a multi-stage `Dockerfile` and optimized `.dockerignore`. The `Dockerfile` leverages `uv` layer caching, non-root user execution (`appuser`), and minimal runtime images.
    - **Model Checkpoints:** The ML template injects ignores for tensor weights (`*.pth`, `*.pt`, `*.onnx`, `*.safetensors`) and experiment tracking directories (`wandb/`, `mlruns/`).

---

## Progressive Scaffolding & Collisions

When Protostar detects existing configuration markers (like `pyproject.toml`), it triggers the __Gravitational Anomaly__ intercept prompt:

```text
Protostar Ignition Sequence Initiated

Gravitational Anomaly: Protostar detected existing configuration files in the workspace.
  - pyproject.toml

? How would you like to proceed?
  » Merge      (Safely injects missing configs; preserves existing user data)
    Overwrite  (Forces injection; updates existing keys to match Protostar)
    Abort      (Safely exit without modifying the environment)
```

Selecting __Merge__ executes an AST injection:

- Leaves your existing dependencies untouched.
- Alphabetically inserts new template dependencies.
- Merges tooling configuration tables into `pyproject.toml`.
- Appends new file patterns to `.gitignore` without duplicating existing rules.

??? abstract "See the comparison"
    === "Directory Structure Before"
        --8<-- "ml_tree.md"

    === "Directory Structure After"
        --8<-- "ml_merged_tree.md"

    <hr>

    === "`Dockerfile` Before"
        --8<-- "ml_Dockerfile.md"

    === "`Dockerfile` After"
        --8<-- "ml_merged_Dockerfile.md"

    <hr>

    === "`.dockerignore` Before"
        --8<-- "ml_dockerignore.md"

    === "`.dockerignore` After"
        --8<-- "ml_merged_dockerignore.md"

    <hr>

    === "`.gitignore` Before"
        --8<-- "ml_gitignore.md"

    === "`.gitignore` After"
        --8<-- "ml_merged_gitignore.md"

    <hr>

    === "`pyproject.toml` Before"
        --8<-- "ml_pyprojecttoml.md"

    === "`pyproject.toml` After"
        --8<-- "ml_merged_pyprojecttoml.md"

!!! tip "Headless Operations"
    In CI/CD environments where interactive prompts are impossible, pass `--force-merge` or `--force-replace` to bypass collision prompts deterministically.

## Advanced Flags

- __Python Version Overrides__: Override the default Python version for a single run using `--python-version` (e.g., `protostar init --template cli --python-version 3.12`).
- __Verbose Output__: Append `--verbose` (or `-v`) to enable debug logs and full tracebacks.

## The Capabilities Matrix

To view all supported subcommands and flags in your terminal, run `protostar help init`.

![Protostar Help Init](../includes/cli_init_help.svg)
