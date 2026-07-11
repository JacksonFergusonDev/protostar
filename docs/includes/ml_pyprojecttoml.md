```toml
[project]
name = "demo-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "huggingface-hub>=1.23.0",
    "scikit-learn>=1.9.0",
    "torch>=2.13.0",
    "tqdm>=4.68.4",
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
    "ruff>=0.15.21",
]

```
