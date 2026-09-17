---
description: "Comprehensive command-line interface reference for the Protostar CLI, including flags and options."
---

# Command Line Interface (CLI) Reference

Protostar provides a composable, deterministic command-line interface. Commands can be run interactively through terminal wizards (TUI) or headlessly via flags.

```bash
protostar [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS]
```

## Global Options

Global options can be passed to any command or evaluated independently:

--8<-- "table_cli_global.md"

## Commands

### `protostar init`

The primary command to scaffold and configure a Python repository.

```bash
protostar init [OPTIONS] [DYNAMIC_VARS...]
```

#### Core Options

--8<-- "table_cli_init_core.md"

#### Tooling Tri-State Flags

Every tooling module can be explicitly enabled (`--<flag>`) or disabled (`--no-<flag>`), overriding template defaults:

--8<-- "table_cli_tooling_flags.md"

#### Dynamic Variables

Any template containing placeholders (e.g., `<% DATABASE_URL %>`) can receive values via trailing arguments:

```bash
protostar init --from ./api.toml --DATABASE_URL="postgresql://localhost:5432/db"
```

### `protostar status` and `protostar diff`

Inspect the current directory using its recorded project recipe and ownership ledger:

```bash
protostar status
protostar diff
protostar diff --json
```

![Status command help](../assets/terminals/cli_status_help.svg)

![Diff command help](../assets/terminals/cli_diff_help.svg)

`status` summarizes accepted edits, conflicts, preserved local edits/deletions,
ownership advancement, and resolver actions. `diff` also displays unified diffs
of accepted direct edits. Conflicting content is preserved; conflict details give
the file, semantic keys or region identity, and reason. Resolver output is unknown
until application; no predicted dependency or lockfile diff is shown.

Both commands support `--json`, `--verbose`, and help. They never prompt, execute
subprocesses, write workspace files, or populate disk caches. Remote template
acquisition may use the network and reads archive data entirely in memory.
Initialization-only tasks and IDE probes are reported as excluded.

The explicit current directory must contain `[tool.protostar]` in `pyproject.toml`
and `.protostar.lock.toml`. For a Stage 1 project, rerun the original explicit
selection with `init --force-merge` to enroll it. Edit the recipe deliberately to
change tool selections; global defaults are never consulted during review.
Custom variables require `[tool.protostar.bindings]` and their environment values.
Recorded template identity changes are rejected.

Valid reviews exit `0`, even with conflicts or pending work. Fatal errors use the
existing domain-specific exit codes. These commands only inspect; `init --dry-run`
continues to show the creation manifest rather than accepted lifecycle changes.

### `protostar config`

Manages your default preferences stored in `~/.config/protostar/config.toml`.

```bash
protostar config [OPTIONS]
```

--8<-- "table_cli_config.md"

### `protostar export-schema`

Exports the official JSON Schema for Protostar TOML templates.

```bash
protostar export-schema [OPTIONS]
```

--8<-- "table_cli_export_schema.md"

### `protostar completion`

Generates dynamic autocompletion scripts for supported shells (Bash, Zsh, Fish, PowerShell).

```bash
protostar completion [SHELL]
```

--8<-- "table_cli_completion.md"

### `protostar help`

Displays comprehensive help panels and usage instructions.

```bash
protostar help [COMMAND]
```

## POSIX Exit Codes

Protostar maps runtime outcomes and operational exceptions to standard POSIX status codes:

--8<-- "table_exit_codes.md"
