```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "astropy>=8.0.1",
    "astroquery>=0.4.11",
    "huggingface-hub>=1.23.0",
    "matplotlib>=3.11.0",
    "nbdime>=4.0.4",
    "numpy>=2.5.1",
    "pandas>=3.0.3",
    "photutils>=3.0.0",
    "scikit-learn>=1.9.0",
    "scipy>=1.18.0",
    "specutils>=2.4.0",
    "torch>=2.13.0",
    "tqdm>=4.68.4",
]
description = "Add your description here."
readme = "README.md"
authors = [{ name = "your-name", email = "your-email" }]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "UP",  # pyupgrade
    "RUF", # ruff-specific rules
]

# ---- Mypy ---- #

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[dependency-groups]
dev = [
    "mypy>=2.2.0",
    "ruff>=0.15.21",
]

```
