# Environment Initialization

The `init` command is Protostar's primary command. It sets up folder structures, wires together tools, and configures dependencies in seconds.

Protostar is designed to be run on Day 1 to build your repository foundation, but it is safe to re-run on Day 50 to inject a forgotten dependency or adopt a new static analysis tool.

- **Safe Merging**

  Protostar doesn't blindly overwrite files. It parses ASTs, deduplicates `.gitignore` entries, and safely deep-merges configurations. It is safe to execute on pre-existing codebases.

- **Instant & Repeatable**

  Instead of manually copying boilerplate from old repositories or relying on fragile shell scripts, Protostar creates a clean, consistent environment in fractions of a second.

______________________________________________________________________

## Opinionated Templates

While Protostar is fully modular, you often want a vetted, turnkey environment without selecting individual flags manually. Protostar ships with built-in **Opinionated Templates** that bundle domain-specific tools, directories, and AST configurations.

To scaffold from a template headlessly, pass `--template` (or `-t`):

```bash
# Scaffold from a built-in template (e.g., astro, cli, ml, api)
protostar init --template astro
```

### Tri-State CLI Toggles

Every tooling option supports tri-state evaluation. You can load a template's baseline and explicitly override any tool: passing `--<tool>` forces it on, while passing `--no-<tool>` forces it off:

```bash
# Scaffold the astro template with direnv disabled and mypy enabled
protostar init -t astro --no-direnv --mypy
```

To explore all built-in templates, load remote team standards (`--from`), supply dynamic parameters, or register global aliases, see the complete **[Templates & Portable Configurations Guide](.././templates/)**.

______________________________________________________________________

## Example Setups

To understand how Protostar interprets your flags, observe what happens when we execute different workflows in an empty directory.

IDE Configurations

The following repository tree examples assume you have configured an IDE in your global settings (e.g., `ide = "vscode"`) in addition to enabling direnv. If your config remains set to the default `None`, the `.vscode/settings.json` file will not be generated, though the universal `.vscode/` exclusion will still be safely appended to your `.gitignore`.

**Command:** `protostar init --template cli`

This example demonstrates Protostar's ability to wire complex tooling together automatically.

```text
.
├── .envrc
├── .github
│   ├── codecov.yml
│   ├── renovate.json
│   └── workflows
│       ├── ci.yml
│       └── release.yml
├── .gitignore
├── .pre-commit-config.yaml
├── .python-version
├── .readthedocs.yaml
├── CHANGELOG.md
├── README.md
├── docs
│   └── index.md
├── justfile
├── mkdocs.yml
├── pyproject.toml
├── src
│   └── demo_project
│       ├── __init__.py
│       └── cli.py
├── tests
│   └── test_cli.py
└── uv.lock
```

Inspect Generated Files

```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "rich>=15.0.0",
    "typer>=0.27.1",
]
description = "Add your description here."
readme = "README.md"
authors = [{ name = "your-name", email = "your-email" }]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Operating System :: MacOS",
    "Operating System :: POSIX :: Linux",
    "Operating System :: Microsoft :: Windows",
]

[project.scripts]
demo-project = "demo_project.cli:app"

[dependency-groups]
dev = [
    "commitizen>=4.18.0",
    "mypy>=2.3.1",
    "prek>=0.5.0",
    "pytest>=9.1.1",
    "pytest-cov>=7.1.0",
    "pytest-mock>=3.15.1",
    "ruff>=0.16.5",
    "rumdl>=0.2.64",
    { include-group = "docs" },
]
docs = [
    "mkdocstrings[python]>=1.0.6",
    "zensical>=0.0.57",
]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = [
    "A",   # flake8-builtins
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "D",   # pydocstyle
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "PT",  # flake8-pytest
    "RET", # flake8-return
    "RUF", # Ruff-specific
    "SIM", # flake8-simplify
    "T20", # flake8-print
    "UP",  # pyupgrade
]
ignore = [
    "D100", # Missing docstring in public module
    "D104", # Missing docstring in public package
    "D107", # Missing docstring in __init__
    "E501", # Line too long - handled automatically by `ruff format`
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/*.py" = ["T201", "D"]

# ---- Mypy ---- #

[tool.mypy]
mypy_path = "src"
python_version = "3.13"
strict = true
pretty = true
show_error_codes = true
show_error_context = true
explicit_package_bases = true

[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_untyped_defs = false
disallow_incomplete_defs = false
disallow_untyped_calls = false
warn_return_any = false

# ---- Pytest ---- #

[tool.pytest.ini_options]
addopts = "--strict-markers"
testpaths = [
    "tests",
]
pythonpath = [
    ".",
]

[tool.coverage.run]
branch = true

[tool.coverage.report]
omit = ["**/__init__.py"]
show_missing = true
skip_covered = true
fail_under = 90

# ---- Commitizen ---- #

[tool.commitizen]
name = "cz_conventional_commits"
version_provider = "pep621"
version_scheme = "semver2"
tag_format = "v$version"
update_changelog_on_bump = true
changelog_incremental = true

# ---- rumdl ---- #

[tool.rumdl]
disable = [
    "MD013", # line length - creates unnecessary diff churn
    "MD033", # inline HTML - required for readme and parts of documentation
    "MD077", # continuation line indentation - 4-space visual indent is intentional
]

# --- Heading style ---
# Enforce ATX style (# Heading) exclusively
[tool.rumdl.MD003]
style = "atx"

# --- Unordered list style ---
# Use dash (-) for list markers for consistency and reduced diff noise
[tool.rumdl.MD004]
style = "dash"

# --- Trailing spaces ---
# Allow exactly 2 spaces for hard line breaks; flag other stray whitespace
[tool.rumdl.MD009]
br-spaces = 2
strict = false

# --- Duplicate headings ---
# Allow identical subheadings under different parent headings
[tool.rumdl.MD024]
siblings-only = true

# --- Ordered list numbering ---
# Use "one" style (1., 1., 1.) to minimize Git diff churn on reorders
[tool.rumdl.MD029]
style = "one"

# --- Per-directory overrides for docs/ ---
# Relax rules that conflict with MkDocs / Zensical extensions
[tool.rumdl.per-file-ignores]
"docs/**/*.md" = [
    "MD041", # first line need not be a top-level heading in doc pages
    "MD046", # code block style - MkDocs extensions mix fenced and indented blocks
]
```

