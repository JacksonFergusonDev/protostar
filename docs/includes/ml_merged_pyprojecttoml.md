```toml
[project]
name = "tmpc5sa0gq6"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "astropy>=7.2.0",
    "astroquery>=0.4.11",
    "huggingface-hub>=1.11.0",
    "matplotlib>=3.10.8",
    "nbdime>=4.0.4",
    "numpy>=2.4.4",
    "pandas>=3.0.2",
    "photutils>=3.0.0",
    "scikit-learn>=1.8.0",
    "scipy>=1.17.1",
    "specutils>=2.3.0",
    "torch>=2.11.0",
    "tqdm>=4.67.3",
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

[dependency-groups]
dev = [
    "mypy>=1.20.1",
    "ruff>=0.15.11",
]

```
