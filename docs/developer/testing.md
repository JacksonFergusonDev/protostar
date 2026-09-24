# Testing Architecture & Philosophy

Protostar enforces a strict separation between state definition (the `EnvironmentManifest`) and state execution (the `SystemExecutor`). This decoupling allows the test suite to validate complex environment configurations rapidly without incurring the I/O penalty of actual disk writes or network requests.

As a contributor, you must adhere to our strict isolation boundaries. Tests that leak state to the host filesystem or execute unmocked system binaries outside of explicit integration markers will fail in CI.

## Core Principles

### 1. Disk I/O Isolation

Protostar's primary function is generating and modifying files. To prevent the test suite from polluting the host machine or overwriting your local configurations, all disk I/O must be sandboxed.

Use the `tmp_path` fixture provided by `pytest` for any test requiring an actual filesystem hierarchy, or patch `pathlib.Path` for purely logical validation.

=== "Logical Validation (Mocked)"

    ```python
    def test_direnv_module_aborts_if_not_installed(mocker):
        # Patch shutil.which to simulate direnv not being installed
        mocker.patch("protostar.modules.tooling_layer.shutil.which", return_value=None)

        module = DirenvModule()
        with pytest.raises(RuntimeError, match="direnv is not installed"):
            module.pre_flight()
    ```

=== "Physical Sandbox (`tmp_path`)"

    ```python
    def test_executor_writes_vscode_settings_empty_file(monkeypatch, tmp_path, mock_config):
        # Anchor the execution context to the ephemeral tmp_path
        monkeypatch.chdir(tmp_path)

        vscode_dir = tmp_path / ".vscode"
        vscode_dir.mkdir()
        settings_file = vscode_dir / "settings.json"
        settings_file.write_text("   \n  \t")

        manifest = EnvironmentManifest()
        manifest.add_ide_setting("files.exclude", {"**/.venv": True})

        # Executor acts on the sandboxed tmp_path hierarchy
        SystemExecutor(manifest, mock_config)._write_ide_settings()
    ```

### 2. Subprocess Mocking

Many modules queue shell commands (e.g., `git init`, `uv init`). Unless a test is explicitly marked for integration, **all `subprocess.run` calls must be mocked**.

We utilize `pytest-mock` (the `mocker` fixture) to intercept the `execute_subprocess` wrapper. This ensures tests run in milliseconds and do not require the CI runner to have heavy binary toolchains installed.

```python
def test_pre_commit_module_build_initializes_git(manifest, mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)

    mod = PreCommitModule()
    mod.build(manifest)

    # Assert declarative intent rather than evaluating the shell execution
    assert any(t.command == ["git", "init"] for t in manifest.tasks.system_tasks)

```

## Test Categories

The test suite is unified and runs rapidly (~30 seconds) across all platforms.

### Core Test Suite (`tests/test_*.py`)

The test suite validates AST TOML and JSONC merging algorithms, manifest deduplication logic, parser routing, generator string formatting, and transactional execution lifecycles in `tmp_path` sandboxes.

Repeatability and semantic-reconciliation acceptance live in `tests/test_template_repeatability.py` and the focused reconciliation suites: a tracked workspace is re-run with the same template, not a different template. Template switching is intentionally rejected rather than treated as a generic deep merge.

### Template Hooks Smoke Matrix (CI)

End-to-end template validation is offloaded to a dedicated parallel matrix job in CI (`template-hooks-smoke`). This job scaffolds each built-in template across operating systems, verifies that `prek` hooks are installed, runs a canary check ensuring non-conventional commit messages are rejected, and asserts that the first commit triggers and cleanly passes all pre-commit hooks.

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

=== "Pre-Push CI Emulation"
    Runs the exact pipeline executed by GitHub Actions, sequentially triggering `lint`, `typecheck`, and `test-cov`. Run this before opening a pull request.
    ```bash
    just ci
    ```

=== "Snapshot Regression & Verification"
    Generates scenario regression snapshots in `tests/snapshots/` and documentation presentation assets in `docs/generated/` and `docs/assets/terminals/`, verifying there is no snapshot drift.

    Scenario snapshot directories include `.protostar.lock.toml` alongside the
    generated workspace files. Dependency versions are frozen consistently across
    the state record and `pyproject.toml`, so snapshot review covers ownership changes
    as well as user-visible output.
    ```bash
    just check-snapshots
    ```

=== "Local Server"
    Spins up the Zensical server for local documentation preview.
    ```bash
    just serve
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

Because Protostar is designed for high-velocity initialization, we enforce a strict performance budget to prevent Python's startup overhead from degrading the CLI experience.

The wizard benchmark sets a hidden environment variable, `PROTOSTAR_BENCHMARK_WIZARD=1`. It treats the session as interactive and makes `protostar init` exit as soon as the recipe editor draws its first frame, so the benchmark measures time to first frame without waiting on input.

The `justfile` includes predefined recipes leveraging [hyperfine](https://github.com/sharkdp/hyperfine) to track regression thresholds. Ensure you test your changes against the fast-path (e.g., `protostar help`) to verify dynamic module imports haven't bloated the instantiation tree.

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

All TUI code and structured configuration use `src/protostar/cli/tui/code.py`.
Use `source_text(CodeSource(...))` for a source pane, `diff_text` for two sources,
and `edit_text` for a prepared edit. These renderers share Protostar's palette;
screens must not select independent syntax themes. Pass a Pygments language alias
when the displayed serialization differs from the filename (for example, a TOML
conflict value displayed as JSON). Unknown languages remain plain text.

Highlighting is presentation-only: it never reads project files, changes merge
policy, or modifies prepared bytes. Source display normalizes CRLF and CR to LF,
preserves indentation and literal markup-like text, and highlights complete
sources before selecting diff hunks. Added and removed lines retain syntax colors;
their markers and subtle backgrounds communicate the change.

Run `uv run pytest tests/test_tui_code.py tests/test_conflict_tui.py tests/test_tui.py`
when changing these renderers. Review the Textual snapshots as well as the text
assertions, including the narrow conflict screen. Use `--snapshot-update` only
when accepting an intentional visual change.