```yaml
default_install_hook_types:
  - pre-commit
  - commit-msg

default_stages:
  - pre-commit

repos:
  # Generic hooks (configured to IGNORE Python)
  - repo: builtin
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: check-case-conflict
      - id: check-symlinks
      - id: check-executables-have-shebangs
      - id: trailing-whitespace
        exclude: \.py$
      - id: end-of-file-fixer
        exclude: \.py$
      - id: check-yaml
      - id: check-json
      - id: check-toml

  # Local Python Toolchain (Managed via uv.lock)
  - repo: local
    hooks:
      - id: uv-lock-check
        name: uv lock check
        entry: uv lock --check
        language: system
        pass_filenames: false
        files: ^(pyproject\.toml|uv\.lock)$

      - id: rumdl-check
        name: rumdl check
        entry: uv run rumdl check --fix
        language: system
        types: [markdown]
        require_serial: true

      - id: rumdl-fmt
        name: rumdl fmt
        entry: uv run rumdl fmt
        language: system
        types: [markdown]
        require_serial: true

      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types: [python]
        require_serial: true

      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types: [python]
        require_serial: true

      - id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        types: [python]
        require_serial: true

  # Check for accidental commits of secrets
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.0
    hooks:
      - id: gitleaks

  # Commit message validation
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v4.18.0
    hooks:
      - id: commitizen
        stages: [commit-msg]

  # Renovate config validation
  - repo: https://github.com/renovatebot/pre-commit-hooks
    rev: 44.24.3
    hooks:
      - id: renovate-config-validator
        files: '.github/renovate.json'
```

```text
*~
.DS_Store
.cache/
.cz-cache/
.direnv/
.env
.envrc.local
.idea/
.mypy_cache/
.pytest_cache/
.ruff_cache/
.rumdl_cache/
.venv/
.vscode/
Thumbs.db
__pycache__/
site/
```

**What Protostar sets up:**

- **Dependency Locking:** Protostar locks `typer` and `rich` from the CLI template.
- **AST Configuration:** It constructs the TOML Abstract Syntax Tree (AST), configuring `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`, and `[tool.rumdl]` alongside development dependency groups.
- **Local Toolchain Hooks:** In `.pre-commit-config.yaml`, Protostar scaffolds local toolchain hooks (`ruff-check`, `ruff-format`, `mypy`, `rumdl-check`, `rumdl-fmt`) that execute directly in your project environment via `uv run`. When commit message validation (such as Commitizen) is included, top-level `default_install_hook_types` (`pre-commit`, `commit-msg`) and `default_stages` (`pre-commit`) are automatically declared.

**Command:** `protostar init --template astro`

This template focuses on managing dataset files and preventing repository bloat.

```text
.
├── .envrc
├── .gitattributes
├── .gitignore
├── .python-version
├── data
│   ├── catalogs
│   └── fits
├── justfile
├── notebooks
├── pyproject.toml
├── src
└── uv.lock
```

Inspect Generated Files

