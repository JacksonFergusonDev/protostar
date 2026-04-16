```toml
[project]
name = "tmpiilcs8lu"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "astropy>=7.2.0",
    "astroquery>=0.4.11",
    "matplotlib>=3.10.8",
    "nbdime>=4.0.4",
    "numpy>=2.4.3",
    "pandas>=3.0.1",
    "photutils>=2.3.0",
    "scipy>=1.17.1",
    "specutils>=2.3.0",
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

[dependency-groups]
dev = [
    "ruff>=0.15.6",
]
```
