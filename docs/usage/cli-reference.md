# Command Line Interface (CLI) Reference

Protostar provides a composable, deterministic command-line interface. Commands can be run interactively through terminal wizards (TUI) or headlessly via flags.

<div class="spacer-2"></div>

```bash
protostar [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS]
```

---

## Global Options

Global options can be passed to any command or evaluated independently:

| Flag | Shorthand | Description |
| :--- | :--- | :--- |
| `--json` | *None* | Position-independent flag. Emits structured JSON to `stdout` and redirects human-readable logging to `stderr`. |
| `--dry-run` | *None* | Executes the read-only `plan()` phase to preview planned files, AST merges, and system tasks without touching disk. |
| `--verbose` | `-v` | Enables debug-level logging and uncapped Python tracebacks for triage. |
| `--version` | *None* | Displays the installed Protostar version string. |
| `--help` | `-h` | Displays top-level help and available subcommands. |

---

## Commands

### `protostar init`

The primary command to scaffold and configure a Python repository.

```bash
protostar init [OPTIONS] [DYNAMIC_VARS...]
```

#### Core Options

| Option | Shorthand | Description |
| :--- | :--- | :--- |
| `--template <NAME>` | `-t <NAME>` | Scaffold from a built-in template or a registered global alias. |
| `--from <TARGET>` | *None* | Scaffold from a local file/directory, raw TOML URL, or remote Git repository archive (`.zip`, `.tar.gz`). |
| `--list-templates` | *None* | Lists all available built-in templates and configured global aliases. |
| `--python-version <VER>` | *None* | Override the target Python version for this initialization (e.g. `3.13`). |
| `--force-merge` | *None* | Non-destructively deep-merge configurations and ignores into existing workspace files without prompting. |
| `--force-replace` | *None* | Forcefully overwrite colliding workspace configuration files without prompting. |

#### Tooling Tri-State Flags

Every tooling module can be explicitly enabled (`--<flag>`) or disabled (`--no-<flag>`), overriding template defaults:

| Enable Flag | Disable Flag | Description |
| :--- | :--- | :--- |
| `--ruff` | `--no-ruff` | Ruff linter and code formatter |
| `--mypy` | `--no-mypy` | Mypy static type checker |
| `--ty` | `--no-ty` | Ty static type checker |
| `--pyrefly` | `--no-pyrefly` | Pyrefly static type checker |
| `--pytest` | `--no-pytest` | Pytest test runner with coverage settings |
| `--pre-commit` | `--no-pre-commit` | Pre-commit Git hook manager |
| `--prek` | `--no-prek` | Prek high-speed Rust Git hook manager |
| `--commitizen` | `--no-commitizen` | Commitizen conventional commits and changelog tooling |
| `--direnv` | `--no-direnv` | Direnv virtual environment auto-activation (`.envrc`) |
| `--markdownlint` | `--no-markdownlint` | Markdownlint configuration (`.markdownlint-cli2.yaml`) |
| `--docker` | `--no-docker` | Multi-stage `Dockerfile` and `.dockerignore` |
| `--renovate` | `--no-renovate` | Renovate automated dependency update configuration |
| `--codecov` | `--no-codecov` | Codecov configuration (`codecov.yml`) |
| `--zensical` | `--no-zensical` | Zensical documentation site scaffolding |
| `--readthedocs` | `--no-readthedocs` | Read the Docs build configuration (`.readthedocs.yaml`) |
| `--ci` | `--no-ci` | GitHub Actions continuous integration workflow |
| `--release` | `--no-release` | GitHub Actions PyPI publishing workflow |
| `--just` | `--no-just` | Task automation runner (`justfile`) |

#### Dynamic Variables

Any template containing placeholders (e.g., `<% DATABASE_URL %>`) can receive values via trailing arguments:

```bash
protostar init --from ./api.toml --DATABASE_URL="postgresql://localhost:5432/db"
```

---

### `protostar config`

Manages user-level default preferences stored in `~/.config/protostar/config.toml`.

```bash
protostar config [OPTIONS]
```

| Option | Description |
| :--- | :--- |
| *(No args)* | Opens `config.toml` in your system's default `$EDITOR`. |
| `--reset` | Resets configuration to factory defaults (prompts for confirmation). |
| `--force-replace` | Bypasses the confirmation prompt when used with `--reset`. |

---

### `protostar export-schema`

Exports the official JSON Schema for Protostar TOML templates.

```bash
protostar export-schema [OPTIONS]
```

| Option | Description |
| :--- | :--- |
| *(No args)* | Pretty-prints the syntax-highlighted schema to the terminal. |
| `--json` | Emits raw JSON schema for piping to files or schema validators. |

---

### `protostar help`

Displays comprehensive help panels and usage instructions.

```bash
protostar help [COMMAND]
```

---

## POSIX Exit Codes

Protostar maps runtime outcomes and operational exceptions to standard POSIX status codes:

| Code | POSIX Name | Trigger Condition |
| :--- | :--- | :--- |
| `0` | `EX_OK` | Successful execution |
| `1` | Generic | Subprocess failure or command timeout |
| `65` | `os.EX_DATAERR` | Template resolution error (corrupted archive, missing variables) |
| `69` | `os.EX_UNAVAILABLE` | Missing required system binary (`uv`, `git`, etc.) |
| `70` | `os.EX_SOFTWARE` | Unhandled internal Python bug (prompts automated bug report) |
| `74` | `os.EX_IOERR` | Local filesystem read/write or permission failure |
| `75` | `os.EX_TEMPFAIL` | Transient network failure during remote template download |
| `77` | `os.EX_NOPERM` | Security violation (e.g., path traversal Zip Slip) |
| `78` | `os.EX_CONFIG` | Invalid TOML syntax or conflicting CLI configuration |
| `130` | Shell Signal | User aborted interactive wizard prompt (Ctrl+C) |
