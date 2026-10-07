---
description: "How Protostar's tests stay isolated from your machine, and the rules a contributor's tests follow."
---

# Testing Architecture & Philosophy

Planning is pure and execution is the only phase that touches the disk, so most of Protostar can be tested without writing a file outside a sandbox or running a real command. This page covers the rules a test follows, the fixtures that help, the checks that guard Protostar's own boundaries, and how CI runs it all.

## Core Principles

### 1. Disk I/O Isolation

Protostar's job is writing and changing files, so a test that writes outside a sandbox could overwrite your own projects. Ordinary tests write only under `pytest`'s `tmp_path`, usually by changing into it, since Protostar works on the current directory:

```python
--8<-- "tests/test_modules.py:git_init"
```

Planning is pure, so most tests stop at the manifest: they build modules and assert what was declared, without executing anything.

### 2. Mock Commands at the Boundary

Unless a test is marked `integration`, it runs no real command. Mock at the boundary the test exercises: `ProcessRunner.run` for a test of planning and execution, or `subprocess.run` and `subprocess.Popen` for a test of `ProcessRunner` itself. Every test finds each program on `PATH` unless it adds the program to the `missing_executables` fixture:

```python
--8<-- "tests/test_missing_tools.py:missing_tools"
```

This executes a real plan in a sandboxed workspace, with `ProcessRunner.run` mocked, and checks that a missing `direnv` skips only the step that runs it.

### 3. Integration Tests Are Few and Isolated

A test marked `@pytest.mark.integration` may run real `uv`, `git`, and hook commands, to check what mocks can't: that a scaffold actually installs, or that a hook really runs. Keep them few, and isolate them with the `real_tool_env` fixture, which gives the process a `HOME` and configuration under `tmp_path`. Its one deliberate write outside `tmp_path` is uv's shared package cache, so repeated runs don't download everything again. They may use the network.

Integration tests stay in the full suite, in pre-push and CI. Leaving them out isn't a useful shortcut: there are few of them.

## Fixtures Worth Knowing

`tests/conftest.py` holds the fixtures most tests need:

| Fixture | What it does |
| :--- | :--- |
| `missing_executables` | Every test sees each program on `PATH`; add one to this set to simulate it missing. Automatic. |
| `isolate_git_repository` | Drops git's repository variables, so a test run from a git hook can't touch this repository. Automatic. |
| `progress` | A progress hook that records each execution step's start and outcome, for testing what the engine reports. |
| `real_tool_env` | An isolated environment for an integration test's real processes. |
| `run_cli` | Runs the CLI as a real process in `tmp_path`, with `real_tool_env`, and returns its exit code and output. For integration tests. |
| `seed_global_config` | Writes a global configuration file under the sandboxed home, for integration tests. |
| `forge` | Routes every template download and ref listing to an in-memory repository host, for testing repository templates without the network. |
| `snap_compare` | Takes a TUI snapshot, and checks the screen's spacing with `check_layout`. |

## Tests That Guard a Boundary

Some tests exist to keep a rule from AGENTS.md true:

