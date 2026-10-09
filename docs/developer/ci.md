---
description: "Where Protostar's checks run: pull requests, Nightly, and releases, and the rollback, mutation, and benchmark metrics they publish."
---

# CI, Nightly & Metrics

[Testing & Philosophy](testing.md) covers the tests themselves. This page covers where they run: what a pull request checks, what Nightly adds, what a release waits for, and the measurements published to the [metrics dashboard](https://protostar.jacksonferguson.me/metrics/).

## Pull Request, Nightly, and Release Platforms

The pytest suite and the smoke matrix are defined once, in `.github/workflows/platforms.yml`, and each caller hands it the matrix to run:

- **Pull requests** (`ci.yml`) run the suite on every operating system and supported Python. They smoke-test every template at every Python on Linux, at the oldest and newest on Windows, and once on macOS, where each test job scaffolds a template or two after its suite.
- **Nightly** (`nightly.yml`) runs, each day on `main`, the smoke tests pull requests leave out, so the two together scaffold every template on every operating system and Python exactly once. It also runs the suite everywhere again, with retries, which is how a flaky test is found, and the full [rollback fault injection](testing.md#rollback-fault-injection) with real commands. It skips a day when `main` hasn't changed since its last pass.
- **A release** (`release.yml`) publishes only when CI and Nightly have both passed on the tagged commit, or on its parent when the tagged commit only changes `pyproject.toml` and `uv.lock` (the version bump). It also smoke-tests the wheel it is about to publish on each operating system, and publishes that same wheel.

The account runs 20 jobs at a time, five of them on macOS, so a pull request starts at most 20, three on macOS, and every job starts at once. Nightly has no such limit: it runs overnight, when nothing waits on it, and starts as many jobs as its work needs. The quick checks share two runners (`Lint, Docs & Secrets` and `Docker Images & Dashboard`), since each finishes well before the Windows suite that sets how long a run takes. A new push to a pull request cancels the run it replaces.

`tests/test_nightly.py` checks that both test every operating system and Python, that together they smoke-test every template on every platform once, that a pull request stays within the runner limits, that Nightly fails every template at every site on every operating system, and that a release can't publish before CI, Nightly, and its smoke test pass.

Nightly retries a failed test or smoke run once. A test that then passes doesn't fail the run; it is filed as flaky instead. Nightly Report (`nightly-report.yml`) opens a `nightly-failure` issue when the run fails, naming the failing jobs and the commits since the last pass, and closes it when a later run passes. Each flaky test gets an issue of its own, labelled `flaky-test`, which a later flake of the same test comments on rather than duplicating (`scripts/flaky_tracking.py`).

A fix doesn't close that issue. Once it lands on `main`, add the `awaiting-verification` label to the test's issue, link the fix, and name the platforms it flaked on. Nightly Report then counts clean runs from each run's explicit per-test results: a run counts only when the test ran and passed on every affected platform without a retry. After three in a row it closes the issue; a skipped or narrowed run counts for nothing. If the test fails or flakes again, the count resets and the label comes off, and a closed issue reopens. Leave the managed block in the issue body alone: it holds that count.

To run Nightly before merging a risky change, or before a release when it hasn't run on the commit yet, start it from the Actions tab or with `gh workflow run nightly.yml --ref <branch or tag>`. To reproduce one rollback failure without starting every job, narrow it: `gh workflow run nightly.yml --ref <branch> -f rollback-only=true -f os=windows-latest -f template=cli` runs only that template's rollback jobs on that operating system.

## Template Hooks Smoke Matrix

End-to-end template validation runs through the `template-smoke` action (`.github/actions/template-smoke`). It scaffolds each built-in template it is given in turn, verifies that `prek` hooks are installed, checks that a commit message that isn't conventional is rejected, and asserts that the first commit runs and passes every pre-commit hook. A `template-hooks-smoke` job runs it for a list of templates, and a test job can run it after the suite through its matrix entry's `smoke` list, which is how macOS smoke-tests templates without a runner of its own.

## Counting Rollback Faults

Every test that injects a fault carries the `rollback_fault` marker, and `--rollback-report PATH` writes how many of them passed, and which failed, per scenario (`tests/rollback_report.py`). A retry of failed tests updates the same file, so it holds each fault's last outcome, and a run that is killed or interrupted writes nothing. Nightly's rollback jobs pass the option and upload the file as an artifact, even when the job fails.

The `Rollback Metrics` workflow (`rollback-metrics.yml`) runs after each scheduled Nightly, apart from it so a publishing failure can never fail the run a release requires. It adds the reports up with `scripts/rollback_report.py` and writes two files under `metrics/` on `gh-pages`: `rollback-history.json`, one entry per fully green run with the count for each operating system and template, and `rollback-latest.json`, a Shields endpoint that reads `rollback faults restored` with the total. The badge stays cyan like the others, so a failure shows in its text, as `N failing`, and never in its color; only green runs reach the history. A run publishes only when every job in the rollback matrix reported: a missing, empty, or foreign report means the result is unknown, so nothing changes. A manual Nightly that covers the whole matrix publishes too; one narrowed to an OS or template is incomplete and records nothing. The count adds every operating system, so the same fault restored on three platforms counts three times. The [rollback section of the metrics dashboard](https://protostar.jacksonferguson.me/metrics/#rollback) graphs the history by operating system and template, and the Pages workflow deploys both files, after which the site is asked to rebuild as it is for the mutation score.

## Mutation Testing

Mutation testing checks that the tests would notice a bug: [mutmut](https://github.com/boxed/mutmut) changes the code one small edit at a time, such as `<` to `<=`, and reports each edit the suite still passes. `[tool.mutmut]` in `pyproject.toml` lists the modules it covers.

The set comes from `[tool.mutmut].source_paths` in `pyproject.toml`; it excludes the CLI, generated code, and modules reached mainly through mocked boundaries. The score describes that selected engine set, not the whole codebase.

The **Mutation Testing** workflow runs nightly at 05:30 UTC (10:30pm Pacific daylight time), with Nightly. GitHub can start a scheduled run late. After the survivor fixes, the slowest measured module, reconciliation, took about 36 minutes across six parallel shards; nightly runs leave room for that work without running it on every commit. A scheduled run skips mutation testing unless its inputs changed since the last published commit: the selected source modules, `tests/`, `pyproject.toml`, `uv.lock`, or the reporting script and mutation workflow. A missing history or a recorded commit no longer in the current branch's ancestry starts a full run.

Run a module locally, or select modules and individual shards through the workflow's manual trigger:

```bash
just mutate journal
gh workflow run mutation.yml --ref main -f modules=journal
gh workflow run mutation.yml --ref main -f modules=reconciliation:append-files
gh workflow run mutation.yml --ref main -f modules=all
```

Local runs write each surviving edit as a diff to `mutants/survivors.md`. Each CI runner uploads raw counts, survivor names, and survivor diffs. The combined job adds shard counts into one result per module. The mutation score is `(killed + timeout) / (killed + timeout + survived + suspicious)`; mutants no test reaches are reported separately. Surviving mutants reduce the score but do not make the workflow fail: inspect their diffs and strengthen tests where a meaningful behavior change went unnoticed.

Only a successful complete run on `main` publishes. Failed or cancelled jobs and manual subset runs cannot update the public score. Publication checks every expected artifact and the configured module set, then appends the commit, UTC date, and raw per-module counts to `metrics/mutation-history.json` on `gh-pages`. `metrics/mutation-latest.json` is a Shields endpoint with the aggregate score and an explicit engine label. Retrying a recorded commit does not add another history point. Counts are retained so the dashboard can later show changes in the module set without averaging percentages.

Publication rebases and retries if the benchmark or release workflow updates `gh-pages` concurrently; a conflicting history update is regenerated against the new branch contents. The shared Pages workflow deploys both mutation JSON files alongside the performance history. The [mutation testing section of the metrics dashboard](https://protostar.jacksonferguson.me/metrics/#mutations) graphs the aggregate and per-module history, marks changes in the module set, and lists the latest raw counts. Use it to inspect a trend, then use survivor diffs to investigate a missed behavior. The README badge reads the latest score.

jacksonferguson.me shows the latest score on Protostar's project card, and fetches it only when it builds. Once the Pages deploy finishes, the workflow sends the site's repository a `remote-assets-updated` dispatch, so the site rebuilds from the file just deployed. The dispatch uses `PORTFOLIO_DISPATCH_TOKEN`, a fine-grained token limited to that repository with Contents read and write; the job fails with a pointer to it when the secret is missing.

GitHub disables scheduled workflows in public repositories after 60 days without repository activity. Re-enable this workflow with:

```bash
gh workflow enable mutation.yml
```

## Performance & Latency Testing

Performance is checked in two ways. A pull request is checked exactly, by the [cost budgets](testing.md#cost-budgets): what each command does, never how long it takes, since a duration on a shared runner varies more from machine to machine than most regressions change it. Durations are measured every night, where two versions can be compared fairly, and locally when a change is meant to be faster.

### Nightly Benchmarks

`benchmark.yml` runs an hour after Nightly, apart from it, so a slowdown can never fail the run a release requires. On Linux it compares the commit with a baseline, running every scenario of the [local harness](#local-benchmarks) in alternating rounds on one runner. `scripts/benchmarks/report.py` then records the result in `metrics/benchmark-history.json` on `gh-pages`: one entry per night, with each scenario's median timings, and its change in Protostar's own CPU time with a 95% interval. The baseline is the last commit recorded on Linux, so each night measures what changed since, and a night with nothing new runs nothing. Routine benchmarks use Linux to conserve macOS runners; use the local harness to investigate platform-specific performance.

A slowdown is judged on CPU time, the steadiest measure: the commands a run waits on are uv's and git's, and the cost budgets already check which ones run. A scenario is suspect when its whole interval lies at least 10% (`THRESHOLD`) slower. A run with a suspect keeps its baseline, so the next night measures the same change again, with or without new commits, and a slowdown found twice is a regression: the run opens a `performance-regression` issue naming the scenario, the change, and the commits. Close it once the slowdown is fixed, or accepted as the cost of a change. Two measurements make a false alarm unlikely, and measuring both against the same baseline still catches a slowdown that landed in a single commit.

The threshold must stay well clear of the noise. A manual run with `calibrate` compares the commit with itself several times on Linux, records nothing, and summarizes the widest interval the noise produced:

```bash
gh workflow run benchmark.yml -f calibrate=true -f repeats=3
```

A pull request labelled `run-benchmark` is compared with its base on one Linux runner, and gets the table as a comment, which each later run replaces. Remove and add the label to run it again. It is never recorded.

The [benchmark section of the metrics dashboard](https://protostar.jacksonferguson.me/metrics/#benchmarks) graphs each scenario's median by operating system and measure, and lists the latest run's changes and verdicts. Shared runners are slower than most computers, so read the trend rather than the number. The startup timings Hyperfine recorded on every push to main from March to October 2026 stay in `metrics/data.js`, shown collapsed as an archive: each was measured on whichever runner its push got, so they can't be compared with the nightly runs.

The `editor` scenario sets a hidden environment variable, `PROTOSTAR_BENCHMARK_RECIPE_EDITOR=1`. It treats the session as interactive and makes `protostar init` exit as soon as the recipe editor draws its first frame, without waiting on input.

Help and version requests load argument definitions and tool descriptions, but do not load project analysis, reviews, execution, or format engines. Command implementations load only after dispatch. A tool reads its document-backed signals when analysis asks for them, and loads its document generators when planning calls `build()`. `tests/test_cli_startup.py` checks this boundary in fresh interpreters, including JSON help, and the cost budgets list the third-party packages each command imports.

The dashboard source lives in `metrics/` on `main`. Pages publishing combines that source with the recorded data files from `gh-pages`; it never publishes dashboard code from the data branch. To test its data handling locally, use Node.js 18 or newer, and to preview a benchmark history before one is published, pass it to the preview server:

```bash
node --test tests/metrics_dashboard.test.mjs
uv run python scripts/serve_metrics.py --benchmark-history .benchmarks/history.json
```

### Local Benchmarks

`scripts/benchmarks/` times the scenarios the [cost budgets](testing.md#cost-budgets) count, for real: real `uv`, `git`, and hook installs. Use it for performance work, not to check a change; the cost budgets do that in every test run. Each sample runs a scenario's command in a fresh interpreter, in an isolated home directory and project, with configuration off and the hook registry offline. A warm-up round fills uv's cache, and the measured rounds run uv offline from it, so the network never enters a timing. A sample records the whole process's duration (`wall`), the CPU time Protostar's own process used (`cpu`), and the time it waited on commands (`commands`). `protostar` is the duration with the commands taken out: the part Protostar's own code decides.

```bash
just bench sync 'init-*'
just bench-compare main sync
just bench-profile sync
```

Nothing runs until a scenario is named (`--all` times every one, which takes several minutes), and `uv run python -m scripts.benchmarks list` lists them. `bench-compare` checks the other version out into a temporary worktree with its own locked environment, then runs the two in alternating rounds, each going first in turn, so a machine that slows down slows both. It reports each scenario's change as the median ratio across rounds, with a 95% bootstrap interval, and a change reads faster or slower only when that interval excludes zero. The verdict says a change isn't noise, not that it matters: a 1ms change in startup can be real. Comparing the working tree with an identical commit reports no detectable change, within about 2% on a quiet machine. Samples go to `.benchmarks/latest.json`, and `bench-profile` writes a pyinstrument profile to `.benchmarks/`, or prints one with `--text`.

## Related Developer Guides

- **[Testing & Philosophy<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./testing.md):** The rules a test follows, the fixtures that help, and the suites CI runs.
- **[Developer Overview & Contributing<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./overview.md):** Setup instructions, coding standards, and PR workflows.
