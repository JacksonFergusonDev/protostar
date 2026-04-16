# Environment Tooling

Tooling modules handle the injection of static analysis, testing frameworks, and continuous integration hooks. They safely deep-merge their configurations into existing host files like `pyproject.toml`.

<div class="grid cards" markdown>

- :material-check-all: __Pre-Commit (`--pre-commit`)__

    The orchestration engine that binds all linting and formatting hooks. Evaluates your workspace, initializes `.git` if absent, and automatically executes `pre-commit install`.

- :material-console: __Direnv (`--direnv`)__

    Scaffolds an `.envrc` file that automatically activates your virtual environment upon directory traversal and allows for non-tracked local variable overrides via `.envrc.local`.

</div>

---

## Available Tooling Modules

--8<-- "table_tooling.md"
