# The Environment Manifest

The `EnvironmentManifest` is the critical boundary between declarative intent and imperative execution. It acts as an isolated, centralized state object that guarantees atomicity during environment scaffolding.

By preventing modules from writing to disk directly during planning, Protostar keeps side effects contained to a single, easily testable execution phase. All disk writes, package downloads, and shell commands are held until this final step.

- **Atomicity**

  If a pre-flight check fails or an invalid configuration is evaluated in the final loaded module, the process aborts cleanly. No partial directories are created; no half-written `.toml` files are left behind.

- **Testability**

  Because modules only append to this object, the entire scaffolding pipeline can be tested declaratively in memory without mocking the filesystem or performing expensive `subprocess.run` calls.

- **Collision Safety**

  The manifest aggregates all requested files, ignores, and configuration injections in one place, allowing the Orchestrator to detect and resolve target collisions before any destructive operations occur.

- **Deterministic Simulation**

  Enables side-effect-free execution simulations (`--dry-run`) and programmatic inspection of planned state ahead of disk mutation.

______________________________________________________________________

## State Architecture

Rather than storing all state in a monolithic structure, `EnvironmentManifest` delegates state management to specialized domain classes: `DependencyManifest`, `FilesystemManifest`, `ToolingManifest`, and `TaskManifest`.

During the `build()` phase, modules route their state declarations through these explicit domain namespaces (e.g., `manifest.dependencies`, `manifest.filesystem`, `manifest.tooling`, `manifest.tasks`). This structure allows the `SystemExecutor` to run setup tasks and write files in the correct dependency order.

Managed by `DependencyManifest`. Holds the required packages for your project setup. These are passed to the package manager (e.g., `uv`, `pip`, `npm`) at the end of the run to install dependencies in a single step and prevent fragmented lockfiles.

- `dependencies`: Core application or scientific libraries (`manifest.dependencies.add()`).
- `dev_dependencies`: Tooling, linters, and testing frameworks (`manifest.dependencies.add_dev()`).
- `docs_dependencies`: Documentation toolchains and themes (`manifest.dependencies.add_docs()`).

Managed by `FilesystemManifest`. Manages physical directory scaffolding, file injections, AST appends, and ignore configurations.

- `directories`: A mathematical set of directories to be scaffolded via `mkdir -p` (`manifest.filesystem.add_directory()`).
- `file_injections`: A 1:1 mapping of exact file paths to their raw string contents (e.g., dropping configuration files like `renovate.json` or `mkdocs.yml` via `manifest.filesystem.add_file_injection()`).
- `file_appends`: A mapping of file paths to lists of configuration blocks used primarily for late-binding AST deep-merges into files like `pyproject.toml` (`manifest.filesystem.add_file_append()`).
- `vcs_ignores`: Deduplicated patterns for `.gitignore` and `.dockerignore` (`manifest.filesystem.add_vcs_ignore()`).
- `workspace_hides`: Patterns hidden from IDE workspace file explorers (`manifest.filesystem.add_workspace_hide()`).

Managed by `ToolingManifest`. Configures development tools, CI/CD pipeline steps, pre-commit hooks, and IDE extension recommendations.

- `pre_commit_hooks` / `pre_commit_local_hooks` / `pre_commit_install_hook_types`: Hook configurations and Git lifecycle hook types (e.g., `commit-msg`) registered via `manifest.tooling.add_pre_commit_hook()`, `manifest.tooling.add_pre_commit_local_hook()`, and `manifest.tooling.add_pre_commit_hook_type()`.
- `ci_steps` / `ci_flags`: Continuous integration steps and workflow flags (`manifest.tooling.add_ci_step()`, `manifest.tooling.add_ci_flag()`).
- `ide_extensions`: Recommended IDE extensions queued for workspace configuration (`manifest.tooling.add_ide_extension()`).

Managed by `TaskManifest`. Maintains ordered queues of `SystemTask` objects for imperative shell execution, combining commands with explicit timeout boundaries.

- `system_tasks`: Pre-installation shell commands executed after filesystem scaffolding (e.g., `git init`, `uv init` queued via `manifest.tasks.add_system_task()`).
- `post_install_tasks`: Commands that strictly require the virtual environment or installed dependencies to be present (e.g., `pre-commit install` queued via `manifest.tasks.add_post_install_task()`).

Attributes directly bound to the root `EnvironmentManifest` instance.

- `metadata`: Structured `ProjectMetadata` dictionary defining author, licensing, and package specs.
- `ide_settings`: Key-value dictionaries mapped directly to local IDE workspace configs via `manifest.add_ide_setting()`.
- `collision_strategy`: Active `CollisionStrategy` (`MERGE`, `OVERWRITE`, `ABORT`).

______________________________________________________________________

## State Serialization

