# Templates & Portable Configurations

The `--template` and `--from` features empower Protostar to dynamically fetch, render, and apply TOML configurations on the fly. This enables teams to standardize environments or inject custom files directly during the scaffolding phase.

This document covers the mechanical lifecycle of a configuration template from initial evaluation to AST injection.

---

## 1. Resolution and Fetching

When the CLI detects the `--template` or `--from` flag, it resolves the target configuration.

- **`--template <name>`:** Resolves to a built-in configuration file shipped inside `protostar.templates` (via `importlib.resources`).
- **`--from <uri>`:** Determines if the target is a local file or a remote URI.

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

### The `active_presets` Validation Trap

Templates can define an `active_presets` list in their `[env]` block to automatically toggle domain pipelines. However, if a user accidentally places `active_presets` in their *global* `~/.protostar.toml` file, it would irreversibly force that preset onto every future repository they scaffold!

To prevent this, `config.py` uses a validation trap. `active_presets` is strictly validated using Python's `typing.get_origin`. If the TOML parser encounters it during the **Base User Config** phase, the global loader intentionally drops the key or errors out, ensuring it can *only* be safely applied during the **Template Overlay** phase.

---

## 4. The CLI Precedence Chain

Once the `ProtostarConfig` object is fully loaded with the template overlay, control is handed back to `cli.py` (`handle_init`).

Because users need to be able to temporarily disable a tool that a template enables by default, Protostar employs a strict precedence chain: `Global Defaults < Template Defaults < CLI Overrides`.

To achieve this, dynamically mounted CLI flags (e.g., `--astro`, `--direnv`) use `argparse.BooleanOptionalAction`. This allows the CLI to differentiate between a flag that wasn't passed (`None`), a flag that was explicitly passed (`True`), and a flag that was explicitly negated (`False` via `--no-<flag>`).

If a CLI flag is explicitly provided (not `None`), it forcefully overrides whatever boolean state the template requested.

---

## The Abstract Syntax Tree Handoff

Once the portable configuration is merged into the global `ProtostarConfig` object, it behaves exactly like standard configurations. The Orchestrator resolves the dependency graph and the Executor performs its safe AST merging into the repository's files.
