---
description: "Every tool Protostar can set up, the flag that turns it on, and the files it adds."
---

# Tooling & Flags Matrix

Every tool Protostar can set up has a flag that turns it on or off, and writes its settings, hooks, and CI steps for you, merging them into files you already have, such as `pyproject.toml`. This page lists each tool and its flag, and the built-in templates.

!!! note "Why prek gets a `.pre-commit-config.yaml`"
    With `--prek`, Protostar still writes `.pre-commit-config.yaml` rather than `prek.toml`. prek reads that file too, so the project isn't tied to one hook runner: collaborators who use `pre-commit`, editor integrations, and Renovate's hook updates all read the same file.

!!! tip "Why rumdl is the Markdown linter"
    Every built-in template's production tier lints and formats Markdown with `rumdl`. It installs as a development dependency through uv, locked in `uv.lock`, and keeps its settings in `pyproject.toml` under `[tool.rumdl]`, so the project needs no Node.js and no extra configuration file. `--markdownlint` sets up MarkdownLint instead.

## Every Tool and Its Flag

--8<-- "table_tooling.md"

## Managed AGENTS.md

`--agents` (or `agents = true` in your [global configuration](./configuration.md)) writes an `AGENTS.md` guide for coding agents such as Codex, Cursor, and Copilot. It is off by default and no built-in template enables it, because working with agents is a developer preference rather than a project shape.

The guide states only facts Protostar knows about the project: the Python version and uv workflow, the `just` recipes (or the raw commands when `just` is off) for formatting, linting, type checking, and testing, and the hook runner that gates each commit. It holds no general advice, so it has nothing to go stale beyond what Protostar keeps current.

Protostar owns only the block between its region markers. Put project notes above or below the block; they are never touched. When the tooling changes, `protostar sync` updates the block, merging line by line with anything you edited inside it. If your edit and the update touch the same or adjacent lines, sync keeps the block exactly as you left it and reports a conflict with those line numbers instead. Running with `--agents` against an existing `AGENTS.md` appends the block after your content.

The block opens with the document's top-level heading so a fresh scaffold passes the Markdown linters. If you merge it into an `AGENTS.md` that already has its own top-level heading, rumdl and MarkdownLint report a second top-level heading (MD025); move your notes under the guide's heading or demote your own.

A `--from` template can add its own team conventions to the same file with a named append, which Protostar places after the managed block:

```toml
[appends."AGENTS.md".conventions]
content = """
## Team Conventions

- Branch from `main` and open a pull request for every change.
"""
```

A template can't also ship `AGENTS.md` as a whole file under `[files]` while `--agents` is on: Protostar can't both keep the block current and leave the file to you, so planning stops with an error.

## Community Health Files

`--community` (or `community = true` in your [global configuration](./configuration.md)) writes the files GitHub shows people who want to contribute. The `cli` and `lib` templates turn it on, because they are packages other people use and improve.

| File | Content | Kept in sync |
| :--- | :--- | :--- |
| `CONTRIBUTING.md` | Setup, the checks a change passes, the hook runner, and the commit convention, from the project's tooling | Yes, as a managed block |
| `CODE_OF_CONDUCT.md` | [Contributor Covenant 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/), with the author email as the enforcement contact | No |
| `SECURITY.md` | Asks for private reports, through GitHub's private vulnerability reporting and the author email | No |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | An issue form asking for steps to reproduce, the version, and one of the supported operating systems | No |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | An issue form asking for the problem before the solution | No |
| `.github/ISSUE_TEMPLATE/config.yml` | Links the issue chooser to private vulnerability reporting; written only when a GitHub username is set | No |
| `.github/pull_request_template.md` | A summary and a checklist of the checks the project can run | No |

`CONTRIBUTING.md` works like the [managed AGENTS.md](#managed-agentsmd): Protostar owns only the block between its region markers, keeps it current on `protostar sync`, and shares the command list with `AGENTS.md`, so the two never disagree. Add project notes above or below the block. The other files are written once and are yours from then on: `protostar sync` never rewrites them, and a deleted one stays deleted.

Without an author email, the code of conduct keeps the covenant's `[INSERT CONTACT METHOD]` placeholder so the missing contact is visible; set `author_email` in your configuration or the recipe editor to fill it in.

GitHub reads a contributing guide, code of conduct, security policy, or pull request template from `.github/`, the repository root, or `docs/`. Protostar creates each at its most visible path, but when your project already has one in any of those places, it uses that file and never adds a second copy. A Markdown issue template with the same name as a form, such as `.github/ISSUE_TEMPLATE/bug_report.md`, keeps Protostar from adding the form beside it.

## Built-in Templates

Each built-in template is a kind of project: a command-line app, a library, a web service, an analysis workbench. Each brings its folders, starter files, and dependencies, and adds to each tool's defaults only the settings that kind of project needs.

!!! tip "No pinned versions"
    Templates name packages without versions. uv picks the newest compatible release of each when the project is set up, and records it in `uv.lock`.

--8<-- "table_templates.md"

## Related Guides

- **[Environment Initialization<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./init.md):** Every file each built-in template writes.
- **[Global Configuration<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./configuration.md):** Choose the tools every new project starts with.
- **[CLI Reference<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./cli-reference.md):** Every tool flag and command-line option.
