# 🌟 Protostar (v0.1.0)

[![CI](https://github.com/jacksonfergusondev/protostar/actions/workflows/ci.yml/badge.svg)](https://github.com/jacksonfergusondev/protostar/actions/workflows/ci.yml)
[![Release](https://github.com/jacksonfergusondev/protostar/actions/workflows/release.yml/badge.svg)](https://github.com/jacksonfergusondev/protostar/actions/workflows/release.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A modular CLI tool for quickly scaffolding software environments.**

Setting up a new project often requires the same manual steps: configuring linters, writing `.gitignore` files, setting up virtual environments, and linking IDEs. Protostar automates this boilerplate so you can skip the setup and get straight to writing code.

---

## 💡 Design Philosophy

While Protostar is a lightweight utility, it was built around two specific structural concepts:

### 1. Deterministic Execution

Most bootstrapping scripts run a sequence of shell commands and fail unpredictably if a dependency is missing. Protostar separates state definition from execution. It uses an internal `EnvironmentManifest` where modules (Python, Rust, Linux, etc.) append their requirements. Disk I/O and subprocesses only occur at the very end, ensuring the environment is generated safely without clobbering existing files.

### 2. Signal vs. Noise

Project configuration is necessary noise; writing logic is the signal. By vertically integrating the OS, IDE, and Language strata into a single command, Protostar attempts to reduce the logistical entropy of starting a new repository.

---

## 📦 Installation

### macOS (Homebrew)

If you are on macOS, you can install via Homebrew:

```bash
brew tap jacksonfergusondev/tap
brew install protostar
```

### Universal (uv)

For isolated CLI tool installation on any OS, `uv` is recommended:

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

### Basic Scaffolding

Navigate to your empty directory and specify the languages you are using. The OS and IDE configurations are automatically inferred from your system and global settings.

```bash
mkdir orbital-mechanics-sim
cd orbital-mechanics-sim
protostar --python --cpp
```

*Result: Initializes `uv`, scaffolds a Python environment, configures C++ build exclusions, and generates your `.vscode/settings.json`.*

### The Scientific Preset

If you are building a data analysis pipeline, use the scientific preset to pre-load a standard analytical stack.

```bash
protostar --python --scientific
```

*Result: Installs the Python scientific stack (`numpy`, `scipy`, `pandas`, `matplotlib`, `seaborn`, `ipykernel`) into the new environment.*

---

## 🛠 Command Reference

| Flag / Command | Description |
| :--- | :--- |
| `--python` | Scaffolds a Python environment using `uv`. Ignores caches and venvs. |
| `--rust` | Scaffolds a Rust environment using `cargo`. Ignores targets. |
| `--node` | Scaffolds a Node.js/TypeScript environment. Ignores `node_modules`. |
| `--cpp` | Configures a C/C++ footprint (ignores `build/`, `*.o`, `compile_commands.json`). |
| `--latex` | Configures a LaTeX footprint (ignores `*.aux`, `*.log`, `*.synctex.gz`). |
| `--scientific` | Injects foundational computational and statistical libraries (Python only). |

---

## ⚙️ Configuration

You can set global defaults in `~/.config/protostar/config.toml` so you don't have to specify your IDE or package manager preferences manually.

```toml
[env]
# Options: "vscode", "cursor", "jetbrains", "none"
ide = "vscode"

# Options: "npm", "pnpm", "yarn"
node_package_manager = "npm"
```

---

## 🤝 Collaboration & Extension

This tool uses a decoupled `BootstrapModule` architecture. Adding support for a new language or framework requires writing a single class that appends rules to the `EnvironmentManifest`. Feel free to open an issue or pull request if you'd like to see a specific toolchain supported.

## 📧 Contact

### Jackson Ferguson

- **GitHub:** [@JacksonFergusonDev](https://github.com/JacksonFergusonDev)
- **LinkedIn:** [Jackson Ferguson](https://www.linkedin.com/in/jackson--ferguson/)
- **Email:** <jackson.ferguson0@gmail.com>

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
