| Tooling Module | CLI Flags | Description | Scaffolded Files |
| :--- | :--- | :--- | :--- |
| direnv | `--direnv` | Activate the project's environment whenever you enter its folder | `.envrc` |
| MarkdownLint | `--markdownlint` | Check Markdown files for formatting mistakes, with relaxed rules | `.markdownlint-cli2.yaml` |
| Rumdl | `--rumdl` | Check and format Markdown files quickly | *None* |
| Ruff | `--ruff` | Find common bugs and style problems in Python code, and format it | *None* |
| Mypy | `--mypy` | Check type hints to catch mistakes before the code runs | *None* |
| Ty | `--ty` | Check type hints quickly, with Astral's type checker | *None* |
| Pyrefly | `--pyrefly` | Check type hints quickly, with Meta's type checker | *None* |
| Pytest | `--pytest` | Run the project's tests | *None* |
| Pre-Commit | `--pre-commit` | Run the project's checks automatically each time you commit | `.pre-commit-config.yaml` |
| Prek | `--prek` | Run the project's checks automatically each time you commit, faster | `.pre-commit-config.yaml` |
| Commitizen | `--commitizen` | Write commit messages in a standard form that sets the next version | `CHANGELOG.md` |
| Renovate | `--renovate` | Open pull requests that keep dependencies up to date | `.github/renovate.json` |
| Codecov | `--codecov` | Report how much of the code the tests exercise, on each pull request | `.github/codecov.yml` |
| Zensical | `--zensical` | Build a documentation website from Markdown files | `docs/index.md`, `zensical.toml` |
| Read the Docs | `--readthedocs` | Publish the documentation website on Read the Docs | `.readthedocs.yaml` |
| GitHub Actions CI | `--ci` | Run the checks and tests on GitHub for every push and pull request | `.github/workflows/ci.yml` |
| GitHub Actions Release | `--release` | Publish the package to PyPI when you push a version tag | `.github/workflows/release.yml` |
| Just | `--just` | Give the project's common commands short names, like `just test` | `justfile` |
| Agents | `--agents` | Tell coding assistants how to work on the project | `AGENTS.md` |
| Community | `--community` | Add the files GitHub shows people who want to contribute | `.github/ISSUE_TEMPLATE/bug_report.yml`, `.github/ISSUE_TEMPLATE/feature_request.yml`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CONTRIBUTING.md`, `.github/pull_request_template.md` |
| Docker | `--docker` | Multi-stage `Dockerfile` and `.dockerignore` container scaffolding | `Dockerfile`, `.dockerignore` |
