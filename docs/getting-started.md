## Prerequisites

- **Python 3.12+**
- **Git** (Required for VCS ignore scaffolding)
- **uv** (Highly recommended for sub-second dependency resolution, though `pip` is supported as a fallback)

## Installation

Protostar is designed to be installed globally as a standalone CLI tool, with native cross-platform support for Linux, macOS, and Windows.

=== "macOS (Homebrew)"
    ```bash
    brew install jacksonfergusondev/tap/protostar
    ```
=== "Universal (uv)"
    ```bash
    uv tool install protostar
    ```
=== "Universal (pip)"
    ```bash
    pip install protostar
    ```

!!! warning "Dependency Isolation (ignore if using `brew` or `uv`)"
    If you install Protostar into an existing Python environment with `pip`, it will bring in `questionary` and `prompt_toolkit` for the interactive TUI wizard. In rare cases, this can conflict with other tools that strictly pin `prompt_toolkit` versions (e.g., specific IPython or Jupyter stacks). For guaranteed isolation, prefer `uv tool` or Homebrew.

`protostar init` is designed to be executed immediately after you `mkdir` a new project directory. It offers two distinct operational modes: an **interactive TUI** for discovery, and a **headless CLI** for speed.

## The Interactive Wizard

If you run `protostar init` without any arguments, it will launch an interactive Terminal User Interface (TUI). This wizard allows you to visually map out your languages, tools, and built-in templates using the spacebar—no CLI flag memorization required.

```bash
mkdir orbital-mechanics-sim
cd orbital-mechanics-sim
protostar init
```

<div class="protostar-asciinema" data-asciinema="../assets/demo_wizard.cast"></div>

## Headless Scaffolding

For rapid, repeatable initialization, you can bypass the TUI entirely by providing your desired environment matrix as CLI flags. Universal system workspace hygiene is automatically applied, and IDE settings are conditionally injected based on your global configuration and chosen language footprints.

```bash
mkdir hyperdrive-cli
cd hyperdrive-cli
protostar init --template cli
```

**What just happened?**
In a fraction of a second, Protostar:

- **Scaffolded Application & Test Suites**: Created a modular package architecture with an executable Typer and Rich CLI application (`src/hyperdrive_cli/cli.py`, `__init__.py`) alongside a unit test suite (`tests/test_cli.py`).
- **Resolved Dependencies & Registered Entrypoints**: Injected runtime dependencies (`rich`, `typer`), wired the console script entrypoint in `pyproject.toml` (`[project.scripts]`), and populated development dependency groups.
- **Configured Static Analysis & Testing ASTs**: Generated strictly typed `[tool.mypy]` rules, configured `[tool.ruff]` linting and formatting opinions, and wired coverage-backed `[tool.pytest.ini_options]`.
- **Wired Automation & Pre-Commit Git Hooks**: Initialized `.pre-commit-config.yaml` with local toolchain hooks, configured Commitizen conventional commit checks (`CHANGELOG.md`), and scaffolded task automation in `justfile`.
- **Provisioned CI/CD & Documentation**: Scaffolded GitHub Actions workflows (`.github/workflows/ci.yml`, `release.yml`, `codecov.yml`, `renovate.json`) alongside a ready-to-publish Zensical documentation site (`mkdocs.yml`, `docs/index.md`, `.readthedocs.yaml`).
- **Applied Universal Workspace Hygiene**: Evaluated the virtual environment via `.envrc` (direnv), locked dependencies with `uv.lock`, injected `.markdownlint-cli2.yaml`, and safely deduplicated `.gitignore` without overwriting existing entries.

<div class="protostar-asciinema" data-asciinema="../assets/demo_headless.cast"></div>

## Exploration & Help

Protostar is self-documenting. You can view the full capabilities matrix and subcommand details directly from your terminal at any time.

![Protostar Help](./fixtures/cli_help.svg)

!!! tip "Command-Specific Help"
    You can also get localized help for specific subcommands by running:
    ```bash
    protostar help init
    ```

## Shell Autocomplete & Aliasing

To speed up your workflow, you can enable CLI autocompletion and set up a shorter alias.

### 1. Enable Autocomplete

Protostar uses `argcomplete` for dynamic tab-completion. Install the CLI bindings globally matching the toolchain you used to install Protostar:

=== "macOS (Homebrew)"
    ```bash
    brew install argcomplete
    ```
=== "Universal (uv)"
    ```bash
    uv tool install argcomplete
    ```
=== "Universal (pip)"
    ```bash
    pip install argcomplete
    ```

!!! warning "Path Resolution for `uv`"
    If using `uv`, ensure `~/.local/bin` is exported in your system `$PATH` so your shell can resolve the `register-python-argcomplete` executable.

=== "Zsh"
    Ensure the bash compatibility layer is loaded by adding this to your `~/.zshrc`:

    ```bash
    autoload -U bashcompinit
    bashcompinit
    eval "$(register-python-argcomplete protostar)"
    ```

=== "Bash"
    Add the evaluation string directly to your `~/.bashrc`:

    ```bash
    eval "$(register-python-argcomplete protostar)"
    ```

### 2. Set an Alias (Optional)

Because `proto` is a common namespace, Protostar does not commandeer it by default. If you want the keystroke savings, map it manually in your `~/.zshrc` or `~/.bashrc`:

```bash
alias proto="protostar"
```

## Next Steps

With your accretion disk stabilized, you can dive deeper into Protostar's mechanics:

- **[Configuration](./usage/configuration.md):** Learn how to set up global defaults (like your preferred Python version, dev dependencies, or custom ruff configuration) so you don't have to specify them every time.
- **[Tooling & Flags Matrix](./usage/tooling-matrix.md):** Explore the full list of supported languages, tools, and built-in templates.
- **[Architecture](./mechanics/orchestrator.md):** Read how the Orchestrator guarantees idempotent disk operations without corrupting your existing files.
