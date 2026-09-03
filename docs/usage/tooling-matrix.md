# Tooling & Flags Matrix

Protostar provides a modular matrix of tooling modules and built-in templates. Tooling modules inject static analysis, testing frameworks, and continuous integration workflows, safely deep-merging configurations into existing project files like `pyproject.toml`.

!!! note "Design Decision: Configuration Portability"
    Even when using `--prek`, Protostar generates a `.pre-commit-config.yaml` file instead of `prek.toml`. Because `prek` fully supports the standard YAML configuration, this strategy ensures maximum ecosystem compatibility. Your repository remains decoupled from the specific hook engine, meaning CI/CD pipelines, IDE plugins (like Dependabot/Renovate), and collaborators using legacy `pre-commit` will still be able to run and update your hooks flawlessly.

!!! tip "Design Decision: Markdown Tooling Architecture"
    Protostar adopts `rumdl` as the default markdown linter and formatter for production templates (`cli`, `api`, `ml`). Because `rumdl` is a fast Rust binary, it installs cleanly as a dev dependency via `uv` (tracked in `uv.lock`) and keeps all configuration consolidated inside `pyproject.toml` (`[tool.rumdl]`). This avoids external Node.js/npx runtime requirements and prevents configuration file sprawl. For projects requiring legacy MarkdownLint tooling, `--markdownlint` remains available as an optional module.

---

## Available Tooling Modules

--8<-- "table_tooling.md"

---

## Built-in Templates

Built-in templates act as high-level macros that execute on top of a base language footprint. They dynamically inject structural scaffolding, directories, and domain-specific dependencies into the environment manifest.

!!! tip "Dynamic Resolution"
    Templates do not hardcode package versions. They pass the library requirements directly to the package manager (`uv`), allowing your environment to resolve the latest compatible telemetry, astrophysics, or API packages at runtime.

--8<-- "table_templates.md"

---

## Related Guides

- __[Environment Initialization](./init.md):__ See complete generated directory trees and configuration footprints for CLI, API, ML, and DSP templates.
- __[Global Configuration](./configuration.md):__ Configure persistent default tooling selections so your preferred flags apply automatically.
- __[CLI Reference](./cli-reference.md):__ Comprehensive reference table for all tri-state tooling flags and CLI options.
