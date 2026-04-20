```toml
[project]
name = "tmpf9fysw0f"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "rich>=15.0.0",
    "typer>=0.24.1",
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
ignore = []

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
    "mypy>=1.20.1",
    "pre-commit>=4.5.1",
    "pytest>=9.0.3",
    "pytest-cov>=7.1.0",
    "pytest-mock>=3.15.1",
    "ruff>=0.15.11",
]
```
