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
    "scikit-learn>=1.9.0",
    "scipy>=1.18.0",
    "specutils>=2.4.0",
    "torch>=2.13.0",
    "tqdm>=4.68.4",
]
description = "Add your description here."
readme = "README.md"
authors = [{ name = "your-name", email = "your-email" }]

[dependency-groups]
dev = [
    "mypy>=2.2.0",
    "pytest>=9.1.1",
    "pytest-mock>=3.15.1",
    "ruff>=0.15.21",
]
docs = [
    "ipywidgets>=8.1.8",
    "jupyterlab>=4.6.3",
    "nbdime>=4.0.4",
]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88
extend-include = ["*.ipynb"]

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
extend-select = ["NPY", "PD"] # NumPy and Pandas specific linting rules

# ---- Mypy ---- #

[tool.mypy]
mypy_path = "src"
python_version = "3.13"
pretty = true
show_error_codes = true
show_error_context = true
warn_return_any = true
warn_unused_configs = true
check_untyped_defs = true
explicit_package_bases = true

# ---- Pytest ---- #

[tool.pytest.ini_options]
addopts = "--strict-markers"
testpaths = [
    "tests",
]
pythonpath = [
    ".",
]

```
