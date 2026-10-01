---
description: "What Protostar does that other Python scaffolding tools don't, where they're the better choice, and how they compare."
icon: material/scale-balance
---

# Why Protostar?

Protostar is a scaffolding tool that understands the Python tools it sets up and the files they live in. That understanding is what keeps it simple. A template says which tools it wants (`ruff = true`, `mypy = false`), and Protostar writes everything those tools need. When the template changes, the update merges by meaning rather than by line: most of it applies on its own, and what's left is a clear choice about one setting, never a block of conflict markers.

General-purpose templaters like Copier and Cookiecutter work with any language because they treat every file as text. Protostar makes the opposite trade: it only does Python, and in exchange its templates stay short and its updates stay clean.

<div class="grid cards" markdown>

- :material-text-box-check-outline: **Templates declare, they don't script**

    A template is a short TOML file: the tools you want, your dependencies, and only the settings that differ from each tool's defaults. There's no Jinja and no conditional logic.

- :material-toggle-switch-outline: **Every tool is a switch**

    Each tool brings its own configuration, commit hooks, and CI steps. Turn any tool on or off, at `init` or a year later, without touching the template.

- :material-source-merge: **Merges that understand the file**

    `pyproject.toml` merges key by key, dependencies go through uv, and workflows merge by job and step. Changes that collide in a line-based merge simply combine.

- :material-shield-check-outline: **Clear decisions, not conflict markers**

    A real conflict is one setting, with both sides and the command for each choice. Your version stays in place until you choose, and a failed run rolls back.

- :material-home-import-outline: **Works on the project you already have**

    It reads an existing repository, proposes each change it would make, and lets you keep yours, including all of them.

- :material-robot-outline: **Safe to automate**

    `protostar sync --check` gates CI, and every command speaks JSON without prompting, for scripts and coding agents.

</div>

## Simple, Declarative Templates

### A Template Says What, Not How

Each tool Protostar supports is a module that knows its own configuration: the settings it needs in `pyproject.toml`, its commit hook, its CI step, its entry in `.gitignore`. A template doesn't write any of that. It names the tools it wants and states only what's different about its project, such as a stricter setting, a dependency, or a starter file.

Here is a complete template for a FastAPI service with a full quality gate, next to what the same template takes in Copier:

<div class="grid cards" markdown>

- **Protostar:** the whole template

    ```toml
    name = "Service"
    description = "FastAPI service with the team's quality gate"

    dependencies = ["fastapi", "uvicorn"]

    ruff = true
    mypy = true
    pytest = true
    prek = true
    ci = true
    docker = true

    [dev.pyproject.strict_typing]
    requires = "mypy"
    content = '''
    [tool.mypy]
    strict = true
    '''
    ```

- **Copier:** the files the author writes and maintains

    ```text
    copier.yml
    pyproject.toml.jinja
    .pre-commit-config.yaml.jinja
    .github/workflows/ci.yml.jinja
    {% if use_docker %}Dockerfile{% endif %}.jinja
    {% if use_docker %}.dockerignore{% endif %}.jinja
    .gitignore
    ```

    Every setting, hook version, and action version lives in these files. Each optional tool needs a question in `copier.yml` and an `{% if %}` in every file it touches.

</div>

From those 18 lines, `protostar init` produces a `pyproject.toml` with Ruff, mypy, and pytest configured, a commit hook configuration, a GitHub Actions workflow, a Dockerfile, and ignore files. That's about 200 lines outside `pyproject.toml`, and the template's author writes and maintains none of them. When Protostar improves a tool's defaults, every template gets the improvement.

Templates are data, not code. A template has a JSON Schema, so your editor can validate it as you type, and `protostar check-template` lints it in CI. Placeholders like `<% PACKAGE_NAME %>` are the only markup inside files. A single TOML file is a complete template; a folder or repository adds starter files.

### Every Tool Is a Switch

Because each tool is a component, every tool in every template is already a choice, and the author writes no question for it. mypy alone appears in four places in the project above: a dev dependency, the `[tool.mypy]` table, a commit hook, and a CI step. One flag covers all four:

```bash
protostar init --from service.toml --no-mypy --no-docker
```

