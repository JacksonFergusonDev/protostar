| Setting | Type | Description |
| :--- | :--- | :--- |
| `ide` | `"vscode"` \| `"cursor"` \| `"none"` | The preferred IDE (e.g., 'vscode', 'cursor', 'none'). |
| `author_name` | `str` \| `None` | Default author name for project metadata. |
| `author_email` | `str` \| `None` | Default author email for project metadata. |
| `github_username` | `str` \| `None` | Default GitHub username for repository URL formatting. |
| `direnv` | `bool` | Whether to auto-scaffold .envrc shell bindings. |
| `python_version` | `str` \| `None` | The specific Python version to scaffold. |
| `license` | `str` \| `None` | Default project license identifier (e.g., 'MIT', 'Apache-2.0'). |
| `supported_os` | `list[str]` | The supported operating systems to scaffold CI for. |
| `markdownlint` | `bool` | Whether to auto-scaffold MarkdownLint configs. |
| `rumdl` | `bool` | Whether to auto-scaffold rumdl fast markdown linter and formatter. |
| `ruff` | `bool` | Whether to auto-scaffold Ruff dependencies and configs. |
| `mypy` | `bool` | Whether to auto-scaffold Mypy dependencies and configs. |
| `ty` | `bool` | Whether to auto-scaffold Astral ty type checker. |
| `pyrefly` | `bool` | Whether to auto-scaffold Pyrefly type checker. |
| `pytest` | `bool` | Whether to auto-scaffold Pytest dependencies and configs. |
| `pre_commit` | `bool` | Whether to auto-scaffold pre-commit hooks. |
| `prek` | `bool` | Whether to auto-scaffold prek git hooks. |
| `commitizen` | `bool` | Whether to auto-scaffold commitizen version bumping and changelog tooling. |
| `renovate` | `bool` | Whether to auto-scaffold Renovate dependency update configuration. |
| `codecov` | `bool` | Whether to auto-scaffold Codecov configuration. |
| `zensical` | `bool` | Whether to auto-scaffold Zensical documentation. |
| `readthedocs` | `bool` | Whether to auto-scaffold Read the Docs configuration. |
| `ci` | `bool` | Whether to auto-scaffold standard GitHub Actions CI workflows. |
| `release` | `bool` | Whether to auto-scaffold GitHub Actions PyPI release workflows. |
| `just` | `bool` | Whether to auto-scaffold a justfile for command execution. |
