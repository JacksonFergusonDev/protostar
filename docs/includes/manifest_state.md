```json
{
    "vcs_ignores": [
        "*.csv",
        "*.fit",
        "*.fits",
        "*.fts",
        "*.ipynb_checkpoints",
        "*.parquet",
        ".ruff_cache/",
        ".venv/",
        "__pycache__/"
    ],
    "workspace_hides": [
        "*.ipynb_checkpoints",
        ".ruff_cache/",
        ".venv/",
        "__pycache__/"
    ],
    "ide_settings": {
        "python.defaultInterpreterPath": "/Users/jacksonferguson/Developer/protostar/.venv/bin/python",
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
            "timeout": 30
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
            "[tool.ruff]\nline-length = 88\n\n[tool.ruff.lint]\nselect = [\n    \"E\",   # pycodestyle errors\n    \"F\",   # pyflakes\n    \"I\",   # isort\n    \"B\",   # flake8-bugbear\n    \"UP\",  # pyupgrade\n    \"RUF\", # ruff-specific rules\n]\nignore = []\n"
        ]
    },
    "wants_pre_commit": false,
    "pre_commit_hooks": [
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v0.15.4\n    hooks:\n      - id: ruff-format\n      - id: ruff\n        args: [ --fix ]"
    ],
    "collision_strategy": "merge"
}
```
