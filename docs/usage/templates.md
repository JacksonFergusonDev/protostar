---
description: "Use built-in templates, your team's from a file or repository, and aliases, and decide which templates may run commands."
---

# Templates

A template describes a kind of project: its tools, dependencies, settings, and starter files. Use a built-in one, your team's from a file or a Git repository, or a short alias for either, and every project made from it starts the same way.

<div class="grid cards" markdown>

- :material-cube-outline: __Built-in Templates__

    Project shapes that ship with Protostar: `api`, `astro`, `cli`, `lib`, and `ml`.

- :material-web: __External & Remote (`--from`)__

    Apply templates from a GitHub, GitLab, Bitbucket, Codeberg, or Sourcehut repository at a release you choose, or from local files.

- :material-card-account-details-outline: __Global Aliases (`[templates]`)__

    Register custom templates in your global `config.toml` to access them directly by name without retyping long URLs.

- :material-shield-alert-outline: __Trust Before Commands__

    A template you haven't trusted runs no command, on `init` or `sync`, until you confirm the list of commands it needs.

</div>

## Using Templates

Protostar provides flags for discovering and loading templates during `init`:

```bash
# 1. Using a built-in template or a global alias (shorthand: -t)
protostar init --template astro
protostar init -t astro

# 2. Listing all available built-in templates and global aliases
protostar init --list-templates

# 3. Using an external template directly from a file or URL
protostar init --from https://github.com/YourOrg/standards/blob/main/backend.toml
```

### Listing Available Templates

To inspect all available built-in templates alongside any global aliases registered in your configuration:

```bash
protostar init --list-templates
```

This displays a structured overview in the terminal outlining template aliases, display names, descriptions, types (Built-in or Global Alias), trust status, and origin sources. When invoked with `--json`, it emits a machine-readable JSON array of discovered templates.

### Turning a Template's Tools On and Off

A template's tool choices are defaults. `--<tool>` and `--no-<tool>` override any of them for the project, as [Initialization](init.md#turning-tools-on-and-off) shows, and [which choice wins](project-recipes.md#which-choice-wins) gives the full order.

## External & Remote Templates (`--from`)

The `--from` flag accepts local filesystem paths, direct raw TOML URLs, and repository web links.

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

Every form below names the same kind of thing: a repository, an optional ref, and an optional path.

| Provider | Examples |
| :--- | :--- |
| __GitHub__ | `/tree/<ref>/<dir>`, `/blob/<ref>/api.toml`, `/archive/refs/tags/<tag>.zip`, `raw.githubusercontent.com/<owner>/<repo>/<ref>/api.toml` |
| __GitLab__ | `/-/tree/<ref>/<dir>`, `/-/blob/<ref>/api.toml`, `/-/archive/<ref>/<repo>-<ref>.zip`; nested groups are supported |
| __Bitbucket__ | `/src/<ref>/<dir>`, `/get/<ref>.zip` |
| __Codeberg__ | `/src/tag/<ref>/<dir>`, `/src/branch/<ref>/<dir>`, `/archive/<ref>.zip` |
| __Sourcehut__ | `/tree/<ref>/item/<dir>`, `/blob/<ref>/api.toml`, `/archive/<ref>.tar.gz` |

The path names either a template directory, which holds a `protostar.toml` and an optional `template/` directory of companion files, or a single `.toml` file. A path to a `protostar.toml` names its directory. Branch names may contain slashes: Protostar matches the longest ref the repository actually has.

Protostar lists the repository's tags and branches with one Git smart-HTTP request (the same one `git ls-remote` makes), without needing `git` installed, and then downloads the template's files for exactly one commit, in memory, rejecting unsafe archive members.

Any other HTTPS URL, such as a raw `protostar.toml` or an archive on your own server, is fetched exactly as given. It has no revisions to choose between. Template source URLs may not carry credentials or query parameters.

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

`sync --to` is an ordinary three-way sync against the new revision: your local edits are kept, and conflicts are reported exactly as for any other update. Editing `ref` in the recipe by hand and running `sync` does the same thing. `sync --check` does not fail just because a newer release exists; it checks that the recorded revision is applied. Pre-releases are offered only while the project is already on one.

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

## Supplying Template Parameters

Templates can define custom parameters (such as service names, regions, or deployment settings). Their values are saved in the project recipe in `pyproject.toml`, so they must never be secrets.

### Passing Parameters via CLI

Pass each value with `--var`, once per parameter:

```bash
protostar init --from ./service.toml --var SERVICE_NAME=billing --var REGION=eu-west-1
```

### Choosing Template Options

