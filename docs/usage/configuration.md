Your global configuration file acts as the singular source of truth for environment initialization. Instead of hunting down the file path, you can open it directly in your system's default `$EDITOR` by running:

```bash
protostar config
```

## The Default Baseline

If you just installed Protostar, this is your baseline configuration. It dictates base environment toggles, preferred developer tools, package managers, and domain-specific dependency overrides.

--8<-- "default_config.md"

Because `protostar init` always reads from this global file, you maintain a consistent, reproducible development signature across every new project you scaffold.

## Deep Dive: The Configuration Matrix

For power users, Protostar's configuration goes far beyond simple boolean toggles. You can define complete dependency footprints, map out directory structures, and inject raw multi-line strings directly into the Abstract Syntax Tree (AST) of target configuration files.

### Pipeline Overrides

You can define explicit overrides for any of the domain presets (e.g., `astro`, `scientific`, `dsp`, `ml`).

Suppose you frequently build data analysis pipelines to process raw radio telescope telemetry or analyze differential fungal growth rates. You can override the `[presets.astro]` or `[presets.scientific]` blocks to automatically generate your exact architecture:

```toml
[presets.astro]
# The primary dependencies required for the pipeline
dependencies = ["astropy", "astroquery", "photutils", "specutils"]
# Development and testing libraries
dev_dependencies = ["pytest-benchmark"]
# The data structures required to hold the observations
directories = ["data/catalogs", "data/fits", "data/raw"]
```

When you run `protostar init --astro`, the orchestrator reads this block, dynamically injects the packages using your configured package manager, and scaffolds the required directories.

### Development Overrides (`[dev]`)

The `[dev]` block allows you to force configurations across *all* initialized environments, regardless of the flags provided at runtime.

#### Extra Dependencies

If you have a tool you use universally (like a version bumper or specific LSP extension), append it here to have it installed as a dev-dependency on every run.

```toml
[dev]
extra_dependencies = ["bump-my-version", "pyright"]
```

#### pyproject.toml Injections

The `[dev.pyproject]` block is one of Protostar's most powerful features. You can define raw, multi-line TOML strings that the orchestrator will safely deep-merge into the target `pyproject.toml`'s Abstract Syntax Tree.

This is highly effective for maintaining a universal static analysis or linting baseline.

```toml
[dev.pyproject]
custom_ruff = '''
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "T20", "PT", "C4", "D"]
ignore = ["E501", "D100", "D104", "D107"]

[tool.ruff.lint.isort]
section-order = ["future", "standard-library", "third-party", "first-party", "local-folder"]
'''
```

## Portable Configurations (`--from`)

The `--from` flag allows you to initialize or augment an environment using a portable TOML configuration template. This is incredibly useful for standardizing team workflows, sharing custom architectures across repositories, or maintaining a universal remote configuration.

When using the `--from` flag, Protostar first reads your global configuration, then overlays the portable configuration on top.

### Sourcing Portable Configurations

You can source portable configurations either locally from your filesystem or remotely via HTTP/HTTPS.

**From a Local File:**

```bash
protostar init --from ./team-config.toml
```

**From a Remote URL:**

```bash
protostar init --from https://raw.githubusercontent.com/org/configs/main/protostar.toml
```

### Passing Template Variables

Portable configurations can contain ERB-style placeholders (e.g., `<% project_name %>`). You can satisfy these variables by passing them as dynamic keyword arguments alongside the `--from` flag:

```bash
protostar init --from ./template.toml --project_name="MyApp" --author="Jane Doe"
```

If the template requires variables that you haven't provided via CLI flags, Protostar will interactively prompt you for the missing values.

### Authoring Custom Templates

Creating a portable template is functionally identical to modifying your own global configuration, but with the added ability to leverage `<% variable %>` templating and preset composition.

A portable TOML template can contain any of the following standard sections:

- `[env]`: Base environment settings (e.g., `python_version = "3.12"`, `ide = "vscode"`, `ruff = true`).
  - `active_presets`: A special list in the `[env]` block (e.g., `active_presets = ["astro"]`). This allows templates to declaratively activate domain presets without requiring the user to pass flags.
- `[presets.preset_name]`: Overrides for specific preset dependencies and directories.
- `[dev]`: Instructions for injecting `extra_dependencies` or raw `pyproject` string injections.
- `[files]`: A powerful block mapping relative file paths to raw string content. This is perfect for scaffolding `README.md` files or custom scripts.
- `[variables]`: Arbitrary key-value metadata for the configuration.

#### Example: A Team Initialization Template

```toml
[env]
python_version = "3.12"
ruff = true
pytest = true
ide = "vscode"

[dev]
extra_dependencies = ["pytest-cov", "httpx"]

[files]
"README.md" = '''
# <% project_name %>

Scaffolded by Protostar for team <% team_name %>.

## Setup
Run `uv sync` to install dependencies.
```
