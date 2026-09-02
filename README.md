<!-- markdownlint-disable-file MD041 -->
<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/readme-light.svg">
  <img alt="Protostar Logo"
       src="docs/assets/readme-light.svg"
       width="480"
       style="max-width:100%; height:auto;">
</picture>

<br>

**A modular CLI that sets up complete Python projects in seconds.**

[![PyPI Version](https://img.shields.io/pypi/v/protostar?color=22d3ee&labelColor=0A0A0A&logo=pypi&logoColor=white)](https://pypi.org/project/protostar/)
[![CI](https://img.shields.io/github/actions/workflow/status/jacksonfergusondev/protostar/ci.yml?color=22d3ee&labelColor=0A0A0A&label=CI)](https://github.com/jacksonfergusondev/protostar/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/actions/workflow/status/jacksonfergusondev/protostar/release.yml?color=22d3ee&labelColor=0A0A0A&label=release)](https://github.com/jacksonfergusondev/protostar/actions/workflows/release.yml)
[![Codecov](https://img.shields.io/codecov/c/github/JacksonFergusonDev/protostar?color=22d3ee&labelColor=0A0A0A&logo=codecov&logoColor=white)](https://codecov.io/gh/JacksonFergusonDev/protostar)
[![Python](https://img.shields.io/badge/python-3.12+-22d3ee?labelColor=0A0A0A&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Documentation](https://img.shields.io/badge/docs-ReadTheDocs-22d3ee?labelColor=0A0A0A&logo=readthedocs&logoColor=white)](https://protostar.readthedocs.io/en/stable/)
[![License](https://img.shields.io/badge/license-MIT-22d3ee?labelColor=0A0A0A)](LICENSE)

</div>

Setting up a new python project often requires the same manual steps: configuring linters, writing `Dockerfile`, `.gitignore` and `.dockerignore` files, setting up virtual environments, and linking IDEs. **Protostar** automates this boilerplate so you can skip the setup and get straight to writing code.

---

<div align="center">
<picture>
  <img alt="Protostar demo"
       src="docs/assets/demo_headless.gif"
       width="900"
       style="max-width:100%; height:auto;">
</picture>
</div>

---

## 🆚 Why Protostar? (vs. Copier/Cookiecutter)

While general-purpose template engines like **Copier** and **Cookiecutter** are incredibly powerful for cross-language scaffolding, they treat configuration files as raw text templates. Protostar is deeply specialized for the modern Python ecosystem:

- **Semantic AST Merging:** Instead of brittle string templates (`{{ dependencies }}`), Protostar natively parses and merges `pyproject.toml` and `.gitignore` files, preserving your comments and formatting.
- **Composable Tooling:** No more sprawling template repos with nested Jinja conditionals. Toggle tools dynamically at runtime (`--no-direnv --docker`).
- **Scalable Templates:** Define entire organizational standards in a single, shareable `.toml` file, or scale up to a full Git repository for complex multi-file architectures.
- **Agent & Machine Ready:** Manifest-first architecture enables atomic `--dry-run` simulations and position-independent `--json` output for AI workflows.

*Use Copier for complex, multi-language codebases needing long-term 3-way git sync. Use Protostar for fast, modular, zero-friction Python environment bootstrapping.*

---

## 📖 Official Documentation

Ready to dive deeper? The README only scratches the surface.

Head over to the **[Official Documentation](https://protostar.readthedocs.io/en/stable/)** for:

- **Command Reference:** Full flags and capabilities for `init`.
- **Agent & Machine Interface:** Driving Protostar programmatically via `--json` and `--dry-run`.
- **Domain Presets:** Matrices for Scientific, Astrophysics, ML, DSP, Embedded, REST API, and CLI Application workflows.
- **Configuration & Shell Autocomplete:** Setting up global defaults, CLI autocompletion, and advanced AST overrides.
- **Architecture Mechanics:** Deep dives into the Orchestrator, Executor, and Manifest lifecycle.

---

## 💡 Design Philosophy

Protostar is built to save you time and stay out of your way. It adheres to a strict separation of concerns to avoid generating bloated artifacts you'll inevitably just delete manually:

1. **Foundational Scaffolding:** The `protostar init` command is designed to be run exactly *once* at the inception of a repository to lay the architectural groundwork, establishing your dependency managers and directory structures.

1. **Plan First, Write Later:** Many setup scripts run a sequence of shell commands and fail unpredictably midway through, leaving behind half-configured files. Protostar plans all changes upfront in memory during the read-only `plan()` phase before touching disk or running subprocesses in `execute()`. This guarantees clean dry-runs and zero partial failures.

1. **AI & Agent Ready:** With position-independent `--json` flags and atomic dry-running, AI agents and automation scripts can programmatically interrogate the CLI, plan workspace changes, resolve collisions, and execute headless scaffolding without hanging on interactive prompts.

1. **Fail Loud, Fail Early:** Pre-flight checks ensure all system dependencies (like `uv`, `git`, or `direnv`) are present before any state is mutated.

1. **Non-Destructive by Default:** Protostar never blindly overwrites your existing work. It dynamically appends to `.gitignore` files, intelligently merges IDE JSON configurations, uses deterministic AST modification to deep-merge TOML configurations, and safely aborts if generated files already exist.

1. **Actionable Telemetry:** When things break, Protostar bubbles up the exact `stderr` so you know immediately if a network request or dependency resolution failed. For unexpected internal crashes, it automatically generates a URL-encoded GitHub issue containing your system environment details to make debugging painless. You can also append the global `--verbose` (or `-v`) flag to any command to enable rich, detailed stack traces and debug-level logging.

---

## ⚡️ Performance & Latency Isolation

Protostar is built to be lightweight, so Python's startup overhead never slows down your local development.

- **Fast Hook Resolution:** Instead of making slow Git network calls to resolve hook versions (like `pre-commit autoupdate`), Protostar resolves them via a pre-compiled JSON registry fetched in milliseconds, with an offline fallback if you are disconnected.
- **Micro-Optimization:** We measure initialization latency using two benchmarking approaches:
  1. **Fast-Path Execution:** Measures the latency of non-interactive commands (e.g., `protostar help init`).
  1. **TUI-Path Execution:** Measures the overhead of triggering the interactive `questionary` wizards.

Our CI pipeline enforces a strict performance budget using `hyperfine`, gating any PR that introduces significant regressions in either path. We maintain historical tracking to ensure long-term architectural stability rather than chasing absolute CI metrics (which are subject to heavy VM variance).

- **View CI Trends:** [Performance Dashboard](https://jacksonfergusondev.github.io/protostar/)

---

## 📦 Installation

Protostar offers full cross-platform support and runs natively on Linux, macOS, and Windows.

### macOS (Homebrew)

```bash
brew install jacksonfergusondev/tap/protostar
```

### Universal (uv)

For isolated CLI tool installation on any OS, `uv` is highly recommended:

```bash
uv tool install protostar
```

### Universal (pip)

```bash
pip install protostar
```

> **Note:** If you install Protostar into an existing Python environment with `pip`, it will bring in `questionary` and `prompt_toolkit` for the interactive wizard. For guaranteed isolation and to avoid dependency conflicts, prefer `uv tool` or Homebrew.

---

## 🚀 Quick Start

Protostar is designed to be run right after you `mkdir` a new project.

### The Interactive Wizard

If you run `protostar` without any arguments, it launches an interactive Terminal User Interface (TUI).

The wizard will first ask if you want to scaffold using a **Template**. Templates are the fastest way to use Protostar, instantly wiring together tools, dependencies, and directory structures. You can choose from built-in domain templates (like `astro` or `cli`), select your own custom global aliases, or build an environment from scratch.

```bash
mkdir orbital-mechanics-sim
cd orbital-mechanics-sim
protostar
```

### Headless Scaffolding & Tri-State Toggles

For rapid, repeatable initialization, bypass the TUI entirely. Templates are the primary way to drive Protostar headlessly:

```bash
protostar init --template cli
```

Because Protostar uses **tri-state toggling**, you always remain in control. You can load a template but explicitly override its default opinions by passing `--<flag>` to force a tool on, or `--no-<flag>` to force it off:

```bash
protostar init --template cli --no-direnv --docker
```

*Result: Scaffolds the cli template, strips out the default direnv scaffolding, and generates container artifacts (`Dockerfile`, `.dockerignore`).*

To bypass any interactive collision prompts when running in headless CI environments, use `--force-merge` or `--force-replace`. You can also explicitly override the target Python version by passing `--python-version 3.13`.

### Dry-Run Simulations & Agent Integration

You can preview the entire scaffolding plan without touching disk or running subprocesses by passing `--dry-run`:

```bash
protostar init --template cli --dry-run
```

For AI coding agents and automated scripts, append the position-independent `--json` flag. Protostar outputs structured, machine-parseable JSON envelopes to `stdout` while routing all human logs to `stderr`:

```bash
# Plan scaffolding via JSON
protostar init --template cli --dry-run --json

# Execute scaffolding via JSON
protostar init --template cli --force-merge --json
```

See the **[Agent & Machine Interface Guide](https://protostar.readthedocs.io/en/stable/usage/agent-interface/)** for complete protocol documentation.

### Portable Templates & Global Aliases

If you want to enforce team-wide standards across multiple repositories, you can host your own custom template TOML files remotely (or store them locally). Use the `--from` flag to dynamically fetch and inject them. Protostar automatically translates web UI links into raw text links for GitHub, GitLab, Bitbucket, Codeberg, and Sourcehut, and natively supports unpacking `.zip`/`.tar.gz` repository archives.

```bash
protostar init --from https://raw.githubusercontent.com/YourOrg/standards/main/backend.toml
```

**Global Aliases:** Instead of typing long URLs, you can register templates in your global configuration (`~/.config/protostar/config.toml`):

```toml
[templates]
backend = "https://raw.githubusercontent.com/YourOrg/standards/main/backend.toml"
```

Now you can run `protostar init --template backend` anywhere, and it will automatically appear alongside built-ins in your interactive wizard.

*Note: To prevent unauthorized remote code execution, external templates containing shell tasks are secured behind an explicit Interactive Trust Dialog. Templates mapped as global aliases bypass this prompt automatically.*

### Authoring Custom Templates & Schema Validation

You can author custom templates to enforce organizational standards across dependencies, linter configurations, and directory structures. Protostar can export the official JSON Schema to enable real-time linting and autocompletion in editors like VS Code (via *Even Better TOML*):

```bash
# Export the template JSON Schema
protostar export-schema --json > protostar-template.schema.json
```

Add the schema header to the top of your custom template file for editor validation:

```toml
#:schema ./protostar-template.schema.json

# --- Dependencies ---
dependencies = ["fastapi", "uvicorn"]
ruff = true
pytest = true
```

For full template specifications, AST injections, and multi-file repository templating, visit the **[Template Authoring Guide](https://protostar.readthedocs.io/en/stable/usage/authoring-templates/)**.

---

## 🤝 Collaboration

This tool uses a highly decoupled, plugin-style architecture. The CLI parser dynamically evaluates module registries at runtime.

- **To add support for a new core tool (e.g., a linter or formatter):** Subclass `BootstrapModule`.
- **To define a new domain workflow:** Author a declarative TOML Template.

Protostar maintains strict engineering standards to ensure reliability, including 100% type-hinting, isolated `pytest` environments (mocked subprocesses and `tmp_path` disk isolation), and automated `ruff` formatting.

Please see the [Documentation](https://protostar.readthedocs.io/en/stable/developer/overview/) for full details on our development setup, architectural rules, and pull request guidelines.

## 📧 Contact

[![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/JacksonFergusonDev)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/jackson--ferguson/)
[![Email](https://img.shields.io/badge/Email-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:jackson.ferguson0@gmail.com)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
