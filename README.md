# Protostar (v0.3.0)

[![CI](https://github.com/jacksonfergusondev/protostar/actions/workflows/ci.yml/badge.svg)](https://github.com/jacksonfergusondev/protostar/actions/workflows/ci.yml)
[![Release](https://github.com/jacksonfergusondev/protostar/actions/workflows/release.yml/badge.svg)](https://github.com/jacksonfergusondev/protostar/actions/workflows/release.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A modular CLI tool for high-velocity environment scaffolding.**

Setting up a new project often requires the same manual steps: configuring linters, writing `.gitignore` and `.dockerignore` files, setting up virtual environments, and linking IDEs. Protostar automates this boilerplate so you can skip the setup and get straight to writing code.

---

## 💡 Design Philosophy

Protostar is built to save you time and stay out of your way. It adheres to a strict separation of concerns to avoid generating bloated artifacts you'll inevitably just delete manually:

1. **`init` vs. `generate`:** The `protostar init` command is designed to be run exactly *once* at the inception of a repository to lay the foundational architecture. The `protostar generate` command provides discrete, repeatable scaffolding for files you create regularly (like C++ classes or LaTeX reports).
1. **Manifest-First, Side-Effects-Last:** Many bootstrapping scripts run a sequence of shell commands and fail unpredictably midway through. Protostar separates state definition from execution. Modules declare their requirements into a centralized `EnvironmentManifest`. Disk I/O and subprocesses only execute in a single, deterministic phase at the very end.
1. **Fail Loud, Fail Early:** Pre-flight checks ensure all system dependencies (like `uv`, `cargo`, or `direnv`) are present before any state is mutated. If a check fails, the environment remains completely untouched.
1. **Non-Destructive by Default:** Protostar never blindly overwrites your existing work. It dynamically appends to `.gitignore` files, intelligently merges IDE JSON configurations, late-binds to generated `pyproject.toml` configurations, and safely aborts if generated files already exist.

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

---

## 🚀 Usage

Protostar is designed to be run right after you `mkdir` a new project.

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

*Result: Installs the Python core environment alongside astrophysics dependencies (`astropy`, `sunpy`, `gwpy`), scaffolds `data/catalogs` and `data/fits`, generates optimized `.gitignore` and `.dockerignore` files, automatically scaffolds and evaluates a `.envrc` file, injects a pragmatic `.markdownlint.yaml` ruleset, resolves `mypy` and `pytest` dev dependencies, and generates a modular `.pre-commit-config.yaml` that auto-installs and updates git hooks tailored exactly to the tools you enabled.*

### File Generation

For repetitive boilerplate, use the `generate` subcommand.

```bash
protostar generate cpp-class TelemetryIngestor
```

*Result: Safely drops a `TelemetryIngestor.hpp` and `TelemetryIngestor.cpp` into your working directory with standard guards and constructors.*

---

## 🛠 Command Reference

### Global Flags

| Flag | Description |
| :--- | :--- |
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
| **Preset** | `--dsp`, `-d` | Injects digital signal processing, waveform, and MIDI analysis tools. |
| **Preset** | `--embedded`, `-e` | Injects host-side embedded hardware interface tools (e.g., `pyserial`). |
| **Tooling** | `--ruff` | Scaffolds Ruff linter and formatter alongside `pyproject.toml` baseline config. |
| **Tooling** | `--mypy` | Scaffolds Mypy static type checker alongside `pyproject.toml` baseline config. |
| **Tooling** | `--pytest` | Scaffolds Pytest testing framework alongside `pyproject.toml` baseline config. |
| **Tooling** | `--pre-commit` | Scaffolds and installs a modular `.pre-commit-config.yaml` based on active languages. |
| **Context** | `--docker` | Generates a highly optimized `.dockerignore` based on the environment footprint. |
| **Context** | `--direnv` | Scaffolds a `.envrc` and evaluates the virtual environment shell hook automatically. |
| **Context** | `--markdownlint`, `-m` | Scaffolds a relaxed `.markdownlint.yaml` configuration. |

### `protostar generate`

| Target | Example | Description |
| :--- | :--- | :--- |
| `tex` | `proto generate tex report` | Generates a boilerplate LaTeX file based on your global config preset. |
| `cpp-class` | `proto generate cpp-class Engine` | Generates a `.hpp` and `.cpp` pair with standard boilerplate. |
| `cmake` | `proto generate cmake` | Generates a `CMakeLists.txt` statically linking local C++ source files. |
| `pio` | `proto generate pio esp32dev` | Generates a `platformio.ini` environment configuration. |
| `circuitpython` | `proto generate circuitpython` | Generates a `code.py` non-blocking state machine and LSP configuration. |

---

## ⚙️ Configuration

You can set global defaults by running `protostar config`, which opens `~/.config/protostar/config.toml` in your system's `$EDITOR`.

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
# no-ruff = true  # Disables the default Ruff scaffolding
# mypy = true
# pytest = true
# pre_commit = true

[presets]
# Generator presets for scaffolding boilerplate
latex = "minimal"
```

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
