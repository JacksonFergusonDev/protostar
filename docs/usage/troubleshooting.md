---
description: "Fixes for missing programs, editor setup, and the other problems people run into most."
---

# Troubleshooting & FAQ

Fixes for the problems people run into most: missing programs, existing files, untrusted templates, errors from `status` and `sync`, and editor setup.

## Missing Dependencies & Environment Checks

Protostar needs `uv` and `git` for every project, and checks for them before it writes anything. If either is missing, it stops with a `MissingDependencyError`, and its hint is one command that installs everything missing. [Installation](../installation.md) covers installing both on each platform.

### `uv` Is Not Installed or Not in `$PATH`

Protostar runs [uv](https://docs.astral.sh/uv/) to create every project and install its packages, so it can't run without it.

=== "macOS & Linux"
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Homebrew (macOS)"
    ```bash
    brew install uv
    ```

=== "Windows (PowerShell)"
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

!!! tip "Programs installed with `uv tool` aren't found"
    Run `uv tool update-shell` and open a new terminal. It adds the folder uv installs programs into to your `PATH`.

### Tool Binaries (`direnv`, `just`)

A program that only a selected tool runs, such as `direnv` or `just`, never stops a run. The tool's files are still written, since they're correct whether or not the program is installed. Protostar skips only the steps that need it, and ends its output with one command that installs every missing program. For `direnv`, also run `direnv allow` in the project once it's installed. The recipe editor marks such a tool `not installed`, and its preview and the change review list the step it skips.

![A run whose direnv and just are missing](../assets/terminals/cli_missing_tools.svg)

The command comes from the package manager Protostar finds. Where it finds none, it links here instead:

=== "macOS"
    ```bash
    brew install direnv just
    ```

=== "Linux"
    ```bash
    sudo apt install direnv
    uv tool install rust-just
    ```

    Use `sudo dnf install direnv` on Fedora, or `sudo pacman -S direnv` on Arch. `just` installs with uv on every distribution: the same current release everywhere, with no `sudo`, including releases that don't package it, such as Debian 12.

=== "Windows"
    ```powershell
    winget install --exact --id direnv.direnv
    winget install --exact --id Casey.Just
    ```

direnv does nothing until it is [hooked into your shell](https://direnv.net/docs/hook.html): add its hook line to your shell's startup file, open a new terminal, and run `direnv allow` in the project. From then on, entering the project's folder activates its virtual environment.

## Working Offline

Installing packages needs the network: `uv` fetches them from the package index. Everything before that works offline, including the recipe editor, `--dry-run`, and the change review. Protostar doesn't test your connection before a run. A proxy or a private package index can make a probe wrong, and `uv` can install from its cache without the network.

- **Before applying**, the recipe editor and the change review say when Protostar couldn't reach the network. It noticed while fetching the latest git hook versions; without them, it pins the versions it shipped with.
- **If `uv` fails** because it couldn't connect, the error says so, and the run rolls back as it does for any failed install. Reconnect and run the command again, or check your proxy or index settings.
- **With packages already in `uv`'s cache**, set `UV_OFFLINE=1` so `uv` installs from the cache instead of the network.

## Workspace Collisions

When a file Protostar would write already exists, such as `pyproject.toml` or `README.md`, it stops with a `WorkspaceCollisionError` rather than touch your work without asking.

```text
Workspace Collision: Protostar detected existing configuration files in the workspace.
  - pyproject.toml
```

### In a Terminal

The recipe editor's **Existing files** panel asks what to do with them:

1. **Merge** keeps your values and adds what's missing. Where your content and Protostar's disagree, yours stays and the change review lists the decision; see [changes to files you already have](lifecycle.md#changes-to-files-you-already-have).
1. **Overwrite** replaces those files with Protostar's version.

**Cancel** leaves without changing anything.

### Without a Terminal (CI and Agents)

Without a terminal, or with `--json`, nothing asks. Choose with a flag:

```bash
# Merge into the existing files
protostar init --template cli --force-merge

# Replace the existing files with Protostar's version
protostar init --template cli --force-replace
```

## Remote Template Security Alerts

A template you haven't trusted (a `--from` path or URL, or an alias without `trusted = true`) runs no command until you confirm it. In a terminal, the change review lists the commands under **Untrusted template**, and **Apply** stays off until you tick the box. Without a terminal, the run stops with `SecurityViolationError` (exit code `77`) before writing anything.

- **For one run,** pass `--trust`. It still lists the commands.
- **Every time,** give the template an alias with `trusted = true` in your configuration (`protostar config --edit`):

    ```toml
    [templates.team-backend]
    source = "https://github.com/YourOrg/standards"
    trusted = true
    ```

See [Trusting a Template](templates.md#trusting-a-template) for exactly which templates count as trusted, and what `sync` asks.

## Template Variables That Look Like Credentials

Template variables are saved to your project's recipe and rendered into its files, so Protostar holds back a newly entered value that looks like a credential before anything is written:

```text
Template variable values look like credentials:
  - org_name (gitleaks rule github-pat)
```

The error names the variable and the [gitleaks](https://github.com/gitleaks/gitleaks) rule it matched, never the value. In `--json` mode the same pairs appear under `error.findings`. In an interactive terminal, a flagged `--var` value opens the variables screen instead of failing, so you can change it or keep it there.

- **You entered a secret:** enter a non-secret value instead, and supply the secret through the environment when the project runs.
- **The template asks for a secret:** the template needs fixing; see [Variables Are Not Secrets](authoring-templates.md#variables-are-not-secrets).
- **The value isn't a secret:** keep it. In the editor, tick **Not a secret; keep this value** under the field. On the command line, add `--allow-secret NAME` for that variable. The confirmation covers only that variable, and once the value is recorded, later runs don't ask again. If a rule flags ordinary values often, [file an issue](https://github.com/JacksonFergusonDev/protostar/issues) with the rule id and the value's shape (not the value).

## Editor Schema Setup for Custom Templates

A Protostar template is a TOML file with a JSON Schema. Point your editor at the schema, and it completes keys, shows each key's description, and flags mistakes as you type.

Export the schema from the Protostar you use, and keep it beside your template:

```bash
protostar export-schema --json > protostar-template.schema.json
```

Export it again after upgrading Protostar, so the schema matches the template format that release reads.

### VS Code & Cursor

1. Install the **Even Better TOML** extension (`tamasfe.even-better-toml`).
1. Add the schema modeline at the top of your `protostar.toml`, pointing at the exported file:

```toml
#:schema ./protostar-template.schema.json

name = "my-custom-template"
description = "FastAPI service with Ruff"
dependencies = ["fastapi", "uvicorn"]
ruff = true
```

### JetBrains (PyCharm / IntelliJ)

1. Open **Settings** (**Preferences** on macOS), then **Languages & Frameworks** › **Schemas and DTDs** › **JSON Schema Mappings**.
1. Add a new mapping named `Protostar Template`.
1. Set the schema file to the exported `protostar-template.schema.json`.
1. Add the file pattern `*protostar*.toml`.

## Errors from Status and Sync

### Protostar Is Older Than the Project

```text
protostar.lock was written by Protostar 0.12.0, but Protostar 0.11.2 is installed.
```

`OutdatedProtostarError`: someone synced the project with a newer Protostar than yours. Built-in templates come from the installed release, so an older one would plan older files and offer them as an update, quietly undoing the newer work. `init`, `status`, `diff`, and `sync` refuse instead. Upgrade, with `brew upgrade protostar` or `uv tool upgrade protostar`, and run the command again. To keep a team and CI on one release, see [Keep Protostar Versions in Step](automating-updates.md#keep-protostar-versions-in-step).

### The Review Is Out of Date

```text
Review input changed: pyproject.toml.
```

`StaleReviewError`: a file changed between the review Protostar showed you and the moment it would apply it, for example because an editor saved it, or a formatter rewrote it. Protostar never applies changes you didn't see, so it stops before writing anything. Run the command again to review the project as it is now.

### No Conflict Matches

```text
No conflict matches: 3f2a9c1b7d4e.
```

`UnmatchedResolutionError`: a `--resolve` names a decision the current review doesn't have. A decision's `id` covers both sides, so it stops matching as soon as either side changes: you edited the file, or the template moved. Run `protostar status` again and use the `id`s it prints now. Nothing was written. See [Resolve Conflicts](lifecycle.md#resolve-conflicts).

### A Project Can't Switch Templates

```text
This project follows a different template.
```

The template you passed isn't the one the project records. A project follows one template for life: switching would turn every file the old template wrote into a conflict with no sensible owner. Pass the template the project records; `protostar status` names it, and the recipe editor preselects it. To move a repository template to a new release, use `protostar sync --to <ref>`, which is the same template at another version.

To start over with a different template, `protostar eject` the project first; the files stay, and the next `init` treats them as yours.

## Execution Interruptions & Rollback

If a run fails or you press `Ctrl+C`, Protostar puts back every file it changed.

!!! info "What rollback covers"
    [Automatic Rollback](./rollback.md) covers what gets restored, what might remain, what to do after a `RollbackFailedError`, and what `Ctrl+C` does.

## Debugging & Bug Reporting

### Verbose Debugging (`--verbose`)

For full Python tracebacks and debug logs, add `-v` or `--verbose` to any command:

```bash
protostar init --template cli --verbose
```

### Automated Crash Reporting

If Protostar itself crashes, which is a bug rather than a problem with your project:

1. A crash during a run rolls the project back, like any other failure.
1. It prints a link that opens a GitHub issue filled in with your operating system, Python version, the command you ran, and the traceback. Nothing is sent until you submit it, so read it first: a traceback can name paths on your machine.

### Filing Bugs & Asking Questions

If this page doesn't cover your problem:

- **Search the existing issues:** the [issue tracker](https://github.com/jacksonfergusondev/protostar/issues) may already have a fix or a workaround.
- **Report a bug:** [open an issue](https://github.com/jacksonfergusondev/protostar/issues/new) with your operating system, Protostar version, and the `--verbose` output.
- **Ask a question or request a feature:** open an issue for questions, or use the [feature request form](https://github.com/jacksonfergusondev/protostar/issues/new?template=feature_request.yml) for ideas.

## Related Resources

- **[Automatic Rollback<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./rollback.md):** What gets restored, what might remain, and how to recover from a partial rollback failure.
- **[Error Handling Architecture<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](../mechanics/error_handling.md):** Every error, its exit code, and how failed commands are reported.
- **[Setting Up a Project<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./init.md):** How `init` handles files you already have, and what `--force-merge` does.
- **[Global Configuration<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./configuration.md):** View, change, or reset your settings.
