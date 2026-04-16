# Configuration Boundaries & Architecture

To prevent configuration drift across projects and maintain strict idempotency, Protostar enforces a hard boundary between global environment initialization and local repository generation.

This document breaks down the configuration mechanics, starting with the basics and diving into the advanced AST manipulation pipelines.

---

## The Quick Start: Global Configuration

Your global configuration file acts as the singular source of truth for environment initialization. Instead of hunting down the file path, you can open it directly in your system's default `$EDITOR` by running:

```bash
protostar config
```

### The Default Baseline

If you just installed Protostar, this is your baseline configuration. It dictates base environment toggles, preferred developer tools, package managers, and domain-specific dependency overrides.

--8<-- "default_config.md"

Because `protostar init` always reads from this global file, you maintain a consistent, reproducible development signature across every new project you scaffold.

---

## Deep Dive: The Configuration Matrix

For power users, Protostar's configuration goes far beyond simple boolean toggles. You can define complete dependency footprints, map out directory structures, and inject raw multi-line strings directly into the Abstract Syntax Tree (AST) of target configuration files.

### 1. Environment Parameters (`[env]`)

The `[env]` block defines your foundational tools and package managers.

:material-code-json: **IDE Integration**

:   `ide`: Conditionally injects IDE-specific configurations (like Python interpreter paths). Universal workspace exclusions (e.g., `.idea/`, `.vscode/`) are handled automatically regardless of this setting.
    Accepts `"vscode"`, `"cursor"`, `"jetbrains"`, or `"none"`. Defaults to `none`.

:material-package-variant-closed: **Package Management**

:   `python_package_manager`: Accepts `"uv"` (the highly-refined default) or `"pip"`.

    <hr>

    `python_version`: Target version to lock (e.g. `"3.13"`).

    <hr>

    `node_package_manager`: Accepts `"npm"`, `"pnpm"`, or `"yarn"`.

:material-hammer-wrench: **Tooling Toggles**

:   `direnv`: Auto-scaffolds a `.envrc` and evaluates the virtual environment shell hook automatically.

    <hr>

    `no-ruff`: Disables the default Ruff scaffolding.

    <hr>

    `mypy`, `pytest`, `pre_commit`, `markdownlint`: Inject dependencies, pyproject tables, and git hooks.

<hr>

### 2. Domain Presets (`[presets]`)

Presets allow you to pre-load dependencies and directory architectures for specific pipelines without typing them out via CLI flags every time.

#### Generator Presets

Currently, you can define the default style for file generation targets, such as the `latex` preset. Passing `"minimal"`, `"science"`, `"lab-report"`, or `"academic"` alters the standard preamble macros injected into your `.tex` targets.

#### Pipeline Overrides

You can define explicit overrides for any of the domain presets (e.g., `astro`, `scientific`, `dsp`, `ml`).

Suppose you frequently build data analysis pipelines to process raw radio telescope telemetry or analyze differential fungal growth rates. You can override the `[presets.astro]` or `[presets.scientific]` blocks to automatically generate your exact architecture:

```toml
[presets.astro]
# The primary dependencies required for the pipeline
dependencies = ["astropy", "astroquery", "photutils", "specutils"]
# Development and testing libraries
dev_dependencies = ["pytest-benchmark"]
# The data structures required to hold the observations
directories = ["data/catalogs", "data/fits", "data/raw"]
```

When you run `protostar init --astro`, the orchestrator reads this block, dynamically injects the packages using your configured package manager, and scaffolds the required directories.

<hr>

### 3. Global Development Overrides (`[dev]`)

The `[dev]` block allows you to force configurations across *all* initialized environments, regardless of the flags provided at runtime.

#### Extra Dependencies

If you have a tool you use universally (like a version bumper or specific LSP extension), append it here to have it installed as a dev-dependency on every run.

```toml
[dev]
extra_dependencies = ["bump-my-version", "pyright"]
```

#### pyproject.toml Injections

The `[dev.pyproject]` block is one of Protostar's most powerful features. You can define raw, multi-line TOML strings that the orchestrator will safely deep-merge into the target `pyproject.toml`'s Abstract Syntax Tree.

This is highly effective for maintaining a universal static analysis baseline.

```toml
[dev.pyproject]
custom_ruff = '''
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "T20", "PT", "C4", "D"]
ignore = ["E501", "D100", "D104", "D107"]

[tool.ruff.lint.isort]
section-order = ["future", "standard-library", "third-party", "first-party", "local-folder"]
'''
```

---

## Local Configuration (`.protostar.toml`)

While `config.toml` dictates global architecture, repository-specific boilerplate generation often requires localized parameters.

**This file is strictly reserved for `protostar generate` targets.** In future releases, this file will be used to define overrides specific to the active repository, such as custom C++ namespaces, specific hardware mappings for embedded constraints, or custom LaTeX macros. While the configuration parser currently evaluates this file, full integration with the generator targets is actively in development.

!!! warning "Scope Enforcement"
    Any global initialization blocks (e.g., `[env]`, `[presets]`, or `[dev]`) placed in a local `.protostar.toml` will be actively stripped and ignored by the orchestrator.

    This is not an oversight; it is a hard architecture rule. It guarantees that running `init` remains perfectly idempotent, and local configurations cannot silently mutate or overwrite your global setup architecture.
