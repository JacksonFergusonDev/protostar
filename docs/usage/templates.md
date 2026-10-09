---
description: "Use built-in templates, your team's from a file or repository, and aliases, and decide which templates may run commands."
---

# Templates

A template describes a kind of project: its tools, dependencies, settings, and starter files. Use a built-in one, your team's from a file or a Git repository, or a short alias for either, and every project made from it starts the same way.

<div class="grid cards" markdown>

- :material-cube-outline: **Built-in Templates**

    The kinds of project that ship with Protostar: `api`, `astro`, `cli`, `lib`, and `ml`.

- :material-web: **External & Remote (`--from`)**

    Apply templates from a GitHub, GitLab, Bitbucket, Codeberg, or Sourcehut repository at a release you choose, or from local files.

- :material-card-account-details-outline: **Global Aliases (`[templates]`)**

    Give a template a short name in your configuration, so you never retype its URL.

- :material-shield-alert-outline: **Trust Before Commands**

    A template you haven't trusted runs no command, on `init` or `sync`, until you confirm the list of commands it needs.

</div>

## Choose a Template

`init` takes a template in one of two ways:

```bash
# A built-in template or one of your aliases, by name (-t for short)
protostar init --template astro

# Any other template, from a file or URL
protostar init --from https://github.com/YourOrg/standards/blob/main/backend.toml
```

### Listing Available Templates

```bash
protostar init --list-templates
```

This lists every built-in template and every alias in your configuration, with its name, description, whether it's built in, whether it's trusted, and where it comes from. With `--json`, it prints the same list as a JSON array.

### Turning a Template's Tools On and Off

A template's tool choices are defaults. `--<tool>` and `--no-<tool>` override any of them for the project, as [Setting Up a Project](init.md#turning-tools-on-and-off) shows, and [which choice wins](project-recipes.md#which-choice-wins) gives the full order.

## External & Remote Templates (`--from`)

`--from` takes a local path, a URL to a TOML file, or a link to a repository.

### Repository URLs

A template in a GitHub, GitLab, Bitbucket, Codeberg, or Sourcehut repository is identified by its repository and its path inside that repository. The revision you apply is a separate choice, so the same template can move between releases without becoming a different template. Point `--from` at the repository, or at any web page, raw file, or archive in it:

```bash
# The repository's newest release
protostar init --from https://github.com/YourOrg/fastapi-template

# A named tag, branch, or full commit SHA
protostar init --from https://github.com/YourOrg/fastapi-template/tree/v1.2.0

# A template in a subdirectory of the repository, at a branch
protostar init --from https://github.com/YourOrg/templates/tree/main/services/api
```

Each of these forms names a repository, and optionally a ref (a tag, branch, or commit) and a path:

| Provider | Examples |
| :--- | :--- |
| **GitHub** | `/tree/<ref>/<dir>`, `/blob/<ref>/api.toml`, `/archive/refs/tags/<tag>.zip`, `raw.githubusercontent.com/<owner>/<repo>/<ref>/api.toml` |
| **GitLab** | `/-/tree/<ref>/<dir>`, `/-/blob/<ref>/api.toml`, `/-/archive/<ref>/<repo>-<ref>.zip`; nested groups are supported |
| **Bitbucket** | `/src/<ref>/<dir>`, `/get/<ref>.zip` |
| **Codeberg** | `/src/tag/<ref>/<dir>`, `/src/branch/<ref>/<dir>`, `/archive/<ref>.zip` |
| **Sourcehut** | `/tree/<ref>/item/<dir>`, `/blob/<ref>/api.toml`, `/archive/<ref>.tar.gz` |

The path names either a template directory, which holds a `protostar.toml` and an optional `template/` directory of companion files, or a single `.toml` file. A path to a `protostar.toml` names its directory. Branch names may contain slashes: Protostar matches the longest ref the repository actually has.

To find the ref, Protostar reads the repository's tags and branches with one HTTPS request, the same one `git ls-remote` makes, so this step doesn't need `git`. It then downloads the template's files for exactly one commit, in memory, and refuses any archive entry that isn't safe to extract.

Any other HTTPS URL, such as a raw `protostar.toml` or an archive on your own server, is downloaded exactly as given, so it has no versions to choose between. A template URL can't carry credentials or query parameters.

### Template Versions

A URL that names no ref starts on the repository's newest release: the highest tag that is a [PEP 440](https://peps.python.org/pep-0440/) version (`v1.2.0` and `1.2.0` both count), not counting pre-releases. A repository with no release tags starts on its default branch.

The recipe in `pyproject.toml` records the ref, and `protostar.lock` records the commit it named:

```toml
[tool.protostar.source]
origin = "remote"
locator = "https://github.com/YourOrg/templates"
path = "services/api"
ref = "v1.2.0"
```

`protostar sync` always applies the recorded commit, so it is reproducible even if someone moves the tag or pushes to the branch. `protostar status` checks the repository and reports what it offers:

```text
Template v1.2.0 @ 4f0b8c2d1e9a; v1.3.0 available (sync --to v1.3.0).
```

A branch reports when it has moved, and a moved tag is reported the same way. Nothing changes until you move the project yourself:

```bash
protostar sync --to v1.3.0 --dry-run   # preview the upgrade
protostar sync --to v1.3.0             # apply it and record the new ref
protostar sync --to latest             # the newest release
protostar sync --to main               # follow a branch, to its current commit
```

`sync --to` is an ordinary update to the new release: your edits stay, and conflicts are reported as for any other update. Editing `ref` in the recipe and running `sync` does the same. `sync --check` doesn't fail because a newer release exists; it checks only that the recorded release is applied. Pre-releases are offered only while the project is already on one.

