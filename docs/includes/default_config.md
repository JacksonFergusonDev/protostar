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
# pytest = true
# pre_commit = true
# commitizen = true  # Scaffold commitizen version bumping and changelog tooling
# renovate = true    # Scaffold Renovate dependency update configuration
# codecov = true     # Scaffold Codecov configuration
# zensical = true    # Scaffold Zensical documentation
# readthedocs = true # Scaffold Read the Docs configuration
# just = true        # Scaffold a justfile for command execution
# active_presets = []

# --- Advanced Configuration Overrides ---
# Protostar allows you to customize the dependencies and directory structures
# for specific pipelines, or inject tooling across all initialized environments.

# [presets.astro]
# dependencies = ["astropy", "astroquery", "photutils", "specutils"]
# dev_dependencies = ["pytest-benchmark"]
# directories = ["data/catalogs", "data/fits", "data/raw"]

# [dev]
# extra_dependencies = ["bump-my-version"]

# [dev.pyproject]
# custom_ruff = '''
# [tool.ruff.lint]
# select = ["E", "F", "I", "B", "UP", "SIM", "T20", "PT", "C4", "D"]
# ignore = ["E501", "D100", "D104", "D107"]
# '''
```
