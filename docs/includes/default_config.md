```toml
[env]
# Preferred IDE: 'vscode', 'cursor', or 'none'
# ide = "vscode"

# Default Author Information
# author_name = "your-name"
# author_email = "your-email"
# github_username = "your-github-username"

# Auto-scaffold direnv with python environments
direnv = false

# Default Python version
python_version = "3.13"
# supported_os = ["MacOS", "Linux", "Windows"]

# Optional dev tool toggles for Python
# markdownlint = true
# ruff = false  # Disables the default Ruff scaffolding
# mypy = true
# ty = true          # Scaffold Astral ty type checker
# pyrefly = true     # Scaffold Pyrefly type checker
# pytest = true
# pre_commit = true
# prek = true        # Scaffold prek git hooks (faster Rust alternative to pre-commit)
# commitizen = true  # Scaffold commitizen version bumping and changelog tooling
# renovate = true    # Scaffold Renovate dependency update configuration
# codecov = true     # Scaffold Codecov configuration
# zensical = true    # Scaffold Zensical documentation
# readthedocs = true # Scaffold Read the Docs configuration
# ci = true          # Scaffold standard GitHub Actions CI workflows
# release = true     # Scaffold GitHub Actions PyPI release workflows
# just = true        # Scaffold a justfile for command execution

# --- Advanced Configuration Overrides ---
# Protostar allows you to customize the dependencies and directory structures
# for specific pipelines, or inject tooling across all initialized environments.

# [dev]
# extra_dependencies = ["bump-my-version"]

# [dev.pyproject]
# custom_ruff = '''
# [tool.ruff.lint]
# select = ["E", "F", "I", "B", "UP", "SIM", "T20", "PT", "C4", "D"]
# ignore = ["E501", "D100", "D104", "D107"]
# '''

# [templates]
# my-org-api = "https://raw.githubusercontent.com/MyOrg/standards/main/api.toml"
# data-science-base = "~/Developer/templates/ds_base.toml"
```