```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "astropy>=8.0.1",
    "astroquery>=0.4.11",
    "matplotlib>=3.11.1",
    "nbdime>=4.0.4",
    "numpy>=2.5.2",
    "pandas>=3.0.5",
    "photutils>=3.0.0",
    "scipy>=1.18.1",
    "specutils>=2.4.0",
]
description = "Add your description here."
readme = "README.md"
authors = [{ name = "your-name", email = "your-email" }]

[dependency-groups]
dev = [
    "ruff>=0.16.5",
]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = [
    "A",   # flake8-builtins
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "RUF", # Ruff-specific
    "UP",  # pyupgrade
]
ignore = [
    "E501", # Line too long - handled automatically by `ruff format`
]
extend-select = ["PD", "NPY"]
```

```text
# Astrophysics binary safety
*.fits binary
*.fit  binary
*.fts  binary

# Improve Jupyter Notebook diffs
*.ipynb text eol=lf

*.ipynb diff=jupyternotebook

*.ipynb merge=jupyternotebook
```

```text
*.csv
*.fit
*.fits
*.fts
*.parquet
*~
.DS_Store
.cache/
.direnv/
.env
.envrc.local
.idea/
.ipynb_checkpoints/
.ruff_cache/
.venv/
.vscode/
Thumbs.db
__pycache__/
```

**What Protostar sets up:**

- **Directory Scaffolding:** It injects `data/catalogs` and `data/fits`, isolating dataset files from source code.
- **Binary Safety:** It generates a `.gitattributes` file explicitly marking `*.fits` files as binary, and configuring `*.ipynb` for clean text diffing.
- **Notebook Diffing:** It automatically configures `nbdime` at the git level, avoiding unreadable JSON diffs when tracking Jupyter Notebooks.
- **Artifact Exclusions:** The `.gitignore` is populated with `*.fits`, `*.csv`, and `*.parquet`, preventing accidental commits of large data files.

**Command:** `protostar init --template ml --docker`

This template focuses on containerization and excluding model artifacts.

```text
.
├── .dockerignore
├── .envrc
├── .gitattributes
├── .gitignore
├── .python-version
├── Dockerfile
├── data
│   ├── 01_raw
│   │   └── .gitkeep
│   ├── 02_processed
│   │   └── .gitkeep
│   └── 03_features
│       └── .gitkeep
├── justfile
├── models
│   └── weights
│       └── .gitkeep
├── notebooks
│   └── exploratory
├── pyproject.toml
├── src
│   └── demo_project
│       ├── data
│       ├── models
│       └── training
├── tests
└── uv.lock
```

Inspect Generated Files

```dockerfile
# syntax=docker/dockerfile:1

# --- Builder Stage ---
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation and copy mode for uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies using cache and bind mounts for optimal layer caching
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy application source and build the environment
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- Runtime Stage ---
FROM python:3.13-slim-bookworm AS runtime

WORKDIR /app

# Security: Run as a non-privileged user
RUN useradd -m -u 10001 appuser
USER appuser

# Copy virtual environment and application code from builder
COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "demo_project"]
```

```text
!data/**/.gitkeep
*.log
*.onnx
*.pt
*.pth
*.safetensors
*~
.DS_Store
.cache/
.direnv/
.env
.envrc.local
.git/
.idea/
.ipynb_checkpoints/
.pytest_cache/
.python-version
.ruff_cache/
.rumdl_cache/
.venv/
.vscode/
README*
Thumbs.db
__pycache__/
data/01_raw/*
data/02_processed/*
data/03_features/*
docs/
mlruns/
runs/
tests/
wandb/
```

```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "matplotlib>=3.11.1",
    "numpy>=2.5.2",
    "pandas>=3.0.5",
    "scikit-learn>=1.9.0",
    "torch>=2.13.0",
    "tqdm>=4.70.0",
]
description = "Add your description here."
readme = "README.md"
authors = [{ name = "your-name", email = "your-email" }]

[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "pytest-mock>=3.15.1",
    "ruff>=0.16.5",
    "rumdl>=0.2.64",
]
docs = [
    "ipywidgets>=8.1.9",
    "jupyterlab>=4.6.3",
    "nbdime>=4.0.4",
]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88
extend-include = ["*.ipynb"]

[tool.ruff.lint]
select = [
    "A",   # flake8-builtins
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "RUF", # Ruff-specific
    "UP",  # pyupgrade
]
ignore = [
    "E501", # Line too long - handled automatically by `ruff format`
]
extend-select = ["NPY", "PD"] # NumPy and Pandas specific linting rules

# ---- Pytest ---- #

[tool.pytest.ini_options]
addopts = "--strict-markers"
testpaths = [
    "tests",
]
pythonpath = [
    ".",
]

# ---- rumdl ---- #

[tool.rumdl]
disable = [
    "MD013", # line length - creates unnecessary diff churn
    "MD033", # inline HTML - required for readme and parts of documentation
    "MD077", # continuation line indentation - 4-space visual indent is intentional
]

# --- Heading style ---
# Enforce ATX style (# Heading) exclusively
[tool.rumdl.MD003]
style = "atx"

# --- Unordered list style ---
# Use dash (-) for list markers for consistency and reduced diff noise
[tool.rumdl.MD004]
style = "dash"

# --- Trailing spaces ---
# Allow exactly 2 spaces for hard line breaks; flag other stray whitespace
[tool.rumdl.MD009]
br-spaces = 2
strict = false

# --- Duplicate headings ---
# Allow identical subheadings under different parent headings
[tool.rumdl.MD024]
siblings-only = true

# --- Ordered list numbering ---
# Use "one" style (1., 1., 1.) to minimize Git diff churn on reorders
[tool.rumdl.MD029]
style = "one"

# --- Per-directory overrides for docs/ ---
# Relax rules that conflict with MkDocs / Zensical extensions
[tool.rumdl.per-file-ignores]
"docs/**/*.md" = [
    "MD041", # first line need not be a top-level heading in doc pages
    "MD046", # code block style - MkDocs extensions mix fenced and indented blocks
]
```