A template can declare [migrations](releasing-templates.md#migrations) for changes a merge can't express, such as a moved or retired file or a renamed variable. They run as the project moves past the release that declared them.

A new version that adds a template variable needs a value: `sync --to` asks for it in an interactive terminal, and otherwise takes `--var NAME=VALUE`.

Aliases work the same way. An alias to a bare repository URL starts every new project on the newest release, and an alias that names a tag starts every project there:

```toml
[templates.backend]
source = "https://github.com/YourOrg/standards/tree/v2.0.0/backend"
```

Built-in templates follow the installed Protostar version, and local templates follow their files, so neither has revisions for `--to` to move between.

## Template Aliases

An alias gives a template a short name in your [global configuration](configuration.md#global-template-aliases-templates), so you never retype its URL or path:

```toml
[templates]
local-ds = "~/Developer/templates/data-science.toml"

[templates.backend]
source = "https://github.com/YourOrg/standards"
description = "The team's FastAPI service"
trusted = true
```

Use it wherever a built-in name goes:

```bash
protostar init --template backend
```

The recipe editor's template picker lists your aliases after the built-in templates, each with its description, and `protostar init --list-templates` lists them too, with whether each is trusted. An alias is also the only way to trust a template permanently; see [the trust model](#trusting-a-template). [Global Configuration](configuration.md#global-template-aliases-templates) lists every field an alias takes.

## Template Variables, Options, and Tiers

### Variables

A template can ask for values of its own, such as a service name or a region. Pass each one with `--var`:

```bash
protostar init --from ./service.toml --var SERVICE_NAME=billing --var REGION=eu-west-1
```

In a terminal, Protostar asks for any you leave out before it writes anything. Without a terminal, including under `--json`, it stops with an error naming every missing variable. The values are saved in the project's recipe in `pyproject.toml`, and later runs reuse them, so a value must never be a secret.

Protostar fills in the standard variables itself, from your configuration, git, and the folder name: the project name, the package name, the Python version, the current year, and your name and email. You never supply these. To use variables in your own template, see [Variables](authoring-templates.md#level-3-variables).

### Choosing Template Options

A template can offer [options](./authoring-templates.md#template-options): a switch, or a choice among named values, that decides which files, dependencies, and configuration it includes. Each option has a default. Choose another with `--option`:

```bash
protostar init --from ./service.toml --option database=postgres --option compose=true
```

Change a choice later with `protostar sync --option NAME=VALUE`. Content the new choice drops is removed if you haven't edited it, and otherwise kept as a conflict for you to settle.

### Choosing a Tier

A template can offer two [tiers](./authoring-templates.md#template-tiers) of tooling: `workbench`, lean tooling for exploring and analyzing, and `production`, the full quality gate for something you'll publish. It starts in its default tier. Choose the other with `--tier`:

```bash
protostar init --from ./service.toml --tier workbench
```

In the recipe editor, the tier sits under the template picker, set to the default. Press `i` on it to see what each tier turns on for that template. Switch later with `protostar sync --tier production`. `protostar init --list-templates` shows each template's default tier.

## Trusting a Template

A template you haven't trusted runs no command until you confirm it. This page is the one place the trust rules are written down; other pages link here.

The confirmation covers more than the template's own `system_tasks` and `post_install_tasks`. Protostar's own commands run in the files the template writes, and those files can make them run the template's code: `uv add` builds the project through the build backend and any build hooks the template configured, and `direnv allow` authorizes the `.envrc` it ships. So the confirmation lists every command the run executes: setup commands such as `git init` and `uv init`, each dependency install, and the commands after install.

### Which Templates Are Trusted

- **Built-in templates** are trusted, because they ship inside Protostar.
- **An alias with `trusted = true`** in your [global configuration](configuration.md#global-template-aliases-templates) trusts the template it names, wherever you use it: the same local `protostar.toml`, or the same repository and path, even through `--from`.
- **Everything else** is untrusted: a `--from` path or URL, and an alias without `trusted = true`.

A project's recipe and `protostar.lock` never grant trust, so cloning a project never trusts its template for you.

### What Happens with an Untrusted Template

| Command | In a terminal | Without a terminal, or with `--json` |
| :--- | :--- | :--- |
| `init` | The change review lists the commands under **Untrusted template**, and **Apply** stays off until you tick the box confirming them (`t`). | Stops with `SecurityViolationError` (exit code `77`) before writing anything. |
| `sync` | After you settle any conflicts, a confirmation screen lists the commands `uv add`, `uv lock`, or a hook install the update needs. | Stops with exit code `77` before writing anything. |
| `status`, `diff`, `--dry-run`, `sync --check` | Never ask: they never run a command. | The same. |

Only the commands you confirmed run. `--trust` runs them without asking, for that one run, and still lists them; it is never saved. To trust a template every time, give it an alias with `trusted = true`. Almost every `init` runs a command, so an untrusted template almost always asks.

The confirmation screen `sync` shows takes these keys:

--8<-- "keys_trust.md"

### What Else Protects You

Whether or not a template is trusted, Protostar writes nothing outside the project directory or into `.git/`, and runs only these programs: `uv`, `git`, `npm`, `yarn`, `pnpm`, `pre-commit`, `prek`, `direnv`, and `just`. A template can't call a shell such as `/bin/sh` directly. Those programs can still run code the template ships, which is why trust exists.

## Next Steps

- **[Authoring Templates<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./authoring-templates.md):** Write your own template, from one TOML file to a repository with starter files and variables.
- **[Tooling & Flags Matrix<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./tooling-matrix.md):** Every tool and built-in template.
- **[Global Configuration<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./configuration.md):** Every field an alias under `[templates]` takes.
- **[Agent & Machine Interface<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./agent-interface.md):** Export the template schema and drive Protostar from scripts and agents.
