```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
        exclude: \.py$
      - id: end-of-file-fixer
        exclude: \.py$
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/DavidAnson/markdownlint-cli2
    rev: v0.23.0
    hooks:
      - id: markdownlint-cli2
        args: ["--fix"]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.21
    hooks:
      - id: ruff-format
      - id: ruff
        args: [ --fix ]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v2.2.0
    hooks:
      - id: mypy
        additional_dependencies:
          - typer
          - rich
```
