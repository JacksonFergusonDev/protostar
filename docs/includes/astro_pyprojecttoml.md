```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "astropy>=8.0.1",
    "astroquery>=0.4.11",
    "matplotlib>=3.11.0",
    "nbdime>=4.0.4",
    "numpy>=2.5.1",
    "pandas>=3.0.3",
    "photutils>=3.0.0",
    "scipy>=1.18.0",
    "specutils>=2.4.0",
]
description = "Add your description here."
readme = "README.md"
authors = [{ name = "your-name", email = "your-email" }]

[dependency-groups]
dev = [
    "ruff>=0.15.21",
]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = [
    "A",   # flake8-builtins
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "RUF", # Ruff-specific
    "UP",  # pyupgrade
]
ignore = [
    "E501", # Line too long - handled automatically by `ruff format`
]
extend-select = ["PD", "NPY"]

```
