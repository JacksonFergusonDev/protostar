# Tooling & Flags Matrix

Protostar provides a modular matrix of tooling modules and built-in templates. Tooling modules inject static analysis, testing frameworks, and continuous integration workflows, safely deep-merging configurations into existing project files like `pyproject.toml`.

!!! note "Design Decision: Configuration Portability"
    Even when using `--prek`, Protostar generates a `.pre-commit-config.yaml` file instead of `prek.toml`. Because `prek` fully supports the standard YAML configuration, this strategy ensures maximum ecosystem compatibility. Your repository remains decoupled from the specific hook engine, meaning CI/CD pipelines, IDE plugins (like Dependabot/Renovate), and collaborators using legacy `pre-commit` will still be able to run and update your hooks flawlessly.

!!! tip "Design Decision: Markdown Tooling Architecture"
    Protostar adopts `rumdl` as the default markdown linter and formatter for production templates (`cli`, `api`, `ml`). Because `rumdl` is a fast Rust binary, it installs cleanly as a dev dependency via `uv` (tracked in `uv.lock`) and keeps all configuration consolidated inside `pyproject.toml` (`[tool.rumdl]`). This avoids external Node.js/npx runtime requirements and prevents configuration file sprawl. For projects requiring legacy MarkdownLint tooling, `--markdownlint` remains available as an optional module.

## Available Tooling Modules

--8<-- "table_tooling.md"

## Managed AGENTS.md

`--agents` (or `agents = true` in your [global configuration](./configuration.md)) writes an `AGENTS.md` guide for coding agents such as Codex, Cursor, and Copilot. It is off by default and no built-in template enables it, because working with agents is a developer preference rather than a project shape.

The guide states only facts Protostar knows about the project it scaffolded: the Python version and uv workflow, the `just` recipes (or the raw commands when `just` is off) for formatting, linting, type checking, and testing, and the hook runner that gates each commit. It holds no general advice, so it has nothing to go stale beyond what Protostar keeps current.

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

A template cannot also ship `AGENTS.md` as a whole file under `[files]` while `--agents` is on; the two ownership models conflict and planning stops with an error.

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

Built-in templates are project shapes that build on a base language footprint. They inject structural scaffolding, directories, and domain-specific dependencies into the environment manifest, and they add only the tooling configuration that defines their shape on top of each tool's casual-user defaults.

!!! tip "Dynamic Resolution"
    Templates do not hardcode package versions. They pass the library requirements directly to the package manager (`uv`), allowing your environment to resolve the latest compatible machine learning, astrophysics, or API packages at runtime.

--8<-- "table_templates.md"

## Related Guides

- __[Environment Initialization](./init.md):__ See complete generated directory trees and configuration footprints for CLI, Library, API, ML, and Astro templates.
- __[Global Configuration](./configuration.md):__ Configure persistent default tooling selections so your preferred flags apply automatically.
- __[CLI Reference](./cli-reference.md):__ Comprehensive reference table for all tri-state tooling flags and CLI options.
