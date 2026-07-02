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

  - repo: https://github.com/igorshubovych/markdownlint-cli
    rev: v0.48.0
    hooks:
      - id: markdownlint
        args: ["--fix"]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.11
    hooks:
      - id: ruff-format
      - id: ruff
        args: [ --fix ]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.20.1
    hooks:
      - id: mypy
        additional_dependencies:
          - typer
          - rich
```
