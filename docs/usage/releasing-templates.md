---
description: "Check a template before you publish it, release it as versioned tags, and migrate the projects that follow it."
---

# Checking & Releasing Templates

Once a template does what you want ([Authoring Templates](authoring-templates.md) covers writing one), check it on every change, publish it from a repository, and tag each release. Projects that follow it move to a new release when they choose, and migrations carry them across the changes a merge can't.

## Checking a Template

`protostar check-template` checks a template without setting up a project. Run it from the template's directory, or name a template directory, a template TOML file, or an HTTPS URL:

```bash
protostar check-template
protostar check-template ./templates/backend.toml
protostar check-template https://github.com/YourOrg/fastapi-template
```

It fills each of the template's own variables with a stand-in value and plans a default `protostar init` into an empty scratch folder. It uses Protostar's built-in configuration rather than yours, so every machine gets the same result. It writes nothing, runs no commands, and ignores what's in the folder you run it from.

It reports two kinds of finding:

- **Errors** (`invalid-template`) are anything that stops `protostar init` from using the template: invalid TOML, a field of the wrong type, a path the template may not write, an unknown tool flag, or a file under `template/` that isn't UTF-8 text.
- **Warnings** break a practice the built-in templates follow. The template works, but its users get a worse result.

| Rule | What it reports |
| :--- | :--- |
| `unknown-key` | A root key Protostar ignores, such as a misspelled field, or a tooling flag whose value isn't `true` or `false` |
| `missing-metadata` | No `name` or `description`, which `--list-templates` and the template picker show |
| `undescribed-variable` | A custom variable with no `[variables]` description |
| `credential-variable` | A custom variable named like a credential |
| `restated-baseline` | A `[dev.pyproject]` payload that repeats a module's baseline value, or redefines a baseline list instead of using an additive key |
| `unbound-tool-config` | A payload that configures a tool without `requires` for that tool |
| `unbound-tool-package` | A tool's package, such as `pytest-cov`, installed unconditionally instead of in an `[[optional]]` block that requires the tool |
| `inconsistent-migration` | A migration that removes or renames away a file the template still ships, renames a file to one it doesn't ship, or renames a variable the template doesn't use under its new name |

The check exits `1` when the template has errors, and also on warnings with `--strict`. If the template can't be downloaded or found at all, through a wrong path, a network failure, or an HTTP error such as 404, nothing is checked. It prints that error and exits with its [exit code](cli-reference.md#exit-codes), such as `65` or `75`, so a failed download is never mistaken for a broken template. `--json` returns the findings as a JSON payload.

The check covers a default `init`, with every option at its default, once in each tier when the template declares tiers. Content that only applies when a user turns on a tool the template leaves off, or chooses another option value, is not planned, so still try the combinations you expect your users to choose.

Each finding names the file and line it concerns, such as `protostar.toml:12`, including a key inside a `[dev.pyproject]` payload. A finding about something the template doesn't contain, such as a missing `name`, names only the file.

## Checking in GitHub Actions

To check a template in its own repository's CI, add a step such as:

```yaml
- uses: actions/checkout@v7
- uses: astral-sh/setup-uv@v10.2.0
- run: uvx protostar check-template --strict --output-format github
```

With `--output-format github`, each finding becomes a workflow annotation: it shows on the pull request's changed files at its line, and in the run's summary. Paths are relative to the repository root (`GITHUB_WORKSPACE`), so the step works from any `working-directory`. A template that couldn't be retrieved gets one annotation saying so, and findings in a remote template annotate the run instead of a file. The step still fails the same way: exit `1` for a failed check, or the retrieval error's own exit code. `--output-format github` can't be combined with `--json`.

## Local Testing

You don't need to push a template to try it. Point `--from` at its folder:

```bash
# From within an empty target directory
protostar init --from ~/Developer/templates/my-custom-template
```

## Distribution & Releases

Once your template is ready, push it to a repository on GitHub, GitLab, Bitbucket, Codeberg, or Sourcehut. Protostar accepts the repository's web, raw, and archive URLs, and a path inside the repository, so one repository can hold several templates.