The same holds later. Turn a tool off in an existing project, and `protostar sync` removes what it added: unedited configuration disappears, and anything you edited is kept as a decision for you.

Templates can also offer two tiers of the same project shape: **workbench** for exploring, and **production** for the full quality gate. An analysis project can start lean and gain CI, commit hooks, and type checking the day it becomes something to publish:

```bash
protostar sync --tier production
```

A template's own choices, like which database to use, are declared [options](usage/authoring-templates.md#template-options). An option includes or leaves out whole files, dependencies, and configuration blocks, so a choice never turns into conditional logic inside a file.

## Updates That Understand Your Files

### Merges by Structure, Not by Line

Copier and Cruft update a project by regenerating the template's old and new versions and merging the difference into your files line by line, the way Git merges branches. That works well for most files. It works worst on the ones a Python project changes most: `pyproject.toml`, where you and the template add to the same lists, and `uv.lock`, which nobody should merge by hand.

Protostar reads each file it manages in that file's own format, and merges only the parts that changed:

| File | How an update merges |
| :--- | :--- |
| `pyproject.toml`, `zensical.toml` | Key by key and table by table, keeping your comments and formatting. Ruff's rule lists merge as sets, so your rules and the template's both stay. |
| Dependencies | Added and removed through uv, which rewrites `uv.lock`. The lockfile is never merged as text. |
| GitHub Actions workflows | By job and by step name, so your own jobs, steps, and triggers stay. An action version you or Renovate changed is yours. |
| Hook configuration, Codecov, Read the Docs | Key by key (YAML). |
| Renovate and VS Code settings | Key by key, comments included (JSONC). |
| `justfile`, `Dockerfile`, managed blocks in `AGENTS.md` and `CONTRIBUTING.md` | Line by line, three ways, like Git. |
| `.gitignore` | Missing patterns are added. Nothing is removed. |

It works from a record. `protostar.lock` stores what Protostar last applied to each file, so it can tell your edit from its own update. It never has to regenerate an old template version to find out, which is how Copier's update works, and why that update depends on the old version still rendering. Content Protostar didn't write stays yours unless you choose otherwise, even when it's identical to what Protostar would write.

### One Update, Two Tools

Here is the same template update applied by Copier and by Protostar. The project started from a template that depends on `httpx` and configures Ruff. Since then, the team has run `uv add rich` and set Ruff's `line-length` to 100. The template's next release adds `pydantic`, a `pytest` dev dependency, and Ruff's `SIM` rules.

<div class="grid cards" markdown>

- **Copier:** `copier update`

    ```toml
    dependencies = [
        "httpx",
    <<<<<<< before updating
        "rich>=15.0.0",
    =======
        "pydantic",
    >>>>>>> after updating
    ]
    ```

    It merged the dev dependency and Ruff rules correctly and kept the line length. But both sides had added a line after `httpx`, which a line-based merge can't settle, so it wrote these markers, and three more sets into `uv.lock`. The command exited successfully, and uv can't read the project until someone resolves both files by hand.

- **Protostar:** `protostar sync`

    ```diff
     dependencies = [
         "httpx>=0.28.1",
    +    "pydantic>=2.13.5",
         "rich>=15.0.0",
     ]

     dev = [
    +    "pytest>=9.1.1",
         "ruff>=0.16.9",
     ]

    -extend-select = ["B"]
    +extend-select = ["B", "SIM"]
    ```

    It added both packages through uv, which rewrote `uv.lock` itself, and merged the Ruff rules by key. It reported the line length as an edit it kept, with the command that takes the template's value instead, and `protostar sync --check` passed.

</div>

Nothing about this scenario is unusual. Adding a dependency is routine on both sides, which is why a line-based merge meets it so often.

??? info "How this was run"
    Copier 9.18.2 and Protostar 0.10.0, on 2026-09-30. Each template lived in a local folder, and Copier's was a Git repository with a tag per release, as Copier's updates require. Its template ran `uv lock` as a task, as uv templates commonly do. The Protostar template declared the same dependencies and a `[tool.ruff.lint]` payload, and was registered as an alias with `trusted = true`, the counterpart of Copier's `--trust`. The commands were `copier update --trust --defaults` and `protostar sync`, each run in a committed project after the same edits.