Every sub-manifest (`DependencyManifest`, `FilesystemManifest`, `ToolingManifest`, `TaskManifest`) as well as the root `EnvironmentManifest` implements a deterministic `.to_dict()` serialization method.

This method enables machine interfaces (such as `protostar init --dry-run --json`) and external tooling to inspect the full planned environment state:

- **Sets $\\to$ Sorted Lists:** Unordered set collections (such as `directories`, `vcs_ignores`, `workspace_hides`) are sorted alphabetically for deterministic JSON output.
- **Ordered Lists Preserved:** Sequential task queues and dependency lists maintain their exact insertion order.
- **Enums & Objects:** Enums (such as `CollisionStrategy`) are emitted as string values, and `SystemTask` objects are serialized as structured dictionaries (`command`, `description`, `timeout`).

Below is an example JSON representation of an aggregate state during a dry-run of `protostar init --template astro --dry-run --json`:

```json
{
    "dependencies": {
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
        "docs_dependencies": []
    },
    "filesystem": {
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
                "[tool.ruff]\nline-length = 88\n\n[tool.ruff.lint]\nselect = [\n    \"A\",   # flake8-builtins\n    \"B\",   # flake8-bugbear\n    \"C4\",  # flake8-comprehensions\n    \"E\",   # pycodestyle errors\n    \"F\",   # Pyflakes\n    \"I\",   # isort\n    \"RUF\", # Ruff-specific\n    \"UP\",  # pyupgrade\n]\nignore = [\n    \"E501\", # Line too long - handled automatically by `ruff format`\n]\n",
                "[tool.ruff.lint]\nextend-select = [\"PD\", \"NPY\"]\n"
            ]
        },
        "vcs_ignores": [
            "*.csv",
            "*.fit",
            "*.fits",
            "*.fts",
            "*.parquet",
            ".cache/",
            ".ipynb_checkpoints/",
            ".ruff_cache/",
            ".venv/",
            "__pycache__/"
        ],
        "workspace_hides": [
            ".cache/",
            ".ruff_cache/",
            ".venv/",
            "__pycache__/"
        ]
    },
    "tooling": {
        "wants_pre_commit": false,
        "wants_prek": false,
        "pre_commit_hooks": [],
        "pre_commit_local_hooks": [
            "      - id: ruff-check\n        name: ruff check\n        entry: uv run ruff check --fix\n        language: system\n        types: [python]\n        require_serial: true\n\n      - id: ruff-format\n        name: ruff format\n        entry: uv run ruff format\n        language: system\n        types: [python]\n        require_serial: true"
        ],
        "pre_commit_install_hook_types": [],
        "wants_ci": false,
        "wants_release": false,
        "ci_flags": [],
        "ci_steps": [
            "      - name: Run Ruff Linter\n        run: uv run ruff check --output-format=github .\n\n      - name: Run Ruff Formatter\n        run: uv run ruff format --check --output-format=github ."
        ],
        "wants_just": false,
        "just_format_commands": [
            "uv run ruff check --fix .",
            "uv run ruff format ."
        ],
        "just_lint_commands": [
            "uv run ruff check .",
            "uv run ruff format --check ."
        ],
        "just_typecheck_commands": [],
        "just_clean_paths": [
            ".ruff_cache"
        ],
        "ide_extensions": [
            "charliermarsh.ruff"
        ]
    },
    "tasks": {
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
                "description": null,
                "timeout": 30
            }
        ]
    },
    "metadata": {},
    "ide_settings": {
        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
        "python.terminal.activateEnvironment": true
    },
    "collision_strategy": "merge",
    "force_merge": false,
    "force_replace": false
}
```

Deduplication & Order

Notice how lists are utilized for task ordering (which must be executed sequentially), while sets are utilized internally for structural artifacts (like ignores and directories) to prevent redundant I/O requests.

______________________________________________________________________

## Collision Strategies

When the Orchestrator detects that a collision marker (e.g., an existing `pyproject.toml`) is present in the target workspace, it alters the manifest's `collision_strategy` attribute based on your input or `--force-merge` / `--force-replace` flags.

The `SystemExecutor` reads this enum to govern its AST mutation logic:

- **`MERGE` (Default):** Safely injects missing configurations. If you have a custom line-length defined in your `pyproject.toml`, it is preserved. Missing arrays are appended, but existing scalar values are respected.
- **`OVERWRITE`:** Forces Protostar's configuration onto the AST. Keys conflicting with Protostar's payload will be updated to match the tool's baseline.
- **`ABORT`:** Halts execution completely.

______________________________________________________________________

## API Reference

If you are extending Protostar with custom domains or tooling layers, your `BootstrapModule` will interact directly with the `EnvironmentManifest` instance passed into its `build()` method.

Core Interface: `EnvironmentManifest`

The materialized build state of the target environment.

Modules mutate this declarative object rather than the host system directly. The Executor subsequently reads this object to execute the unified system changes.

