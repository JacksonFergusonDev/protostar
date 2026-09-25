# Project recipes

By default, a successful `protostar init` records project intent in `[tool.protostar]` inside
`pyproject.toml`. Commit it alongside `protostar.lock`. The recipe describes
what you request; the lock records contributions actually accepted by semantic
reconciliation. Conflicts can therefore leave desired intent ahead of applied
ownership. The ownership ledger remains schema v1.

`init --one-shot` uses the recipe and ownership decisions only during the run.
It writes neither the recipe nor `protostar.lock`, so lifecycle commands cannot
update that scaffold. It still generates the separate `uv.lock` dependency lockfile.

`protostar eject` takes an already tracked project out of the lifecycle. It removes
the recipe and `protostar.lock` in one transaction while retaining `uv.lock` and all
other project files. The CLI shows the pending changes and asks for confirmation;
`--dry-run` previews the pyproject diff, and `--yes` confirms a noninteractive run.
After ejection, `status`, `diff`, and `sync` are unavailable for that project.

In a `pyproject.toml` that Protostar creates, the recipe is the last section, under its own `# ---- Protostar ---- #` header, like every other tool's configuration. Everything that is not tool configuration (`[project]`, `[build-system]`, `[dependency-groups]`, and build-backend tables such as `[tool.hatch...]`) sits above the `# Tool Configuration` banner. A `pyproject.toml` you already had keeps your own order.

For new uv projects, the captured project name uses uv normalization (`Demo_Project`
becomes `demo-project`); the package identifier remains `demo_project`. This keeps
early file rendering and later TOML rendering consistent.

In a project that had no recipe, the Python version, author, and year come from the project itself where it states them (see [existing projects](../usage/init.md#existing-projects)), and from your configuration otherwise.

`[tool.protostar.tools]`, `[tool.protostar.metadata]`, and `[tool.protostar.variables]` are written only while they have entries, and an absent table means empty. `fallback` and `context` are always present.

The schema-v1 recipe captures the resolved template origin and locator (or explicit
`mode = "tooling-only"`), and for a repository template its `path` inside the
repository and the `ref` it follows (see [template versions](../usage/templates.md#template-versions)), Python version, Docker selection, IDE, original tooling
fallbacks, built-in rendering context, template variable values, and non-secret
project metadata. Template
aliases are resolved when enrolled; the recipe records their exact source, not the
alias. Local relative locators resolve against the project directory. Unknown
fields, versions, tools, and unsafe source paths are rejected.

The recipe belongs to the project. Templates and modules cannot contribute to,
replace, or own any part of `tool.protostar`. Use structured TOML contributions for
`pyproject.toml`; free-form replacement is rejected even with `--force-replace`.
Recipe edits use round-trip TOML manipulation, preserving unrelated content and
comments. Recipe and ownership updates share the same filesystem transaction;
a late write failure rolls both back, including original bytes and modes.
`init --dry-run` remains a manifest preview and writes neither file.

## Tool selections

`[tool.protostar.tools]` records explicit diversions. Omitted tools follow the
current same-source template opinion, then the fallback captured on enrollment.
`true` requests a tool; `false` opts out of its contributions and warnings. An
opt-out affects that module only: an independent template or another module can
still contribute to the same file or dependency group. No files, dependencies, or
ownership records are pruned when a tool is disabled.

The table is omitted while it has no entries, so a new project has none. To record a diversion, add the table:

```toml
[tool.protostar.tools]
mypy = true
renovate = false
```

Do not fill this table with every tool boolean: absence permits template opinions
to evolve. Later explicit initialization flags update their corresponding entries;
unspecified flags preserve existing diversions. `--docker` and `--no-docker`
explicitly change Docker intent. Metadata and `CURRENT_YEAR` are captured, so repeat
initialization preserves rendering context despite changed Git settings, global
defaults, or the clock.

## Enrolling a Stage 1 project

Rerun the original explicit selection with safe merging:

```bash
protostar init --template cli --force-merge
```

This establishes a recipe without reconstructing the original command from the
lock or adopting equal foreign content. Template identity checks still apply.
Use `status`, `diff`, and `sync` after enrollment; see the
[lifecycle walkthrough](../usage/lifecycle.md).

## Template variables

A template's custom variables (every `<% NAME %>` placeholder that isn't a
built-in) get their values when you initialize, and the recipe records them:

```bash
protostar init --from ./blueprint.toml --var REGION=eu-west-1 --var TIER=gold
```

```toml
[tool.protostar.variables]
REGION = "eu-west-1"
TIER = "gold"
```

Values come from three places, each overriding the one before: the recipe from an
earlier `init`, `--var NAME=VALUE` flags, and, in an interactive terminal, a prompt
for anything still missing. A `--var` that names no variable of the template is an
error, and so is a mistyped flag. Values the template no longer uses are dropped the
next time you run `init`.

Without a terminal, including under `--json`, a missing value stops `init` before
anything is written, with a `MissingTemplateVariablesError` naming every missing
variable (`error.missing_variables` in JSON). `sync` never prompts: when a template
gains a variable, add its value under `[tool.protostar.variables]` or rerun `init`
with `--var`.

Template variables are non-secret by definition, because the recipe is committed.
Each newly entered value passes the
[secret guard](../usage/authoring-templates.md#variables-are-not-secrets), and a value
that looks like a credential is held back until the user confirms it isn't a secret.
Recorded values are not checked again. Keep secrets in the environment the
project reads at runtime. Trust permissions and command lines are never
serialized. Generated project files and ownership baselines contain rendered
content; diffs are not a secret-redaction system.
