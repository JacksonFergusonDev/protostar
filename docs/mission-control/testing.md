# Testing Architecture & Philosophy

Protostar enforces a strict separation between state definition (the `EnvironmentManifest`) and state execution (the `SystemExecutor`). This decoupling allows the test suite to validate complex environment topologies rapidly without incurring the I/O penalty of actual disk writes or network requests.

As a contributor, you must adhere to our strict isolation boundaries. Tests that leak state to the host filesystem or execute unmocked system binaries outside of explicit integration markers will fail in CI.

---

## Core Principles

### 1. Disk I/O Isolation

Protostar's primary function is generating and modifying files. To prevent the test suite from polluting the host machine or overwriting a developer's local configurations, all disk I/O must be sandboxed.

Use the `tmp_path` fixture provided by `pytest` for any test requiring an actual filesystem hierarchy, or patch `pathlib.Path` for purely logical validation.

=== "Logical Validation (Mocked)"

    ```python
    def test_latex_generator_aborts_on_existing_file(mocker, mock_config):
        # Patch the target to simulate an existing file without touching the disk
        mocker.patch("protostar.generators.latex.Path.exists", return_value=True)

        generator = LatexGenerator()
        with pytest.raises(FileExistsError, match="Target file already exists"):
            generator.execute("main.tex", mock_config)
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

Many modules queue shell commands (e.g., `git init`, `cargo init`, `npm init`). Unless a test is explicitly marked for integration, **all `subprocess.run` calls must be mocked**.

We utilize `pytest-mock` (the `mocker` fixture) to intercept the `execute_subprocess` wrapper. This ensures tests run in milliseconds and do not require the CI runner to have heavy binary toolchains installed.

```python
def test_pre_commit_module_build_initializes_git(manifest, mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)

    mod = PreCommitModule()
    mod.build(manifest)

    # Assert declarative intent rather than evaluating the shell execution
    assert ["git", "init"] in manifest.system_tasks

```

---

## The Non-Python Exemption (Declarative Testing)

Protostar is heavily optimized for Python environments. While we support C++, Rust, Node.js, and LaTeX footprints, these target environments are currently **deprioritized for End-to-End (E2E) testing**.

We strictly test non-Python modules via **Declarative Validation**. Instead of shelling out to the host machine to compile a generated `CMakeLists.txt` or execute an `npm` package configuration, we assert that the `EnvironmentManifest` correctly queued the required operations and configuration payloads.

!!! info "Seeking Domain Contributors"
    Because the core maintainership is deeply biased toward Python capabilities, we rely on community experts for non-Python domains. If you are a Rust, C++, or Node.js expert, contributions to enhance the declarative boundaries or add isolated, nightly integration tests for these environments are welcome.

---

## Test Categories

We divide the test suite into three architectural tiers to balance coverage confidence with execution latency.

### Unit Tests (`tests/test_*.py`)

The vast majority of the suite. These run entirely in-memory or via mocked boundaries. They validate AST TOML merging algorithms, manifest deduplication logic, parser routing, and generator string formatting.

### Integration Tests (`@pytest.mark.integration`)

Found in `tests/test_integration.py`, these tests bypass the subprocess mocks and execute real commands inside the `tmp_path` sandbox.

We use the custom `run_cli` fixture in `conftest.py` to spawn the `uv` toolchain dynamically. To prevent CI timeouts, these tests preserve the `UV_CACHE_DIR` across test permutations to avoid re-downloading massive ML libraries like `torch` when the `HOME` directory is mocked.

### Exhaustive Tests (`@pytest.mark.exhaustive`)

Found in `tests/test_exhaustive.py`, these tests leverage `itertools.combinations` to permute every domain-specific preset against each other. This guarantees that loading multiple presets (e.g., `--astro` alongside `--ml`) does not cause `KeyError` collisions or corrupted TOML AST injections.

---

## Running the Suite

We utilize a `Makefile` to standardize test execution and abstract the underlying `uv` and `pytest` invocations. This is the recommended approach for local development to ensure parity with the GitHub Actions CI runners.

=== "Standard Suite"
    Executes the standard test matrix without coverage overhead.
    ```bash
    make test
    ```

=== "Coverage Run"
    Executes the suite and validates coverage thresholds (fail under 90%).
    ```bash
    make test-cov
    ```

=== "Detailed Coverage Report"
    Generates a line-by-line coverage report and outputs missing branches to the terminal.
    ```bash
    make test-cov-report
    ```

=== "Pre-Push CI Emulation"
    Runs the exact pipeline executed by GitHub Actions, sequentially triggering `install`, `lint`, `typecheck`, and `test-cov`. Run this before opening a pull request.
    ```bash
    make ci
    ```

!!! tip "Manual Execution"
    If you need to pass specific markers or flags directly to pytest (e.g., to run a single file or skip exhaustive tests), bypass the Makefile and use `uv` directly:
    ```bash
    uv run pytest tests/test_executor.py uv run pytest -m "not exhaustive"
    ```

### Pytest Configuration

The test runner utilizes the following base configuration injected dynamically from `pyproject.toml`:

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

---

## Performance & Latency Testing

Because Protostar is designed for high-velocity initialization, we enforce a strict performance budget to prevent Python's startup overhead from degrading the CLI experience.

To bypass the `questionary` interactive TUI blockage during benchmark or headless CI environments, we expose a hidden environment variable constraint (`PROTOSTAR_BENCHMARK_WIZARD=1`).

The `Makefile` includes predefined targets leveraging [hyperfine](https://github.com/sharkdp/hyperfine) to track regression thresholds. Ensure you test your changes against the fast-path (e.g., `protostar help`) to verify dynamic module imports haven't bloated the instantiation tree.

=== "Quick Benchmark"
    Runs a 5-iteration warmup and 30 statistical runs.

    ```bash
    make test-benchmark
    ```

=== "Rigorous Benchmark"
    Runs a 30-iteration warmup and 90 statistical runs, exporting results to `benchmark.json`.

    ```bash
    make test-benchmark-slower
    ```
