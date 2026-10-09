---
description: "Set up a new or existing project with protostar init: templates, tool flags, the recipe editor, and the change review."
---

# Environment Initialization

`protostar init` sets up a project in the current directory, either an empty folder or a project you already have. In a terminal with no template given, it opens the recipe editor. With `--template` or `--from`, it runs without any screens. Either way, nothing is written until you have seen the plan, in the change review or with `--dry-run`, and if anything fails part-way, every change is [rolled back](rollback.md).

Afterwards Protostar tracks the project: `pyproject.toml` records what you asked for (the [recipe](project-recipes.md)), `protostar.lock` records what Protostar wrote, and `status`, `diff`, and `sync` keep it current. [How Protostar Tracks Your Files](tracking.md) explains how these fit together, and [Project Lifecycle](lifecycle.md) shows the commands.

To update a project Protostar already tracks, use `protostar sync`. Running `init --force-merge` there instead reapplies the same template, without the change review:

- Content Protostar wrote that you haven't touched takes the template's current version.
- Your edits and deletions stay.
- Content the template no longer produces is removed.
- Each conflict keeps your version. `init` ends by counting them, and `protostar sync` settles them.

It can't switch the project to a different template.

## Built-in Templates

A built-in template is a tested starting point, so you don't have to choose every tool yourself. Each one is a kind of project (a command-line app, a web service, an analysis workbench) with the tools, folders, and settings that kind of project needs. It isn't a fixed stack of libraries.

