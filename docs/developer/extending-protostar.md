---
description: "How to add a tool to Protostar: the module that declares what it needs, where it is registered, and the rules its commands follow."
---

# Extending Protostar

Every tool Protostar sets up is a `ToolModule`: a class whose `build()` method declares what the tool needs into the `EnvironmentManifest`. Planning collects every module's declarations, and execution applies them in one transaction. A module never writes a file or runs a command itself, so adding a tool never touches the orchestrator or the executor.

## A Tool Module

This is the Mypy module, exactly as Protostar ships it:

```python
--8<-- "src/protostar/modules/tooling_layer.py:mypy_module"
```

- **`cli_flags`** names the flag. The parser adds `--mypy` and `--no-mypy` from it.
- **`info`** is a `ToolInfo`, the one description of the tool. Its `summary` is the flag's `--help` line and the recipe editor's tooltip, and `adds` and `workflow` fill the editor's `i` popup. Write it for someone who has never heard of the tool, and say what changes in their project rather than what category the tool is in. `ToolModule.info` is abstract, so mypy rejects a module without one, and `scripts/check_doc_links.py` checks every `docs_url`.
- **`config_key`** is the tool's name in templates, recipes, and the global configuration.
- **`signals`** say what shows that a project Protostar has never touched already uses the tool; see [Signals](#signals-recognizing-an-existing-project).
- **`build()`** declares everything the tool brings: its development dependency, its cache directory, its editor extension, its commit hook, its CI step, its `just` recipe, and its `pyproject.toml` settings. Each declaration is retracted again when the tool is turned off.

The `pyproject.toml` settings are a baseline for a casual project. Stricter settings belong in the templates whose shape wants them; see [Built-in Templates](built-in-templates.md#baseline-in-modules-delta-in-templates).

## Registering a Tool

A tool is listed in a few places, so that every part of Protostar knows it. Tests fail, naming what's missing, until each is in place:

1. A `Tool` member in `src/protostar/recipe.py`, whose value is the module's `config_key`.
1. A `bool` field of the same name on `UserConfig` in `src/protostar/config.py`, `False` unless most new projects want the tool.
1. The module, appended to `TOOLING_MODULES` in `src/protostar/modules/__init__.py`. The flag, its help, the template schema, the configuration form, and the recipe editor all read this tuple.
1. Its place in a group of the recipe editor, in `TOOL_GROUPS` in `src/protostar/cli/tui/tool_info.py`.
1. A `ToolSection` in `src/protostar/documents/pyproject_layout.py`, when the tool writes a `[tool.<name>]` table; see [The pyproject.toml Layout](pyproject-layout.md).

Then run `just check-snapshots` and review what changed. `tests/test_tool_definitions.py`, `tests/test_tool_info.py`, and `tests/test_pyproject_layout.py` check that the lists agree.

A tool with a configuration file of its own, such as a YAML or JSONC file, also declares that file as a document under `src/protostar/documents/`, which says where it lives and how it merges. The format engines never name a file; see [Managed Documents](reconciliation/documents.md).

## Programs a Tool Runs

Only `uv` and `git` can stop a run. A program that only one tool runs, such as `direnv`, is declared in the module's `executables`. Planning records each one missing from `PATH` in `manifest.missing_tools`, and the module still writes the tool's files but skips the step that runs the program, with a diagnostic saying so:

```python
--8<-- "src/protostar/modules/tooling_layer.py:missing_executable"
```

The run then ends with the command that installs everything missing. A new program needs a `GlobalExecutable` member in `src/protostar/system_deps.py`, with its package name for each package manager. Look a program up only through `system_deps.find_executable`, never `shutil.which`: on Windows a bare lookup searches the working directory first, where a template's `git.bat` would win.

## Commands and the Files They Create

A module queues commands rather than running them:

- `manifest.tasks.add_system_task()` runs once the project's files are written, before its dependencies are installed, like `git init` and `uv init`.
- `manifest.tasks.add_post_install_task()` runs after the dependencies are installed, like a hook install.

Each command's program must be in the safelist in `src/protostar/security.py`, and a template's commands must be confirmed by the user unless the template is trusted.

A command's output is invisible to Protostar unless the module declares it. List every file a command creates in `owned_files`, and every directory tree in `owned_trees`:

```python
--8<-- "src/protostar/modules/lang_layer.py:owned_files"
```

Declared files appear in every preview of the run, and rollback restores them if it fails. `just check-snapshots` fails when a scaffold leaves a file its dry run didn't list, so a missing declaration is caught.

## Signals: Recognizing an Existing Project

`signals` tells `init` that a project it has never touched already uses the module's tool, so the recipe editor can start with it switched on. A module lists every signal that holds for its tool:

- `PathSignal(path)`: a file or directory, matched with its exact spelling.
- `TableSignal(keys)`: a table in `pyproject.toml`, such as `("tool", "ruff")`.
- `SectionSignal(path, section)`: a section of an INI file, such as `("setup.cfg", "mypy")`.
- `RequirementSignal(name)`: a package in any of the project's dependency lists.

A module that manages a document builds its path signals from that document's locations in `protostar.documents`, so every name the tool reads counts. Analysis knows no tool by name: it reads only what modules declare, and every tooling module must declare at least one signal.

## The Manifest API

!!! danger "Declare, never act"
    `build()` may check what the workspace holds, as the `uv init` example does, but it never writes a file or runs a process. Everything it wants done goes into the manifest, so `--dry-run` and the change review show it before it happens.

| Method | What it declares |
| --- | --- |
| `manifest.dependencies.add(package)` | A runtime dependency, added with `uv add`. |
| `manifest.dependencies.add_dev(package)` | A development dependency, in the `dev` group. |
| `manifest.dependencies.add_docs(package)` | A documentation dependency, in the `docs` group. |
| `manifest.dependencies.add_include(group, include)` | One dependency group including another (`dev` including `docs`). |
| `manifest.filesystem.add_directory(path)` | A directory to create. |
| `manifest.filesystem.add_file_injection(path, content)` | A file written once, when the project doesn't have it. After that it belongs to the project. |
| `manifest.filesystem.add_structured(path, content, producer=...)` | TOML (or a supported YAML file) merged key by key and kept up to date. A `ToolModule` uses `add_pyproject_config()` for `pyproject.toml`. |
| `manifest.filesystem.add_region(path, content, identity=...)` | A named block of text inside a file, kept up to date between its markers. |
| `manifest.filesystem.add_vcs_ignore(path)` | A pattern added to `.gitignore`. |
| `manifest.tasks.add_system_task(command, timeout=30, description=None, owned_files=None, owned_trees=None)` | A command run before dependencies are installed, with the files and trees it creates. |
| `manifest.tasks.add_post_install_task(command, timeout=30, description=None, owned_files=None, owned_trees=None)` | A command run after dependencies are installed, with the files and trees it creates. |

## Next Steps

- **[The Module Architecture](../mechanics/modules.md):** The module families and the contract every module follows.
- **[Testing Architecture & Philosophy](./testing.md):** How to test a module without touching the machine.
- **[API Reference](./api-reference.md):** Complete class documentation for `BootstrapModule` and `EnvironmentManifest`.