### Clear Decisions, Not Conflict Markers

Structure-aware merging leaves only true conflicts: you and the update changed the same setting. Had the template in the example above also changed `line-length`, this is all `protostar status` would ask about:

```text
pyproject.toml tool.ruff.line-length: You and the update both changed it.
  Yours stays until you choose:
    keep yours        protostar sync --resolve 76d476390115=local
    use the update's  protostar sync --resolve 76d476390115=desired
```

- Your version stays in the file until you choose. Protostar never writes conflict markers or `.rej` files.
- `protostar status`, `protostar diff`, and `protostar sync --dry-run` show every pending change as a labelled file tree and unified diffs, before anything is written.
- In a terminal, `protostar sync` opens a review screen with your side, the update's side, and the file each choice produces. Headless, `--resolve` settles each conflict by an ID derived from its content, so a choice can never apply to content you didn't review.
- An edit you keep stays kept, and `sync --check` still passes. You can take the update later, one edit at a time.
- Execution is transactional. If a step fails or you press Ctrl+C, every file Protostar wrote, including `pyproject.toml` and `uv.lock`, is restored to its exact original bytes.

<div class="protostar-demo-shell">
  <div class="panel-top">
    <span class="terminal-dots" aria-hidden="true">
      <span class="dot dot-close"></span>
      <span class="dot dot-minimize"></span>
      <span class="dot dot-maximize"></span>
    </span>
    <span class="terminal-title">PROTOSTAR / SYNC</span>
  </div>
  <div class="protostar-asciinema" data-asciinema="../assets/demo_sync.cast">
    <noscript>
      <a href="../assets/demo_sync.cast">Download the Protostar terminal recording</a>
    </noscript>
  </div>
</div>

A template update meets a team's own edits: keep both versions of the overlapping lines, take the template's stricter coverage floor, apply, and `sync --check` passes.

## Existing Projects, Releases, and Automation

### It Works on the Project You Already Have

Most templates assume an empty directory. Run `protostar init` in an existing repository, and it first reads what's there: the Python version from `requires-python`, the author and license from `[project]`, and the tools you already use, which the recipe editor starts switched on. Reading changes nothing and runs nothing.

Every change it would then make to a file you wrote is a proposal you can keep out. **Keep all mine** adopts the project exactly as it is. `protostar status` then lists each change you kept out, with the command that takes it, so the project can adopt its template's standards one at a time. With Copier, the documented route is to overwrite the project and restore your changes by hand; a first-class adopt command is an [open request](https://github.com/copier-org/copier/issues/2486).

### Template Releases You Control