**What Protostar sets up:**

- **Container Scaffolding:** Passing `--docker` generates a multi-stage `Dockerfile` and optimized `.dockerignore`. The `Dockerfile` leverages `uv` layer caching, non-root user execution (`appuser`), and minimal runtime images.
- **Model Checkpoints:** The ML template injects ignores for tensor weights (`*.pth`, `*.pt`, `*.onnx`, `*.safetensors`) and experiment tracking directories (`wandb/`, `mlruns/`).

**Command:** `protostar init --template api`

This template scaffolds a modern asynchronous web API service using FastAPI and Pydantic.

```text
.
├── .env.example
├── .envrc
├── .github
│   ├── renovate.json
│   └── workflows
│       └── ci.yml
├── .gitignore
├── .pre-commit-config.yaml
├── .python-version
├── CHANGELOG.md
├── justfile
├── pyproject.toml
├── src
│   └── demo_project
│       ├── api
│       │   └── routers
│       ├── core
│       │   └── config.py
│       ├── main.py
│       ├── models
│       ├── schemas
│       └── services
├── tests
│   └── api
└── uv.lock
```

Inspect Generated Files

```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.141.1",
    "pydantic-settings>=2.15.0",
    "uvicorn>=0.52.4",
]
description = "Add your description here."
readme = "README.md"
authors = [{ name = "your-name", email = "your-email" }]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Operating System :: MacOS",
    "Operating System :: POSIX :: Linux",
    "Operating System :: Microsoft :: Windows",
]

[dependency-groups]
dev = [
    "commitizen>=4.18.0",
    "httpx>=0.28.1",
    "mypy>=2.3.1",
    "prek>=0.5.0",
    "pytest>=9.1.1",
    "pytest-asyncio>=1.4.0",
    "pytest-mock>=3.15.1",
    "ruff>=0.16.5",
    "rumdl>=0.2.64",
]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = [
    "A",   # flake8-builtins
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "RUF", # Ruff-specific
    "UP",  # pyupgrade
]
ignore = [
    "E501", # Line too long - handled automatically by `ruff format`
]

# ---- Mypy ---- #

[tool.mypy]
mypy_path = "src"
python_version = "3.13"
pretty = true
show_error_codes = true
show_error_context = true
warn_return_any = true
warn_unused_configs = true
check_untyped_defs = true
explicit_package_bases = true

# ---- Pytest ---- #

[tool.pytest.ini_options]
addopts = "--strict-markers"
testpaths = [
    "tests",
]
pythonpath = [
    ".",
]

# ---- Commitizen ---- #

[tool.commitizen]
name = "cz_conventional_commits"
version_provider = "pep621"
version_scheme = "semver2"
tag_format = "v$version"
update_changelog_on_bump = true
changelog_incremental = true

# ---- rumdl ---- #

[tool.rumdl]
disable = [
    "MD013", # line length - creates unnecessary diff churn
    "MD033", # inline HTML - required for readme and parts of documentation
    "MD077", # continuation line indentation - 4-space visual indent is intentional
]

# --- Heading style ---
# Enforce ATX style (# Heading) exclusively
[tool.rumdl.MD003]
style = "atx"

# --- Unordered list style ---
# Use dash (-) for list markers for consistency and reduced diff noise
[tool.rumdl.MD004]
style = "dash"

# --- Trailing spaces ---
# Allow exactly 2 spaces for hard line breaks; flag other stray whitespace
[tool.rumdl.MD009]
br-spaces = 2
strict = false

# --- Duplicate headings ---
# Allow identical subheadings under different parent headings
[tool.rumdl.MD024]
siblings-only = true

# --- Ordered list numbering ---
# Use "one" style (1., 1., 1.) to minimize Git diff churn on reorders
[tool.rumdl.MD029]
style = "one"

# --- Per-directory overrides for docs/ ---
# Relax rules that conflict with MkDocs / Zensical extensions
[tool.rumdl.per-file-ignores]
"docs/**/*.md" = [
    "MD041", # first line need not be a top-level heading in doc pages
    "MD046", # code block style - MkDocs extensions mix fenced and indented blocks
]
```

