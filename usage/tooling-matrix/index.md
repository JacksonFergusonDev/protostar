# Tooling & Flags Matrix

Protostar provides a modular matrix of tooling modules and built-in templates. Tooling modules inject static analysis, testing frameworks, and continuous integration workflows, safely deep-merging configurations into existing project files like `pyproject.toml`.

Design Decision: Configuration Portability

Even when using `--prek`, Protostar generates a `.pre-commit-config.yaml` file instead of `prek.toml`. Because `prek` fully supports the standard YAML configuration, this strategy ensures maximum ecosystem compatibility. Your repository remains decoupled from the specific hook engine, meaning CI/CD pipelines, IDE plugins (like Dependabot/Renovate), and collaborators using legacy `pre-commit` will still be able to run and update your hooks flawlessly.

Design Decision: Markdown Tooling Architecture

Protostar adopts `rumdl` as the default markdown linter and formatter for production templates (`cli`, `api`, `ml`). Because `rumdl` is a fast Rust binary, it installs cleanly as a dev dependency via `uv` (tracked in `uv.lock`) and keeps all configuration consolidated inside `pyproject.toml` (`[tool.rumdl]`). This avoids external Node.js/npx runtime requirements and prevents configuration file sprawl. For projects requiring legacy MarkdownLint tooling, `--markdownlint` remains available as an optional module.

______________________________________________________________________

## Available Tooling Modules

| Tooling Module         | CLI Flags        | Description                                                                   | Collision Markers             |
| ---------------------- | ---------------- | ----------------------------------------------------------------------------- | ----------------------------- |
| direnv                 | `--direnv`       | Scaffold a .envrc and evaluate the virtual environment                        | `.envrc`                      |
| MarkdownLint           | `--markdownlint` | Scaffold a relaxed .markdownlint-cli2.yaml configuration                      | `.markdownlint-cli2.yaml`     |
| Rumdl                  | `--rumdl`        | Scaffold rumdl fast markdown linter and formatter                             | *None*                        |
| Ruff                   | `--ruff`         | Scaffold Ruff linter and formatter                                            | *None*                        |
| Mypy                   | `--mypy`         | Scaffold Mypy static type checker                                             | *None*                        |
| Ty                     | `--ty`           | Scaffold Ty static type checker                                               | *None*                        |
| Pyrefly                | `--pyrefly`      | Scaffold pyrefly static type checker                                          | *None*                        |
| Pytest                 | `--pytest`       | Scaffold Pytest testing framework                                             | *None*                        |
| Pre-Commit             | `--pre-commit`   | Scaffold pre-commit hooks and configuration                                   | `.pre-commit-config.yaml`     |
| Prek                   | `--prek`         | Scaffold prek hooks and configuration (faster Rust alternative to pre-commit) | `.pre-commit-config.yaml`     |
| Commitizen             | `--commitizen`   | Scaffold commitizen version bumping and changelog tooling                     | *None*                        |
| Renovate               | `--renovate`     | Scaffold Renovate dependency update configuration                             | `renovate.json`               |
| Codecov                | `--codecov`      | Scaffold Codecov configuration                                                | `codecov.yml`                 |
| Zensical               | `--zensical`     | Scaffold Zensical documentation                                               | `mkdocs.yml`, `docs`          |
| Read the Docs          | `--readthedocs`  | Scaffold Read the Docs configuration                                          | `.readthedocs.yaml`           |
| GitHub Actions CI      | `--ci`           | Scaffold standard GitHub Actions CI workflows                                 | `ci.yml`                      |
| GitHub Actions Release | `--release`      | Scaffold GitHub Actions PyPI release workflows                                | `release.yml`                 |
| Just                   | `--just`         | Scaffold a justfile for command execution                                     | `justfile`                    |
| Docker                 | `--docker`       | Multi-stage `Dockerfile` and `.dockerignore` container scaffolding            | `Dockerfile`, `.dockerignore` |

______________________________________________________________________

## Built-in Templates

Built-in templates act as high-level macros that execute on top of a base language footprint. They dynamically inject structural scaffolding, directories, and domain-specific dependencies into the environment manifest.

Dynamic Resolution

Templates do not hardcode package versions. They pass the library requirements directly to the package manager (`uv`), allowing your environment to resolve the latest compatible telemetry, astrophysics, or API packages at runtime.

| Template   | Invocation                           | Dependencies                                                                                          |
| ---------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `api`      | `protostar init --template api`      | `fastapi`, `uvicorn`, `pydantic-settings`                                                             |
| `astro`    | `protostar init --template astro`    | `numpy`, `scipy`, `pandas`, `matplotlib`, `astropy`, `astroquery`, `photutils`, `specutils`, `nbdime` |
| `cli`      | `protostar init --template cli`      | `typer`, `rich`                                                                                       |
| `dsp`      | `protostar init --template dsp`      | `librosa`, `soundfile`, `scipy`, `numpy`, `matplotlib`, `pedalboard`                                  |
| `embedded` | `protostar init --template embedded` | `pyserial`, `mpremote`                                                                                |
| `ml`       | `protostar init --template ml`       | `torch`, `scikit-learn`, `pandas`, `numpy`, `matplotlib`, `tqdm`                                      |

______________________________________________________________________

## Related Guides

- **[Environment Initialization](.././init/):** See complete generated directory trees and configuration footprints for CLI, API, ML, and DSP templates.
- **[Global Configuration](.././configuration/):** Configure persistent default tooling selections so your preferred flags apply automatically.
- **[CLI Reference](.././cli-reference/):** Comprehensive reference table for all tri-state tooling flags and CLI options.
