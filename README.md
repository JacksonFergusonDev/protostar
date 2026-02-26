# 🌟 Protostar (v0.1.0)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Uses Rich](https://img.shields.io/badge/uses-rich-0A0A0A?logo=rich&logoColor=white)](https://github.com/Textualize/rich)

**High-velocity, deterministic environment scaffolding.**

> **Starting a new project often introduces immediate logistical entropy: configuring linters, generating ignores, setting up virtual environments, and linking IDEs. This is pure noise.**
>
> **Protostar is an accretion engine for software environments. It vertically integrates your OS, IDE, and Language toolchains into a strict dependency graph, allowing you to instantly extract the Signal (writing code) from the Noise (configuration).**

---

## ⚙️ Engineering Philosophy: Deterministic Scaffolding

This system is designed to apply the rigor of physical supply chains and scientific modeling to software initialization. It guarantees that environments are generated safely, without destructive disk I/O or race conditions.

### 1. Additive Manifestation (The State Engine)

Most bootstrapping scripts aggressively run shell commands in sequence, failing unpredictably if a dependency is missing.

- **The Invariant:** Disk I/O must only occur when the entire desired state is known and validated.
- **The Implementation:** Protostar uses an `EnvironmentManifest`. Modules (Python, Rust, VS Code, Linux) do not execute commands; they *append* their requirements to this central state object. Only when the manifest is fully resolved does the orchestrator execute the system tasks.

### 2. Vertical Integration

Environments are not flat; they are stacked.

- **The Mechanism:** Protostar separates concerns into three distinct strata: **OS Layer** (handling `.DS_Store` or `*~`), **Language Layer** (handling compilers and package managers like `uv` or `cargo`), and **IDE Layer** (handling workspace exclusions like `.vscode/settings.json`).
- **The Topology:** These layers stack seamlessly. You can combine multiple languages without their configuration files colliding.

### 3. Entropy Reduction (Scientific Presets)

Setting up a data analysis pipeline requires a predictable, immutable stack. Protostar features dependency presets (e.g., `--scientific`) that automatically inject a locked matrix of analytical tools (`numpy`, `pandas`, `scipy`, `matplotlib`) so you can begin statistical modeling immediately.

---

## ⚡ Features

- **Zero-Friction Ignition:** Spin up a fully configured workspace in seconds using ultra-fast package managers like `uv`.
- **Modular Ecosystem:** Natively supports Python, Rust, Node.js (npm/pnpm/yarn), C/C++, and LaTeX.
- **IDE Awareness:** Automatically generates workspace settings for VS Code/Cursor and handles indexing exclusions for JetBrains IDEs.
- **Non-Destructive:** Safely deep-merges JSON configurations (like `settings.json`) and deduplicates `.gitignore` entries without clobbering your existing work.
- **Rich Observability:** Swallows the noisy `stdout` of underlying package managers, presenting a clean, deterministic UI with clear success/failure states.

---

## 📦 Installation

### macOS (Homebrew)

Install via Homebrew alongside Git Pulsar.

```bash
brew tap jacksonfergusondev/tap
brew install protostar
```

### Linux / Generic

Install via `uv` (recommended for isolated CLI tools).

```bash
uv tool install protostar
```

---

## 🚀 The Protostar Workflow

Protostar is designed to be executed the moment you `mkdir` a new project.

### 1. The Standard Ignition

Navigate to your empty project directory and declare your languages. The OS and IDE layers are automatically inferred from your system and global config.

```bash
mkdir orbital-mechanics-sim
cd orbital-mechanics-sim
protostar --python --cpp
```

*Protostar will initialize `uv`, scaffold a Python environment, configure C++ build exclusions, and generate your `.vscode/settings.json`.*

### 2. The Scientific Preset

Need to jump straight into data analysis or signal processing? Use the scientific preset to pre-load the analytical stack.

```bash
protostar --python --scientific
```

*Installs the Python scientific stack (`numpy`, `scipy`, `pandas`, `matplotlib`, `seaborn`, `ipykernel`) instantly.*

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

Set your global defaults so you never have to specify your IDE or package manager manually.

### `~/.config/protostar/config.toml`

```toml
[env]
# Options: "vscode", "cursor", "jetbrains", "none"
ide = "vscode"

# Options: "npm", "pnpm", "yarn"
node_package_manager = "npm"
```

---

## 🤝 Collaboration & Extension

This tool is built on a highly decoupled `BootstrapModule` architecture. Adding a new language or framework is as simple as creating a new module class that appends to the `EnvironmentManifest`.

See the source code for examples on how to write custom integration layers.

## 📄 License

MIT © [Jackson Ferguson](https://github.com/jacksonfergusondev)
