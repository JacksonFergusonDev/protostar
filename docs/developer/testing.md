---
description: "How Protostar's tests stay isolated from your machine, and the rules a contributor's tests follow."
---

# Testing Architecture & Philosophy

Planning is pure and execution is the only phase that touches the disk, so most of Protostar can be tested without writing a file outside a sandbox or running a real command. This page covers the rules a test follows, the fixtures that help, and the checks that guard Protostar's own boundaries. [CI, Nightly & Metrics](ci.md) covers where they run and what they measure.

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

`just test-rollback` runs the full scope with faked commands. The harness skips `fsync`: rollback restores what is on disk, and durability through a power cut isn't under test. Nightly counts every fault restored for the metrics dashboard; see [Counting Rollback Faults](ci.md#counting-rollback-faults).

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

The diff then shows the change in review. Say in the pull request why it changed: a new parse or process is fine when the feature needs it, and a cost that falls is worth a line too. Durations are timed nightly instead; see [Nightly Benchmarks](ci.md#nightly-benchmarks).

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

    Scenario snapshot directories include `protostar.lock` alongside the generated workspace files. Dependency versions are frozen consistently across the state record and `pyproject.toml`, so snapshot review covers ownership changes as well as user-visible output. The snapshot's `producer_version` is normalized to `0.0.0`, so a package version bump alone does not cause drift. Real project lock files still record the installed version.

    Before each scenario command, the runner also takes the `--dry-run --json` plan and fails when the finished scaffold's tree (the one the docs show) has a file no plan listed, or lacks one a plan listed. The dry-run tree, the recipe editor's preview, and the change review all read that plan, so this keeps every preview tree true to what `init` leaves behind.
    ```bash
    just check-snapshots
    ```

=== "Local Server"
    Spins up the Zensical server for local documentation preview.
    ```bash
    just serve
    ```

=== "Metrics Dashboard"
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

??? abstract "`tests/fixtures/base_complex.toml`"
    ```toml
    --8<-- "tests/fixtures/base_complex.toml"
    ```

## TUI Source Presentation

All TUI code and structured configuration use `src/protostar/cli/tui/code.py`. Use `source_text(CodeSource(...))` for a source pane, `diff_text` for two sources, and `edit_text` for a prepared edit. These renderers share Protostar's palette; screens must not select independent syntax themes. Pass a Pygments language alias when the displayed serialization differs from the filename (for example, a TOML conflict value displayed as JSON). Unknown languages remain plain text. The Pygments adapter and token theme in `syntax.py` load on the first source render; keep that import lazy so opening the recipe editor loads no Pygments.

Highlighting is presentation-only: it never reads project files, changes merge policy, or modifies prepared bytes. Source display normalizes CRLF and CR to LF, preserves indentation and literal markup-like text, and highlights complete sources before selecting diff hunks. Added and removed lines retain syntax colors; their markers and subtle backgrounds communicate the change.

Run `uv run pytest tests/test_tui_code.py tests/test_conflict_tui.py tests/test_tui.py` when changing these renderers. Review the Textual snapshots as well as the text assertions, including the narrow conflict screen. Use `--snapshot-update` only when accepting an intentional visual change.

## Related Developer Guides

- **[CI, Nightly & Metrics<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./ci.md):** Where the suite runs, and the rollback, mutation, and benchmark results it publishes.
- **[Developer Overview & Contributing<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./overview.md):** Setup instructions, coding standards, and PR workflows.
- **[Extending Protostar<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](./extending-protostar.md):** Build new tooling modules to accompany your tests.
- **[The Orchestrator<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](../mechanics/orchestrator.md):** Understand the headless core and execution lifecycle under test.
