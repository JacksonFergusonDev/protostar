```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "rich>=15.0.0",
    "typer>=0.26.8",
]
description = "Add your description here."
readme = "README.md"
authors = [{ name = "your-name", email = "your-email" }]

[project.scripts]
demo_project = "demo_project.cli:app"

[dependency-groups]
dev = [
    "mypy>=2.2.0",
    "prek>=0.4.13",
    "pytest>=9.1.1",
    "pytest-mock>=3.15.1",
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