A template can also offer [options](./authoring-templates.md#template-options): a switch, or a choice among named values, that decides which files, dependencies, and configuration it includes. Each has a default; choose another with `--option`, once per option:

```bash
protostar init --from ./service.toml --option database=postgres --option compose=true
```

Change a choice later with `protostar sync --option NAME=VALUE`. Content the new choice drops is retracted: removed when you haven't edited it, and otherwise kept as a conflict for you to settle.

### Choosing a Tier

A template can offer two [tiers](./authoring-templates.md#template-tiers) of tooling for its shape: `workbench`, lean tooling for exploring and analyzing, and `production`, the full quality gate for building something to publish. It starts in the tier it names as its default; choose the other with `--tier`:

```bash
protostar init --from ./service.toml --tier workbench
```

In the recipe editor, the tier sits directly under the template picker, preselected to the default; `i` on it shows what each tier turns on for that template. Switch later with `protostar sync --tier production`. `protostar init --list-templates` shows each template's default tier.

### Interactive Resolution

If a template requires parameters that were not supplied with `--var`, Protostar prompts for the missing values in an interactive terminal before any disk mutations occur. Without a terminal, including under `--json`, it stops with an error naming every missing parameter. Later runs of `init` reuse the recorded values.

### Automatic Metadata Resolution

Standard project variables—such as the human-readable project name, PEP 8 sanitized package identifier, target Python version, current calendar year, and author details—are resolved automatically by Protostar from your environment and directory context. You do not need to provide these manually.

!!! tip "Defining Template Variables"
    If you are authoring your own template and want to embed `<% VARIABLE_NAME %>` placeholders or inspect all built-in late-binding variables, see the [Authoring Custom Templates: Variable Interpolation](authoring-templates.md#level-3-variable-interpolation) guide.

## Trusting a Template

This is the one place the trust rules are written down; other pages link here.

A template you haven't trusted runs no command until you confirm it. That covers more than its own `system_tasks` and `post_install_tasks`. Protostar's own commands run in the files the template writes, and those files can make them run its code: `uv add` builds the project through the build backend and any build hooks the template configured, and `direnv allow` authorizes the `.envrc` it ships. So the confirmation lists every command the run executes: setup commands such as `git init` and `uv init`, each dependency install, and the commands after install.

### Which Templates Are Trusted

- __Built-in templates__ are trusted, because they ship inside Protostar.
- __An alias with `trusted = true`__ in your [global configuration](configuration.md#global-template-aliases-templates) trusts the template it names, wherever you use it: the same local `protostar.toml`, or the same repository and path, even through `--from`.
- __Everything else__ is untrusted: a `--from` path or URL, and an alias without `trusted = true`.

A project's recipe and `protostar.lock` never grant trust, so cloning a project never trusts its template for you.

### What Happens with an Untrusted Template

| Command | In a terminal | Without a terminal, or with `--json` |
| :--- | :--- | :--- |
| `init` | The change review lists the commands under __Untrusted template__, and __Apply__ stays off until you tick the box confirming them (`t`). | Stops with `SecurityViolationError` (exit code `77`) before writing anything. |
| `sync` | After you settle any conflicts, a confirmation screen lists the commands `uv add`, `uv lock`, or a hook install the update needs. | Stops with exit code `77` before writing anything. |
| `status`, `diff`, `--dry-run`, `sync --check` | Never ask: they never run a command. | The same. |

Only the commands you confirmed run. `--trust` runs them without asking, for that one run, and still lists them; it is never saved. To trust a template every time, give it an alias with `trusted = true`. Almost every `init` runs a command, so an untrusted template almost always asks.

The confirmation screen `sync` shows takes these keys:

--8<-- "keys_trust.md"

### What Else Protects You

Whether or not a template is trusted, Protostar writes nothing outside the project directory or into `.git/`, and runs only these programs: `uv`, `git`, `npm`, `yarn`, `pnpm`, `pre-commit`, `prek`, `direnv`, and `just`. A template can't call a shell such as `/bin/sh` directly. Those programs can still run code the template ships, which is why trust exists.

## Related Guides & Next Steps

- __[Authoring Custom Templates<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./authoring-templates.md):__ Build your own single-file blueprints or multi-file repository archives with dynamic variables.
- __[Tooling & Flags Matrix<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./tooling-matrix.md):__ Explore all tools and built-in templates available in Protostar.
- __[Global Configuration<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./configuration.md):__ Learn how to register shorthand aliases under `[templates]` in your `config.toml`.
- __[Agent & Machine Interface<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./agent-interface.md):__ Inspect blueprints and validate template JSON schemas in automated agent pipelines.