Source code in `src/protostar/manifest.py`

```python
@dataclass
class EnvironmentManifest:
    """The materialized build state of the target environment.

    Modules mutate this declarative object rather than the host system directly. The Executor
    subsequently reads this object to execute the unified system changes.
    """

    dependencies: DependencyManifest = field(default_factory=DependencyManifest)
    filesystem: FilesystemManifest = field(default_factory=FilesystemManifest)
    tooling: ToolingManifest = field(default_factory=ToolingManifest)
    tasks: TaskManifest = field(default_factory=TaskManifest)

    metadata: ProjectMetadata = field(default_factory=lambda: cast(ProjectMetadata, {}))
    ide_settings: IDESettings = field(default_factory=lambda: cast(IDESettings, {}))
    collision_strategy: CollisionStrategy = CollisionStrategy.MERGE
    force_merge: bool = False
    force_replace: bool = False

    def add_ide_setting(self, key: IDESettingKey, value: Any) -> None:
        """Sets a key-value configuration for the requested IDE."""
        self.ide_settings[key] = value

    def should_skip_file(self, target: Path) -> bool:
        """Returns True if the file exists and collision strategy is not OVERWRITE."""
        return (
            target.exists() and self.collision_strategy != CollisionStrategy.OVERWRITE
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the full environment manifest to a JSON-safe dictionary.

        Delegates serialization to each sub-manifest's ``to_dict()`` method and
        coerces top-level scalar fields to JSON-safe types. The collision_strategy
        enum is emitted as its string value. Metadata and IDE settings are included
        as-is since they are already dict-typed.

        Returns:
            A JSON-serializable dictionary representation of the full manifest.
        """
        return {
            "collision_strategy": self.collision_strategy.value,
            "force_merge": self.force_merge,
            "force_replace": self.force_replace,
            "metadata": dict(self.metadata),
            "ide_settings": dict(self.ide_settings),
            "dependencies": self.dependencies.to_dict(),
            "filesystem": self.filesystem.to_dict(),
            "tooling": self.tooling.to_dict(),
            "tasks": self.tasks.to_dict(),
        }
```

## add_ide_setting

```python
add_ide_setting(key, value)
```

Sets a key-value configuration for the requested IDE.

Source code in `src/protostar/manifest.py`

```python
def add_ide_setting(self, key: IDESettingKey, value: Any) -> None:
    """Sets a key-value configuration for the requested IDE."""
    self.ide_settings[key] = value
```

## should_skip_file

```python
should_skip_file(target)
```

Returns True if the file exists and collision strategy is not OVERWRITE.

Source code in `src/protostar/manifest.py`

```python
def should_skip_file(self, target: Path) -> bool:
    """Returns True if the file exists and collision strategy is not OVERWRITE."""
    return (
        target.exists() and self.collision_strategy != CollisionStrategy.OVERWRITE
    )
```

## to_dict

```python
to_dict()
```

Serializes the full environment manifest to a JSON-safe dictionary.

Delegates serialization to each sub-manifest's `to_dict()` method and coerces top-level scalar fields to JSON-safe types. The collision_strategy enum is emitted as its string value. Metadata and IDE settings are included as-is since they are already dict-typed.

Returns:

| Type             | Description                                                         |
| ---------------- | ------------------------------------------------------------------- |
| `dict[str, Any]` | A JSON-serializable dictionary representation of the full manifest. |

Source code in `src/protostar/manifest.py`

```python
def to_dict(self) -> dict[str, Any]:
    """Serializes the full environment manifest to a JSON-safe dictionary.

    Delegates serialization to each sub-manifest's ``to_dict()`` method and
    coerces top-level scalar fields to JSON-safe types. The collision_strategy
    enum is emitted as its string value. Metadata and IDE settings are included
    as-is since they are already dict-typed.

    Returns:
        A JSON-serializable dictionary representation of the full manifest.
    """
    return {
        "collision_strategy": self.collision_strategy.value,
        "force_merge": self.force_merge,
        "force_replace": self.force_replace,
        "metadata": dict(self.metadata),
        "ide_settings": dict(self.ide_settings),
        "dependencies": self.dependencies.to_dict(),
        "filesystem": self.filesystem.to_dict(),
        "tooling": self.tooling.to_dict(),
        "tasks": self.tasks.to_dict(),
    }
```

______________________________________________________________________

## Related Mechanics & Guides

- **[The Orchestrator](.././orchestrator/):** Learn how the engine coordinates the planning and execution phases using the manifest.
- **[The System Executor](.././executor/):** Discover how the manifest is transformed into atomic disk mutations and managed subprocesses.
- **[The Module Architecture](.././modules/):** Understand how modules declare dependencies, file injections, and AST appends.
- **[Extending Protostar](../../developer/extending-protostar/):** Build custom bootstrap modules that interact directly with `EnvironmentManifest`.
