---
description: "How Protostar's tests stay isolated from your machine, and the rules a contributor's tests follow."
---

# Testing Architecture & Philosophy

Protostar enforces a strict separation between state definition (the `EnvironmentManifest`) and state execution (the `SystemExecutor`). This decoupling allows the test suite to validate complex environment configurations rapidly without incurring the I/O penalty of actual disk writes or network requests.

As a contributor, you must adhere to our strict isolation boundaries. Tests that leak state to the host filesystem or execute unmocked system binaries outside of explicit integration markers will fail in CI.

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

## Test Categories

The test suite is unified and runs rapidly (~30 seconds) across all platforms.

### Core Test Suite (`tests/test_*.py`)

The test suite validates AST TOML and JSONC merging algorithms, manifest deduplication logic, parser routing, generator string formatting, and transactional execution lifecycles in `tmp_path` sandboxes.

Repeatability and semantic-reconciliation acceptance live in `tests/test_template_repeatability.py` and the focused reconciliation suites (see the [acceptance suite](reconciliation/execution.md#acceptance-suite)): a tracked workspace is re-run with the same template, not a different template. Template switching is intentionally rejected rather than treated as a generic deep merge.

### Template Hooks Smoke Matrix (CI)

End-to-end template validation runs through the `template-smoke` action (`.github/actions/template-smoke`). It scaffolds each built-in template it is given in turn, verifies that `prek` hooks are installed, runs a canary check ensuring non-conventional commit messages are rejected, and asserts that the first commit triggers and cleanly passes all pre-commit hooks. A `template-hooks-smoke` job runs it for a list of templates, and a test job can run it after the suite through its matrix entry's `smoke` list, which is how macOS smoke-tests templates without a runner of its own.

### Pull Request, Nightly, and Release Platforms

The pytest suite and the smoke matrix are defined once, in `.github/workflows/platforms.yml`, and each caller hands it the matrix to run:

- **Pull requests** (`ci.yml`) run the suite on every operating system and supported Python. They smoke-test every template at every Python on Linux, at the oldest and newest on Windows, and once on macOS, where each test job scaffolds a template or two after its suite.
- **Nightly** (`nightly.yml`) runs, each day on `main`, the smoke tests pull requests leave out, so the two together scaffold every template on every operating system and Python exactly once. It also runs the suite everywhere again, with retries, which is how a flaky test is found. It skips a day when `main` hasn't changed since its last pass.
- **A release** (`release.yml`) publishes only when CI and Nightly have both passed on the tagged commit, or on its parent when the tagged commit only changes `pyproject.toml` and `uv.lock` (the version bump). It also smoke-tests the wheel it is about to publish on each operating system, and publishes that same wheel.

The account runs 20 jobs at a time, five of them on macOS, across every open pull request and push. A pull request starts 20, three on macOS. The quick checks share two runners (`Lint, Docs & Secrets` and `Benchmark & Docker Images`), since each finishes well before the Windows suite that sets how long a run takes. A new push to a pull request cancels the run it replaces.

`tests/test_nightly.py` checks that both test every operating system and Python, that together they smoke-test every template on every platform once, that a pull request stays within the runner limits, and that a release can't publish before CI, Nightly, and its smoke test pass.

Nightly retries a failed test or smoke run once. A test that then passes doesn't fail the run; it is filed as flaky instead. Nightly Report (`nightly-report.yml`) opens a `nightly-failure` issue when the run fails, naming the failing jobs and the commits since the last pass, and closes it when a later run passes. Flaky tests go to a separate `flaky-test` issue that stays open until they are fixed.

To run Nightly before merging a risky change, or before a release when it hasn't run on the commit yet, start it from the Actions tab or with `gh workflow run nightly.yml --ref <branch or tag>`.

### Crash Reporter Testing (`--crash-test`)

If you are working on the orchestrator's exception handling or the GitHub issue crash report generation, you can simulate a catastrophic failure without having to manually break the codebase. Pass the hidden `--crash-test` flag to the `init` command to raise an intentional exception at the end of the module evaluation phase:

```bash
protostar init --crash-test
```

This guarantees the crash reporter is invoked, allowing you to inspect the URL-encoded GitHub issue generation.

## Running the Suite

We utilize `just` to standardize test execution, abstracting the underlying `uv`, `ruff`, and `pytest` invocations. This is the recommended approach for local development to ensure parity with the GitHub Actions CI runners.

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

=== "Pre-Push CI Emulation"
    Runs the exact pipeline executed by GitHub Actions, sequentially triggering `lint`, `typecheck`, and `test-cov`. Run this before opening a pull request.
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
    Opens the benchmark dashboard at `http://127.0.0.1:8765/benchmarks/`, independently of the documentation server on port 8000. It fetches the published measurements once; refresh the page to see source edits. Stop it with `Ctrl+C`, or choose another port with `just serve-benchmarks 8766`.
    ```bash
    just serve-benchmarks
    ```

!!! tip "Manual Execution"
    If you need to pass specific flags directly to pytest or run a single file, bypass the runner and use `uv` directly:
    ```bash
    uv run pytest tests/test_executor.py
    ```

### TOML Merge Fixture Reference

The test runner utilizes the following messy baseline configuration (injected dynamically from a dummy `pyproject.toml`) to validate AST deep-merging behavior:

```toml
[project]
name = "protostar-test"
version = "0.1.0"
description = "A messy baseline TOML file"
authors = [
    { name = "Test User", email = "test@example.com" } # Inline table
]
requires-python = ">=3.11"
dependencies = [
    "requests>=2.31.0",
    "numpy", # A random comment inside an array
]

[tool.ruff]
line-length = 120 # Overly long default
target-version = "py310"
ignore = ["E501"]

# We expect this comment to survive the merge
[tool.ruff.lint]
select = ["E", "F"]

[[tool.mypy.overrides]]
module = "tests.*"
ignore_errors = true
```

## Performance & Latency Testing

CI tracks help-command startup (`protostar help init`) and the recipe editor's first frame to catch large regressions in the CLI experience. These measurements do not include a completed scaffold or dependency installation.

The recipe editor benchmark sets a hidden environment variable, `PROTOSTAR_BENCHMARK_RECIPE_EDITOR=1`. It treats the session as interactive and makes `protostar init` exit as soon as the recipe editor draws its first frame, without waiting on input. Hyperfine measures the whole process, including Python startup and shutdown, in the checked-out repository.

The [CI performance history](https://protostar.jacksonferguson.me/benchmarks/) records main-branch measurements on GitHub Actions Ubuntu runners with Python 3.14. Each recorded point is the mean of 90 executions after 30 warmups. These timings describe the CI environment, not local workstation latency; runner variability and changes to the runner image or project checkout also limit comparisons between commits. Look for sustained trends rather than treating a single increase as a confirmed regression. Older wizard measurements remain in the downloadable history but are excluded from the recipe-editor chart.

The CI regression check uses 30 executions after 5 warmups and fails when a measurement exceeds 250% of the preceding recorded result for the same benchmark. Historical tracking alerts above 200% without failing the run. These are relative checks for large regressions, not an absolute latency budget. The dashboard's comparison with up to 100 preceding benchmark runs is a separate descriptive summary, not the baseline used by either check.

The `justfile` includes predefined recipes using [Hyperfine](https://github.com/sharkdp/hyperfine) to reproduce the measurements locally. Compare changes on the same machine and checkout conditions to check whether dynamic module imports have increased startup time.

Help and version requests load argument definitions and tool descriptions, but do not load project analysis, reviews, execution, or format engines. Command implementations load only after dispatch. A tool reads its document-backed signals when analysis asks for them, and loads its document generators when planning calls `build()`. `tests/test_cli_startup.py` checks this boundary in fresh interpreters, including JSON help; this catches unnecessary imports without a machine-dependent timing threshold.

The dashboard source lives in `benchmarks/` on `main`. Pages publishing combines that source with the recorded `benchmarks/data.js` from `gh-pages`; it never publishes dashboard code from the data branch. To test its data handling locally, use Node.js 18 or newer:

```bash
node --test tests/benchmark_metrics.test.mjs
```

=== "Quick Benchmark"
    Runs a 5-iteration warmup and 30 statistical runs.

    ```bash
    just test-benchmark
    ```

=== "Rigorous Benchmark"
    Runs a 30-iteration warmup and 90 statistical runs, exporting results to `benchmark.json`.

    ```bash
    just test-benchmark-slower
    ```

## Related Developer Guides

- **[Developer Overview & Contributing](./overview.md):** Setup instructions, coding standards, and PR workflows.
- **[Extending Protostar](./extending-protostar.md):** Build new tooling modules to accompany your tests.
- **[The Orchestrator](../mechanics/orchestrator.md):** Understand the headless core and execution lifecycle under test.

## TUI source presentation

All TUI code and structured configuration use `src/protostar/cli/tui/code.py`. Use `source_text(CodeSource(...))` for a source pane, `diff_text` for two sources, and `edit_text` for a prepared edit. These renderers share Protostar's palette; screens must not select independent syntax themes. Pass a Pygments language alias when the displayed serialization differs from the filename (for example, a TOML conflict value displayed as JSON). Unknown languages remain plain text. The Pygments adapter and token theme in `syntax.py` load on the first source render; keep that import lazy so opening the recipe editor loads no Pygments.

Highlighting is presentation-only: it never reads project files, changes merge policy, or modifies prepared bytes. Source display normalizes CRLF and CR to LF, preserves indentation and literal markup-like text, and highlights complete sources before selecting diff hunks. Added and removed lines retain syntax colors; their markers and subtle backgrounds communicate the change.

Run `uv run pytest tests/test_tui_code.py tests/test_conflict_tui.py tests/test_tui.py` when changing these renderers. Review the Textual snapshots as well as the text assertions, including the narrow conflict screen. Use `--snapshot-update` only when accepting an intentional visual change.