- **`tests/test_headless_boundary.py`** fails if importing any module outside `protostar.cli` loads `rich` or `textual`.
- **`tests/test_cli_startup.py`** checks in fresh interpreters that `--help` and `--version` import no project analysis, execution, or format engine.
- **`tests/test_legacy_encoding.py`** renders output to a strict cp1252 stream, as Windows does for redirected output. Test new output there; macOS and Linux never hit it.
- **`tests/test_tui_theme.py`** fails when TUI code names a color outside the theme.
- **`tests/test_rollback.py`** fails `init` and `sync` at every write, directory, removal, and command, and fails when a run changes a file it never journaled (see [Rollback Fault Injection](#rollback-fault-injection)).
- **`tests/test_cost_budgets.py`** fails when what a command does changes: the commands and processes it runs, its hook registry fetches, the documents it parses, and the packages it imports (see [Cost Budgets](#cost-budgets)).
- **TUI snapshots** compare each screen's rendering, and `check_layout` measures its spacing against the layout rule, so every new screen needs a snapshot. Drive TUI tests with `pilot.press`, and use `pilot.click` only in tests about the mouse.

## Test Categories

### Core Test Suite (`tests/test_*.py`)

The suite runs in parallel with `just test` (`pytest -n auto --dist worksteal`). It covers the format engines, the reconciliation kernel, planning, the CLI and TUI, and transactional execution in `tmp_path` sandboxes.

Repeatability and reconciliation acceptance live in `tests/test_template_repeatability.py` and the focused reconciliation suites (see the [acceptance suite](reconciliation/execution.md#acceptance-suite)): a tracked project is run again with the same template, never a different one, since switching templates is rejected.

### Rollback Fault Injection

Execution is one transaction: a failure anywhere must leave the project and the home directory exactly as they were. `tests/test_rollback.py` checks that at every point a real `init` or `sync` can fail. Every disk mutation goes through three `TransactionAwareFS` operations and every command through `ProcessRunner.run`, so the harness (`tests/rollback_harness.py`) wraps those four seams and names each call a site: `write:pyproject.toml#2` is the second write of `pyproject.toml`. Each case seeds a project, fails the run at one site, and compares the trees afterwards:

- **Where:** before the operation, mid-way (a write's final rename fails after its temporary file exists; a command does half its work), or after it.
- **How:** an error (`OSError`, or a failed command) or an interrupt (`KeyboardInterrupt`).
- **Seeds:** for `init`, an empty folder, an existing project Protostar merges into (comments, kept file modes, binary and CRLF files, an unrelated tree), and the same project already a git repository. For `sync`, a project `init` just created whose recipe then turns tools off and on and loses an installed hook, so the run removes files, adds one, resolves dependencies, and installs hooks again.

A case passes when the run exits with a domain error (or 130 for an interrupt), every path is restored byte for byte with its mode, nothing is left behind, and no file the run never journaled was rewritten. The one exception is an error in the hook install on `sync`, which only warns: that run must finish, say so, and leave what a clean run leaves apart from the hooks. Only what the rollback boundary disclaims goes uncompared: uv's `.venv/` and tool caches in the home directory, listed with their reasons in the harness.

The commit is a site too. An interrupt just before it rolls everything back; one just after it must keep the finished run whole and report a plain interrupt, never a rollback. Three more checks cover rollback itself:

- **A restore that fails:** each path the run writes fails its restore in turn. Rollback must name that path (and any directory it created above it) in `RollbackFailedError`, and restore everything else.
- **A second `Ctrl+C`:** a real `SIGINT` arrives as rollback starts, and every path must still come back. POSIX only.
- **Running again:** after an interrupt at the last write, which rolls back the most, running the command again must leave exactly the project a clean run does. Once per scenario is enough: every fault case already proves a rolled-back project matches the seed byte for byte, so this catches only state a run keeps outside the files.

Commands run through a fake that writes exactly what the executor journaled for them (and, for `uv add` and `uv lock`, what uv writes), so the cases stay fast and offline. A clean run must journal every path it changes, which catches a write made around the seams. Integration tests run the real commands for one scenario: they pass the same sites as the fake, and an error after each command, or an interrupt after the last, rolls back what it really did.

The sites each scenario passes are committed in `tests/rollback_sites/`, and the cases are generated from them. A change that adds, removes, or reorders a site fails until the lists are regenerated:

```bash
uv run pytest tests/test_rollback.py -k sites_match --snapshot-update
```

Pull requests keep to what guards coverage, so their test jobs stay within a few minutes on every platform: every scenario's clean run and site list, an error after each site of two representative scenarios (`cli` merged into an existing project, and a `sync` of `cli`), and the first one's real commands once, except on Windows, where a real init takes a minute. The three Linux pull-request jobs raise every position and fault in every template and seed (`--rollback-scope full`) between them, a third each (`--rollback-shard 1/3` and so on, a stable split by test id), which faked commands make cheap there. Nightly does the same with every fault raised around real commands too (`--rollback-real all`), in one job per template and operating system, and six slices per template on Windows, where each run is slowest:

```bash
uv run pytest tests/test_rollback.py --rollback-scope full --rollback-real all --rollback-templates ml
```

`just test-rollback` runs the full scope with faked commands. The harness skips `fsync`: rollback restores what is on disk, and durability through a power cut isn't under test.

#### Counting the Faults

Every test that injects a fault carries the `rollback_fault` marker, and `--rollback-report PATH` writes how many of them passed, and which failed, per scenario (`tests/rollback_report.py`). A retry of failed tests updates the same file, so it holds each fault's last outcome, and a run that is killed or interrupted writes nothing. Nightly's rollback jobs pass the option and upload the file as an artifact, even when the job fails.

The `Rollback Metrics` workflow (`rollback-metrics.yml`) runs after each scheduled Nightly, apart from it so a publishing failure can never fail the run a release requires. It adds the reports up with `scripts/rollback_report.py` and writes two files under `metrics/` on `gh-pages`: `rollback-history.json`, one entry per fully green run with the count for each operating system and template, and `rollback-latest.json`, a Shields endpoint that reads `rollback faults restored` with the total. The badge stays cyan like the others, so a failure shows in its text, as `N failing`, and never in its color; only green runs reach the history. A run publishes only when every job in the rollback matrix reported: a missing, empty, or foreign report means the result is unknown, so nothing changes. A manual Nightly that covers the whole matrix publishes too; one narrowed to an OS or template is incomplete and records nothing. The count adds every operating system, so the same fault restored on three platforms counts three times. The [rollback section of the metrics dashboard](https://protostar.jacksonferguson.me/metrics/#rollback) graphs the history by operating system and template, and the Pages workflow deploys both files, after which the site is asked to rebuild as it is for the mutation score.

### Cost Budgets

A command's duration on a shared CI runner varies more from one machine to the next than most regressions change it, so no test fails on a timing. What a test can check exactly is what a command does. `tests/test_cost_budgets.py` runs each scenario in `scripts/benchmarks/scenarios.py`: every built-in template's `init`, an `init --dry-run`, and `sync`, `sync --check`, `status`, and `diff` on a project with nothing to update, plus `--version` and `help init`. For each it counts:

- every command it runs and any other process it starts, labelled as the rollback sites are (`command:uv add --no-sync --dev`);
- each hook registry fetch;
- each YAML, TOML, and JSONC parse;
- the third-party packages it imports;
- its exit code.

The counts must equal the scenario's file in `tests/cost_budgets/`. Each scenario runs in a fresh interpreter (`tests/cost_budget_runner.py`), because what a run parses or imports depends on what earlier code in the same process cached. Commands are faked as the rollback suite fakes them, every tool counts as installed, and the registry is offline, so the counts are the same on every host. `scripts/benchmarks/probes.py` wraps the seams the costs pass through. It wraps a parser only when its module is first imported, so recording loads nothing extra, and a test fails if a seam it wraps moves.

A change that adds or removes a cost fails until the budgets are regenerated:

```bash
uv run pytest tests/test_cost_budgets.py --snapshot-update
```

The diff then shows the change in review. Say in the pull request why it changed: a new parse or process is fine when the feature needs it, and a cost that falls is worth a line too.

### Template Hooks Smoke Matrix (CI)

End-to-end template validation runs through the `template-smoke` action (`.github/actions/template-smoke`). It scaffolds each built-in template it is given in turn, verifies that `prek` hooks are installed, runs a canary check ensuring non-conventional commit messages are rejected, and asserts that the first commit triggers and cleanly passes all pre-commit hooks. A `template-hooks-smoke` job runs it for a list of templates, and a test job can run it after the suite through its matrix entry's `smoke` list, which is how macOS smoke-tests templates without a runner of its own.

### Pull Request, Nightly, and Release Platforms

The pytest suite and the smoke matrix are defined once, in `.github/workflows/platforms.yml`, and each caller hands it the matrix to run:

- **Pull requests** (`ci.yml`) run the suite on every operating system and supported Python. They smoke-test every template at every Python on Linux, at the oldest and newest on Windows, and once on macOS, where each test job scaffolds a template or two after its suite.
- **Nightly** (`nightly.yml`) runs, each day on `main`, the smoke tests pull requests leave out, so the two together scaffold every template on every operating system and Python exactly once. It also runs the suite everywhere again, with retries, which is how a flaky test is found, and the full [rollback fault injection](#rollback-fault-injection) with real commands. It skips a day when `main` hasn't changed since its last pass.
- **A release** (`release.yml`) publishes only when CI and Nightly have both passed on the tagged commit, or on its parent when the tagged commit only changes `pyproject.toml` and `uv.lock` (the version bump). It also smoke-tests the wheel it is about to publish on each operating system, and publishes that same wheel.

The account runs 20 jobs at a time, five of them on macOS, so a pull request starts at most 20, three on macOS, and every job starts at once. Nightly has no such limit: it runs overnight, when nothing waits on it, and starts as many jobs as its work needs. The quick checks share two runners (`Lint, Docs & Secrets` and `Benchmark & Docker Images`), since each finishes well before the Windows suite that sets how long a run takes. A new push to a pull request cancels the run it replaces.

`tests/test_nightly.py` checks that both test every operating system and Python, that together they smoke-test every template on every platform once, that a pull request stays within the runner limits, that Nightly fails every template at every site on every operating system, and that a release can't publish before CI, Nightly, and its smoke test pass.

Nightly retries a failed test or smoke run once. A test that then passes doesn't fail the run; it is filed as flaky instead. Nightly Report (`nightly-report.yml`) opens a `nightly-failure` issue when the run fails, naming the failing jobs and the commits since the last pass, and closes it when a later run passes. Flaky tests go to a separate `flaky-test` issue that stays open until they are fixed.

To run Nightly before merging a risky change, or before a release when it hasn't run on the commit yet, start it from the Actions tab or with `gh workflow run nightly.yml --ref <branch or tag>`. To reproduce one rollback failure without starting every job, narrow it: `gh workflow run nightly.yml --ref <branch> -f rollback-only=true -f os=windows-latest -f template=cli` runs only that template's rollback jobs on that operating system.

### Crash Reporter Testing (`--crash-test`)

If you are working on the orchestrator's exception handling or the GitHub issue crash report generation, you can simulate a catastrophic failure without having to manually break the codebase. Pass the hidden `--crash-test` flag to the `init` command to raise an intentional exception at the end of the module evaluation phase:

```bash
protostar init --crash-test
```

This guarantees the crash reporter is invoked, allowing you to inspect the URL-encoded GitHub issue generation.

## Running the Suite

The `justfile` holds the commands CI runs, so local runs match it.

!!! tip "Self-Documenting Tooling"
    For the complete list of available development, formatting, and benchmarking commands, simply run `just` in the root of the repository.

### Manual Sandbox Scenarios (macOS)

Each recipe builds the current Protostar source in a temporary virtual environment, uses a separate HOME, and opens a shell in a disposable Git repository. Exit the shell to remove the entire sandbox.

```bash
just sandbox                # Empty workspace
just sandbox-existing       # Existing Python project with no Protostar recipe
just sandbox-sync           # Tracked project with a pending local template update
just sandbox-sync-conflict  # Tracked project with a conflicting template update
```

In `sandbox-existing`, try `protostar init --dry-run` to inspect how Protostar handles user-owned `pyproject.toml`, source files, and a justfile. In `sandbox-sync`, try `protostar status`, `protostar diff`, and `protostar sync` in that order. The scenario starts with a committed Protostar initialization and a committed local edit. Its template then updates managed TOML in `pyproject.toml` and adds a setup document; the project's local notes should remain intact. The template and its trusted alias exist only inside the sandbox.

Use `just sandbox-sync-conflict` to practice the interactive sync screen. The project's committed coverage threshold differs from both its recorded baseline and the updated template. The team also edited a setup instruction that the template changed on the same line. `protostar sync` opens the TUI for those two decisions, while the template's new setup document and updated coverage reporting setting can apply safely. A project note outside the managed instructions stays in place. Run bare `protostar sync` inside the sandbox shell; `--json`, `--dry-run`, `--check`, and `--resolve` skip the TUI.

Pass Protostar arguments to run one command without entering a shell, such as `just sandbox-sync status`. Each recipe invocation creates a new sandbox, so use the interactive shell when testing a sequence of commands against one project.

=== "Everything CI Runs"
    Runs every check CI and the push hooks run, one after another: `lint`, `typecheck`, `test`, `docs`, `check-snapshots`, `check-doc-links`, `check-docs-drift`, `check-schemas`, and `secrets`. The pre-commit and pre-push hooks already run these, so reach for it only to debug a difference from CI.
    ```bash
    just ci
    ```

=== "Snapshot Regression & Verification"
    Generates scenario regression snapshots in `tests/snapshots/` and documentation presentation assets in `docs/generated/` and `docs/assets/terminals/`, verifying there is no snapshot drift.

    Scenario snapshot directories include `protostar.lock` alongside the
    generated workspace files. Dependency versions are frozen consistently across
    the state record and `pyproject.toml`, so snapshot review covers ownership changes
    as well as user-visible output. The snapshot's `producer_version` is normalized
    to `0.0.0`, so a package version bump alone does not cause drift. Real project
    lock files still record the installed version.

    Before each scenario command, the runner also takes the `--dry-run --json`
    plan and fails when the finished scaffold's tree (the one the docs show)
    has a file no plan listed, or lacks one a plan listed. The dry-run tree,
    the recipe editor's preview, and the change review all read that plan, so
    this keeps every preview tree true to what `init` leaves behind.
    ```bash
    just check-snapshots
    ```

=== "Local Server"
    Spins up the Zensical server for local documentation preview.
    ```bash
    just serve
    ```

=== "Benchmark Preview"
    Opens the metrics dashboard at `http://127.0.0.1:8765/metrics/`, independently of the documentation server on port 8000. It fetches the published measurements once; refresh the page to see source edits. Stop it with `Ctrl+C`, or choose another port with `just serve-metrics 8766`.
    ```bash
    just serve-metrics
    ```

!!! tip "Manual Execution"
    If you need to pass specific flags directly to pytest or run a single file, bypass the runner and use `uv` directly:
    ```bash
    uv run pytest tests/test_executor.py
    ```

### TOML Merge Fixture Reference

The TOML merge tests start from this deliberately messy `pyproject.toml`, `tests/fixtures/base_complex.toml`, with inline tables, comments inside arrays, and nested tables, to check that merging keeps all of it:

```toml
--8<-- "tests/fixtures/base_complex.toml"
```

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

CI tracks [help-command startup](https://protostar.jacksonferguson.me/metrics/#startup) (`protostar help init`) and the [recipe editor's first frame](https://protostar.jacksonferguson.me/metrics/#editor) to catch large regressions in the CLI experience. These measurements do not include a completed scaffold or dependency installation.

The recipe editor benchmark sets a hidden environment variable, `PROTOSTAR_BENCHMARK_RECIPE_EDITOR=1`. It treats the session as interactive and makes `protostar init` exit as soon as the recipe editor draws its first frame, without waiting on input. Hyperfine measures the whole process, including Python startup and shutdown, in the checked-out repository.

The [benchmark dashboard](https://protostar.jacksonferguson.me/metrics/#benchmarks) records main-branch measurements on GitHub Actions Ubuntu runners with Python 3.14. Each recorded point is the mean of 90 executions after 30 warmups. These timings describe the CI environment, not local workstation latency; runner variability and changes to the runner image or project checkout also limit comparisons between commits. Look for sustained trends rather than treating a single increase as a confirmed regression. Older wizard measurements remain in the downloadable history but are excluded from the recipe-editor chart.

The CI regression check uses 30 executions after 5 warmups and fails when a measurement exceeds 250% of the preceding recorded result for the same benchmark. Historical tracking alerts above 200% without failing the run. These are relative checks for large regressions, not an absolute latency budget. The dashboard's comparison with up to 100 preceding benchmark runs is a separate descriptive summary, not the baseline used by either check.

Help and version requests load argument definitions and tool descriptions, but do not load project analysis, reviews, execution, or format engines. Command implementations load only after dispatch. A tool reads its document-backed signals when analysis asks for them, and loads its document generators when planning calls `build()`. `tests/test_cli_startup.py` checks this boundary in fresh interpreters, including JSON help; this catches unnecessary imports without a machine-dependent timing threshold.

The dashboard source lives in `metrics/` on `main`. Pages publishing combines that source with the recorded `metrics/data.js` from `gh-pages`; it never publishes dashboard code from the data branch. To test its data handling locally, use Node.js 18 or newer:

```bash
node --test tests/metrics_dashboard.test.mjs
```

### Local Benchmarks

`scripts/benchmarks/` times the scenarios the [cost budgets](#cost-budgets) count, for real: real `uv`, `git`, and hook installs. Use it for performance work, not to check a change; the cost budgets do that in every test run. Each sample runs a scenario's command in a fresh interpreter, in an isolated home directory and project, with configuration off and the hook registry offline. A warm-up round fills uv's cache, and the measured rounds run uv offline from it, so the network never enters a timing. A sample records the whole process's duration (`wall`), the CPU time Protostar's own process used (`cpu`), and the time it waited on commands (`commands`). `protostar` is the duration with the commands taken out: the part Protostar's own code decides.

```bash
just bench sync 'init-*'
just bench-compare main sync
just bench-profile sync
```

Nothing runs until a scenario is named (`--all` times every one, which takes several minutes), and `uv run python -m scripts.benchmarks list` lists them. `bench-compare` checks the other version out into a temporary worktree with its own locked environment, then runs the two in alternating rounds, each going first in turn, so a machine that slows down slows both. It reports each scenario's change as the median ratio across rounds, with a 95% bootstrap interval, and a change reads faster or slower only when that interval excludes zero. The verdict says a change isn't noise, not that it matters: a 1ms change in startup can be real. Comparing the working tree with an identical commit reports no detectable change, within about 2% on a quiet machine. Samples go to `.benchmarks/latest.json`, and `bench-profile` writes a pyinstrument profile to `.benchmarks/`, or prints one with `--text`.

## TUI Source Presentation

All TUI code and structured configuration use `src/protostar/cli/tui/code.py`. Use `source_text(CodeSource(...))` for a source pane, `diff_text` for two sources, and `edit_text` for a prepared edit. These renderers share Protostar's palette; screens must not select independent syntax themes. Pass a Pygments language alias when the displayed serialization differs from the filename (for example, a TOML conflict value displayed as JSON). Unknown languages remain plain text. The Pygments adapter and token theme in `syntax.py` load on the first source render; keep that import lazy so opening the recipe editor loads no Pygments.

Highlighting is presentation-only: it never reads project files, changes merge policy, or modifies prepared bytes. Source display normalizes CRLF and CR to LF, preserves indentation and literal markup-like text, and highlights complete sources before selecting diff hunks. Added and removed lines retain syntax colors; their markers and subtle backgrounds communicate the change.

Run `uv run pytest tests/test_tui_code.py tests/test_conflict_tui.py tests/test_tui.py` when changing these renderers. Review the Textual snapshots as well as the text assertions, including the narrow conflict screen. Use `--snapshot-update` only when accepting an intentional visual change.

## Related Developer Guides

- **[Developer Overview & Contributing](./overview.md):** Setup instructions, coding standards, and PR workflows.
- **[Extending Protostar](./extending-protostar.md):** Build new tooling modules to accompany your tests.
- **[The Orchestrator](../mechanics/orchestrator.md):** Understand the headless core and execution lifecycle under test.
