# Contributing To Protostar

## Architecture & Implementation Rules

Protostar has one job: save you time on setup you would have done anyway. When evaluating a new feature, ask:

- Would *most* users want this, or just some?
- Would you plausibly revert this manually after running the tool?

If the answer to either of the first two is "maybe not", the feature probably doesn't belong in the tool.

### 1. Manifest-first, side-effects-last & Transactional Execution

Modules declare intent into the manifest during `build()`. The orchestrator executes all side effects afterward in a single, ordered phase. Never call `subprocess.run` or write to disk inside a module's `build()` method.

The execution phase (`SystemExecutor`) operates under strict transactional guarantees:

- **Mutation Journaling:** Every transaction-managed file or directory is recorded by `MutationJournal` before Protostar mutates it.
- **Transaction-Aware Filesystem:** All direct filesystem writes, text appends, and directory creations route through `TransactionAwareFS`.
- **Bounded Subprocess Side Effects:** Subprocesses are managed by `ProcessRunner` in isolated process groups. External mutations that Protostar is expected to produce (such as `uv add` modifying `pyproject.toml` and `uv.lock`) are pre-journaled before invoking the tool.
- **Fatal Dependency Policy:** Package installation failures are fatal rather than soft diagnostics. A failed `uv add` triggers rollback of declared dependency files and workspace mutations.
- **Automated Rollback:** If an execution fails or is interrupted (`SIGINT`), Protostar terminates and reaps active subprocesses, shields against secondary signals, and rolls back journaled paths in reverse order to their original bytes and modes.

### 2. The Headless Core (CLI vs. Engine Separation)

Protostar's core engine (`Orchestrator`, `SystemExecutor`, `BootstrapModule`) is strictly headless and deterministic:

- **Decoupled Lifecycle (`plan` vs. `execute`):** The orchestrator separates state calculation (`plan() -> EnvironmentManifest`) from disk mutation (`execute(manifest) -> ExecutionResult`). `plan()` must remain mathematically pure and side-effect free—never mutating disk state or executing subprocesses.
- **Strict UI Separation:** Engine modules must **never** import or instantiate terminal UI libraries (`rich.console.Console`, `questionary`), invoke interactive prompts, or make terminal-interactive decisions. All interactive wizards, collision strategy prompts (`Merge`, `Overwrite`, `Abort`), remote template trust dialogs, and progress spinners belong exclusively in the CLI layer (`cli.py`).
- **Structured Boundary Communication:** The CLI passes caller intent into the engine via immutable `InitRequest` objects and receives execution outcomes via `ExecutionResult`. Collision states are signaled by raising `WorkspaceCollisionError(paths=...)`, allowing caller interfaces to decide how to handle conflicts (e.g., interactive prompt vs. CI failure).
- **Headless Logging:** Engine components emit progress updates via `logging.getLogger("protostar").info(...)`. The CLI layer captures these messages via custom handlers (such as `SpinnerHandler`) to render rich terminal spinners.

### 3. Fail loud, fail early

All system dependency checks happen in `pre_flight()`, before the manifest is built and before anything is written. If a preflight check fails, the environment is untouched. This is a guarantee, not a coincidence.

### 4. Non-destructive by default

Protostar never overwrites existing work. `.gitignore` entries are appended and deduplicated. IDE settings are merged. It must be safe to run against a repo that is already partially configured. In addition, the transactional execution engine guarantees that if an execution fails or is interrupted midway, all journaled workspace modifications (direct file writes, AST merges, and declared dependency files) are rolled back to their pre-run bytes and modes. Note that Protostar reliably reverts tracked changes, but does not promise reverting undeclared side effects produced by external commands (such as `.git/` created by `git init`).

### 5. Modules are composable, not coupled

A module only interacts with the manifest interface. It must not inspect what other modules are loaded, assume a particular run order, or conditionally change behaviour based on the presence of sibling modules.

### 6. Built-in templates state a delta, not a stack

A built-in template is a project *shape* (a CLI, a web service, an analysis workbench), never a particular stack of libraries. Stacks belong in a `--from` template or a global alias. Built-ins are trusted implicitly and maintained forever, so the bar is high: the default answer to a new-template proposal is "publish it as a `--from` template".