How much tooling a template starts with is its [tier](./templates.md#choosing-a-tier), chosen with `--tier`:

- **Production** adds the full quality gate: strict typing, tests, CI, and commit hooks. `cli`, `api`, and `lib` start here.
- **Workbench** stays lean, with only Ruff, direnv, and `just`, so exploratory work isn't buried in checks on day one. `astro` and `ml` start here.

Every built-in offers both tiers, and either one is only a starting point: the flags below turn any tool on or off.

To set up a project from a template without the recipe editor, pass `--template` (or `-t`):

```bash
protostar init --template astro
```

### Turning Tools On and Off

Every tool has a pair of flags. `--<tool>` turns it on and `--no-<tool>` turns it off, whatever the template chose. A tool you pass neither flag for follows the template. The project records your choice, so `sync` keeps it ([which choice wins](project-recipes.md#which-choice-wins)):

```bash
# The astro template, without direnv and with mypy
protostar init -t astro --no-direnv --mypy
```

[Templates](./templates.md) covers the rest: every built-in, your team's templates from a file or repository (`--from`), template variables, and aliases.

## What Each Template Writes

Here is what each built-in template writes into an empty folder.

!!! note "Editor settings"
    These trees assume your configuration names an editor (such as `ide = "vscode"`) and direnv is on. Without an editor set, Protostar writes no `.vscode/settings.json`, but still adds `.vscode/` to `.gitignore`.

=== "cli: a command-line app"
    `protostar init --template cli` sets up a command-line app with the full quality gate.

    ```text
    --8<-- "tree_cli.txt"
    ```

    ??? abstract "Inspect Generated Files"
        === "pyproject.toml"
            ```toml
            --8<-- "cli/pyproject.toml"
            ```
        === ".pre-commit-config.yaml"
            ```yaml
            --8<-- "cli/pre-commit-config.fixture.yaml"
            ```
        === ".gitignore"
            ```gitignore
            --8<-- "cli/.gitignore"
            ```

    - **Dependencies:** `typer` and `rich`, installed and locked by uv.
    - **Tool settings:** `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`, and `[tool.rumdl]` in `pyproject.toml`, and the tools themselves in the development dependency group.
    - **Commit hooks:** `.pre-commit-config.yaml` runs `ruff-check`, `ruff-format`, `mypy`, `rumdl-check`, and `rumdl-fmt` through `uv run`, so each hook uses the version locked in `uv.lock`. `mypy` checks the whole project, as CI does, because checking only the staged files misses errors they cause elsewhere. `actionlint` checks the workflows, and `check-jsonschema` validates the Renovate and Read the Docs configuration wherever those files live.
    - **When hooks run:** most hooks run on each commit. Commitizen checks the commit message. Pytest runs before a push that changes `src/`, `tests/`, `pyproject.toml`, or `uv.lock`, rather than on every commit.

=== "lib: a library"
    `protostar init --template lib` sets up a library package other people install.

    ```text
    --8<-- "tree_lib.txt"
    ```

    ??? abstract "Inspect Generated Files"
        === "pyproject.toml"
            ```toml
            --8<-- "lib/pyproject.toml"
            ```
        === "src/demo_project/__init__.py"
            ```python
            --8<-- "lib/src/demo_project/__init__.py"
            ```
        === ".pre-commit-config.yaml"
            ```yaml
            --8<-- "lib/pre-commit-config.fixture.yaml"
            ```
        === ".gitignore"
            ```gitignore
            --8<-- "lib/.gitignore"
            ```

    - **Type information for users:** a `py.typed` file, so type checkers like mypy and Pyright read the package's annotations (PEP 561).
    - **Packaging:** the `hatchling` build backend and a `src/` layout, for building wheels and source distributions.
    - **A public API:** `__init__.py` re-exports the package's names in `__all__` and reads `__version__` from the installed package's metadata.
    - **Stricter checks:** strict mypy, docstring rules (Ruff's `D`), and Ruff's `TC` rules, which keep imports used only for type hints out of the runtime.

=== "astro: astronomy data analysis"
    `protostar init --template astro` sets up a workbench for astronomy data.

    ```text
    --8<-- "tree_astro.txt"
    ```

    ??? abstract "Inspect Generated Files"
        === "pyproject.toml"
            ```toml
            --8<-- "astro/pyproject.toml"
            ```
        === ".gitattributes"
            ```gitattributes
            --8<-- "astro/.gitattributes"
            ```
        === ".gitignore"
            ```gitignore
            --8<-- "astro/.gitignore"
            ```

    - **Data folders:** `data/catalogs` and `data/fits`, kept apart from the code.
    - **Binary files:** `.gitattributes` marks `*.fits` files as binary, and sets up `*.ipynb` for readable diffs.
    - **Notebook diffs:** `nbdime` is set up in git, so a change to a Jupyter notebook shows as a readable diff instead of raw JSON.
    - **Large files stay out of git:** `.gitignore` lists `*.fits`, `*.csv`, and `*.parquet`.

=== "ml: machine learning"
    `protostar init --template ml --docker` sets up a machine learning project with a container image.

    ```text
    --8<-- "tree_ml.txt"
    ```

    ??? abstract "Inspect Generated Files"
        === "Dockerfile"
            ```dockerfile
            --8<-- "ml/Dockerfile"
            ```
        === ".dockerignore"
            ```dockerignore
            --8<-- "ml/.dockerignore"
            ```
        === "pyproject.toml"
            ```toml
            --8<-- "ml/pyproject.toml"
            ```

    - **A container image:** `--docker` writes a multi-stage `Dockerfile` and a `.dockerignore`. The `Dockerfile` caches uv's layers, runs as a non-root user (`appuser`), and builds a small runtime image. A template can turn Docker on itself, as `api` does, and `--no-docker` turns it off.
    - **Model files stay out of git:** `.gitignore` lists model weights (`*.pth`, `*.pt`, `*.onnx`, `*.safetensors`) and experiment-tracking folders (`wandb/`, `mlruns/`).

=== "api: a web API"
    `protostar init --template api` sets up a FastAPI web service.

    ```text
    --8<-- "tree_api.txt"
    ```

    ??? abstract "Inspect Generated Files"
        === "pyproject.toml"
            ```toml
            --8<-- "api/pyproject.toml"
            ```
        === "justfile"
            ```just
            --8<-- "api/justfile"
            ```
        === "CHANGELOG.md"
            ```markdown
            --8<-- "api/CHANGELOG.md"
            ```

    - **A layout for a growing service:** separate folders for routers (`src/demo_project/api/routers`), settings (`src/demo_project/core/config.py`), database models, and schemas.
    - **Async from the start:** `fastapi`, `uvicorn`, and `pydantic-settings`, with async tests through `pytest-asyncio` and `httpx`.
    - **Versions and a changelog:** Commitizen bumps the version and keeps `CHANGELOG.md` from your commit messages.

## Run the Project's Checks with `just`

With `just` on, the project gets a `justfile` built from its tools. Each recipe runs the linters, type checker, tests, or docs the project has. This is the `cli` template's:

??? abstract "The `cli` template's `justfile`"
    ```just
    --8<-- "cli/justfile"
    ```

Run `just` in the project folder to list them. The common ones:

- **`just format`:** formats the code with Ruff and the Markdown with rumdl.
- **`just lint`:** checks the code with Ruff and the Markdown with rumdl.
- **`just typecheck`:** runs the type checker over the project.
- **`just test` and `just test-cov`:** run the tests, the second with a coverage report.
- **`just ci`:** runs the linters, the type checker, and the tests together, the same checks CI runs.

## The Recipe Editor

Run `protostar init` in a terminal without `--template`, and the recipe editor opens. Pick a template, switch tools on and off, and fill in the project's details while a preview shows the files it will write. Each file in the preview says what `init` does to it:

- `new`: Protostar creates it.
- `modified`: Protostar changes a file you already have.
- `existing`: the file is already there and stays as it is.
- `after setup`: a command writes it once setup runs.
- `conflict`: you decide in the change review.

![Protostar recipe editor](../assets/terminals/tui_recipe_editor.svg)

The editor is built for the keyboard, and the mouse works too. Moving never changes a value: only `Space` and `Enter` do. The footer shows the keys for whatever has focus, each button shows its own key, and `?` lists them all.

??? info "Every key in the recipe editor"
    --8<-- "keys_recipe_editor.md"

The editor fills in these details from your [global configuration](configuration.md) and git, and you can change any of them:

--8<-- "table_metadata.md"

### The Change Review

**Continue** (`Ctrl+S`) opens the change review, where you see everything before anything runs. Its left panel has three tabs:

- **Decisions** appears when something needs you: every conflict, and every change to a file you already have. Each row starts with what happens to it, and the tab shows how many are still open.
- **Files** lists every path Protostar plans, marked new, modified, conflict, existing, or after setup.
- **Setup** lists the commands and packages that follow.

The diff beside them shows the highlighted decision or file. Settling a conflict moves to the next open one. Nothing runs until you choose **Apply**.

??? info "Every key in the change review"
    --8<-- "keys_change_review.md"

![Protostar change review](../assets/terminals/tui_change_review.svg)

## What Happens When You Apply

Protostar writes the project files, then runs each command as its own step: `git init`, `uv init`, one `uv add` per dependency group, and the hook install. The running step shows a spinner, and each finished step leaves a `✔` line, so the completed work stays on screen:

![Protostar Init](../assets/terminals/cli_init.svg)

If a step fails or you press `Ctrl+C`, that step is marked `✖`, every change is rolled back, and the error follows. When output goes to a pipe or file, the spinner is left out but the `✔` lines stay. `--json` prints none of them.

A successful run ends with what to do next: the command that runs the app, when the project has one, and `protostar guide`, which shows how to test, check, and document the project. If a program that a selected tool needs isn't installed, the output ends with the one command that installs it; see [Tool Binaries](troubleshooting.md#tool-binaries-direnv-just).

## Existing Projects

When `init` runs in a folder that already holds a project but has no recipe yet, Protostar first reads what's there. Reading writes nothing and runs nothing.

What it reads fills in the recipe in place of defaults:

- The Python version, from `requires-python` or `.python-version`.
- The author, description, and GitHub account, from `[project]`.
- The license, from `[project].license`, the classifiers, or the license file's heading.
- The supported operating systems, from the classifiers.
- The copyright year, from the license file, so a regenerated license keeps its year.

A value you pass or type always wins over one it read. Runs without the editor use these values too.

The tools the project already uses start switched on in the recipe editor, each marked `found`. Press `i` on a tool to see what showed it, such as `justfile` or `pyproject.toml [tool.ruff]`. A found tool is only ever added: the template's choices and your configured defaults still apply to everything else, except that a found hook runner replaces the configured one. A found tool whose prerequisite is off stays off, still marked, so you can decide. Without the editor, a tool is never switched on because it was found; only flags select tools there.

The editor's headline says when it has filled in an existing project, and a note under **Tools** names any file it couldn't read. When the project has other GitHub Actions workflows, the CI tool's `i` popup lists them. `protostar init --dry-run --json` reports the same findings for scripts and agents (see the [machine interface](agent-interface.md)).

The change review then lists every change Protostar would make to a file you already have, and you can keep any of them out. **Keep all mine** (`K`) keeps the project exactly as it is, and `protostar sync` can take any change you kept out later (see [changes to files you already have](lifecycle.md#changes-to-files-you-already-have)).

## Files You Already Have

When a file Protostar would write already exists, such as `pyproject.toml`, the recipe editor's **Existing files** panel asks what to do with it:

- **Merge** keeps your content and adds what's missing.
- **Overwrite** replaces the file with Protostar's version.

Either choice prepares the review again with its diffs. **Cancel** exits without changing anything.

Under Merge, a file Protostar can't merge into is kept as it is and marked `conflict`. An existing `justfile` that Protostar has never managed is one example. Highlight it to see your version beside Protostar's, and settle it under **Conflicts**:

- **Keep mine** (`k`) leaves the file as it is and adopts it, so later updates merge into it line by line.
- **Take update** (`u`) replaces it.
- **Keep both** (`b`), offered when lines overlap, keeps both versions of those lines.
- **Leave open** (`x`) decides nothing now: your file stays, and `protostar status` keeps listing the conflict.

Everything else Merge would change in a file you already have is listed under **Changes to your file**: each key, table, list item, or dependency it adds. Each one applies unless you keep it out with `k`. Keeping it out records Protostar's version without writing it, so `protostar sync` can take it later. **Keep all mine** (`K`) keeps your side of every conflict and change at once, which leaves the project exactly as it is.

The review shows the result before anything runs. It covers the files written before the setup commands. It also covers configuration and dependencies when no command creates their files; anything a command creates is listed after setup, and `protostar sync` settles it the same way (see [changes to files you already have](lifecycle.md#changes-to-files-you-already-have)).

In a project Protostar already tracks, Merge works from what `protostar.lock` records, and only with the template the project already follows; see [A Project Can't Switch Templates](troubleshooting.md#a-project-cant-switch-templates).

Here is a tracked ML project after someone added their own astronomy dependencies, ignore rules, and data folders. It then runs the ML template again with `--mypy --docker --force-merge`:

- Their dependencies, ignore rules, and folders stay as they were.
- uv adds the new dependencies.
- Settings Protostar wrote and nobody edited take the template's current values. Edits and deletions stay, and the run reports each one.
- `.gitignore` gains the patterns it was missing, without duplicates.

??? abstract "See the changes"
    ```diff
    --8<-- "diff_ml_ml_merged_pyproject_toml.diff"
    --8<-- "diff_ml_ml_merged__gitignore.diff"
    ```

!!! tip "Without a terminal"
    In CI, or anywhere nothing can ask, choose with `--force-merge` or `--force-replace`.

## More Options

- **Preview without writing:** `--dry-run` shows what a run would do, without writing a file or running a command (for example, `protostar init --template cli --dry-run`). It shows the same review as the recipe editor: each file marked `new`, `modified`, or `conflict`, the commands and packages, and every conflict and proposal with its id.

    ![Protostar Dry Run](../assets/terminals/cli_dry_run.svg)
- **Settle decisions without the review:** `--resolve SELECTOR=CHOICE`, once per decision, settles the conflicts and proposals `--dry-run` lists (for example, `protostar init --template cli --force-merge --resolve 89cd01278762=desired`). `CHOICE` is `desired` to take the update, `local` to keep yours or keep a proposal out, or `both` for overlapping text lines. A file path as the selector settles every decision in that file. Without `--resolve`, a run keeps your version of every conflict and applies every proposal. `--resolve` doesn't choose between merging and overwriting, so existing files still need `--force-merge`. Add `--dry-run` to see the settled result first. It works like [`sync --resolve`](lifecycle.md#resolve-conflicts).
- **Output for scripts:** `--json` prints one JSON result on `stdout` and sends everything else to `stderr` (for example, `protostar init --template cli --json`). It can go anywhere on the command line. See the [Agent & Machine Interface](./agent-interface.md).
- **Shorter template flag:** `-t` is short for `--template` (for example, `protostar init -t cli`).
- **List templates:** `protostar init --list-templates` lists every built-in template and your configured aliases.
- **Template variables:** `--var NAME=VALUE`, once per variable, supplies a template's own variables (for example, `protostar init --from ./team.toml --var REGION=eu-west-1`). In a terminal, Protostar asks for any you leave out. Anywhere else, including under `--json`, a missing value is an error. Values are saved in the project's recipe, so never pass a secret. A value that looks like a credential stops `init`; if it isn't a secret, keep it with `--allow-secret NAME`. See [Template variables](project-recipes.md#template-variables).
- **Template options:** `--option NAME=VALUE`, once per option, chooses a template's [options](./authoring-templates.md#template-options): `true` or `false`, or one of a choice's values (for example, `protostar init --from ./team.toml --option database=postgres`). An option you leave out takes the template's default. The recipe editor shows a switch or a choice for each.
- **Python version:** `--python-version` sets the Python version for this run (for example, `protostar init --template cli --python-version 3.13`).
- **More detail:** `--verbose` (or `-v`) prints debug logs and full tracebacks.

## Set Up Once, Without Tracking

Use `--one-shot` when you want the project files without Protostar managing later updates:

```bash
protostar init --template cli --one-shot
```

Protostar writes the same files and installs the dependencies, including `uv.lock`. It doesn't add `[tool.protostar]` to `pyproject.toml` or write `protostar.lock`, so `status`, `diff`, and `sync` can't manage the project afterwards. The generated `AGENTS.md` describes the project without mentioning a recipe or `protostar sync`. Conflicts and rollback work as usual.

`--one-shot` needs a project with neither a recipe nor a `protostar.lock`. A later `init --force-merge` can start tracking the project, and the files already there stay yours unless you choose otherwise.

## Next Steps

- **[Templates<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./templates.md):** Use your team's templates from a file or repository, and supply their variables.
- **[Tooling & Flags Matrix<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./tooling-matrix.md):** Every tool Protostar sets up, its flag, and the files it writes.
- **[Global Configuration<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./configuration.md):** Set your default Python version, license, and template aliases once.
- **[CLI Reference<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./cli-reference.md#protostar-init):** Every `init` option, also printed by `protostar help init`.
- **[Troubleshooting & FAQ<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./troubleshooting.md):** Fixes for missing programs, existing files, and editor setup.