```text
set shell := ["bash", "-euc", "-o", "pipefail"]
set unstable
set quiet

# --- ANSI Colors ---

blue := '\033[1;34m'
green := '\033[1;32m'
yellow := '\033[1;33m'
nc := '\033[0m'

# Show available commands
default:
    @just --list

# Sync/install dependencies using uv
sync:
    uv sync --quiet

# Auto-format code
format: sync
    @printf "\n{{ blue }}=== Formatting Code ==={{ nc }}\n"
    uv run rumdl check --fix .
    uv run rumdl fmt .
    uv run ruff check --fix .
    uv run ruff format .
    @printf "{{ green }}✔ Formatting complete{{ nc }}\n"

# Run linters
lint: sync
    @printf "\n{{ blue }}=== Running Linters ==={{ nc }}\n"
    uv run rumdl check .
    uv run rumdl fmt --check .
    uv run ruff check .
    uv run ruff format --check .
    @printf "{{ green }}✔ Linting passed{{ nc }}\n"

# Run static type checking
typecheck: sync
    @printf "\n{{ blue }}=== Running Type Checks ==={{ nc }}\n"
    uv run mypy .
    @printf "{{ green }}✔ Type checking passed{{ nc }}\n"

# Run the full automated testing matrix
test: sync
    @printf "\n{{ blue }}=== Running Tests ==={{ nc }}\n"
    uv run pytest
    @printf "{{ green }}✔ All tests passed{{ nc }}\n"

# Run tests with coverage
test-cov: sync
    @printf "\n{{ blue }}=== Running Tests with Coverage ==={{ nc }}\n"
    uv run pytest --cov
    @printf "{{ green }}✔ Coverage run complete{{ nc }}\n"

# Run the fast local CI pipeline executed before pushing
ci: lint typecheck test
    @printf "\n{{ green }}✔ Local CI pipeline completed successfully. Clear to push!{{ nc }}\n"

# Remove caches, artifacts, and temp files
clean:
    @printf "\n{{ blue }}=== Cleaning Workspace ==={{ nc }}\n"
    rm -rf \
        .rumdl_cache \
        .ruff_cache \
        .mypy_cache \
        .pytest_cache \
        htmlcov \
        .coverage \
        coverage.xml
    find . -type d -name "__pycache__" -exec rm -rf {} +
    @printf "{{ green }}✔ Workspace cleaned{{ nc }}\n"
```

```markdown
# Changelog

All notable changes to this project will be documented in this file.
```

**What Protostar sets up:**

- **Modular API Architecture:** Establishes a clean directory layout separating routers (`src/demo_project/api/routers`), core application settings (`src/demo_project/core/config.py`), database models, and schemas.
- **Async Toolchain:** Pre-configures `fastapi`, `uvicorn`, `pydantic-settings`, and asynchronous test infrastructure powered by `pytest-asyncio` and `httpx`.
- **Semantic Versioning & Changelogs:** Integrates Commitizen changelog tooling and automated release tracking out of the box.

**Command:** `protostar init --template dsp`

This template focuses on audio signal processing, feature extraction, and exploratory analysis.

```text
.
├── .envrc
├── .gitignore
├── .python-version
├── data
│   └── samples
│       ├── bounces
│       │   └── .gitkeep
│       └── raw
│           └── .gitkeep
├── justfile
├── notebooks
├── pyproject.toml
├── src
│   └── demo_project
│       ├── analysis
│       └── effects
├── tests
└── uv.lock
```

Inspect Generated Files

```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "librosa>=1.0.0",
    "matplotlib>=3.11.1",
    "numpy>=2.5.2",
    "pedalboard>=0.9.24",
    "scipy>=1.18.1",
    "soundfile>=0.14.0",
]
description = "Add your description here."
readme = "README.md"
authors = [{ name = "your-name", email = "your-email" }]

[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "pytest-mock>=3.15.1",
    "ruff>=0.16.5",
]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = [
    "A",   # flake8-builtins
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "RUF", # Ruff-specific
    "UP",  # pyupgrade
]
ignore = [
    "E501", # Line too long - handled automatically by `ruff format`
]

# ---- Pytest ---- #

[tool.pytest.ini_options]
addopts = "--strict-markers"
testpaths = [
    "tests",
]
pythonpath = [
    ".",
]
```