Publish releases as tags that are [PEP 440](https://peps.python.org/pep-0440/) versions, such as `v1.3.0`. A new project starts on your newest release, `protostar status` tells existing projects when a newer one exists, and `protostar sync --to v1.3.0` moves them to it, merging your changes into their configuration while keeping their local edits. Tag pre-releases as such (`v2.0.0rc1`): they are offered only to projects already on a pre-release. Never move a published tag. Projects stay on the commit they applied, and `status` reports the moved tag as an update. [protostar-example-templates](https://github.com/JacksonFergusonDev/protostar-example-templates) is a working example of a template repository: two templates, release tags, and `check-template` in CI. To move projects onto each release without anyone running `sync --to` by hand, point your users to the scheduled workflow in [Automating Updates](automating-updates.md#open-update-pull-requests-on-a-schedule).

Users can name the repository directly:

```bash
protostar init --from https://github.com/YourOrg/data-science-template
```

Or give it an alias in your configuration (`protostar config --edit`), so it appears by name in the recipe editor's template picker:

```toml
[templates]
org-ds-base = "https://github.com/YourOrg/data-science-template"
```

## Migrations

Most changes between your releases need nothing extra: `sync --to` merges your changes to `[dev.pyproject]` payloads, dependencies, and named append regions into each project, and your users' edits stay. Starter files are different. A file in `[files]` or `template/` is written once and then belongs to the project, so a later release's edits to it don't reach existing projects. A few changes are about files and names rather than their contents, including moving or retiring a starter file. Declare those as migrations:

```toml
version = "2.0.0"

[[migrations]]
version = "2.0.0"
rename = [{ from = "src/<% PACKAGE_NAME %>/settings.py", to = "src/<% PACKAGE_NAME %>/config.py" }]
remove = ["setup.cfg"]
rename_variables = [{ from = "ORG", to = "ORGANIZATION" }]
```

A migration's `version` is the release that introduced the change. A project runs it when it moves from a release before that version to that version or later, and never again; a project that skips releases runs every migration in between, oldest first. A template with migrations must declare a [PEP 440](https://peps.python.org/pep-0440/) root `version`, and no migration may be newer than it. Keep every migration in later releases: the new release is the only one a project reads them from.

- **`rename`** moves a starter file, with the user's edits to it, and Protostar's record of it. Ship the file under its new name. If something already exists at the new path, the file stays where it is and `status` says so. A file the user deleted stays deleted at its new path.
- **`remove`** retires a starter file you no longer ship. An unedited copy is deleted. A copy with edits stays and becomes a `retracted` conflict until the user settles it: `local` keeps it as their own file, and `desired` deletes it.
- **`rename_variables`** moves a recorded variable value to its new name before anything renders, so users aren't asked for a value they already gave.

Migrations only touch files Protostar wrote: a path it never wrote is left alone. Migrations are declarations rather than scripts on purpose. `status` and `sync --dry-run` list each one before anything changes, and a failed `sync` rolls them back with everything else. Scripts would make both impossible, so migrations never run commands. A project can't move back to a release before a migration it has run, because the older release can't know how to reverse it.

Renaming or removing a dependency, or a file a tool generates, isn't a migration yet.

## Security Considerations

Your users confirm every command a run executes before it runs, unless they have trusted your template: Protostar's own setup commands and dependency installs as well as your `system_tasks` and `post_install_tasks`, because your files decide what those commands do. Without a terminal, an untrusted run stops instead, so users who run your template in CI give it an alias with `trusted = true`, or pass `--trust` for that run. See [Trusting a Template](templates.md#trusting-a-template).

## Next Steps

- **[Authoring Templates<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./authoring-templates.md):** Every key a template can set, from tools and payloads to options and tiers.
- **[Automating Updates<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./automating-updates.md):** Move projects onto each release with a scheduled pull request.
- **[Templates<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./templates.md):** How your users choose, trust, and update a template.
