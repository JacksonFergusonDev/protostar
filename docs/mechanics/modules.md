---
description: "How modules turn a project's choices into declarations, the order they run in, and the contract each one follows."
---

# The Module Architecture

Everything Protostar sets up comes from a module: a class whose `build()` method declares what one part of the project needs into the `EnvironmentManifest`. Modules never write a file or run a command; execution does that later, from the manifest. They may check what the workspace already holds, as the system module does before queuing `git init`, but never change it.

## The Modules and Their Order

Every run builds the same two foundation modules first, then each enabled tool module in a fixed order:

1. **`SystemWorkspaceModule`** (`modules/system_layer.py`): `git init` when the project has no repository, and the ignore patterns every project wants, such as `.DS_Store` and `.venv/`.
1. **`PythonCore`** (`modules/lang_layer.py`): `uv init` when the project has no `pyproject.toml`, the `[project]` metadata, the license file, and the README.
1. **Tool modules**, in the order of `TOOLING_MODULES` in `modules/__init__.py`: each enabled tool's module, from direnv and the linters through CI, Docker, `just`, `AGENTS.md`, and the community files. Their classes live in `tooling_layer.py`, `ci_layer.py`, `community_layer.py`, and `docker.py`.

Which tool modules are enabled comes from the recipe, the template, and the captured defaults; see [which choice wins](../usage/project-recipes.md#which-choice-wins).

Modules don't talk to each other. Files that several tools contribute to, such as the hook configuration, the CI workflow, and the `justfile`, are assembled after every module has built, from what each declared. When two modules declare different values for the same setting, the run fails before anything is written, rather than letting the later one win silently.

## The Module Contract

Every module subclasses `BootstrapModule` and has a `name` and a `build()`. A tool the user can switch on and off is a `ToolModule`, which adds:

- **`cli_flags`**: the flag, such as `--mypy`; the parser adds the matching `--no-<tool>` flag.
- **`info`**: a `ToolInfo`, the one description of the tool, used for its `--help` line, the template schema, and the recipe editor's tooltip and `i` popup. It's abstract, so mypy rejects a tool without one.
- **`config_key`**: the tool's name in templates, recipes, and the global configuration.
- **`signals`**: what shows that a project Protostar has never touched already uses the tool, such as a `[tool.mypy]` table.
- **`executables`**: the programs the tool runs, such as `direnv`. Planning records each one missing from `PATH` in `manifest.missing_tools` and never fails for it; the module still writes the tool's files and skips only the step that runs the program. Only `uv` and `git`, which Protostar itself runs, can fail a run.

A tool module's settings suit a casual project: they should never make a small script painful. Strict settings such as `mypy`'s `strict = true` belong in the templates whose shape calls for them. See [Built-in Templates](../developer/built-in-templates.md#baseline-in-modules-delta-in-templates).

The Mypy module, as Protostar ships it:

```python
--8<-- "src/protostar/modules/tooling_layer.py:mypy_module"
```

[Extending Protostar](../developer/extending-protostar.md) covers adding a tool: the registries it joins, and the rules for its commands.

## API Reference

??? abstract "Core Interface: `BootstrapModule`"
    ::: protostar.modules.base.BootstrapModule
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true
            members_order: source

## Related Pages

- **[<span class="hs-icon hs-icon-brand-github" aria-hidden="true"></span>Built-in Modules](https://github.com/JacksonFergusonDev/protostar/tree/main/src/protostar/modules):** The source of every module.
- **[Extending Protostar<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](../developer/extending-protostar.md):** How to add a tool module.
- **[The Environment Manifest<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./manifest.md):** What a module can declare in `build()`.
- **[Testing Architecture & Philosophy<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](../developer/testing.md):** How to test a module in memory, without running a command.