```text
set shell := ["bash", "-euc", "-o", "pipefail"]
set unstable
set quiet

# --- ANSI Colors ---

blue := '\033[1;34m'
green := '\033[1;32m'
yellow := '\033[1;33m'
nc := '\033[0m'

# Show available commands
default:
    @just --list

# Sync/install dependencies using uv
sync:
    uv sync --quiet

# Auto-format code
format: sync
    @printf "\n{{ blue }}=== Formatting Code ==={{ nc }}\n"
    uv run ruff check --fix .
    uv run ruff format .
    @printf "{{ green }}✔ Formatting complete{{ nc }}\n"

# Run linters
lint: sync
    @printf "\n{{ blue }}=== Running Linters ==={{ nc }}\n"
    uv run ruff check .
    uv run ruff format --check .
    @printf "{{ green }}✔ Linting passed{{ nc }}\n"

# Run the full automated testing matrix
test: sync
    @printf "\n{{ blue }}=== Running Tests ==={{ nc }}\n"
    uv run pytest
    @printf "{{ green }}✔ All tests passed{{ nc }}\n"

# Run tests with coverage
test-cov: sync
    @printf "\n{{ blue }}=== Running Tests with Coverage ==={{ nc }}\n"
    uv run pytest --cov
    @printf "{{ green }}✔ Coverage run complete{{ nc }}\n"

# Run the fast local CI pipeline executed before pushing
ci: lint test
    @printf "\n{{ green }}✔ Local CI pipeline completed successfully. Clear to push!{{ nc }}\n"

# Remove caches, artifacts, and temp files
clean:
    @printf "\n{{ blue }}=== Cleaning Workspace ==={{ nc }}\n"
    rm -rf \
        .ruff_cache \
        .pytest_cache \
        htmlcov \
        .coverage \
        coverage.xml
    find . -type d -name "__pycache__" -exec rm -rf {} +
    @printf "{{ green }}✔ Workspace cleaned{{ nc }}\n"
```

**What Protostar sets up:**

- **Audio Pipeline Layout:** Scaffolds dedicated sample directories (`data/samples/raw`, `data/samples/bounces`) alongside modular analysis and effects packages (`src/demo_project/analysis`, `src/demo_project/effects`).
- **Scientific Signal Stack:** Locks in core numerical and audio processing libraries: `librosa`, `soundfile`, `pedalboard`, `scipy`, `numpy`, and `matplotlib`.
- **Notebook Prototyping:** Prepares a `notebooks/` directory for visual spectrum inspection and rapid experimentation.

**Command:** `protostar init --template embedded`

This template scaffolds an embedded hardware development environment optimized for MicroPython and circuit prototyping.

```text
.
├── .envrc
├── .gitignore
├── .python-version
├── justfile
├── pyproject.toml
├── src
│   ├── board
│   │   ├── boot.py
│   │   └── main.py
│   └── host
├── tests
│   └── host_mocks
└── uv.lock
```

Inspect Generated Files

```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "mpremote>=1.29.0",
    "pyserial>=3.5",
]
description = "Add your description here."
readme = "README.md"
authors = [{ name = "your-name", email = "your-email" }]

[dependency-groups]
dev = [
    "ruff>=0.16.5",
]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = [
    "A",   # flake8-builtins
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "RUF", # Ruff-specific
    "UP",  # pyupgrade
]
ignore = [
    "E501", # Line too long - handled automatically by `ruff format`
]
```

```text
set shell := ["bash", "-euc", "-o", "pipefail"]
set unstable
set quiet

# --- ANSI Colors ---

blue := '\033[1;34m'
green := '\033[1;32m'
yellow := '\033[1;33m'
nc := '\033[0m'

# Show available commands
default:
    @just --list

# Sync/install dependencies using uv
sync:
    uv sync --quiet

# Auto-format code
format: sync
    @printf "\n{{ blue }}=== Formatting Code ==={{ nc }}\n"
    uv run ruff check --fix .
    uv run ruff format .
    @printf "{{ green }}✔ Formatting complete{{ nc }}\n"

# Run linters
lint: sync
    @printf "\n{{ blue }}=== Running Linters ==={{ nc }}\n"
    uv run ruff check .
    uv run ruff format --check .
    @printf "{{ green }}✔ Linting passed{{ nc }}\n"

# Run the fast local CI pipeline executed before pushing
ci: lint
    @printf "\n{{ green }}✔ Local CI pipeline completed successfully. Clear to push!{{ nc }}\n"

# Remove caches, artifacts, and temp files
clean:
    @printf "\n{{ blue }}=== Cleaning Workspace ==={{ nc }}\n"
    rm -rf \
        .ruff_cache
    find . -type d -name "__pycache__" -exec rm -rf {} +
    @printf "{{ green }}✔ Workspace cleaned{{ nc }}\n"

# --- Protostar Injection: 57494455 ---
port := "/dev/ttyACM0" # Default Linux port, update for macOS (/dev/tty.usbmodem*) or Windows (COM*)

# Copy the board directory to the microcontroller
flash:
    mpremote connect {{ port }} fs cp -r src/board/* :

# Open a REPL on the board
repl:
    mpremote connect {{ port }} repl
# --- End Protostar Injection ---
```

