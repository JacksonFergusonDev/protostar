# Agent & Machine Interface

Protostar features an experimental, machine-readable command-line interface designed specifically for AI coding agents, CI/CD pipelines, and automated developer tooling.

By passing the position-independent `--json` flag and utilizing the `--dry-run` phase, external agents can programmatically inspect Protostar's capabilities, simulate environment scaffolding without side-effects, automatically handle collisions, and safely execute operations.

- **Operational Strictness**

  `stdout` is strictly reserved for the machine-readable JSON payload. All human-readable logging, diagnostic summaries, and tracebacks are routed exclusively to `stderr`. Agents can safely ignore `stderr` and parse `stdout` directly.

- **Zero Interactive Blocking**

  In `--json` mode, interactive TUI prompts (such as collision prompts or security trust dialogs) are bypassed. Untrusted templates raise immediate error payloads, and existing workspace collisions return structured collision paths.

- **Deterministic Simulation (`--dry-run`)**

  The `--dry-run` flag executes the headless `plan()` phase without writing files or running shell subprocesses, returning the full `EnvironmentManifest` as a structured dictionary.

- **Template Schema Validation**

  The `export-schema` subcommand exports the official JSON Schema for TOML templates, allowing agents to validate dynamically generated template files ahead of execution.

______________________________________________________________________

## The Machine Protocol

Protostar marks its machine interface with an explicit `api_version` field in all JSON payloads (`"api_version": 0` during the experimental phase).

The CLI uses a position-independent `--json` flag that can appear anywhere in the argument list (e.g., `protostar --json`, `protostar init --template cli --json`, or `protostar --json init`).

### Protocol States

Every JSON response emitted to `stdout` follows one of three structured envelopes:

Emitted when running `protostar init --dry-run --json`. Returns the complete planned `manifest`.

```json
{
  "api_version": 0,
  "status": "planned",
  "manifest": {
    "collision_strategy": "merge",
    "force_merge": false,
    "force_replace": false,
    "metadata": {
      "description": "High-velocity CLI application.",
      "author_name": "Demo Author",
      "license": "MIT"
    },
    "ide_settings": {
      "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
      "python.terminal.activateEnvironment": true
    },
    "dependencies": {
      "dependencies": [],
      "dev_dependencies": [
        "ruff"
      ],
      "docs_dependencies": []
    },
    "filesystem": {
      "directories": [],
      "file_injections": {
        "LICENSE": "MIT License\n\nCopyright (c) <% CURRENT_YEAR %> <% AUTHOR_NAME %>\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n"
      },
      "file_appends": {
        "pyproject.toml": [
          "[project]\ndescription = \"High-velocity CLI application.\"\nreadme = \"README.md\"\nauthors = [{ name = \"Demo Author\", email = \"your-email\" }]\nlicense = { file = \"LICENSE\" }\nclassifiers = [\n    \"License :: OSI Approved :: MIT License\",\n]\n",
          "[tool.ruff]\nline-length = 88\n\n[tool.ruff.lint]\nselect = [\n    \"A\",   # flake8-builtins\n    \"B\",   # flake8-bugbear\n    \"C4\",  # flake8-comprehensions\n    \"E\",   # pycodestyle errors\n    \"F\",   # Pyflakes\n    \"I\",   # isort\n    \"RUF\", # Ruff-specific\n    \"UP\",  # pyupgrade\n]\nignore = [\n    \"E501\", # Line too long - handled automatically by `ruff format`\n]\n"
        ]
      },
      "vcs_ignores": [
        "*~",
        ".DS_Store",
        ".cache/",
        ".env",
        ".idea/",
        ".ruff_cache/",
        ".venv/",
        ".vscode/",
        "Thumbs.db",
        "__pycache__/"
      ],
      "workspace_hides": [
        "*~",
        ".DS_Store",
        ".cache/",
        ".env",
        ".idea/",
        ".ruff_cache/",
        ".venv/",
        ".vscode/",
        "Thumbs.db",
        "__pycache__/"
      ]
    },
    "tooling": {
      "wants_pre_commit": false,
      "wants_prek": false,
      "pre_commit_hooks": [],
      "pre_commit_local_hooks": [
        "      - id: ruff-check\n        name: ruff check\n        entry: uv run ruff check --fix\n        language: system\n        types: [python]\n        require_serial: true\n\n      - id: ruff-format\n        name: ruff format\n        entry: uv run ruff format\n        language: system\n        types: [python]\n        require_serial: true"
      ],
      "wants_ci": false,
      "wants_release": false,
      "ci_flags": [],
      "ci_steps": [
        "      - name: Run Ruff Linter\n        run: uv run ruff check --output-format=github .\n\n      - name: Run Ruff Formatter\n        run: uv run ruff format --check --output-format=github ."
      ],
      "wants_just": false,
      "just_format_commands": [
        "uv run ruff check --fix .",
        "uv run ruff format ."
      ],
      "just_lint_commands": [
        "uv run ruff check .",
        "uv run ruff format --check ."
      ],
      "just_typecheck_commands": [],
      "just_clean_paths": [
        ".ruff_cache"
      ],
      "ide_extensions": [
        "charliermarsh.ruff"
      ]
    },
    "tasks": {
      "system_tasks": [],
      "post_install_tasks": []
    }
  }
}
```

