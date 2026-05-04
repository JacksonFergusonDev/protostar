```toml
[env]
# Preferred IDE: 'vscode', 'cursor', 'jetbrains', or 'none'
# ide = "vscode"

# Auto-scaffold direnv with python environments
direnv = false

# Preferred Python package manager: 'uv' or 'pip'
python_package_manager = "uv"

# Default Python version
python_version = "3.13"

# Optional dev tool toggles for Python
# markdownlint = true
# no-ruff = true  # Disables the default Ruff scaffolding
# mypy = true
# pytest = true
# pre_commit = true

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
