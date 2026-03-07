# Contributing To Protostar

## Architecture & Implementation Rules

Protostar has one job: save the user time on setup they would have done anyway. When evaluating a new feature, ask:

- Would *most* users want this, or just some?
- Would a user plausibly revert this manually after running the tool?
- Does this belong in `init` (run once) or `generate` (run repeatedly)?

If the answer to either of the first two is "maybe not", the feature probably doesn't belong in the tool.

### 1. Manifest-first, side-effects-last

Modules declare intent into the manifest during `build()`. The orchestrator executes all side effects afterward in a single, ordered phase. Never call `subprocess.run` or write to disk inside a module's `build()` method.

### 2. Fail loud, fail early

All system dependency checks happen in `pre_flight()`, before the manifest is built and before anything is written. If a preflight check fails, the environment is untouched. This is a guarantee, not a coincidence.

### 3. Non-destructive by default

Protostar never overwrites existing work. `.gitignore` entries are appended and deduplicated. IDE settings are merged. It must be safe to run against a repo that is already partially configured.

### 4. Modules are composable, not coupled

A module only interacts with the manifest interface. It must not inspect what other modules are loaded, assume a particular run order, or conditionally change behaviour based on the presence of sibling modules.

### 5. Presets are Independent Pipeline Injections

Presets inherit from the `PresetModule` abstract base class and evaluate independently during the manifest aggregation phase. They do not override language modules; they strictly append domain-specific dependencies and directory scaffolding to the `EnvironmentManifest`.

### 6. Configuration Scope Boundaries

To prevent configuration drift and unexpected mutations, Protostar enforces a strict boundary between global and local configuration states:

- **Global Configuration (`~/.config/protostar/config.toml`):** The singular source of truth for repository initialization (`protostar init`). This file dictates base environment toggles (`[env]`), global developer tools (`[dev]`), and domain-specific scaffolding (`[presets]`).

- **Local Configuration (`.protostar.toml`):** Strictly reserved for configuring discrete file generation (`protostar generate`) specific to the active repository (e.g., custom C++ namespace targets or LaTeX macro overrides).

**Rule:** The orchestrator will actively strip and ignore any `init`-specific blocks found in a local `.protostar.toml` file to guarantee idempotent scaffolding.

## Coding Standards

1. **Type Hinting:** All new application functions and methods must include strict Python 3.12 type hints. We use `mypy` to statically enforce this (`disallow_untyped_defs = true`). The test suite (`tests/*`) is granted an exemption from strict untyped definition checks.

1. **Docstrings:** Use Google-style docstrings for public functions, classes, and methods. Module-level, package-level, and `__init__` docstrings are exempt from linting checks.

1. **Formatting & Linting:** Code is formatted and linted using `ruff`.
    - Use 4-space indentation and double quotes.
    - The formatter enforces an 88-character line length.
    - Do not bypass the pre-commit hooks, as they will automatically apply the required `isort` block ordering and formatting rules.

## Testing Guidelines

Because Protostar is a scaffolding tool, its execution inherently interacts with the host filesystem and shell. To maintain a deterministic and isolated test suite:

1. **Relaxed Linting:** The test suite (`tests/*`) is exempt from docstring requirements and `print` statement linting restrictions (`T201`).

1. **Disk I/O:** Never write to the actual host filesystem during tests. Always use the `pytest` `tmp_path` fixture to sandbox generated artifacts.

1. **Subprocesses:** Use `pytest-mock` to patch `subprocess.run`. Do not allow the test suite to execute unmocked shell commands (e.g., `uv init` or `cargo init`) on the host machine.

1. **Coverage:** Ensure new modules or generators maintain or improve the current test coverage metrics (measured via `pytest-cov`).

## How to Contribute

### Reporting Bugs

1. Check if the issue has already been reported.
1. Open a new issue with a clear title and description.
1. Include the command that caused the error and the resulting traceback.

### Development Setup

This project uses [uv](https://github.com/astral-sh/uv) for dependency management and requires Python 3.12+.

1. **Fork & Clone**
    Fork the repo and clone it locally:

    ```bash
    git clone https://github.com/yourusername/protostar.git
    cd protostar
    ```

1. **Environment Setup**
    We use `uv` to manage the virtual environment and dependencies. Running sync will install the core application alongside the `dev` dependency group (which includes `build`, `bump-my-version`, `mypy`, `pre-commit`, `pytest`, `pytest-cov`, `pytest-mock`, and `ruff`).

    ```bash
    uv sync
    ```

1. **Install Hooks**
    Set up pre-commit hooks to handle linting and type checking automatically.

    ```bash
    pre-commit install
    ```

### Running Tests

We use `pytest` for the test suite.

```bash
uv run pytest
```

### Pull Requests

1. **Create a Branch**

    ```bash
    git checkout -b feature/my-amazing-feature
    ```

1. **Make Changes**
    Write your code. Ensure your changes are tightly scoped to a single feature, preset, or bug fix. Avoid monolithic pull requests that mix refactoring with new logic.

1. **Verify**
    Ensure your code passes the linter and tests locally.

    ```bash
    uv run pytest
    ```

    (Pre-commit will also run `ruff` and `mypy` when you commit).

1. **Commit & Push**
    Use clear, descriptive commit messages.

    ```bash
    git commit -m "feat: add support for Go"
    git push origin feature/my-amazing-feature
    ```

1. **Open a Pull Request**
    Submit your PR against the `main` branch.