Modules and templates divide the work:

- **Modules ship a baseline tuned for casual projects.** A default must never make a small script painful, so `MypyModule` has no `strict` and `RuffModule` selects only a gentle rule set.
- **Templates state only the delta that defines their shape**, such as `strict = true` for the `cli` template. Use a tool's additive keys (`extend-select`) rather than redefining a list, because sequences merge atomically.
- **Tool configuration follows the tool.** A payload that configures a tool declares `requires = "<tool>"`, and dev packages only a tool needs (such as `pytest-cov`) go under `[dev.tool_dependencies]`, so `--no-<tool>` leaves none of it behind. Tool-agnostic payloads (such as `[build-system]`) stay plain strings.
- **Every built-in declares all eight quality flags explicitly** (`ruff`, `mypy`, `pytest`, `prek`, `ci`, `rumdl`, `direnv`, `just`) as `true` or `false`.
- **A fresh scaffold passes the gates its flags enable.** Do not enable `pytest` without shipping a test.

`tests/test_builtin_template_contract.py` and the exhaustive suite enforce this. The full contract, the two tiers, and how to add or retire a built-in are in `docs/developer/built-in-templates.md`.

### 7. Structural Error Handling Paradigm

To guarantee that the workspace remains deterministic, error management follows a strict type verification structure:

- **Never Raise Coarse Exceptions:** Do not raise bare `RuntimeError`, `ValueError`, or `OSError` instances inside pipeline operations. Always throw a specific, domain-modeled subclass of `ProtostarError` defined in `protostar.errors`:
  - `ConfigurationError`: For invalid/malformed configuration files or invalid CLI configuration options.
  - `NetworkFetchError`: For remote template downloads, network timeouts, or insecure protocol violations.
  - `TemplateResolutionError`: For template archive extraction failures, unsupported formats, or missing template variables.
  - `WorkspaceCollisionError`: For detected collisions with existing workspace configuration markers during `plan()`.
  - `MissingDependencyError`: For pre-flight binary checks when a required system tool is absent.
  - `AggregatedDependencyError`: For pre-flight checks when multiple required system tools are absent.
  - `CommandExecutionError`: For non-zero return codes from managed subprocesses.
  - `CommandTimeoutError`: For subprocesses exceeding allocated runtime limits.
  - `ProcessTerminationError`: For failures when stopping or reaping an active managed subprocess tree before rollback.
  - `FileSystemError`: For local disk I/O, file writing, or directory creation failures.
  - `UnsupportedFilesystemNodeError`: For transaction targets that are unsupported node types such as symbolic links or special files.
  - `TransactionStateError`: For invalid lifecycle transitions on a mutation journal (e.g. attempting writes after commit or rollback).
  - `SecurityViolationError`: For unauthorized path traversal attempts (e.g. Zip Slip).
  - `ExecutionAbortedError`: For explicit cancellations during interactive wizard prompts.
  - `ExecutionInterruptedError`: For interruptions occurring mid-execution when Protostar successfully rolls back tracked workspace changes (stores immutable `frozenset[str]` of touched paths; notes that external commands may have also modified files).
  - `RollbackFailedError`: For interrupted or failed executions where automated rollback was only partially successful (stores failed paths and chains the root exception).
- **Respect POSIX Exit Code Mappings:**

<!-- BEGIN_EXIT_CODES -->

