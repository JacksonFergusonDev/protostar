---
description: "Keep projects current without running sync by hand: scheduled update pull requests, checks in CI, pinned releases, and template upgrades."
---

# Automating Updates

[Project Lifecycle](lifecycle.md) covers reviewing and syncing one project by hand. This page covers keeping projects current without anyone remembering to: a workflow that opens update pull requests, a check that fails CI when a project falls behind, one Protostar release across a team, and moving projects to a template's new releases.

## Open Update Pull Requests on a Schedule

Protostar doesn't open pull requests on its own, but a scheduled workflow can: it runs `protostar sync` and opens a pull request with whatever changed. Save this as `.github/workflows/protostar-sync.yml`:

```yaml
name: Protostar sync

on:
  schedule:
    - cron: "0 6 * * 1" # Mondays at 06:00 UTC
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10.2.0

      - name: Sync with the template
        run: |
          # The release that last wrote protostar.lock, so CI matches your team.
          version=$(sed -n 's/^producer_version = "\(.*\)"$/\1/p' protostar.lock)
          set +e
          # --trust runs the uv and hook commands the update needs without asking.
          # The template's files decide what they run, so keep it to a template you trust.
          # For a repository template, add --to latest to move to its newest release.
          uvx "protostar@$version" sync --trust --json > "$RUNNER_TEMP/sync.json"
          code=$?
          set -e
          # 0: in step. 1: safe changes applied, conflicts left for a person.
          if [ "$code" -gt 1 ]; then exit "$code"; fi
          conflicts=$(jq '.review.conflicts | length' "$RUNNER_TEMP/sync.json")
          {
            echo "Protostar $version synced this project with its template."
            if [ "$conflicts" -gt 0 ]; then
              echo
              echo "$conflicts conflict(s) kept your version. Run \`protostar status\`"
              echo "locally to see each one and the command that settles it."
            fi
          } > "$RUNNER_TEMP/body.md"
          # sync installs this clone's git hooks; keep them off the bot's commit.
          git config core.hooksPath /dev/null

      - uses: peter-evans/create-pull-request@v8
        with:
          branch: protostar/sync
          commit-message: "chore: sync with the project template"
          title: "chore: sync with the project template"
          body-path: ${{ runner.temp }}/body.md
          delete-branch: true
```

- **What it updates.** The workflow runs the Protostar release that last wrote `protostar.lock`, so it never [refuses](#keep-protostar-versions-in-step) and never changes built-in output behind your back. Built-in updates arrive when someone syncs with a newer Protostar locally and commits the lock; the next run follows. A repository template stays on the commit the lock records; add `--to latest` to the `sync` command to move to its newest release each week. When a new release adds a variable, add `--var NAME=VALUE` too, or the run stops asking for it.
- **Trust.** When an update changes dependencies or the hooks to install, the run executes `uv add`, `uv lock`, or a hook install in files the template wrote, and those can run the template's code on the runner, which holds a token that can write to the repository. `--trust` allows that without asking, so use this workflow only with a template you trust. Without `--trust`, a run that needs a command stops with exit code `77` instead.
- **Conflicts.** A sync that keeps your version somewhere exits `1` with the safe changes applied, and the workflow still opens the pull request. Its body says how many conflicts were kept. Settle them locally: `protostar status` prints the `sync --resolve` command for each choice, and `sync --check` fails until you do.
- **Repeat runs.** A run with nothing new changes nothing and opens nothing. A pull request that is still open is updated in place, on the `protostar/sync` branch.
- **Git hooks.** `sync` installs the clone's hooks, so the workflow switches them off before the pull request's commit, which would otherwise run every check.
- **Repository settings.** Allow the workflow to open pull requests under **Settings** › **Actions** › **General** › **Workflow permissions**. A pull request opened with the default `GITHUB_TOKEN` doesn't trigger other workflows, so your CI won't run on it. To have it run, give `create-pull-request` a `token` from a GitHub App or a fine-grained personal access token.

## Use Checks in CI

```bash
protostar sync --check --json > review.json
```

| Command and outcome | Exit code |
| --- | --- |
| `status`, `diff`, or a `--dry-run`, even with conflicts | `0` |
| `sync` that applied everything, or had nothing to do | `0` |
| `sync` that applied the safe changes and left conflicts open | `1` |
| `sync --check` with an update to apply or a conflict open | `1` |
| `sync --check` with nothing pending, or only edits you kept | `0` |
| An error | That error's [exit code](cli-reference.md#exit-codes); `Ctrl+C` exits `130` |

`--check` never changes anything, and can't be combined with `--dry-run`. With `--json`, every command prints one JSON payload on stdout and never prompts; diagnostics and command output go to stderr. A check's payload includes `check_passed`, a review's has `status: "reviewed"`, and an applied sync's has `"success"` or `"partial"`. See the [machine interface](agent-interface.md) for examples and schemas.

## Keep Protostar Versions in Step

Built-in output comes from the installed Protostar, so every contributor needs a release at least as new as the one that last wrote `protostar.lock`. The lock records that release as `producer_version`. When the installed Protostar is older, `init`, `status`, `diff`, and `sync` (including `--check`) refuse to run instead of treating the older output as an update. Upgrade Protostar, for example with `uv tool upgrade protostar`, and run the command again. In `--json` mode, the error carries `recorded_version` and `installed_version`.

In CI, run the release that last wrote the lock, which it records as `producer_version`, so a new release never changes the check before the project is synced with it:

```bash
uvx "protostar@$(sed -n 's/^producer_version = "\(.*\)"$/\1/p' protostar.lock)" sync --check
```

## Upgrade a Repository Template

`status` starts with the template's ref and what its repository offers:

```bash
protostar status
# Template v1.2.0 @ 4f0b8c2d1e9a; v1.3.0 available (sync --to v1.3.0).
protostar sync --to v1.3.0 --dry-run
protostar sync --to v1.3.0
```

`sync --to` records the new ref in the recipe, downloads that revision, and reviews it like any other update, in the same transaction. When the template declares [migrations](releasing-templates.md#migrations) between the two releases, they run first: seeded files it moved keep your edits at their new path, files it retired are deleted when unedited and kept as a `retracted` conflict otherwise, and renamed variables keep their values. `status` lists each step as `Migration <version>: ...`. A project can't move back before a migration it has run. It accepts a tag, a branch, a full commit SHA, or `latest`. Variables the new version adds come from `--var NAME=VALUE`, or from the variables screen in an interactive terminal. When the repository can't be reached, `status` says so and still reviews the recorded commit.
