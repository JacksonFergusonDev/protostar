---
description: "Comprehensive command-line interface reference for the Protostar CLI, including flags and options."
---

# Command Line Interface (CLI) Reference

Protostar provides a composable, deterministic command-line interface. Commands can be run interactively through terminal wizards (TUI) or headlessly via flags.

```bash
protostar [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS]
```

---

## Global Options

Global options can be passed to any command or evaluated independently:

--8<-- "table_cli_global.md"

---

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

---

### `protostar config`

Manages your default preferences stored in `~/.config/protostar/config.toml`.

```bash
protostar config [OPTIONS]
```

--8<-- "table_cli_config.md"

---

### `protostar export-schema`

Exports the official JSON Schema for Protostar TOML templates.

```bash
protostar export-schema [OPTIONS]
```

--8<-- "table_cli_export_schema.md"

---

### `protostar help`

Displays comprehensive help panels and usage instructions.

```bash
protostar help [COMMAND]
```

---

## POSIX Exit Codes

Protostar maps runtime outcomes and operational exceptions to standard POSIX status codes:

--8<-- "table_exit_codes.md"
