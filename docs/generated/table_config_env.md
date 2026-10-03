| Setting | Type | Description |
| :--- | :--- | :--- |
| `ide` | `"vscode"` \| `"cursor"` \| `"none"` | The preferred IDE (e.g., 'vscode', 'cursor', 'none'). |
| `author_name` | `str` \| `None` | Default author name for project metadata. |
| `author_email` | `str` \| `None` | Default author email for project metadata. |
| `github_username` | `str` \| `None` | Default GitHub username for repository URL formatting. |
| `python_version` | `str` \| `None` | The specific Python version to scaffold. |
| `license` | `str` \| `None` | Default project license identifier (e.g., 'MIT', 'Apache-2.0'). |
| `supported_os` | `list[str]` | The supported operating systems to scaffold CI for. |
| `direnv` | `bool` | Activate the project's environment whenever you enter its folder. Default: `false`. |
| `markdownlint` | `bool` | Check Markdown files for formatting mistakes, with relaxed rules. Default: `false`. |
| `rumdl` | `bool` | Check and format Markdown files quickly. Default: `false`. |
| `ruff` | `bool` | Find common bugs and style problems in Python code, and format it. Default: `true`. |
| `mypy` | `bool` | Check type hints to catch mistakes before the code runs. Default: `false`. |
| `ty` | `bool` | Check type hints quickly, with Astral's type checker. Default: `false`. |
| `pyrefly` | `bool` | Check type hints quickly, with Meta's type checker. Default: `false`. |
| `pytest` | `bool` | Run the project's tests. Default: `false`. |
| `pre_commit` | `bool` | Run the project's checks automatically each time you commit. Default: `false`. |
| `prek` | `bool` | Run the project's checks automatically each time you commit, faster. Default: `false`. |
| `commitizen` | `bool` | Write commit messages in a standard form that sets the next version. Default: `false`. |
| `renovate` | `bool` | Open pull requests that keep dependencies up to date. Default: `false`. |
| `codecov` | `bool` | Report how much of the code the tests exercise, on each pull request. Default: `false`. |
| `zensical` | `bool` | Build a documentation website from Markdown files. Default: `false`. |
| `readthedocs` | `bool` | Publish the documentation website on Read the Docs. Default: `false`. |
| `ci` | `bool` | Run the checks and tests on GitHub for every push and pull request. Default: `false`. |
| `release` | `bool` | Publish the package to PyPI when you push a version tag. Default: `false`. |
| `docker` | `bool` | Package the project as a container image that runs anywhere. Default: `false`. |
| `just` | `bool` | Give the project's common commands short names, like `just test`. Default: `false`. |
| `agents` | `bool` | Tell coding assistants how to work on the project. Default: `false`. |
| `community` | `bool` | Add the files GitHub shows people who want to contribute. Default: `false`. |