| Exit Code | POSIX Name | Exception Class | Trigger Condition |
| :--- | :--- | :--- | :--- |
| `0` | `EX_OK` | *None* | Successful execution |
| `1` | Generic Exit | `CommandExecutionError`<br>`CommandTimeoutError` | Subprocess failure or command timeout |
| `64` | `os.EX_USAGE` | `InvalidUsageError` | Invalid CLI arguments or command usage syntax |
| `65` | `os.EX_DATAERR` | `TemplateResolutionError` | Template resolution error (corrupted archive, missing variables) |
| `69` | `os.EX_UNAVAILABLE` | `MissingDependencyError`<br>`AggregatedDependencyError` | Missing required system binary (`uv`, `git`, etc.) |
| `70` | `os.EX_SOFTWARE` | *(Unhandled exception)* | Unhandled internal Python bug (prompts automated bug report) |
| `74` | `os.EX_IOERR` | `FileSystemError` | Local filesystem read/write or permission failure |
| `75` | `os.EX_TEMPFAIL` | `NetworkFetchError` | Transient network failure during remote template download |
| `77` | `os.EX_NOPERM` | `SecurityViolationError` | Security violation (e.g., path traversal Zip Slip, or a template variable value that looks like a credential) |
| `78` | `os.EX_CONFIG` | `ConfigurationError` | Invalid TOML syntax or conflicting CLI configuration |
| `130` | Shell Signal | `ExecutionAbortedError`<br>`ExecutionInterruptedError` | You aborted interactive wizard prompt or interrupted execution (Ctrl+C) |

<!-- END_EXIT_CODES -->
- **Enforce Exception Chaining:** When catching lower-level subprocess or OS errors and raising domain exceptions, always preserve the original traceback using the `raise NewException(...) from e` syntax.
- **Isolate Actionable Hints:** Keep description fields focused on *what* broke. Place direct system installation fix guidelines or instructions inside the decoupled `hint` keyword configuration parameter so they can be parsed and formatted cleanly on their own visual tier in the terminal.

### 8. Machine & Agent Interface Invariants (`--json` & `--dry-run`)

Protostar exposes an experimental machine-readable CLI interface for AI agents, automation pipelines, and external developer tools. Any new subcommands, flags, or error paths must preserve the following operational invariants:

- **Strict `stdout` Purity:** `stdout` is strictly reserved for the machine-readable JSON payload. All human-readable logging, diagnostic summaries, progress spinners, and Rich tracebacks must route exclusively to `stderr` (e.g., via `_stderr_console` or logging handlers). An automated consumer must always be able to parse `stdout` directly as valid JSON.
- **Position-Independent Flag Evaluation:** The `--json` flag is position-independent and must be recognized globally across all commands, subparsers, and bare invocations.
- **Zero Interactive Trapping in Machine Mode:** When `is_json_mode` is active, the CLI must **never** block on terminal-interactive prompts (such as `questionary` wizards, collision resolution prompts, or external template trust dialogs). Instead, the CLI must either bypass the prompt deterministically (if explicit override flags like `--force-merge` are present) or raise a domain exception immediately so that a structured JSON error envelope is returned.
- **Deterministic State Serialization (`.to_dict()`):** All manifest domain slices and execution models exposed to agents must implement deterministic `.to_dict()` methods:
  - Mathematical sets (such as `directories`, `vcs_ignores`, `workspace_hides`) must serialize to alphabetically sorted lists.
  - `ExecutionResult` serializes `created_paths`, `mutated_paths`, and the derived union `touched_paths` to alphabetically sorted lists, alongside diagnostic events.
  - Insertion-ordered lists (such as `dependencies`, `dev_dependencies`, `system_tasks`) must preserve their exact declaration order.
  - Enums (such as `CollisionStrategy`) must serialize as their string `.value`.
  - File system paths must be normalized to POSIX string format.
- **Protocol Envelopes & API Versioning:** All JSON outputs must be wrapped in standard envelopes (`planned`, `success`, or `error`) and include the top-level `"api_version"` key (`CLI_API_VERSION = 0` during experimental phase) to maintain forward-compatible schema evolution.

## Coding Standards

1. **Type Hinting:** All new application functions and methods must include strict Python 3.12 type hints. We use `mypy` to statically enforce this (`strict = true`). The test suite (`tests/*`) is granted an exemption from strict untyped definition checks.

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

*(If you are on macOS with Homebrew: `brew install uv just`)*

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

    Set up [prek](https://github.com/j178/prek) hooks to handle linting and type checking automatically.

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

    Write your code. Ensure your changes are tightly scoped to a single feature, template, or bug fix. Avoid monolithic pull requests that mix refactoring with new logic. If you change a built-in template or a tooling module's defaults, read `docs/developer/built-in-templates.md` first, then regenerate snapshots with `just check-snapshots` and review every generated file.

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
