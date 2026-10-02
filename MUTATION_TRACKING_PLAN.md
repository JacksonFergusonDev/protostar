# Mutation Tracking Plan

Widen mutation testing to the rest of the engine, then run it on a schedule, record each score on `gh-pages` beside the performance benchmarks, graph it, and show the current score in the README and on jacksonferguson.me.

**How to use this file:** one PR per agent. Read `AGENTS.md` first, then the settled decisions below and your phase's section. Stay inside its scope, and note anything out of scope in the PR description instead of doing it. When a PR merges, update the status table and collapse its section to a short summary under "Finished". Delete this file in the last PR.

## Status

| Phase | Work | Status |
|---|---|---|
| 1 | One module list for mutation testing | Planned |
| 2 | Expand coverage to the target set | Planned |
| 3 | Record scores on `gh-pages` on a schedule | Planned |
| 4 | Dashboard graph and README badge | Planned |
| 5 | Score on jacksonferguson.me | Planned |
| 6 | Further coverage (ongoing) | Planned |

## Settled Decisions

- **Expand coverage before tracking starts.** The public score (badge and website) begins with the expanded set, so it opens near its long-run value instead of dropping each time a module joins. The expanded set's cost also decides the schedule and how runners are split, so Phase 3 is designed after Phase 2 is measured.
- **The target set is fixed.** Phase 2 ends when the modules listed under it are mutated and have had a survivor pass. Anything else is Phase 6 and does not hold up tracking.
- **Engine logic only, never the whole codebase.** Leave out `cli/` and `cli/tui/` (their mutants mostly change labels, styles, and layout, and snapshot tests catch them slowly or not at all), `_secret_rules.py` (generated), `errors.py` (mostly message text), and modules whose behavior the suite reaches only through mocked boundaries, such as `system.py` and `network.py` (their mutants survive whatever the tests do).
- **Scheduled, gated by change.** No run on every commit. A scheduled run first checks whether the mutated modules, `tests/`, or `pyproject.toml` changed since the last recorded commit, and stops if not. Quiet periods cost nothing, and a busy period gets one point per scheduled run. The manual trigger stays for development.
- **Only complete runs publish.** A run publishes a score only if every module in the set succeeded. Manual runs on a subset never publish.
- **Store raw counts per module.** Each history entry records the commit, the date, and each module's counts (killed, timeout, survived, and the rest `mutation_report.py` tracks), not just percentages. The overall score is computed from them, so it stays correct when the set grows, and the graph can mark when the scope changed.
- **Our own JSON, not github-action-benchmark.** That action writes a JS file built for speed regressions. Mutation results go in their own files under `benchmarks/` on `gh-pages`: a history file for the graph and a small latest-score file in shields.io's endpoint format, which the badge and the website both read.
- **The website reads the score when it builds.** jacksonferguson.me (Astro, `~/Developer/JacksonFergusonDev.github.io`) already fetches remote files at build time through `config/remote-assets.json`, and its `deploy.yml` already rebuilds on `repository_dispatch` of type `remote-assets-updated`, plus weekly. Protostar sends that dispatch after the Pages deploy finishes, not just after the `gh-pages` push, so the site never fetches a stale file.
- **Say what the score covers.** It covers the mutated modules, not the whole codebase. The dashboard says which modules, and the badge label doesn't imply full coverage.

## Phase 1: One module list for mutation testing

`mutation.yml`'s plan step hardcodes the modules it accepts, which repeats `[tool.mutmut].source_paths` in `pyproject.toml`. Derive the workflow's module list (and its `all` choice) from `source_paths`, so adding a module is a one-line change in `pyproject.toml`. Keep `just mutate <module>` working.

## Phase 2: Expand coverage to the target set

Add each module (or a small group) in its own PR:

1. Add it to `source_paths`.
1. Run it through the manual workflow, and note its runtime and survivors in the PR.
1. Kill the survivors worth killing, following #407–#409: strengthen tests, and mark only mutants that cannot change behavior with `# pragma: no mutate` and a reason on the line above.

The target set, roughly in order of value:

- `reconciliation.py`: the most important module not yet covered and by far the largest. Measure it first. If it doesn't fit comfortably in one runner's time limit, split it across runners.
- `manifest.py`, `sync_state.py`, `appends.py`, `toml_lines.py`, `dependencies.py`, `documents/pyproject_layout.py`.

Already covered: `fs_transaction`, `journal`, `jsonc_ast`, `merge`, `text_merge`, `toml_ast`, `yaml_ast`.

## Phase 3: Record scores on `gh-pages` on a schedule

- **Report:** give `scripts/mutation_report.py` JSON output for one history entry and for the shields endpoint file.
- **Workflow:** add a schedule to `mutation.yml` with the change check above. Choose how often it runs from Phase 2's measured runtime: nightly if a full run is short enough, less often if not. Add a publish job that runs only when every module succeeded. It appends to the history and writes the latest-score file on `gh-pages`, rebases and retries its push (the benchmark workflow pushes to the same branch), then calls `pages.yml` as `benchmark.yml` does.
- **Pages:** `scripts/prepare_pages.py` copies only `benchmarks/data.js` from `gh-pages` today; teach it to carry the mutation files too.
- **Docs:** document mutation testing and its schedule in `docs/developer/testing.md`, including that GitHub disables scheduled workflows in a public repo after 60 days without commits, and that `gh workflow enable mutation.yml` turns it back on.

## Phase 4: Dashboard graph and README badge

- Add a mutation panel to the benchmarks dashboard (`benchmarks/`), sharing its styles and house-style: the overall score over time, a line per module, and a marker where the module set changed.
- Add a shields.io endpoint badge to the README beside the others, in the same colors (`22d3ee` on `0A0A0A`), reading the latest-score file and linking to the dashboard.

## Phase 5: Score on jacksonferguson.me

The first PR is in the site's repo; the second is in Protostar.

1. **Site:** add a `json` type to `scripts/fetch-remote-assets.mjs` that checks the file's shape, add a manifest entry for the published latest-score file, and show the score on the Protostar project card, linked to the dashboard.
1. **Protostar:** after the Pages deploy, send `remote-assets-updated` to the site repo. This needs a fine-grained token limited to that repo, stored as its own secret (not `TAP_GITHUB_TOKEN`). The maintainer creates the token; an agent only wires up the workflow.

## Phase 6: Further coverage (ongoing)

After tracking starts, add more engine modules the same way as Phase 2, one or a few at a time, each with its survivor pass. Candidates include `executor.py`, `workspace.py`, `migrations.py`, `options.py`, `secret_guard.py`, and `recipe.py`. The graph marks each change of scope.

## Finished

Nothing yet.
