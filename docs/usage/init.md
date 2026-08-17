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

    ```text
    --8<-- "tree_cli.txt"
    ```

    ??? abstract "See the generated `.gitignore`"
        ```gitignore
        --8<-- "cli/.gitignore"
        ```

    ??? abstract "See the generated `.markdownlint-cli2.yaml`"
        ```yaml
        --8<-- "cli/.markdownlint-cli2.yaml"
        ```

    ??? abstract "See the generated `.pre-commit-config.yaml`"
        ```yaml
        --8<-- "cli/.pre-commit-config.yaml"
        ```

    ??? abstract "See the generated `pyproject.toml`"
        ```toml
        --8<-- "cli/pyproject.toml"
        ```

    **The Intelligence:**

    - **Dependency Locking:** Protostar locks `typer` and `rich` from the CLI template.
    - **AST Configuration:** It constructs the TOML Abstract Syntax Tree (AST), configuring `[tool.ruff]`, `[tool.mypy]`, and `[tool.pytest.ini_options]` alongside development dependency groups.
    - **Local Toolchain Hooks:** In `.pre-commit-config.yaml`, Protostar scaffolds local Python toolchain hooks (`ruff-check`, `ruff-format`, `mypy`) that execute directly in your project environment via `uv run`. This eliminates isolated virtualenv overhead and version discrepancies.

=== "The Astrophysics Pipeline (Data Focus)"
    __Command:__ `protostar init --template astro`

    This footprint focuses on managing serialized data assets and preventing repository bloat.

    ```text
    --8<-- "tree_astro.txt"
    ```

    ??? abstract "See the generated `.gitattributes`"
        ```gitattributes
        --8<-- "astro/.gitattributes"
        ```

    ??? abstract "See the generated `.gitignore`"
        ```gitignore
        --8<-- "astro/.gitignore"
        ```

    ??? abstract "See the generated `pyproject.toml`"
        ```toml
        --8<-- "astro/pyproject.toml"
        ```

    **The Intelligence:**

    - **Directory Scaffolding:** It injects `data/catalogs` and `data/fits`, isolating telemetry from source code.
    - **Binary Safety:** It generates a `.gitattributes` file explicitly marking `*.fits` files as binary, and configuring `*.ipynb` for clean text diffing.
    - **Notebook Diffing:** It automatically configures `nbdime` at the git level, avoiding unreadable JSON diffs when tracking Jupyter Notebooks.
    - **Artifact Exclusions:** The `.gitignore` is populated with `*.fits`, `*.csv`, and `*.parquet`, preventing accidental commits of massive telemetry files.

=== "The Machine Learning Stack (Artifact Focus)"
    __Command:__ `protostar init --template ml --docker`

    This footprint focuses on containerization and strictly excluding model artifacts.

    ```text
    --8<-- "tree_ml.txt"
    ```

    ??? abstract "See the generated `Dockerfile`"
        ```dockerfile
        --8<-- "ml/Dockerfile"
        ```

    ??? abstract "See the generated `.dockerignore`"
        ```dockerignore
        --8<-- "ml/.dockerignore"
        ```

    ??? abstract "See the generated `.gitignore`"
        ```gitignore
        --8<-- "ml/.gitignore"
        ```

    ??? abstract "See the generated `pyproject.toml`"
        ```toml
        --8<-- "ml/pyproject.toml"
        ```

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
        ```text
        --8<-- "tree_ml.txt"
        ```

    === "Directory Structure After"
        ```text
        --8<-- "tree_ml_merged.txt"
        ```

    <hr>

    === "`Dockerfile` Before"
        ```dockerfile
        --8<-- "ml/Dockerfile"
        ```

    === "`Dockerfile` After"
        ```dockerfile
        --8<-- "ml_merged/Dockerfile"
        ```

    <hr>

    === "`.dockerignore` Before"
        ```dockerignore
        --8<-- "ml/.dockerignore"
        ```

    === "`.dockerignore` After"
        ```dockerignore
        --8<-- "ml_merged/.dockerignore"
        ```

    <hr>

    === "`.gitignore` Before"
        ```gitignore
        --8<-- "ml/.gitignore"
        ```

    === "`.gitignore` After"
        ```gitignore
        --8<-- "ml_merged/.gitignore"
        ```

    <hr>

    === "`pyproject.toml` Before"
        ```toml
        --8<-- "ml/pyproject.toml"
        ```

    === "`pyproject.toml` After"
        ```toml
        --8<-- "ml_merged/pyproject.toml"
        ```

!!! tip "Headless Operations"
    In CI/CD environments where interactive prompts are impossible, pass `--force-merge` or `--force-replace` to bypass collision prompts deterministically.

## Advanced Flags

- __Python Version Overrides__: Override the default Python version for a single run using `--python-version` (e.g., `protostar init --template cli --python-version 3.12`).
- __Verbose Output__: Append `--verbose` (or `-v`) to enable debug logs and full tracebacks.

## The Capabilities Matrix

To view all supported subcommands and flags in your terminal, run `protostar help init`.

![Protostar Help Init](../fixtures/cli_init_help.svg)