A repository template starts new projects on its newest release tag. `protostar status` says when a newer release exists, and `protostar sync --to v1.3.0` moves the project there with the same review as any update. Each project records the exact commit it applied, so a moved tag or a pushed branch changes nothing until you move the project yourself. You can watch this happen in [protostar-example-project](https://github.com/JacksonFergusonDev/protostar-example-project): when [its template](https://github.com/JacksonFergusonDev/protostar-example-templates) tagged v1.1.0, a scheduled workflow opened [this update pull request](https://github.com/JacksonFergusonDev/protostar-example-project/pull/1).

Declarative [migrations](usage/authoring-templates.md#migrations) handle what a merge can't, such as a renamed or retired starter file, or a renamed variable. They never run commands, so a dry run lists them and a failed run rolls them back.

### It's Safe to Automate

- `protostar sync --check` exits `1` when a project is out of step with its recipe, so CI can gate on it. Edits you chose to keep don't fail it.
- Every command takes `--json`: one envelope on `stdout`, and no prompts. A missing decision fails with a structured error instead of hanging.
- `--dry-run` shows the complete plan without writing a file or running a command.
- `protostar.lock` records the Protostar release that wrote it. An older release refuses to run instead of quietly rolling the project back, so a teammate on an old version can't undo an update.

[Automating Updates](usage/automating-updates.md) has a ready-made workflow that opens a weekly update pull request. The same commands let a coding agent plan, review, and apply changes; see the [agent interface](usage/agent-interface.md).

## Why Not Ask a Coding Agent?

An agent can write a good setup in a minute, tailored to what you asked for. But it writes it a little differently in every repository, and a year later it can't tell which lines you changed on purpose. Protostar gives the setup a record: projects from the same template start alike, and every later change arrives as a reviewable diff. The two work well together, since an agent can drive Protostar with `--json`, `--dry-run`, and `--resolve`.

## When Another Tool Is the Better Choice

- **Your project isn't Python, or doesn't use uv.** Protostar builds on uv, so it doesn't fit a project managed by Poetry, PDM, or conda. Copier and Cookiecutter work with any language and any tooling.
- **Your template's value is starter code that keeps changing.** Protostar keeps configuration, dependencies, tool files, and managed blocks current. The starter files a template ships are written once and then belong to the project. A later release can move or retire them through a migration, but its edits to them don't reach existing projects. Copier merges every file on every update, starter code included.
- **You need logic inside files.** Copier's Jinja can compute any file from the answers to its questions. Protostar's options include or leave out whole files and configuration, and its placeholders only insert values.
- **You want files once and never again.** Cookiecutter has the largest collection of ready-made templates, and a GitHub template repository needs no tool at all.
- **You want a bare project.** `uv init` is already installed and creates one instantly. Protostar runs `uv init` for you, and adds everything after it.
- **You want every generated file locked.** projen generates configuration from a `.projenrc` program and treats generated files as read-only, which suits teams that allow no local deviation. Protostar assumes every project will diverge somewhere, and keeps those edits.

## Where Protostar Is Headed

Protostar is young, and it grows with the people using it. What comes next depends on what users run into, so if something stands between Protostar and your project or your team, [open a feature request](https://github.com/jacksonfergusondev/protostar/issues/new?template=feature_request.yml). Each release's notes are on [GitHub](https://github.com/jacksonfergusondev/protostar/releases).

These are the gaps known today:

- GitHub Actions is the only CI it generates.
- A project inside a uv workspace isn't supported.
- A project follows one template; templates can't be layered, such as an organization's base under a team's template.
- Nothing opens update pull requests for you yet. Copier has a Renovate manager that does; with Protostar, a [scheduled workflow](usage/automating-updates.md#open-update-pull-requests-on-a-schedule) runs `protostar sync` and opens the pull request itself.
- There are few community templates so far.

Until 1.0, a release may still change a command or the template format when that makes Protostar simpler.

## At a Glance

| | Protostar | Copier | Cookiecutter + Cruft | `uv init` |
| :--- | :--- | :--- | :--- | :--- |
| **Languages** | Python, with uv | Any | Any | Python |
| **Template format** | TOML and plain files, with a JSON Schema | YAML questions and Jinja files | JSON variables and Jinja files | None: app, library, or bare |
| **Tool configuration** | Written by Protostar's modules; templates state the difference | Written by the template author | Written by the template author | None |
| **Optional tools** | Every tool is a flag, with nothing in the template | A question, plus a conditional in each file | A variable, plus a conditional in each file | — |
| **Updates a project** | `protostar sync` | `copier update` | `cruft update` | No |
| **How updates merge** | By key, job, and step; dependencies through uv; lines only for free-form files | Line by line, through Git | Line by line, through Git | — |
| **Updates starter files** | No: written once; migrations move or retire them | Yes | Yes | — |
| **Conflicts** | Kept out of the file and settled by a choice | Markers or `.rej` files written into the project | Markers or `.rej` files written into the project | — |
| **Existing projects** | Reads them and proposes each change | Overwrite or skip each file | `cruft link`, for projects first made from the template | — |
| **CI check** | `sync --check`: is the project in step? | `check-update`: is a newer release out? | `cruft check`: is a newer template out? | — |
| **Machine interface** | `--json` on every command | Python API | Python API | — |
| **Maturity** | New, pre-1.0 | Mature, wide template ecosystem | The largest template ecosystem | Built into uv |

## Next Steps

- **[Your First Project](first-project.md):** Scaffold a project step by step, from choosing a template to running its checks.
- **[Authoring Templates](usage/authoring-templates.md):** Write a template for your team, from a single TOML file to a versioned repository.
- **[Project Lifecycle](usage/lifecycle.md):** Review, sync, and resolve updates in a project you already have.
- **[Design Principles](design-principles.md):** The architecture behind the planning, merging, and rollback guarantees.
