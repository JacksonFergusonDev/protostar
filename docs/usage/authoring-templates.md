# Authoring Custom Templates

Protostar templates allow platform engineers, team leads, and open-source maintainers to define reusable, declarative environment blueprints. By abstracting away the boilerplate of configuring linters, type checkers, and directory hierarchies, templates ensure that new projects adhere to organizational standards from initialization.

Templates scale gracefully from a single declarative TOML file to complex, multi-file repository archives.

---

## Level 1: The Single-File Blueprint

At its simplest, a template is a single TOML file containing the configuration state. You can host this file remotely or keep it on your local machine.

### The Template Schema

Below is the complete annotated schema for a Protostar template. It defines how to declare dependencies, scaffold directories, and override base tooling opinions.

```toml
--8<-- "template_schema.toml"
```

??? tip "Exporting the JSON Schema (`protostar export-schema`)"
    Protostar can generate the official JSON Schema for template files. You can use this for automated validation in external pipelines or configure IDE plugins like VS Code's *Even Better TOML* to get real-time autocompletion and linting:

    ```bash
    # Print formatted schema to terminal:
    protostar export-schema

    # Export machine-readable JSON schema to a file:
    protostar export-schema --json > protostar-template.schema.json
    ```

### AST Injections & Appends

Protostar's true power lies in its ability to safely mutate existing files via Abstract Syntax Tree (AST) deep-merging and marker blocks.

- **`[dev.pyproject]`**: Any table defined here is parsed via `tomlkit` and deeply merged into the target workspace's `pyproject.toml`. This allows you to inject custom linter configurations (e.g., specific Ruff rules) without overwriting your existing dependencies or project metadata.
- **`[appends]`**: For non-TOML files (like `justfile`, `Makefile`, or `.envrc`), you can define generic string payloads. Protostar wraps these payloads in language-aware comment markers (e.g., `# --- Protostar Injection ---`) and safely appends them to the target file.

---

## Level 2: The Multi-File Repository

While the `[files]` table in a single TOML file is excellent for small injections (like a standard `LICENSE` or a minimal `main.py`), complex scaffolds—such as a full FastAPI architecture or a PyTorch training pipeline—require physical files.

When you point the `--from` flag at a remote repository or a local directory archive, Protostar utilizes the following resolution sequence:

1. **Locate the Manifest:** Protostar searches the root of the archive for a `protostar.toml` file to act as the primary configuration blueprint.
1. **Resolve the `template/` Directory:** If a directory named `template/` exists adjacent to the `protostar.toml` file, Protostar recursively maps its contents into the target workspace.

### Example Repository Structure

```text
my-org-fastapi-template/
├── README.md
├── protostar.toml       # The environment manifest
└── template/            # Files here are mapped to your root workspace
    ├── src/
    │   └── <% PACKAGE_NAME %>/
    │       ├── __init__.py
    │       ├── core/
    │       │   └── config.py
    │       └── main.py
    └── tests/
        ├── conftest.py
        └── test_api.py
```

*Note: Protostar automatically ignores compilation artifacts (`__pycache__`) and `.DS_Store` files inside the `template/` directory during extraction.*

---

## Level 3: Variable Interpolation

Protostar features a lightweight, regex-based templating engine that evaluates placeholders wrapped in `<% VARIABLE_NAME %>` delimiters. This interpolation runs across the `protostar.toml` manifest, inline `[files]` strings, and physical files housed within the `template/` directory.

### Built-in Variables

The execution engine automatically computes and injects the following variables based on your CLI inputs, Git configuration, and directory context:

- `<% PROJECT_NAME %>`: The human-readable project name (e.g., `my-cool-app`).
- `<% PACKAGE_NAME %>`: The PEP 8 sanitized Python module identifier (e.g., `my_cool_app`).
- `<% PYTHON_VERSION %>`: The resolved target Python version (e.g., `3.13`).
- `<% CURRENT_YEAR %>`: The current four-digit year (useful for copyright headers).
- `<% AUTHOR_NAME %>`: The author's name, resolved from the global Protostar config or `git config user.name`.

### Custom Variables & Interactive Prompts

You can define custom placeholders tailored to your domain footprint. For example, if your template configures a database connection, you might include:

```python
# template/src/<% PACKAGE_NAME %>/database.py
DATABASE_URL = "<% DATABASE_URL %>"
```

If you initialize the template headlessly via CLI flags:

```bash
protostar init --from https://github.com/Org/template --DATABASE_URL="sqlite:///./test.db"
```

If you *omit* the flag, Protostar parses the AST, detects the unresolved `<% DATABASE_URL %>` placeholder, and automatically halts to prompt you via the interactive terminal wizard before any disk mutations occur.

---

## Level 4: Testing & Distribution

### Local Testing

When authoring a template, you do not need to commit and push to a remote repository to test its execution. You can point the `--from` flag directly at your local template directory:

```bash
# From within an empty target directory
protostar init --from ~/Developer/templates/my-custom-template
```

### Distribution & URL Translation

Once your template is ready, push it to your organization's version control platform. Protostar automatically translates standard web UI URLs into raw downloadable endpoints or archive targets for all major hosting providers (GitHub, GitLab, Bitbucket, Codeberg, and Sourcehut).

You can invoke your template directly:

```bash
protostar init --from https://github.com/YourOrg/data-science-template
```

Or, you can register it as a global alias in your `~/.config/protostar/config.toml` to access it natively in your interactive wizard:

```toml
[templates]
org-ds-base = "https://github.com/YourOrg/data-science-template"
```

### Security Considerations

Protostar enforces an **Informed Consent Security Model**. If your template defines `system_tasks` or `post_install_tasks` (executable shell commands), and you load it directly from an untrusted remote URL via `--from`, Protostar will halt execution and display an interactive security prompt.

Templates registered in your global `config.toml` aliases bypass this prompt. For a complete breakdown of how the runtime evaluates trust boundaries, see the [Remote Trust Model](templates.md#security-model-the-remote-trust-dialog).

---

## Best Practices

When building templates for your team or the open-source community, keep the following guidelines in mind:

- **Choose the Right Complexity:** Start with a single-file blueprint (`protostar.toml`) if you only need to enforce tooling configurations (like Ruff or Pyright rules). Graduate to a multi-file repository only when you need to scaffold physical code, directories, or CI/CD pipelines.
- **Descriptive Variable Names:** Use clear, self-explanatory names for custom placeholders (e.g., `<% AWS_REGION %>` instead of `<% REG %>`). Since Protostar automatically generates interactive terminal prompts for unresolved variables, descriptive names provide a better user experience.
- **Minimize Shell Scripts:** Be cautious with `system_tasks` and `post_install_tasks`. Heavy reliance on shell commands can compromise cross-platform compatibility (e.g., failing on Windows). It also triggers the Informed Consent Security Model for remote URLs, which might alarm users.
- **Test Locally:** Always test your template locally against an empty target directory (`protostar init --from ./path/to/template`) before publishing it to a remote version control platform.

---

## Next Steps

- **[Templates & Portable Configs](./templates.md):** Learn about CLI options, URL translation, and template consumption.
- **[Global Configuration](./configuration.md):** Register your custom templates under `[templates]` in your `config.toml`.
- **[Extending Protostar](../developer/extending-protostar.md):** Implement custom Python bootstrap modules if your project requires engine-level integrations.