**What Protostar sets up:**

- **Board & Host Decoupling:** Separates on-device firmware code (`src/board/boot.py`, `src/board/main.py`) from host workstation tools (`src/host/`).
- **Host Mock Testing:** Scaffolds a `tests/host_mocks/` harness to validate hardware interaction logic locally without physical microcontrollers connected.
- **MicroPython Device Tooling:** Bundles `mpremote` and `pyserial` for device communication, flashing, and interactive REPL sessions.

______________________________________________________________________

## Task Runner Orchestration (`justfile`)

Every initialized repository includes a turnkey `justfile` generated from your active tooling configuration. Recipes dynamically adapt to your selected linters, test frameworks, and documentation engines:

```text
set shell := ["bash", "-euc", "-o", "pipefail"]
set unstable
set quiet

# --- ANSI Colors ---

blue := '\033[1;34m'
green := '\033[1;32m'
yellow := '\033[1;33m'
nc := '\033[0m'

# Show available commands
default:
    @just --list

# Sync/install dependencies using uv
sync:
    uv sync --quiet

# Auto-format code
format: sync
    @printf "\n{{ blue }}=== Formatting Code ==={{ nc }}\n"
    uv run rumdl check --fix .
    uv run rumdl fmt .
    uv run ruff check --fix .
    uv run ruff format .
    @printf "{{ green }}✔ Formatting complete{{ nc }}\n"

# Run linters
lint: sync
    @printf "\n{{ blue }}=== Running Linters ==={{ nc }}\n"
    uv run rumdl check .
    uv run rumdl fmt --check .
    uv run ruff check .
    uv run ruff format --check .
    @printf "{{ green }}✔ Linting passed{{ nc }}\n"

# Run static type checking
typecheck: sync
    @printf "\n{{ blue }}=== Running Type Checks ==={{ nc }}\n"
    uv run mypy .
    @printf "{{ green }}✔ Type checking passed{{ nc }}\n"

# Run the full automated testing matrix
test: sync
    @printf "\n{{ blue }}=== Running Tests ==={{ nc }}\n"
    uv run pytest
    @printf "{{ green }}✔ All tests passed{{ nc }}\n"

# Run tests with coverage
test-cov: sync
    @printf "\n{{ blue }}=== Running Tests with Coverage ==={{ nc }}\n"
    uv run pytest --cov
    @printf "{{ green }}✔ Coverage run complete{{ nc }}\n"

# Run the fast local CI pipeline executed before pushing
ci: lint typecheck test
    @printf "\n{{ green }}✔ Local CI pipeline completed successfully. Clear to push!{{ nc }}\n"

# Remove caches, artifacts, and temp files
clean:
    @printf "\n{{ blue }}=== Cleaning Workspace ==={{ nc }}\n"
    rm -rf \
        .rumdl_cache \
        .ruff_cache \
        .mypy_cache \
        .pytest_cache \
        htmlcov \
        .coverage \
        coverage.xml
    find . -type d -name "__pycache__" -exec rm -rf {} +
    @printf "{{ green }}✔ Workspace cleaned{{ nc }}\n"

# Start the documentation preview server
serve: sync
    @printf "\n{{ blue }}=== Launching Zensical Server ==={{ nc }}\n"
    uv run zensical serve -o
```

Running `just` in your project root provides standard developer workflows immediately:

- **`just format`**: Runs automated code formatting with Ruff and rumdl.
- **`just lint`**: Executes static analysis with Ruff and rumdl.
- **`just typecheck`**: Runs static type checking across the project source tree.
- **`just test` / `just test-cov`**: Executes the test suite with coverage reporting.
- **`just ci`**: Emulates the GitHub Actions CI pipeline locally.

______________________________________________________________________

## Interactive Wizard & Metadata

When running `protostar init` without a `--template` flag, Protostar launches an interactive prompt wizard to configure your environment.

The following metadata fields are prompted during initialization or automatically resolved from your global configuration and git environment:

