```json
{
    "vcs_ignores": [
        "*.csv",
        "*.fit",
        "*.fits",
        "*.fts",
        "*.parquet",
        ".ipynb_checkpoints/",
        ".ruff_cache/",
        ".venv/",
        "__pycache__/"
    ],
    "workspace_hides": [
        ".ruff_cache/",
        ".venv/",
        "__pycache__/"
    ],
    "ide_settings": {
        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
        "python.terminal.activateEnvironment": true
    },
    "dependencies": [
        "numpy",
        "scipy",
        "pandas",
        "matplotlib",
        "astropy",
        "astroquery",
        "photutils",
        "specutils",
        "nbdime"
    ],
    "dev_dependencies": [
        "ruff"
    ],
    "docs_dependencies": [],
    "system_tasks": [],
    "post_install_tasks": [
        {
            "command": [
                "uv",
                "run",
                "nbdime",
                "config-git",
                "--enable"
            ],
            "timeout": 30,
            "description": "Configuring nbdime git integration"
        }
    ],
    "directories": [
        "data/catalogs",
        "data/fits",
        "notebooks",
        "src"
    ],
    "file_injections": {
        ".gitattributes": "# Astrophysics binary safety\n*.fits binary\n*.fit  binary\n*.fts  binary\n\n# Improve Jupyter Notebook diffs\n*.ipynb text eol=lf\n"
    },
    "file_appends": {
        "pyproject.toml": [
            "[project]\ndescription = \"Add your description here.\"\nreadme = \"README.md\"\nauthors = [{ name = \"your-name\", email = \"your-email\" }]\n",
            "[tool.ruff]\nline-length = 88\n\n[tool.ruff.lint]\nselect = [\n    \"A\",   # flake8-builtins\n    \"B\",   # flake8-bugbear\n    \"C4\",  # flake8-comprehensions\n    \"E\",   # pycodestyle errors\n    \"F\",   # Pyflakes\n    \"I\",   # isort\n    \"RUF\", # Ruff-specific\n    \"UP\",  # pyupgrade\n]\nignore = [\n    \"E501\", # Line too long - handled automatically by `ruff format`\n]\n"
        ]
    },
    "wants_pre_commit": false,
    "wants_prek": false,
    "pre_commit_hooks": [
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v0.15.4\n    hooks:\n      - id: ruff-format\n      - id: ruff\n        args: [ --fix ]"
    ],
    "metadata": {},
    "wants_ci": false,
    "wants_release": false,
    "ci_flags": [],
    "ci_steps": [
        "      - name: Run Ruff Linter\n        run: uv run ruff check --output-format=github .\n\n      - name: Run Ruff Formatter\n        run: uv run ruff format --check --output-format=github ."
    ],
    "ide_extensions": [
        "charliermarsh.ruff"
    ],
    "collision_strategy": "merge",
    "diagnostics": []
}
```
