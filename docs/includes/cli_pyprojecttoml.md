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
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Operating System :: MacOS",
    "Operating System :: POSIX :: Linux",
    "Operating System :: Microsoft :: Windows",
]

[project.scripts]
demo-project = "demo_project.cli:app"

[dependency-groups]
dev = [
    "commitizen>=4.17.0",
    "mypy>=2.2.0",
    "prek>=0.4.13",
    "pytest>=9.1.1",
    "pytest-cov>=7.1.0",
    "pytest-mock>=3.15.1",
    "ruff>=0.15.21",
    { include-group = "docs" },
]
docs = [
    "mkdocstrings[python]>=1.0.6",
    "zensical>=0.0.54",
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
    "D",   # pydocstyle
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "PT",  # flake8-pytest
    "RET", # flake8-return
    "RUF", # Ruff-specific
    "SIM", # flake8-simplify
    "T20", # flake8-print
    "UP",  # pyupgrade
]
ignore = [
    "D100", # Missing docstring in public module
    "D104", # Missing docstring in public package
    "D107", # Missing docstring in __init__
    "E501", # Line too long - handled automatically by `ruff format`
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/*.py" = ["T201", "D"]

# ---- Mypy ---- #

[tool.mypy]
mypy_path = "src"
python_version = "3.13"
strict = true
pretty = true
show_error_codes = true
show_error_context = true
explicit_package_bases = true

[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_untyped_defs = false
disallow_incomplete_defs = false
disallow_untyped_calls = false
warn_return_any = false

# ---- Pytest ---- #

[tool.pytest.ini_options]
addopts = "--strict-markers"
testpaths = [
    "tests",
]
pythonpath = [
    ".",
]

# ---- Commitizen ---- #

[tool.commitizen]
name = "cz_conventional_commits"
version_provider = "pep621"
version_scheme = "semver2"
tag_format = "v$version"
update_changelog_on_bump = true
changelog_incremental = true

[tool.coverage.run]
branch = true

[tool.coverage.report]
omit = ["**/__init__.py"]
show_missing = true
skip_covered = true
fail_under = 90

```
