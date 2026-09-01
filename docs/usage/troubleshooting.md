# Troubleshooting & FAQ

This guide provides remediation steps for common operational errors, environment constraints, and editor integrations when using Protostar.

<div class="spacer-2"></div>

---

## Missing Dependencies & Environment Checks

Protostar verifies system-level dependencies during its `pre_flight()` phase before writing files or modifying configurations. If a required binary is missing, execution halts with a `MissingDependencyError`.

### `uv` is not installed or not in `$PATH`

Protostar strongly recommends [uv](https://docs.astral.sh/uv/) for high-velocity package resolution and environment management.

=== "macOS & Linux"
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Homebrew (macOS)"
    ```bash
    brew install uv
    ```

=== "Windows (PowerShell)"
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

!!! tip "Verifying `$PATH` Resolution"
    If you installed tools via `uv tool`, ensure your shell's environment includes `~/.local/bin`:
    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    ```

### Optional Binaries (`direnv`, `just`, `prek`)

If an optional tool (such as `direnv` or `just`) is not installed on your system when requested, Protostar logs a non-fatal diagnostic warning and safely skips subprocess initialization without aborting repository creation.

---

## Workspace Collisions

When Protostar detects pre-existing configuration markers (such as an existing `pyproject.toml` or `README.md`) in the target workspace, it raises a `WorkspaceCollisionError` to protect your existing work.

```text
Gravitational Anomaly: Protostar detected existing configuration files in the workspace.
  - pyproject.toml
```

### Interactive Resolution

In interactive terminals, you can choose from three strategies:

1. **Merge (Default):** Deep-merges AST tables and arrays into `pyproject.toml` and appends missing rules to `.gitignore`, preserving all custom user settings and comments.
1. **Overwrite:** Overwrites existing configuration keys with Protostar's baseline standards.
1. **Abort:** Safely cancels the operation without making changes.

### Automated Environments (CI/CD & Agents)

In non-interactive environments or when running with `--json`, interactive prompts are disabled. Pass explicit strategy flags to proceed:

```bash
# Safely deep-merge into existing configs:
protostar init --template cli --force-merge

# Forcefully overwrite existing configs:
protostar init --template cli --force-replace
```

---

## Remote Template Security Alerts

When you load a template from an untrusted remote URL (`--from https://...`) that contains executable `system_tasks` or `post_install_tasks`, Protostar halts execution to display the **Informed Consent Security Dialog**:

```text
⚠️  REMOTE TEMPLATE WARNING ⚠️

This template was loaded from an external source and will execute the following shell commands on your system:
  - uv run nbdime config-git --enable

Do you trust this source to modify your system? [y/N]
```

### Bypassing Prompts for Trusted Templates

To permanently trust a remote or team template and bypass security prompts:

1. Run `protostar config` to open your global settings.
1. Register the template under the `[templates]` table:

```toml
[templates]
team-backend = "https://raw.githubusercontent.com/YourOrg/standards/main/backend.toml"
```

1. Invoke it via shorthand: `protostar init --template team-backend`.

---

## Editor Schema Setup for Custom Templates

Protostar templates are pure TOML files validated against a JSON Schema. Configuring your editor provides instant autocompletion, hover tooltips, and real-time schema validation.

### VS Code & Cursor

1. Install the **Even Better TOML** extension (`tamasfe.even-better-toml`).
1. Add the schema modeline at the top of your custom `protostar.toml` file:

```toml
#:schema https://raw.githubusercontent.com/jacksonfergusondev/protostar/main/schemas/template.schema.json

name = "my-custom-template"
dependencies = ["fastapi", "uvicorn"]
ruff = true
```

Alternatively, export the schema locally for offline validation:

```bash
protostar export-schema --json > protostar-template.schema.json
```

### JetBrains (PyCharm / IntelliJ)

1. Open **Settings / Preferences** $\to$ **Languages & Frameworks** $\to$ **Schemas and DTDs** $\to$ **JSON Schema Mappings**.
1. Add a new mapping named `Protostar Template`.
1. Set the schema URL to `https://raw.githubusercontent.com/jacksonfergusondev/protostar/main/schemas/template.schema.json`.
1. Add the file pattern `*protostar*.toml`.

---

## Debugging & Bug Reporting

### Verbose Debugging (`--verbose`)

To view full Python tracebacks and detailed debug logs, append `-v` or `--verbose` to any command:

```bash
protostar init --template cli --verbose
```

### Automated Crash Reporting

If Protostar encounters an unexpected internal error or AST collapse:

1. It traps the exception to prevent incomplete disk operations.
1. It collects non-sensitive system environment vectors (OS, Python version, command invocation).
1. It outputs a URL-encoded link that opens a pre-formatted GitHub issue ticket with the exact telemetry attached.

---

## Related Resources

- **[Error Handling Architecture](../mechanics/error_handling.md):** Deep dive into the domain exception hierarchy, POSIX exit codes, and subprocess telemetry.
- **[Environment Initialization](./init.md):** Review collision handling, AST injection, and `--force-merge` behavior.
- **[Global Configuration](./configuration.md):** Learn how to view, modify, or reset your global settings with `protostar config --reset`.
