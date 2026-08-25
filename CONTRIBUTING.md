# Contributing To Protostar

## Architecture & Implementation Rules

Protostar has one job: save the user time on setup they would have done anyway. When evaluating a new feature, ask:

- Would *most* users want this, or just some?
- Would a user plausibly revert this manually after running the tool?

If the answer to either of the first two is "maybe not", the feature probably doesn't belong in the tool.

### 1. Manifest-first, side-effects-last

Modules declare intent into the manifest during `build()`. The orchestrator executes all side effects afterward in a single, ordered phase. Never call `subprocess.run` or write to disk inside a module's `build()` method.

### 2. The Engine Bulkhead (State vs. Execution)

Protostar's core engine (`Orchestrator`, `SystemExecutor`, `BootstrapModule`) is strictly headless and deterministic:

- **Decoupled Lifecycle (`plan` vs. `execute`):** The orchestrator separates state calculation (`plan() -> EnvironmentManifest`) from disk mutation (`execute(manifest) -> ExecutionResult`). `plan()` must remain mathematically pure and side-effect free—never mutating disk state or executing subprocesses.
- **Strict UI Separation:** Engine modules must **never** import or instantiate terminal UI libraries (`rich.console.Console`, `questionary`), invoke interactive prompts, or make terminal-interactive decisions. All interactive wizards, collision strategy prompts (`Merge`, `Overwrite`, `Abort`), remote template trust dialogs, and progress spinners belong exclusively in the CLI layer (`cli.py`).
- **Structured Boundary Communication:** The CLI passes caller intent into the engine via immutable `InitRequest` objects and receives execution outcomes via `ExecutionResult`. Collision states are signaled by raising `WorkspaceCollisionError(paths=...)`, allowing caller interfaces to decide how to handle conflicts (e.g., interactive prompt vs. CI failure).
- **Headless Logging:** Engine components emit progress updates via `logging.getLogger("protostar").info(...)`. The CLI layer captures these messages via custom handlers (such as `SpinnerHandler`) to render rich terminal spinners.

### 3. Fail loud, fail early

All system dependency checks happen in `pre_flight()`, before the manifest is built and before anything is written. If a preflight check fails, the environment is untouched. This is a guarantee, not a coincidence.

### 4. Non-destructive by default

Protostar never overwrites existing work. `.gitignore` entries are appended and deduplicated. IDE settings are merged. It must be safe to run against a repo that is already partially configured.

### 5. Modules are composable, not coupled

A module only interacts with the manifest interface. It must not inspect what other modules are loaded, assume a particular run order, or conditionally change behaviour based on the presence of sibling modules.

### 6. Presets are Independent Pipeline Injections

Presets inherit from the `PresetModule` abstract base class and evaluate independently during the manifest aggregation phase. They do not override language modules; they strictly append domain-specific dependencies and directory scaffolding to the `EnvironmentManifest`.

### 7. Structural Error Handling Paradigm

To guarantee that the workspace remains deterministic, error management follows a strict type verification structure:

- **Never Raise Coarse Exceptions:** Do not raise bare `RuntimeError`, `ValueError`, or `OSError` instances inside pipeline operations. Always throw a specific, domain-modeled subclass of `ProtostarError` defined in `protostar.errors`:
  - `ConfigurationError`: For invalid/malformed configuration files or invalid CLI configuration options.
  - `NetworkFetchError`: For remote template downloads, network timeouts, or insecure protocol violations.
  - `TemplateResolutionError`: For template archive extraction failures, unsupported formats, or missing template variables.
  - `WorkspaceCollisionError`: For detected collisions with existing workspace configuration markers during `plan()`.
  - `MissingDependencyError`: For pre-flight binary checks when required system tools are absent.
  - `CommandExecutionError`: For non-zero return codes from managed subprocesses.
  - `CommandTimeoutError`: For subprocesses exceeding allocated runtime limits.
  - `FileSystemError`: For local disk I/O, file writing, or directory creation failures.
  - `SecurityViolationError`: For unauthorized path traversal attempts (e.g. Zip Slip).
  - `ExecutionAbortedError`: For explicit cancellations during interactive wizard prompts.
  - `PartialExecutionAbortedError`: For interruptions occurring mid-execution after disk mutations have begun (stores immutable `frozenset[str]` of touched paths).
- **Respect POSIX Exit Code Mappings:** The top-level CLI main routine automatically routes domain exceptions to standardized POSIX return codes (`os.EX_CONFIG` / 78, `os.EX_TEMPFAIL` / 75, `os.EX_DATAERR` / 65, `os.EX_UNAVAILABLE` / 69, `os.EX_IOERR` / 74, `os.EX_NOPERM` / 77). Ensure your exception selection aligns with the expected POSIX category.
- **Enforce Cause Chains:** When wrapping secondary background subprocess tracking or physical system calls, always retain stack telemetry history using the `raise NewException(...) from e` syntax.
- **Isolate Actionable Hints:** Keep description fields focused on *what* broke. Place direct user-facing system installation fix guidelines or instructions inside the decoupled `hint` keyword configuration parameter so they can be parsed and formatted cleanly on their own visual tier in the terminal.

### 8. Machine & Agent Interface Invariants (`--json` & `--dry-run`)

Protostar exposes an experimental machine-readable CLI interface for AI agents, automation pipelines, and external developer tools. Any new subcommands, flags, or error paths must preserve the following operational invariants:

