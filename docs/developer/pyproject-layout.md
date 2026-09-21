---
description: "How Protostar lays out the pyproject.toml it creates, where that order is defined, and how to add a tool."
---

# The pyproject.toml Layout

A `pyproject.toml` that Protostar creates always has the same shape. Everything that is not tool configuration comes first, then a banner, then one labelled section per tool, with Protostar's own recipe last:

```toml
[project]
[build-system]
[dependency-groups]
[tool.hatch.build.targets.wheel]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #
[tool.ruff]

# ---- Mypy ---- #
[tool.mypy]

# ---- Protostar ---- #
[tool.protostar]
```

The order is a fixed property of the tool, not of when a section happened to be written. `uv add` appends `[dependency-groups]` to the end of the file, and the recipe is written after that, so a finished project needs one last pass to settle it.

## One definition

`src/protostar/documents/pyproject_layout.py` is the only place that knows the layout:

| Name | Decides |
| :--- | :--- |
| `ROOT_ORDER` | The root tables that come first, in order. |
| `TOOL_SECTIONS` | For each `[tool.<key>]`: its position, and the title of the header above it. |
| `PACKAGING_RANK` | Build-backend tables such as `tool.hatch`, which sort above the banner because they are not tooling. |

Sort order, header text, and the set of managed comment lines are all derived from these. Tables that share a title (`pytest` and `coverage`) share one header.

!!! warning "Adding a tool means adding a `ToolSection`"
    A tool that writes `[tool.<name>]` without an entry sorts after the known tools and gets no header. Two tests fail if you forget: one checks every tool module, and one checks every built-in template.

## Sections

The file is handled as a list of `Section` pieces: each root table, and each child of `[tool]`. Each piece is rendered with tomlkit's public API, and joining the pieces reproduces the original file byte for byte. That means a change to one section cannot disturb another.

The banner and headers that trail a piece are kept apart in `Section.tail`, and are recognized by exact line match, never by pattern. Nothing in Protostar reads or writes tomlkit's private container state, and a test enforces that.

## Two ways the layout is applied

- **Files Protostar creates** are formatted whole. Managed decoration is discarded and rebuilt from the spec, so the result never depends on where a previous layout left it.
- **Files you already had** are never reformatted. A table a run adds is placed by the spec, and every section that already existed keeps its text.

### Adding a table to an existing file

A merge, or a later run that enables a tool, can add a table to a file the user already owns. The new section goes **after the last existing section that ranks at or below it**, so the file's own order is kept, a new tool lands before `[tool.protostar]`, and a new build backend lands after `[project]`. Then:

- **Only the two seams change.** Each is left with exactly one blank line, in the file's own newline style, and a missing final newline is supplied.
- **A header announces the section after it,** so headers are re-homed. A new titled tool gets its header, and takes the banner and any sibling's header with it when it now comes first. A tool the user already had is never labelled, and the banner is added only if the file has none.
- **A comment directly above a table stays with it.** A comment set apart by a blank line stays where it was.
- **Order does not matter.** Adding tool A then B gives the same file as B then A, and inserting into a canonical file gives the canonical file. The tests check both.

## The safety fallback

Formatting must not change a project's configuration. The formatted text is parsed and compared with the original data, and if they differ the file is left as it was. That is reported as a warning diagnostic (`Left pyproject.toml unformatted: ...`) as well as logged, so it is never silent. The same check guards placing an added table, where the fallback is a plain dump of the merged document. The test suite checks every combination of the known tools and asserts the fallback never triggers.

## Related Pages

- **[Built-in Templates](./built-in-templates.md):** The contract a template's tool configuration follows.
- **[Project Recipes](../development/project-recipe.md):** What `[tool.protostar]` records.
- **[Testing Architecture & Philosophy](./testing.md):** How the layout tests fit the unit and exhaustive tiers.
