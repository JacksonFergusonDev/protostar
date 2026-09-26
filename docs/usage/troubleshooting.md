# Troubleshooting & FAQ

This guide provides remediation steps for common operational errors, environment constraints, and editor integrations when using Protostar.

## Missing Dependencies & Environment Checks

Protostar needs `uv` and `git` for every project, and checks for them before writing files or modifying configurations. If either is missing, execution halts with a `MissingDependencyError` whose hint is one command that installs everything missing.

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

### Tool Binaries (`direnv`, `just`)

A binary that only a selected tool runs never stops a run. The tool's files are still written, since they are correct whether or not the binary is installed. Protostar reports the binary in the result's `missing_tools` and skips only the steps that need it: without `direnv`, run `direnv allow` in the project once it is installed.

## Workspace Collisions

When Protostar detects pre-existing files (such as an existing `pyproject.toml` or `README.md`) matching planned manifest targets in the target workspace, it raises a `WorkspaceCollisionError` to protect your existing work.

```text
Workspace Collision: Protostar detected existing configuration files in the workspace.
  - pyproject.toml
```

### Interactive Resolution

In interactive terminals, you can choose from three strategies:

1. **Merge (Default):** Reconciles previously managed TOML/YAML contributions (including GitHub Actions workflows) and line-merged generated files such as the `justfile` while preserving unowned content, local edits, and deletions. It also appends missing rules to `.gitignore`.
1. **Overwrite:** Overwrites existing configuration keys with Protostar's baseline standards.
1. **Abort:** Safely cancels the operation without making changes.

### Automated Environments (CI/CD & Agents)

In non-interactive environments or when running with `--json`, interactive prompts are disabled. Pass explicit strategy flags to proceed:

```bash
# Safely reconcile an already managed workspace:
protostar init --template cli --force-merge

# Forcefully overwrite existing configs:
protostar init --template cli --force-replace
```

## Remote Template Security Alerts

When you load a template from an untrusted remote URL (`--from https://...`) that contains executable `system_tasks` or `post_install_tasks`, Protostar lists its exact commands under **Untrusted template** in the change review. **Apply** stays disabled until you tick the checkbox confirming those commands, and only the commands you confirmed run.

### Bypassing Prompts for Trusted Templates

To permanently trust a remote or team template and bypass security prompts:

1. Run `protostar config` to open your global settings.
1. Register the template under the `[templates.<alias>]` table with `trusted = true`:

```toml
[templates.team-backend]
source = "https://raw.githubusercontent.com/YourOrg/standards/main/backend.toml"
name = "Team Backend"
description = "Internal FastAPI microservice template"
trusted = true
```

1. Invoke it via shorthand: `protostar init --template team-backend`. External templates configured with `trusted = true` bypass interactive confirmation dialogs and execute cleanly in non-interactive CI/CD pipelines.

## Template Variables That Look Like Credentials

Template variables are saved to your project's recipe and rendered into its files, so Protostar holds back a newly entered value that looks like a credential before anything is written:

```text
Template variable values look like credentials:
  - org_name (gitleaks rule github-pat)
```

The error names the variable and the [gitleaks](https://github.com/gitleaks/gitleaks) rule it matched, never the value. In `--json` mode the same pairs appear under `error.findings`. In an interactive terminal, a flagged `--var` value opens the variables screen instead of failing, so you can change it or keep it there.

- **You entered a secret:** enter a non-secret value instead, and supply the secret through the environment when the project runs.
- **The template asks for a secret:** the template needs fixing; see [Variables Are Not Secrets](authoring-templates.md#variables-are-not-secrets).
- **The value isn't a secret:** keep it. In the editor, tick **Not a secret; keep this value** under the field. On the command line, add `--allow-secret NAME` for that variable. The confirmation covers only that variable, and once the value is recorded, later runs don't ask again. If a rule flags ordinary values often, [file an issue](https://github.com/JacksonFergusonDev/protostar/issues) with the rule id and the value's shape (not the value).

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

## Execution Interruptions & Rollback

If an error occurs or you press `Ctrl+C` mid-run, Protostar automatically restores your workspace.

!!! info "Dedicated rollback guide"
    Full documentation on what gets restored, what might remain, `RollbackFailedError` remediation, and `Ctrl+C` behavior is in the [Automatic Rollback](./rollback.md) guide.

## Debugging & Bug Reporting

### Verbose Debugging (`--verbose`)

To view full Python tracebacks and detailed debug logs, append `-v` or `--verbose` to any command:

```bash
protostar init --template cli --verbose
```

### Automated Crash Reporting

If Protostar encounters an unexpected internal error or AST parse failure:

1. It traps the exception to prevent incomplete disk operations.
1. It collects non-sensitive system environment details (OS, Python version, command invocation).
1. It outputs a URL-encoded link that opens a pre-formatted GitHub issue ticket with the exact crash details attached.

### Filing Bugs & Asking Questions

If you encounter an issue or behavior not covered in this guide:

- **Search Existing Issues:** Check the [GitHub Issues tracker](https://github.com/jacksonfergusondev/protostar/issues) to see if a workaround or fix already exists.
- **Open a Bug Report:** If you've found a bug or unexpected behavior, [open a new issue](https://github.com/jacksonfergusondev/protostar/issues/new) with your environment details and `--verbose` output attached.
- **Community Support:** For general questions, configuration help, or workflow ideas, start a thread in [GitHub Discussions](https://github.com/jacksonfergusondev/protostar/discussions).

## Related Resources

- **[Automatic Rollback](./rollback.md):** What gets restored, what might remain, and how to recover from a partial rollback failure.
- **[Error Handling Architecture](../mechanics/error_handling.md):** Deep dive into the domain exception hierarchy, POSIX exit codes, and subprocess diagnostics.
- **[Environment Initialization](./init.md):** Review collision handling, AST injection, and `--force-merge` behavior.
- **[Global Configuration](./configuration.md):** Learn how to view, modify, or reset your global settings with `protostar config --reset`.