- **Strict `stdout` Purity:** `stdout` is strictly reserved for the machine-readable JSON payload. All human-readable logging, diagnostic summaries, progress spinners, and Rich tracebacks must route exclusively to `stderr` (e.g., via `_stderr_console` or logging handlers). An automated consumer must always be able to parse `stdout` directly as valid JSON.
- **Position-Independent Flag Evaluation:** The `--json` flag is position-independent and must be recognized globally across all commands, subparsers, and bare invocations.
- **Zero Interactive Trapping in Machine Mode:** When `is_json_mode` is active, the CLI must **never** block on terminal-interactive prompts (such as `questionary` wizards, collision resolution prompts, or external template trust dialogs). Instead, the CLI must either bypass the prompt deterministically (if explicit override flags like `--force-merge` are present) or raise a domain exception immediately so that a structured JSON error envelope is returned.
- **Deterministic State Serialization (`.to_dict()`):** All manifest domain slices and execution models exposed to agents must implement deterministic `.to_dict()` methods:
  - Mathematical sets (such as `directories`, `vcs_ignores`, `workspace_hides`) must serialize to alphabetically sorted lists.
  - Insertion-ordered lists (such as `dependencies`, `dev_dependencies`, `system_tasks`) must preserve their exact declaration order.
  - Enums (such as `CollisionStrategy`) must serialize as their string `.value`.
  - File system paths must be normalized to POSIX string format.
- **Protocol Envelopes & API Versioning:** All JSON outputs must be wrapped in standard envelopes (`planned`, `success`, or `error`) and include the top-level `"api_version"` key (`CLI_API_VERSION = 0` during experimental phase) to maintain forward-compatible schema evolution.

## Coding Standards

1. **Type Hinting:** All new application functions and methods must include strict Python 3.12 type hints. We use `mypy` to statically enforce this (`disallow_untyped_defs = true`). The test suite (`tests/*`) is granted an exemption from strict untyped definition checks.

1. **Docstrings:** Use Google-style docstrings for public functions, classes, and methods. Module-level, package-level, and `__init__` docstrings are exempt from linting checks.

1. **Formatting & Linting:** Code is formatted and linted using `ruff`.
    - Use 4-space indentation and double quotes.
    - The formatter enforces an 88-character line length.
    - Do not bypass the prek hooks, as they will automatically apply the required `isort` block ordering and formatting rules.

## Testing Guidelines

Because Protostar is a scaffolding tool, its execution inherently interacts with the host filesystem and shell. To maintain a deterministic and isolated test suite:

1. **Relaxed Linting:** The test suite (`tests/*`) is exempt from docstring requirements and `print` statement linting restrictions (`T201`).

1. **Disk I/O:** Never write to the actual host filesystem during tests. Always use the `pytest` `tmp_path` fixture to sandbox generated artifacts.

1. **Subprocesses:** Use `pytest-mock` to patch `subprocess.run`. Do not allow the test suite to execute unmocked shell commands (e.g., `uv init` or `cargo init`) on the host machine.

1. **Coverage:** Ensure new modules or generators maintain or improve the current test coverage metrics (measured via `pytest-cov`).

## How to Contribute

### Reporting Bugs

1. Check if the issue has already been reported.
1. Open a new issue with a clear title and description.
1. Include the command that caused the error and the resulting traceback.

### Development Setup

To contribute to this project, you will need the following system-level dependencies installed:

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)**: For dependency and environment management.
- **[just](https://just.systems/man/en/packages.html)**: Our command runner.

*(For macOS users with homebrew: `brew install uv just`)*

1. **Fork & Clone**

    Fork the repo and clone it locally:

    ```bash
    git clone https://github.com/JacksonFergusonDev/protostar.git
    cd protostar
    ```

1. **Environment Setup**

    ```bash
    uv sync
    ```

1. **Install Hooks**

    Set up prek hooks to handle linting and type checking automatically.

    ```bash
    uv run prek install
    ```

### Running Tests & Tooling

We use `just` as our command runner to standardize test execution, linting, and formatting.

To see all available commands and their descriptions, run `just` in the repository root:

```bash
just
```

To execute the standard test matrix:

```bash
just test
```

### Isolated Manual Testing (Sandboxes)

To manually test Protostar in an isolated workspace without modifying your global `~/.config/protostar` or host git configuration:

- **macOS Sandbox:** Drops into an ephemeral sub-shell in `/tmp` where `protostar` is built fresh from the working tree and `$HOME` is sandboxed:

    ```bash
    just sandbox
    # Or run single commands headlessly:
    just sandbox init --template cli
    ```

- **Linux Sandbox (OrbStack / Docker):** Runs inside a clean, disposable Debian container pre-loaded with required system binaries (`direnv,` `markdownlint-cli2`) and inspection tools (`eza`, `bat`, `ripgrep`):

    ```bash
    just sandbox-linux
    # Or run single commands headlessly:
    just sandbox-linux init --template astro
    ```

### Pull Requests

1. **Create a Branch**

    ```bash
    git checkout -b feature/my-amazing-feature
    ```

1. **Make Changes**

    Write your code. Ensure your changes are tightly scoped to a single feature, preset, or bug fix. Avoid monolithic pull requests that mix refactoring with new logic.

1. **Verify**

    Ensure your code passes the linter, type checker, and test suite locally. We provide a single command that emulates the GitHub Actions CI pipeline. Run this before pushing:

    ```bash
    just ci
    ```

    (Prek will also run `ruff` and `mypy` when you commit).

1. **Commit & Push**

    Use clear, descriptive commit messages.

    ```bash
    git commit -m "feat: added something cool"
    git push origin feature/my-amazing-feature
    ```

1. **Open a Pull Request**

    Submit your PR against the `main` branch.
