# Portable Configurations

The `--from` feature empowers Protostar to dynamically fetch, render, and apply portable TOML configurations on the fly. This enables teams to standardize environments or inject custom files directly during the scaffolding phase.

This document covers the mechanical lifecycle of a portable configuration template from initial evaluation to AST injection.

---

## 1. Remote Fetching and Resolution

When the CLI detects the `--from` flag, it determines if the target is a local file or a remote URI.

```python
if override_target.startswith("http://") or override_target.startswith("https://"):
    content = fetch_remote_config(override_target)
else:
    target_path = Path(override_target)
    content = target_path.read_text(encoding="utf-8")
```

If the target is a remote URL, `fetch_remote_config` resolves the HTTP/HTTPS request to pull the raw string payload down into memory, completely removing the need for users to manually download configuration files.

## 2. Dynamic Templating

Because portable configurations are designed to be shared, they often contain parameterized fields using Jinja-style placeholders (e.g., `{{ project_name }}`).

Before parsing the TOML, Protostar's templating engine dynamically injects runtime context into the configuration payload.

### Variable Extraction

The raw string is scanned via regex (`extract_variables`) to locate all `{{ variable }}` boundaries. This prevents the system from naively merging a template containing unpopulated variables which would break downstream tooling.

### The CLI Kwarg Parser

When trailing unknown arguments are passed alongside `--from`, `_parse_dynamic_kwargs` intercepts them.

For example, given:

```bash
protostar init --from remote.toml --author="Jane" --version="1.0"
```

The CLI parses these trailing flags into a `template_context` dictionary:

```python
{"author": "Jane", "version": "1.0"}
```

### Interactive Resolution

If the template requires variables not provided in the `template_context`, Protostar triggers an interactive prompt (`resolve_missing_variables`). It asks the user to provide the missing values before proceeding.

### Rendering

The variables are safely escaped (e.g. replacing unescaped newlines and quotation marks) and injected into the template string via `render_template`.

## 3. Configuration Merging

Protostar's `ProtostarConfig.load` uses a unified loading strategy:

1. **Base User Config**: It reads the global config at `~/.config/protostar/config.toml` (if it exists) to establish the user's defaults.
1. **Template Overlay**: It takes the dynamically rendered portable configuration and passes it into `_parse_and_merge`.
1. **Surgical Overlay**: `_parse_and_merge` reads the incoming TOML and updates the `ProtostarConfig` object in-memory.

This guarantees that a user's local baseline defaults (like `ide = "vscode"`) remain intact unless explicitly overwritten by the portable configuration.

---

## The Abstract Syntax Tree Handoff

Once the portable configuration is merged into the global `ProtostarConfig` object, it behaves exactly like standard configurations. The Orchestrator resolves the dependency graph and the Executor performs its safe AST merging into the repository's files.
