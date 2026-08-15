# Environment Tooling

Tooling modules handle the injection of static analysis, testing frameworks, and continuous integration hooks. They safely deep-merge their configurations into existing host files like `pyproject.toml`.

<div class="grid cards" markdown>

- :material-check-all: __Pre-Commit (`--pre-commit`)__

    The orchestration engine that binds all linting and formatting hooks. Evaluates your workspace, initializes `.git` if absent, and automatically executes `pre-commit install`.

- :material-lightning-bolt: __Prek (`--prek`)__

    A dependency-free, extremely fast Rust alternative to `pre-commit`. Like `--pre-commit`, this initializes `.git` and installs your git hooks.

- :material-console: __Direnv (`--direnv`)__

    Scaffolds an `.envrc` file that automatically activates your virtual environment upon directory traversal and allows for non-tracked local variable overrides via `.envrc.local`.

!!! note "Design Decision: Configuration Portability"
    Even when using `--prek`, Protostar generates a `.pre-commit-config.yaml` file instead of `prek.toml`. Because `prek` fully supports the standard YAML configuration, this strategy ensures maximum ecosystem compatibility. Your repository remains decoupled from the specific hook engine, meaning CI/CD pipelines, IDE plugins (like Dependabot/Renovate), and collaborators using legacy `pre-commit` will still be able to run and update your hooks flawlessly.

</div>

---

## Available Tooling Modules

--8<-- "table_tooling.md"
