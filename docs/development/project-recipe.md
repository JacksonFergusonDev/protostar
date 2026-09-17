# Project recipes

A successful `protostar init` records project intent in `[tool.protostar]` inside
`pyproject.toml`. Commit it alongside `.protostar.lock.toml`. The recipe describes
what you request; the lock records contributions actually accepted by semantic
reconciliation. Conflicts can therefore leave desired intent ahead of applied
ownership. The ownership ledger remains schema v1.

For new uv projects, the captured project name uses uv normalization (`Demo_Project`
becomes `demo-project`); the package identifier remains `demo_project`. This keeps
early file rendering and later TOML rendering consistent.

The schema-v1 recipe captures the resolved template origin and locator (or explicit
`mode = "tooling-only"`), Python version, Docker selection, IDE, original tooling
fallbacks, built-in rendering context, and non-secret project metadata. Template
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

For example, after initialization, edit the existing tools table:

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

## Custom interpolation

Custom variable answers are never stored in the recipe. Bind each custom template
variable to an environment variable during initialization:

```bash
export PROJECT_ENDPOINT="https://example.invalid"
protostar init --from ./blueprint.toml --bind ENDPOINT=PROJECT_ENDPOINT
```

The resulting recipe contains only the binding name:

```toml
[tool.protostar.bindings]
ENDPOINT = "PROJECT_ENDPOINT"
```

Subsequent initialization and lifecycle commands resolve these values in memory.
Missing bindings or missing environment variables fail before workspace mutation. Arbitrary answers
provided through dynamic interpolation flags cannot enroll a project unless the
variables also have environment bindings. Interactive custom answers likewise
cannot establish replayable intent; use explicit bindings instead. Trust
permissions and command lines are never serialized. Generated project files and
ownership baselines can contain rendered content; diffs are not a secret-redaction
system.