| Key               | Label                            | Prompt Type | Default                 |
| ----------------- | -------------------------------- | ----------- | ----------------------- |
| `description`     | Project description              | `text`      | *None*                  |
| `license`         | Project license                  | `select`    | `MIT`                   |
| `author_name`     | Author name                      | `text`      | *None*                  |
| `author_email`    | Author email                     | `text`      | *None*                  |
| `github_username` | GitHub username                  | `text`      | *None*                  |
| `minimum_python`  | Minimum supported Python version | `text`      | `3.13`                  |
| `supported_os`    | Supported Operating Systems      | `checkbox`  | `MacOS, Linux, Windows` |
| `docker_port`     | Container exposed port           | `text`      | `8000`                  |

______________________________________________________________________

## Progressive Scaffolding & Collisions

When Protostar detects existing configuration files (like `pyproject.toml`), it prompts you to choose how to handle the conflict:

```text
Protostar Ignition Sequence Initiated

Workspace Collision: Protostar detected existing configuration files in the workspace.
  - pyproject.toml

? How would you like to proceed?
  » Merge      (Safely injects missing configs; preserves existing user data)
    Overwrite  (Forces injection; updates existing keys to match Protostar)
    Abort      (Safely exit without modifying the environment)
```

Selecting **Merge** executes an AST injection:

- Leaves your existing dependencies untouched.

- Alphabetically inserts new template dependencies.

- Merges tooling configuration tables into `pyproject.toml`.

- Appends new file patterns to `.gitignore` without duplicating existing rules.

  See the injected changes

  ```diff
  --- a/pyproject.toml
  +++ b/pyproject.toml
  @@ -3,10 +3,16 @@
   version = "0.1.0"
   requires-python = ">=3.13"
   dependencies = [
  +    "astropy>=8.0.1",
  +    "astroquery>=0.4.11",
       "matplotlib>=3.11.1",
  +    "nbdime>=4.0.4",
       "numpy>=2.5.2",
       "pandas>=3.0.5",
  +    "photutils>=3.0.0",
       "scikit-learn>=1.9.0",
  +    "scipy>=1.18.1",
  +    "specutils>=2.4.0",
       "torch>=2.13.0",
       "tqdm>=4.70.0",
   ]
  @@ -16,6 +22,7 @@

   [dependency-groups]
   dev = [
  +    "mypy>=2.3.1",
       "pytest>=9.1.1",
       "pytest-mock>=3.15.1",
       "ruff>=0.16.5",
  @@ -53,6 +60,19 @@
   ]
   extend-select = ["NPY", "PD"] # NumPy and Pandas specific linting rules

  +# ---- Mypy ---- #
  +
  +[tool.mypy]
  +mypy_path = "src"
  +python_version = "3.13"
  +pretty = true
  +show_error_codes = true
  +show_error_context = true
  +warn_return_any = true
  +warn_unused_configs = true
  +check_untyped_defs = true
  +explicit_package_bases = true
  +
   # ---- Pytest ---- #

   [tool.pytest.ini_options]

  --- a/.gitignore
  +++ b/.gitignore
  @@ -25,3 +25,9 @@
   mlruns/
   runs/
   wandb/
  +*.csv
  +*.fit
  +*.fits
  +*.fts
  +*.parquet
  +.mypy_cache/
  ```

Headless Operations

In CI/CD environments where interactive prompts are impossible, pass `--force-merge` or `--force-replace` to bypass collision prompts deterministically.

## Advanced Flags

- **Dry-Run Simulation**: Append `--dry-run` to preview the planned filesystem structure, dependencies, and tasks without writing files or running shell commands (e.g., `protostar init --template cli --dry-run`).
- **Machine-Readable Output**: Pass the position-independent `--json` flag to emit structured JSON envelopes to `stdout` and route logs to `stderr` (e.g., `protostar init --template cli --json`). See the **[Agent & Machine Interface](.././agent-interface/)** for the full protocol specification.
- **Template Shorthand**: Use `-t` as shorthand for `--template` (e.g., `protostar init -t cli`).
- **List Available Templates**: Run `protostar init --list-templates` to view all built-in templates and registered global aliases.
- **Python Version Overrides**: Override the default Python version for a single run using `--python-version` (e.g., `protostar init --template cli --python-version 3.13`).
- **Verbose Output**: Append `--verbose` (or `-v`) to enable debug logs and full tracebacks.

## The Capabilities Matrix

To view all supported subcommands and flags in your terminal, run `protostar help init`.

______________________________________________________________________

## Next Steps

- **[Templates & Portable Configs](.././templates/):** Learn how to create and share custom TOML blueprints, fetch remote templates, and interpolate variables.
- **[Tooling & Flags Matrix](.././tooling-matrix/):** Explore all supported linters, formatters, type checkers, and test runners.
- **[Global Configuration](.././configuration/):** Customize your default Python version, licenses, and template aliases.
- **[Troubleshooting & FAQ](.././troubleshooting/):** Resolve missing binary dependencies, workspace collisions, and editor configuration issues.
