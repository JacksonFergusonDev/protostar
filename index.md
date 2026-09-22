[Documentation](getting-started/) [Why Protostar?](why-protostar/) [GitHub](https://github.com/jacksonfergusondev/protostar)

# Modular. Declarative. Fast.

Protostar sets up Python development environments cleanly and predictably—without overwriting existing work or leaving half-finished setups.

Install globally via uv

`uv tool install protostar` Copy command

## Overview

Protostar is a modular CLI for initializing repositories and generating repeatable boilerplate. It is designed to automate environment setup while staying out of your way.

### Manifest-first

State is declared before side effects execute, reducing partial failures and setup drift.

### Non-destructive

Existing files are respected, merged carefully, or left untouched when collisions occur.

### Composable tooling

Modern Python tools composed dynamically via tri-state CLI flags and declarative blueprints.

### Actionable telemetry

Errors surface clearly, with useful diagnostics instead of opaque setup failures.

## Quick start

```bash
mkdir hyperdrive-cli
cd hyperdrive-cli
protostar init --template cli  # (a Typer-based CLI application)
```

This initializes a working environment quickly while preserving explicit control over tools and context.

## Next steps

- Read **[Why Protostar?](./why-protostar/)** to see how it compares to general-purpose templaters like Copier.
- Head to **[Getting Started](./getting-started/)** to get Protostar onto your system.
- Use **[Environment Initialization](./usage/init/)** to learn the `init` workflow.
- Read **[Mechanics: Executor](./mechanics/executor/)** to see how Protostar safely merges a `pyproject.toml` without breaking existing keys or stripping your comments.
- Visit **[Developer Guide](./developer/overview/)** for architecture, philosophy, and advanced guidance.
