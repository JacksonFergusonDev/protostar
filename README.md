# Protostar (v0.5.0)

[![CI](https://github.com/jacksonfergusondev/protostar/actions/workflows/ci.yml/badge.svg)](https://github.com/jacksonfergusondev/protostar/actions/workflows/ci.yml)
[![Release](https://github.com/jacksonfergusondev/protostar/actions/workflows/release.yml/badge.svg)](https://github.com/jacksonfergusondev/protostar/actions/workflows/release.yml)
[![codecov](https://codecov.io/gh/JacksonFergusonDev/protostar/graph/badge.svg?token=VIR3EZDXRN)](https://codecov.io/gh/JacksonFergusonDev/protostar)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A modular CLI tool for high-velocity environment scaffolding.**

Setting up a new project often requires the same manual steps: configuring linters, writing `.gitignore` and `.dockerignore` files, setting up virtual environments, and linking IDEs. Protostar automates this boilerplate so you can skip the setup and get straight to writing code.

---

## 💡 Design Philosophy

Protostar is built to save you time and stay out of your way. It adheres to a strict separation of concerns to avoid generating bloated artifacts you'll inevitably just delete manually:

1. **`init` vs. `generate`:** The `protostar init` command is designed to be run exactly *once* at the inception of a repository to lay the foundational architecture. The `protostar generate` command provides discrete, repeatable scaffolding for files you create regularly (like C++ classes or LaTeX reports).
1. **Manifest-First, Side-Effects-Last:** Many bootstrapping scripts run a sequence of shell commands and fail unpredictably midway through. Protostar separates state definition from execution. Modules declare their requirements into a centralized `EnvironmentManifest`. Disk I/O and subprocesses only execute in a single, deterministic phase at the very end.
1. **Fail Loud, Fail Early:** Pre-flight checks ensure all system dependencies (like `uv`, `git`, `cargo`, or `direnv`) are present before any state is mutated. If a check fails, the environment remains completely untouched.
1. **Non-Destructive by Default:** Protostar never blindly overwrites your existing work. It dynamically appends to `.gitignore` files, intelligently merges IDE JSON configurations, uses deterministic AST modification to deep-merge TOML configurations, and safely aborts if generated files already exist.
1. **Actionable Telemetry:** When things break, Protostar bubbles up the exact `stderr` so you know immediately if a network request or dependency resolution failed. For unexpected internal crashes, it automatically generates a URL-encoded GitHub issue containing your system environment vector to eliminate debugging entropy.

---

## ⚡️ Performance & Latency Isolation

Protostar is built to be lightweight, so Python's startup overhead never slows down your local development. We measure initialization latency using two benchmarking approaches:

1. **Fast-Path Execution:** Measures the latency of non-interactive commands (e.g., `protostar help init`). This validates the efficiency of our `argparse` configuration and dynamic module resolution. Tested locally on a MacBook Air M3, this path executes in **83.7 ms ± 8.5 ms**.

1. **TUI-Path Execution:** Measures the overhead of triggering the interactive `questionary` wizards. This ensures that even when heavy TUI dependencies are dynamically imported, the "time-to-first-prompt" remains imperceptible. Tested locally on a MacBook Air M3, this path executes in **83.7 ms ± 8.5 ms**.

Our CI pipeline enforces a strict performance budget using `hyperfine`, gating any PR that introduces significant regressions in either path. We maintain historical tracking to ensure long-term architectural stability rather than chasing absolute CI metrics (which are subject to heavy VM variance).

- **View CI Trends:** [Performance Dashboard](https://jacksonfergusondev.github.io/protostar/)

---

## 📦 Installation

### macOS (Homebrew)

If you are on macOS, you can install via Homebrew:

```bash
brew tap jacksonfergusondev/tap
brew install protostar
```

### Universal (uv)

For isolated CLI tool installation on any OS, `uv` is highly recommended:

```bash
uv tool install protostar
```

### Universal (pip)

You can also install it into your active environment using standard pip:

```bash
pip install protostar
```

> **Note:** If you install Protostar into an existing Python environment with `pip`, it will bring in `questionary` and `prompt_toolkit` for the interactive wizard. In rare cases, this can conflict with other tools that strictly pin `prompt_toolkit` versions (e.g., some IPython/Jupyter stacks). For the smoothest experience and guaranteed isolation, prefer `uv tool install protostar` or Homebrew.

---

## 🚀 Usage

Protostar is designed to be run right after you `mkdir` a new project.

### Interactive Wizard

If you run `protostar` without any arguments, it will launch an interactive Terminal User Interface (TUI). This wizard allows you to visually select your languages, tools, and presets using the spacebar without needing to memorize CLI flags.

```bash
protostar
```

You can also bypass the discovery menu and jump directly into the specific wizards by running `protostar init` or `protostar generate` with no additional flags.

### Basic Environment Initialization

Navigate to your empty directory and specify the languages you are using. The OS and IDE configurations are automatically inferred from your system and global settings.

```bash
mkdir orbital-mechanics-sim
cd orbital-mechanics-sim
protostar init --python --cpp
```

*Result: Initializes `uv` (or `pip`), scaffolds a Python environment, configures C++ build exclusions, and generates your `.vscode/settings.json`.*

### Domain-Specific Presets & Contexts

If you are building a specific type of pipeline, use presets to pre-load standard tools and directory structures without tying yourself to a rigid template. You can also automate context boundaries like Docker, virtual environment activation, and dev tooling.

```bash
protostar init --python --astro --docker --direnv -m --mypy --pytest --pre-commit
```

*Result: Installs the Python core environment alongside astrophysics dependencies (`astropy`, `photutils`, `specutils`), scaffolds `data/catalogs` and `data/fits`, generates optimized `.gitignore` and `.dockerignore` files, automatically scaffolds and evaluates a `.envrc` file, injects a pragmatic `.markdownlint.yaml` ruleset, resolves `mypy` and `pytest` dev dependencies, and generates a modular `.pre-commit-config.yaml` that auto-installs and updates git hooks tailored exactly to the tools you enabled.*

### File Generation

For repetitive boilerplate, use the `generate` subcommand.

```bash
protostar generate cpp-class TelemetryIngestor
```

*Result: Safely drops a `TelemetryIngestor.hpp` and `TelemetryIngestor.cpp` into your working directory with standard guards and constructors.*

---

## ⚡️ Shell Autocomplete & Aliasing

To speed up your workflow, you can enable CLI autocompletion and set up a shorter alias.

### 1. Enable Autocomplete

Protostar uses `argcomplete` for dynamic tab-completion. Install the CLI bindings globally:

```bash
uv tool install argcomplete
# Or using pip: pip install argcomplete
```

> **Note:** If using `uv`, ensure `~/.local/bin` is exported in your system `$PATH` so your shell can resolve the `register-python-argcomplete` executable.

**For Zsh:**
Ensure the bash compatibility layer is loaded by adding this to your `~/.zshrc`:

```bash
autoload -U bashcompinit
bashcompinit
eval "$(register-python-argcomplete protostar)"
```

**For Bash:**
Add the evaluation string directly to your `~/.bashrc`:

```bash
eval "$(register-python-argcomplete protostar)"
```

### 2. Set an Alias (Optional)

Because `proto` is a common namespace (often used by Protocol Buffers), Protostar does not commandeer it by default. If you want the keystroke savings, map it manually in your `~/.zshrc` or `~/.bashrc`:

```bash
alias proto="protostar"
```

---

## 🛠 Command Reference

### Global Flags

| Flag | Description |
| :--- | :--- |
| `--version` | Show the application's version footprint and exit. |
| `--verbose`, `-v` | Enables verbose debug output and rich tracebacks. |

### `protostar init`

| Category | Flag | Description |
| :--- | :--- | :--- |
| **Language** | `--python`, `-p` | Scaffolds a Python environment (`uv` or `pip`). Ignores caches and venvs. |
| **Language** | `--python-version` | Specify the Python version to scaffold (e.g., `3.12`). Overrides global configuration. |
| **Language** | `--rust`, `-r` | Scaffolds a Rust environment using `cargo`. Ignores target directories. |
| **Language** | `--node`, `-n` | Scaffolds a Node.js/TS environment. Ignores `node_modules` and `dist/`. |
| **Language** | `--cpp`, `-c` | Configures a C/C++ footprint (ignores `build/`, `*.o`, `compile_commands.json`). |
| **Language** | `--latex`, `-l` | Configures a LaTeX footprint (ignores `*.aux`, `*.log`, `*.synctex.gz`). |
| **Preset** | `--scientific`, `-s` | Injects foundational computational and statistical libraries. |
| **Preset** | `--astro`, `-a` | Injects astrophysics and observational data dependencies. |
| **Preset** | `--ml` | Injects machine learning and deep learning dependencies. |
| **Preset** | `--api` | Injects REST API backend dependencies. |
| **Preset** | `--cli` | Injects CLI application dependencies. |
| **Preset** | `--dsp`, `-d` | Injects digital signal processing, waveform, and MIDI analysis tools. |
| **Preset** | `--embedded`, `-e` | Injects host-side embedded hardware interface tools (e.g., `pyserial`). |
| **Tooling** | `--ruff` | Scaffolds Ruff linter and formatter alongside `pyproject.toml` baseline config. |
| **Tooling** | `--mypy` | Scaffolds Mypy static type checker alongside `pyproject.toml` baseline config. |
| **Tooling** | `--pytest` | Scaffolds Pytest testing framework alongside `pyproject.toml` baseline config. |
| **Tooling** | `--pre-commit` | Scaffolds and installs a modular `.pre-commit-config.yaml` based on active languages. |
| **Context** | `--docker` | Generates a highly optimized `.dockerignore` based on the environment footprint. |
| **Context** | `--direnv` | Scaffolds a `.envrc` and evaluates the virtual environment shell hook automatically. |
| **Context** | `--markdownlint`, `-m` | Scaffolds a relaxed `.markdownlint.yaml` configuration. |
| **Context** | `--force`, `-f` | Bypasses interactive prompts and forces a merge on file collisions. |

### `protostar generate`

| Target | Example | Description |
| :--- | :--- | :--- |
| `tex` | `protostar generate tex report` | Generates a boilerplate LaTeX file based on your global config preset. |
| `cpp-class` | `protostar generate cpp-class Engine` | Generates a `.hpp` and `.cpp` pair with standard boilerplate. |
| `cmake` | `protostar generate cmake` | Generates a `CMakeLists.txt` statically linking local C++ source files. |
| `pio` | `protostar generate pio esp32dev` | Generates a `platformio.ini` environment configuration. |
| `circuitpython` | `protostar generate circuitpython` | Generates a `code.py` non-blocking state machine and LSP configuration. |

---

## ⚙️ Configuration

Protostar enforces a strict architectural boundary between global initialization and local repository generation to prevent configuration drift.

### Global Configuration (`init` & Defaults)

Run `protostar config` to open your global configuration file (`~/.config/protostar/config.toml`) in your system's default `$EDITOR`. This file acts as the singular source of truth for environment initialization (`protostar init`), dictating base environment toggles, developer tools, and domain-specific scaffolding.

```toml
[env]
# Preferred IDE: "vscode", "cursor", "jetbrains", "none"
ide = "vscode"

# Auto-scaffold direnv with python environments
direnv = false

# Preferred Python package manager: "uv", "pip"
python_package_manager = "uv"

# Optional default Python version (e.g., "3.12")
# python_version = "3.12"

# Preferred Node.js package manager: "npm", "pnpm", "yarn"
node_package_manager = "npm"

# Optional dev tool toggles for Python
# markdownlint = true
# no-ruff = true  # Disables the default Ruff scaffolding
# mypy = true
# pytest = true
# pre_commit = true

[presets]
# Generator presets for scaffolding boilerplate
latex = "minimal"

# --- Advanced Configuration Overrides ---
# Protostar allows you to customize the dependencies and directory structures
# for specific pipelines, or inject tooling across all initialized environments.

# [presets.astro]
# dependencies = ["astropy", "astroquery", "photutils", "specutils"]
# dev_dependencies = ["pytest-benchmark"]
# directories = ["data/catalogs", "data/fits", "data/raw"]

# [dev]
# extra_dependencies = ["bump-my-version"]

# [dev.pyproject]
# custom_ruff = '''
# [tool.ruff.lint]
# select = ["E", "F", "I", "B", "UP", "SIM", "T20", "PT", "C4", "D"]
# ignore = ["E501", "D100", "D104", "D107"]
# '''
```

### Local Configuration (`generate`)

For repository-specific boilerplate generation, you can create a `.protostar.toml` file in your project root. **This file is strictly reserved for `protostar generate` targets.** Any global initialization blocks (`[env]`, `[presets]`, `[dev]`) placed in this file will be actively ignored by the orchestrator to guarantee idempotent scaffolding.

---

## 🤝 Collaboration

This tool uses a highly decoupled, plugin-style architecture. The CLI parser dynamically evaluates module registries at runtime.

- **To add support for a new language:** Subclass `BootstrapModule`.
- **To add a new dependency pipeline:** Subclass `PresetModule`.

Both independently append rules to the `EnvironmentManifest` without requiring modifications to the core orchestration engine. Modules are strictly isolated and interact only via the manifest interface.

We maintain strict engineering standards to ensure reliability:

- **Static Typing:** 100% type-hinted, strictly enforced via `mypy`.
- **Isolated Testing:** `pytest` test suite utilizing `tmp_path` for disk I/O sandboxing and `pytest-mock` to prevent host-machine side effects.
- **Formatting & Linting:** Automated via `ruff` in our pre-commit hooks and CI pipelines.

Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for full details on our development setup, architectural rules, and pull request guidelines. Feel free to open an issue or PR if you'd like to see a specific toolchain supported.

## 📧 Contact

### Jackson Ferguson

- **GitHub:** [@JacksonFergusonDev](https://github.com/JacksonFergusonDev)
- **LinkedIn:** [Jackson Ferguson](https://www.linkedin.com/in/jackson--ferguson/)
- **Email:** <jackson.ferguson0@gmail.com>

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
