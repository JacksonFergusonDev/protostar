# Mutation Tracking Plan

Widen mutation testing to the rest of the engine, then run it on a schedule, record each score on `gh-pages` beside the performance benchmarks, graph it, and show the current score in the README and on jacksonferguson.me.

**How to use this file:** one PR per agent. Read `AGENTS.md` first, then the settled decisions below and your phase's section. Stay inside its scope, and note anything out of scope in the PR description instead of doing it. When a PR merges, update the status table and collapse its section to a short summary under "Finished". Delete this file in the last PR.

## Status

| Phase | Work | Status |
|---|---|---|
| 1 | One module list for mutation testing | Finished (#413) |
| 2 | Expand coverage to the target set | Finished (#415, #417, #418, #425, #428) |
| 3 | Record scores on `gh-pages` on a schedule | Finished (#441) |
| 4 | Dashboard graph and README badge | Finished (#442) |
| 5 | Score on jacksonferguson.me | Implemented; awaiting merge |
| 6 | Further coverage (ongoing) | Planned |

## Settled Decisions

- **Expand coverage before tracking starts.** The public score (badge and website) begins with the expanded set, so it opens near its long-run value instead of dropping each time a module joins. The expanded set's cost also decides the schedule and how runners are split, so Phase 3 is designed after Phase 2 is measured.
- **The target set is fixed.** Phase 2 ended when its seven modules (listed under "Finished") were mutated and had a survivor pass. Anything else is Phase 6 and does not hold up tracking.
- **Engine logic only, never the whole codebase.** Leave out `cli/` and `cli/tui/` (their mutants mostly change labels, styles, and layout, and snapshot tests catch them slowly or not at all), `_secret_rules.py` (generated), `errors.py` (mostly message text), and modules whose behavior the suite reaches only through mocked boundaries, such as `system.py` and `network.py` (their mutants survive whatever the tests do).
- **Scheduled, gated by change.** No run on every commit. A scheduled run first checks whether the mutated modules, `tests/`, or `pyproject.toml` changed since the last recorded commit, and stops if not. Quiet periods cost nothing, and a busy period gets one point per scheduled run. The manual trigger stays for development.
- **Only complete runs publish.** A run publishes a score only if every module in the set succeeded. Manual runs on a subset never publish.
- **Store raw counts per module.** Each history entry records the commit, the date, and each module's counts (killed, timeout, survived, and the rest `mutation_report.py` tracks), not just percentages. The overall score is computed from them, so it stays correct when the set grows, and the graph can mark when the scope changed.
- **Our own JSON, not github-action-benchmark.** That action writes a JS file built for speed regressions. Mutation results go in their own files under `benchmarks/` on `gh-pages`: a history file for the graph and a small latest-score file in shields.io's endpoint format, which the badge and the website both read.
- **The website reads the score when it builds.** jacksonferguson.me (Astro, `~/Developer/JacksonFergusonDev.github.io`) already fetches remote files at build time through `config/remote-assets.json`, and its `deploy.yml` already rebuilds on `repository_dispatch` of type `remote-assets-updated`, plus weekly. Protostar sends that dispatch after the Pages deploy finishes, not just after the `gh-pages` push, so the site never fetches a stale file.
- **Say what the score covers.** It covers the mutated modules, not the whole codebase. The dashboard says which modules, and the badge label doesn't imply full coverage.

## Phase 5: Score on jacksonferguson.me

The first PR is in the site's repo; the second is in Protostar.

1. **Site:** add a `json` type to `scripts/fetch-remote-assets.mjs` that checks the file's shape, add a manifest entry for the published latest-score file, and show the score on the Protostar project card, linked to the dashboard.
1. **Protostar:** after the Pages deploy, send `remote-assets-updated` to the site repo. This needs a fine-grained token limited to that repo, stored as its own secret (not `TAP_GITHUB_TOKEN`). The maintainer creates the token; an agent only wires up the workflow.

## Phase 6: Further coverage (ongoing)

After tracking starts, add more engine modules the same way as Phase 2, one or a few at a time: add the module to `source_paths`, run it through the manual workflow, kill the survivors worth killing (strengthen tests, and mark only mutants that cannot change behavior with `# pragma: no mutate` and a reason on the line above), and run it again on the finished tests.

Before the survivor pass, check for two things that hide mutants:

- **State built before a test runs.** mutmut forks each mutant from a process that has already imported the tests and run the module once, so an `lru_cache` in the module or an object built at import in a test file means the mutated code never runs. Clear caches in an autouse fixture (#409) and build test objects in fixtures (#415).
- **Local runs on macOS.** Forked workers there crash on mutants in widely reached functions, which then count as suspicious instead of surviving. Trust the workflow's counts.

A module too large for one runner is split by function through `[tool.mutmut-shards]` in `pyproject.toml`, as `reconciliation` is.

Candidates include `executor.py`, `workspace.py`, `migrations.py`, `options.py`, `secret_guard.py`, and `recipe.py`. The graph marks each change of scope.

## Finished

- Phase 1 (#413): The workflow derives its module list and `all` selection from `[tool.mutmut].source_paths`, including nested modules. `just mutate <module>` continues to work.
- Phase 2 (#415, #417, #418, #425, #428): `appends`, `toml_lines`, `dependencies`, `sync_state`, `manifest`, `documents/pyproject_layout`, and `reconciliation` joined `source_paths`, and every survivor was killed or marked as equivalent. `reconciliation` runs as six shards. Each module's first run took far longer than its run on the finished tests, because a surviving mutant runs every test that reaches its function while a killed one stops at its first failure. Plan Phase 3 with the runs on the finished tests:

  | Module | First run | Finished tests |
  |---|---|---|
  | `appends` | 76m | 7m |
  | `toml_lines` | 8m | 10m |
  | `dependencies` | 58m | 7m |
  | `sync_state` | 2h55m | 8m |
  | `documents/pyproject_layout` | 37m | 28m |
  | `manifest` | 3h38m | 11m |
  | `reconciliation` (6 shards) | 2h30m wall, 8h40m runner | 36m wall, 1h55m runner |

- Phase 3 (#441): Complete main-branch runs publish raw per-module history and the latest-score endpoint nightly at 02:23 UTC, gated by changed inputs. Pages carries both JSON files.
- Phase 4 (#442): The benchmarks dashboard graphs the overall score and each module from `mutation-history.json`, marking where the module set changed, and the README carries a shields.io endpoint badge reading `mutation-latest.json`.
