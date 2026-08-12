```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "rich>=15.0.0",
    "typer>=0.26.8",
]

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

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q --strict-markers"
testpaths = [
    "tests",
]

[dependency-groups]
dev = [
    "mypy>=2.2.0",
    "prek>=0.4.13",
    "pytest>=9.1.1",
    "pytest-cov>=7.1.0",
    "pytest-mock>=3.15.1",
    "ruff>=0.15.21",
]

```
