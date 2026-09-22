# Command Line Interface (CLI) Reference

Protostar provides a composable, deterministic command-line interface. Commands can be run interactively through terminal wizards (TUI) or headlessly via flags.

```bash
protostar [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS]
```

______________________________________________________________________

## Global Options

Global options can be passed to any command or evaluated independently:

| Flag        | Shorthand | Description                                                                                                         |
| ----------- | --------- | ------------------------------------------------------------------------------------------------------------------- |
| `--json`    | *None*    | Position-independent flag. Emits structured JSON to `stdout` and redirects human-readable logging to `stderr`.      |
| `--dry-run` | *None*    | Executes the read-only `plan()` phase to preview planned files, AST merges, and system tasks without touching disk. |
| `--verbose` | `-v`      | Enables debug-level logging and uncapped Python tracebacks for triage.                                              |
| `--version` | *None*    | Displays the installed Protostar version string.                                                                    |
| `--help`    | `-h`      | Displays top-level help and available subcommands.                                                                  |

______________________________________________________________________

## Commands

### `protostar init`

The primary command to scaffold and configure a Python repository.

```bash
protostar init [OPTIONS] [DYNAMIC_VARS...]
```

#### Core Options

| Option                   | Shorthand   | Description                                                                                               |
| ------------------------ | ----------- | --------------------------------------------------------------------------------------------------------- |
| `--template <NAME>`      | `-t <NAME>` | Scaffold from a built-in template or a registered global alias.                                           |
| `--from <TARGET>`        | *None*      | Scaffold from a local file/directory, raw TOML URL, or remote Git repository archive (`.zip`, `.tar.gz`). |
| `--list-templates`       | *None*      | Lists all available built-in templates and configured global aliases.                                     |
| `--python-version <VER>` | *None*      | Override the target Python version for this initialization (e.g. `3.13`).                                 |
| `--force-merge`          | *None*      | Non-destructively deep-merge configurations and ignores into existing workspace files without prompting.  |
| `--force-replace`        | *None*      | Forcefully overwrite colliding workspace configuration files without prompting.                           |

#### Tooling Tri-State Flags

Every tooling module can be explicitly enabled (`--<flag>`) or disabled (`--no-<flag>`), overriding template defaults:

| Enable Flag      | Disable Flag        | Description                                                                   |
| ---------------- | ------------------- | ----------------------------------------------------------------------------- |
| `--direnv`       | `--no-direnv`       | Scaffold a .envrc and evaluate the virtual environment                        |
| `--markdownlint` | `--no-markdownlint` | Scaffold a relaxed .markdownlint-cli2.yaml configuration                      |
| `--rumdl`        | `--no-rumdl`        | Scaffold rumdl fast markdown linter and formatter                             |
| `--ruff`         | `--no-ruff`         | Scaffold Ruff linter and formatter                                            |
| `--mypy`         | `--no-mypy`         | Scaffold Mypy static type checker                                             |
| `--ty`           | `--no-ty`           | Scaffold Ty static type checker                                               |
| `--pyrefly`      | `--no-pyrefly`      | Scaffold pyrefly static type checker                                          |
| `--pytest`       | `--no-pytest`       | Scaffold Pytest testing framework                                             |
| `--pre-commit`   | `--no-pre-commit`   | Scaffold pre-commit hooks and configuration                                   |
| `--prek`         | `--no-prek`         | Scaffold prek hooks and configuration (faster Rust alternative to pre-commit) |
| `--commitizen`   | `--no-commitizen`   | Scaffold commitizen version bumping and changelog tooling                     |
| `--renovate`     | `--no-renovate`     | Scaffold Renovate dependency update configuration                             |
| `--codecov`      | `--no-codecov`      | Scaffold Codecov configuration                                                |
| `--zensical`     | `--no-zensical`     | Scaffold Zensical documentation                                               |
| `--readthedocs`  | `--no-readthedocs`  | Scaffold Read the Docs configuration                                          |
| `--ci`           | `--no-ci`           | Scaffold standard GitHub Actions CI workflows                                 |
| `--release`      | `--no-release`      | Scaffold GitHub Actions PyPI release workflows                                |
| `--just`         | `--no-just`         | Scaffold a justfile for command execution                                     |
| `--docker`       | `--no-docker`       | Multi-stage `Dockerfile` and `.dockerignore` container scaffolding            |

#### Dynamic Variables

Any template containing placeholders (e.g., `<% DATABASE_URL %>`) can receive values via trailing arguments:

```bash
protostar init --from ./api.toml --DATABASE_URL="postgresql://localhost:5432/db"
```

______________________________________________________________________

### `protostar config`

Manages your default preferences stored in `~/.config/protostar/config.toml`.

```bash
protostar config [OPTIONS]
```

| Option            | Description                                                          |
| ----------------- | -------------------------------------------------------------------- |
| *(No args)*       | Opens `config.toml` in your system's default `$EDITOR`.              |
| `--reset`         | Resets configuration to factory defaults (prompts for confirmation). |
| `--force-replace` | Bypasses the confirmation prompt when used with `--reset`.           |

______________________________________________________________________

### `protostar export-schema`

Exports the official JSON Schema for Protostar TOML templates.

```bash
protostar export-schema [OPTIONS]
```

| Option      | Description                                                     |
| ----------- | --------------------------------------------------------------- |
| *(No args)* | Pretty-prints the syntax-highlighted schema to the terminal.    |
| `--json`    | Emits raw JSON schema for piping to files or schema validators. |

______________________________________________________________________

### `protostar help`

Displays comprehensive help panels and usage instructions.

```bash
protostar help [COMMAND]
```

______________________________________________________________________

## POSIX Exit Codes

Protostar maps runtime outcomes and operational exceptions to standard POSIX status codes:

| Exit Code | POSIX Name          | Exception Class                               | Trigger Condition                                                |
| --------- | ------------------- | --------------------------------------------- | ---------------------------------------------------------------- |
| `0`       | `EX_OK`             | *None*                                        | Successful execution                                             |
| `1`       | Generic Exit        | `CommandExecutionError` `CommandTimeoutError` | Subprocess failure or command timeout                            |
| `64`      | `os.EX_USAGE`       | `InvalidUsageError`                           | Invalid CLI arguments or command usage syntax                    |
| `65`      | `os.EX_DATAERR`     | `TemplateResolutionError`                     | Template resolution error (corrupted archive, missing variables) |
| `69`      | `os.EX_UNAVAILABLE` | `MissingDependencyError`                      | Missing required system binary (`uv`, `git`, etc.)               |
| `70`      | `os.EX_SOFTWARE`    | *(Unhandled exception)*                       | Unhandled internal Python bug (prompts automated bug report)     |
| `74`      | `os.EX_IOERR`       | `FileSystemError`                             | Local filesystem read/write or permission failure                |
| `75`      | `os.EX_TEMPFAIL`    | `NetworkFetchError`                           | Transient network failure during remote template download        |
| `77`      | `os.EX_NOPERM`      | `SecurityViolationError`                      | Security violation (e.g., path traversal Zip Slip)               |
| `78`      | `os.EX_CONFIG`      | `ConfigurationError`                          | Invalid TOML syntax or conflicting CLI configuration             |
| `130`     | Shell Signal        | `ExecutionAbortedError`                       | You aborted interactive wizard prompt (Ctrl+C)                   |