Emitted upon successful environment execution via `protostar init --json` or discovery via `protostar --json`.

```json
{
  "api_version": 0,
  "status": "success",
  "result": {
    "touched_paths": [
      ".gitignore",
      "pyproject.toml",
      "src/my_app/__init__.py",
      "tests/test_cli.py"
    ],
    "diagnostics": []
  }
}
```

Emitted when a domain validation or runtime error occurs. Standard POSIX exit codes are maintained.

```json
{
  "api_version": 0,
  "status": "error",
  "error": {
    "type": "WorkspaceCollisionError",
    "message": "Workspace collision detected: existing configuration files found in the workspace:\n  - pyproject.toml\nUse --force-merge or --force-replace to bypass, or resolve interactively.",
    "docs_url": "https://protostar.readthedocs.io/en/stable/usage/troubleshooting/#workspace-collisions",
    "paths": [
      "pyproject.toml"
    ]
  }
}
```

______________________________________________________________________

## The Agent Scaffolding Lifecycle

AI agents can interact with Protostar using a predictable three-phase lifecycle:

```
%%{init: {'sequence': {'mirrorActors': false, 'diagramMarginY': 30, 'bottomMarginAdj': 50}}}%%
sequenceDiagram
    autonumber
    actor Agent as AI Agent
    participant CLI as Protostar CLI
    participant Disk as Local Workspace

    Agent->>CLI: Phase 1: Request Capabilities
    CLI-->>Agent: Return capabilities schema

    Agent->>CLI: Phase 2: Request Dry-Run Plan
    CLI-->>Agent: Return planned manifest

    Agent->>CLI: Phase 3: Execute Scaffold
    CLI->>Disk: Apply disk mutations & tasks
    CLI-->>Agent: Return Success
```

### 1. Capabilities Discovery

An agent can interrogate the CLI to discover available commands, flags, and built-in templates:

```bash
protostar --json
```

Or inspect a specific command's arguments:

```bash
protostar init --help --json
```

### 2. Dry-Run Planning

Before touching the filesystem, an agent should run with `--dry-run --json` to inspect the planned changes:

```bash
protostar init --template astro --dry-run --json
```

The resulting payload exposes all directories, injected file contents, dependencies, and shell commands that Protostar plans to execute.

#### Collision Handling & Recovery

If the target workspace already contains files (such as an existing `pyproject.toml` or `README.md`), Protostar will not prompt interactively in JSON mode. Instead, it exits with an error payload:

```json
{
  "api_version": 0,
  "status": "error",
  "error": {
    "type": "WorkspaceCollisionError",
    "message": "Workspace collision detected: existing configuration files found in the workspace:\n  - pyproject.toml\nUse --force-merge or --force-replace to bypass, or resolve interactively.",
    "docs_url": "https://protostar.readthedocs.io/en/stable/usage/troubleshooting/#workspace-collisions",
    "paths": [
      "pyproject.toml"
    ]
  }
}
```

The agent can parse the `"paths"` array and choose how to proceed:

- Pass `--force-merge` to safely deep-merge configurations and append ignore rules.
- Pass `--force-replace` to overwrite existing configuration files.

### 3. Headless Execution

Once the plan is verified, the agent executes initialization:

```bash
protostar init --template astro --force-merge --json
```

Upon completion, the agent receives a list of all `touched_paths` that were created or modified on disk.

______________________________________________________________________

## Template Schema Export

When agents generate custom Protostar template TOML files dynamically, they can validate their syntax against the official schema.

Run `protostar export-schema` to export the JSON Schema:

```bash
# Pretty-printed, syntax-highlighted for human review:
protostar export-schema

# Compact JSON for machine validation:
protostar export-schema --json > protostar-template.schema.json
```

Agents can use standard JSON Schema validators (e.g., `jsonschema` in Python or `ajv` in JavaScript) to verify their generated blueprints before invoking `protostar init --from <file>`.

______________________________________________________________________

## Related Architecture & Next Steps

- **[The Environment Manifest](../../mechanics/manifest/):** Detailed structure and domain slices of the in-memory state object serialized during `--dry-run --json`.
- **[Error Handling Architecture](../../mechanics/error_handling/):** Deep dive into machine error envelopes, collision paths, and POSIX exit code mappings.
- **[CLI Reference](.././cli-reference/):** Full list of subcommands, global flags, and exit status codes.
