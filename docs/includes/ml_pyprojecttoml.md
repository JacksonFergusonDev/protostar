```toml
[project]
name = "tmp-luu98vu"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "huggingface-hub>=1.11.0",
    "scikit-learn>=1.8.0",
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

[dependency-groups]
dev = [
    "ruff>=0.15.11",
]
```
