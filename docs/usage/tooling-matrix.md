# Tooling & Flags Matrix

Protostar provides a modular matrix of tooling modules and built-in templates. Tooling modules inject static analysis, testing frameworks, and continuous integration workflows, safely deep-merging configurations into existing project files like `pyproject.toml`.

<div class="spacer-2"></div>

<div class="grid cards" markdown>

- :material-check-all: __Pre-Commit (`--pre-commit`)__

    The orchestration engine that binds all linting and formatting hooks. Evaluates your workspace, initializes `.git` if absent, and automatically executes `pre-commit install`. When modules requiring additional Git lifecycle stages (such as Commitizen for `commit-msg`) are enabled, Protostar automatically declares `default_install_hook_types` (`pre-commit`, `commit-msg`) and `default_stages` (`pre-commit`) at the top of `.pre-commit-config.yaml` so standard `pre-commit install` commands wire all hook lifecycles out-of-the-box.

- :material-lightning-bolt: __Prek (`--prek`)__

    A dependency-free, extremely fast Rust alternative to `pre-commit`. Like `--pre-commit`, this initializes `.git` and installs your git hooks using the same portable `.pre-commit-config.yaml` configuration.

- :material-console: __Direnv (`--direnv`)__

    Scaffolds an `.envrc` file that automatically activates your virtual environment upon directory traversal and allows for non-tracked local variable overrides via `.envrc.local`.

</div>

!!! note "Design Decision: Configuration Portability"
    Even when using `--prek`, Protostar generates a `.pre-commit-config.yaml` file instead of `prek.toml`. Because `prek` fully supports the standard YAML configuration, this strategy ensures maximum ecosystem compatibility. Your repository remains decoupled from the specific hook engine, meaning CI/CD pipelines, IDE plugins (like Dependabot/Renovate), and collaborators using legacy `pre-commit` will still be able to run and update your hooks flawlessly.

---

## Available Tooling Modules

--8<-- "table_tooling.md"

---

## Built-in Templates

Built-in templates act as high-level macros that execute on top of a base language footprint. They dynamically inject structural scaffolding, directories, and domain-specific dependencies into the environment manifest.

!!! tip "Dynamic Resolution"
    Templates do not hardcode package versions. They pass the library requirements directly to the package manager (`uv`), allowing your environment to resolve the latest compatible telemetry, astrophysics, or API packages at runtime.

--8<-- "table_templates.md"
