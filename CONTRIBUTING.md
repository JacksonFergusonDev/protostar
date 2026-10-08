# Contributing to Protostar

Protostar has one job: save you time on setup you would have done anyway. Before proposing a feature, ask two questions:

- Would *most* users want this, or just some?
- Would you plausibly undo it by hand after running the tool?

If the answer to either is "maybe not", the feature probably doesn't belong in Protostar. A team's own conventions belong in a template; see [Authoring Templates](https://protostar.jacksonferguson.me/usage/authoring-templates/).

## The Rules the Code Follows

[`AGENTS.md`](https://github.com/JacksonFergusonDev/protostar/blob/main/AGENTS.md) is the source of truth for Protostar's architectural rules, for people and coding agents alike. Read it before your first change. These are the ones a change most often meets, each with the page that explains it:

- **Plan first, act last.** A module's `build()` only declares what its tool needs into the `EnvironmentManifest`; it never writes a file or runs a command. Only the executor changes the project, and every write goes through `TransactionAwareFS` and every command through `ProcessRunner`, so a failure rolls everything back. See [Design Principles](https://protostar.jacksonferguson.me/design-principles/#manifest-first) and [Rollback Internals](https://protostar.jacksonferguson.me/mechanics/rollback/).
- **The engine is headless.** Nothing outside `protostar.cli` imports `rich` or `textual`, prompts, or prints. The engine reports progress only through the `ProgressStep` hook, never through logging, and asks for missing input by raising a domain error the CLI handles. See [The Headless Core](https://protostar.jacksonferguson.me/design-principles/#the-headless-core).
- **Only `uv` and `git` can stop a run.** `plan()` checks for them. A program only one tool runs, such as `direnv`, is declared in that module's `executables`, and a missing one skips only the step that runs it. See [Extending Protostar](https://protostar.jacksonferguson.me/developer/extending-protostar/#programs-a-tool-runs).
- **Errors are domain errors.** Raise a subclass of `ProtostarError` from `protostar.errors`, never a bare `RuntimeError` or `ValueError`. Put what broke in the message and how to fix it in `hint`, and chain the cause with `raise ... from e`. Each error class has its own exit code. See [Error Handling](https://protostar.jacksonferguson.me/mechanics/error_handling/).
- **`--json` keeps `stdout` for the payload.** Everything else goes to `stderr`, and machine mode never prompts. See [Agent & Machine Interface](https://protostar.jacksonferguson.me/usage/agent-interface/).
- **Never overwrite someone's work.** Structured files merge by key through their format engines, and a disagreement becomes a decision for the user. See [How Protostar Tracks Your Files](https://protostar.jacksonferguson.me/usage/tracking/).
- **Built-in templates are project shapes, not stacks.** Modules carry a baseline for casual projects; a template states only what defines its shape. Built-ins **declare every quality flag explicitly** (`ruff`, `mypy`, `pytest`, `prek`, `ci`, `rumdl`, `direnv`, `just`). The default answer to a new built-in is "publish it as a `--from` template". See [Built-in Templates](https://protostar.jacksonferguson.me/developer/built-in-templates/).

Code is typed with `mypy --strict`, uses Google-style docstrings on public functions, classes, and methods, and is formatted by Ruff at 88 characters. Use `enum.StrEnum` for a fixed set of choices and a frozen dataclass for related values, rather than strings and loose tuples.

## Development Setup

You need:

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)**, for the environment and dependencies
- **[just](https://just.systems/man/en/packages.html)**, the command runner

On macOS with Homebrew, `brew install uv just` installs both. Then fork the repository, clone your fork, and install the environment and the commit hooks:

```bash
git clone https://github.com/<your-username>/protostar.git
cd protostar
uv sync
uv run prek install
```

Add dependencies with `uv add` (or `uv add --dev`), never by editing `pyproject.toml`, so `uv.lock` stays in step.

## Checks and Tests

The hooks run the checks for you:

- **On commit:** `uv lock --check`, Ruff, mypy, rumdl, actionlint, the Renovate schema check, and gitleaks.
- **On push:** the full test suite, the strict docs build, and the docs, schema, and snapshot checks.

If a hook fails or reformats a file, look at what it reported, fix it, and stage again. While you work, run what your change touches, such as `uv run pytest tests/test_executor.py`. `just test` runs the whole suite in parallel, and `just` lists every recipe. `just ci` runs everything CI runs, one after another; the hooks already cover it, so reach for it only to debug a difference from CI.

Tests write only under `pytest`'s `tmp_path` and mock commands at the boundary they exercise, usually `ProcessRunner.run`. Only tests marked `integration` run real `uv`, `git`, or hook commands, through the `real_tool_env` fixture. Some changes need checked-in results regenerated, and the pull request should say why they changed:

```bash
just check-snapshots                                                # scaffolds, terminal images, and generated docs
uv run pytest tests/test_rollback.py -k sites_match --snapshot-update  # the sites each rollback scenario passes
uv run pytest tests/test_cost_budgets.py --snapshot-update          # what each command costs
```

[Testing Architecture & Philosophy](https://protostar.jacksonferguson.me/developer/testing/) covers the fixtures, the rollback fault injection, the cost budgets, CI, and flaky tests.

## Manual Testing in a Sandbox

To try Protostar without touching your own configuration or projects:

- `just sandbox` builds Protostar from your working tree and opens a shell in an empty project under `/tmp`, with its own `$HOME`. `just sandbox-existing`, `just sandbox-sync`, and `just sandbox-sync-conflict` start from an existing project, a pending template update, and a conflicting one. Pass arguments to run one command instead of a shell: `just sandbox init --template cli`.
- `just sandbox-linux` does the same in a disposable Debian container (OrbStack or Docker), with `direnv` and `markdownlint-cli2` installed: `just sandbox-linux init --template astro`.

## Documentation

The docs site lives in `docs/` and is built by Zensical; `just serve` previews it. It shares its design rules with jacksonferguson.me through [house-style](https://github.com/JacksonFergusonDev/house-style), whose guidelines are vendored at `docs/house/GUIDELINES.txt`: read them before changing a page. Write each Markdown paragraph on one line, never hard-wrapped. `just check-docs-drift` fails when a page disagrees with the code, such as a command, an error, or a file path that no longer exists.

### Publishing

GitHub Pages must use **GitHub Actions** as its source (Settings → Pages → Build and deployment). The `gh-pages` branch stores released documentation and benchmark, mutation, and rollback data; it is not itself the published site. Releases and metric updates invoke `.github/workflows/pages.yml`, which serializes site assembly and deployment together and reads the current branch contents after acquiring its publishing slot.

The publisher creates a clean artifact with `scripts/prepare_pages.py`. The release carrying `latest` in `versions.json` is served at the bare documentation URLs, and every release, that one included, keeps its versioned copy. Each versioned page the latest release still has names the bare URL as its canonical address, so search engines rank one URL across releases; pages the latest release dropped are marked `noindex`. Version aliases redirect to wherever their release is served, preserving query parameters and anchors, and the sitemap lists the bare URLs. Old root copies are excluded. Markdown and `llms.txt` come from the latest release's HTML and tagged navigation, with links to the bare Markdown files. The metrics dashboard is included in every deployment, and the old `/benchmarks/` address redirects to it. The root also gets `robots.txt`, which welcomes search engines and AI search agents, turns away AI training crawlers, and names the sitemap.

To republish the current documentation and metrics without rebuilding a release or publishing to PyPI, run `gh workflow run pages.yml --ref main`. To rebuild a released documentation version, run `gh workflow run release.yml --ref main -f tag=vX.Y.Z`; this moves `latest` to that version and invokes the same publisher. Keep Pages in Actions mode so branch updates cannot replace the assembled artifact.

## Pull Requests

1. Branch from `main`, and keep each pull request to one feature, template, or fix. If you change a built-in template or a tool module's defaults, read [Built-in Templates](https://protostar.jacksonferguson.me/developer/built-in-templates/) first, then run `just check-snapshots` and review every generated file.
1. Title it as a [Conventional Commit](https://www.conventionalcommits.org/), such as `feat(cli): ...` or `fix(executor): ...`.
1. Fill in the template: the problem, how you decided what to build and what you rejected, and any rule the change establishes. Scale it to the change; a small fix needs a sentence or two.

Protostar is pre-1.0 with no compatibility promises, so change or delete an API, flag, or format outright rather than adding a deprecation shim.

## Reporting Bugs

Search the [issues](https://github.com/JacksonFergusonDev/protostar/issues) first. A new report needs the command you ran, what you expected, and the output with `--verbose`. When Protostar crashes, it prints a link that opens an issue with the details filled in. Report security problems privately, as [SECURITY.md](https://github.com/JacksonFergusonDev/protostar/blob/main/SECURITY.md) describes.
