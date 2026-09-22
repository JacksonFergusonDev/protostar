# Protostar Agent Guidelines

Guidelines and architectural invariants for AI agents working in the Protostar codebase.

## Development Phase & Backwards Compatibility (Pre-1.0)

- **Zero External Users:** Protostar is in active pre-1.0 development with no external users or production stability commitments.
- **Do NOT preserve backwards compatibility:** Do not create deprecation warnings, alias wrappers, fallback shims, or legacy compatibility layers.
- **Break and delete cleanly:** If an internal or public API, CLI flag, schema, or configuration model needs improvement, change or break it directly. Delete obsolete code and dead parameters outright rather than carrying tech debt.
- **Prioritize ergonomics:** Clean, simple, and idiomatic architecture always takes precedence over historical continuity.

## Core Architectural Invariants

### 1. Manifest-First, Side-Effects-Last & Transactional Execution

Execution is strictly split into two decoupled phases:

1. **`plan() -> EnvironmentManifest`:** Pure, read-only phase. Modules declare files, dependencies, system tasks, and TOML injections into the manifest. **No disk writes and no subprocess execution are permitted here.**
1. **`execute(manifest) -> ExecutionResult`:** The only phase where physical mutations and subprocesses occur via `SystemExecutor`.

**Pipeline Transactionality & Rollback Invariants:**

- **Pre-Mutation Journaling:** Every transaction-managed path is journaled before Protostar first mutates it, and rollback restores that path to its supported pre-transaction state.
- **Transaction-Aware Filesystem:** All direct file and directory mutations in the execution phase must route through `TransactionAwareFS` (`src/protostar/fs_transaction.py`) backed by `MutationJournal` (`src/protostar/journal.py`).
- **Bounded Subprocess Side Effects:** Subprocess side effects are bounded and explicitly declared before execution. Dependency installation pre-journals workspace `pyproject.toml` and `uv.lock` before invoking package managers.
- **Fatal Dependency Policy:** Dependency installation failures are fatal (raising `CommandExecutionError` or `CommandTimeoutError` directly rather than soft diagnostics) to trigger automated rollback of declared dependency files and workspace changes.
- **Process Ownership:** Subprocesses are managed via `ProcessRunner` (`src/protostar/system.py`) in isolated process groups. On error or interrupt (`SIGINT`), active managed subprocesses are terminated and reaped before rollback begins.
- **Bytes-Over-Intent Rollback:** Rollback restores exact original bytes and POSIX file modes captured before first mutation. Created directories are removed only if empty. Symlinks and special filesystem nodes are rejected before transaction-managed mutation (`UnsupportedFilesystemNodeError`).
- **Rollback Boundary:** Rollback reliably covers paths written directly through Protostar's transaction-aware filesystem layer. Subprocess side effects are strictly disclaimed unless explicitly pre-declared by a module (e.g., `git init` declaring the `.git/` tree, or `pre-commit` declaring specific hook files). Unbounded or externally managed state (like `.venv/` or global caches) falls outside the transacted boundary.

### 2. The Headless Core

- The core engine (`Orchestrator`, `SystemExecutor`, `BootstrapModule`, etc.) is **strictly headless**.
- **Never** import or call UI/terminal interaction packages (`rich.console`, `questionary`, progress spinners) inside engine modules. `tests/test_headless_boundary.py` enforces this: importing any module outside `protostar.cli` must not load `rich`, `questionary`, `prompt_toolkit`, or `textual`.
- Terminal prompts, wizards, interactive conflict resolvers (`Merge`, `Overwrite`, `Abort`), and the progress trail belong exclusively to the CLI layer (`src/protostar/cli/`).
- Engine code communicates via immutable request/result models and raises domain exceptions.
- **The engine never prompts or calls back into the CLI for input.** Missing input is a domain error carrying structured data (e.g., `MissingTemplateVariablesError.variables`), and the CLI decides whether to ask. Split an operation so the CLI can learn what's needed first, as `TemplateSource.load()` / `.variables` / `.render()` do.
- **Progress crosses the boundary only through `ProgressStep`** (`src/protostar/progress.py`). Wrap each new subprocess or slow operation in `with self.progress("<present-progressive label>"):`. Never use logging as a UI channel.
- **Only a fatal failure (one that triggers rollback) may raise through a step.** Report non-fatal outcomes as diagnostics. A presenter must never raise on its own: the engine can't tell that apart from a failed step and will roll the work back.
- Test steps with the `progress` fixture in `tests/conftest.py`, which records each step's start and outcome.

### 3. Agent & Machine Mode Invariants (`--json`)

- **`stdout` Purity:** When `--json` is active, `stdout` is reserved exclusively for the JSON payload. All Rich formatting, diagnostics, and human-facing logs must be directed to `stderr`. Machine mode passes no progress hook, so execution emits no progress output at all.
- **Zero Blocking Prompts:** Machine mode must never hang on terminal prompts. Unresolved collisions or missing confirmations must raise domain exceptions immediately so a structured error JSON envelope can be returned.
- **Deterministic Serialization:** Models implementing `.to_dict()` must sort mathematical sets alphabetically and normalize file paths to POSIX strings. `ExecutionResult` exposes `created_paths`, `mutated_paths`, and derived `touched_paths` (all serialized as sorted lists).

### 4. Non-Destructive Modifications & AST Merging

- Never overwrite user files blindly.
- Use `tomlkit` to manipulate and merge `pyproject.toml` files to preserve comments, indentation, and formatting. Do not use string templating or regex for structured TOML files.
- Deduplicate and append to `.gitignore` files rather than replacing them.
- **Format engines know no file by name.** `toml_ast`, `yaml_ast`, and `jsonc_ast` reconcile whatever spec they are handed. A file's target path, merge spec, and policy (guards, layout, pin handling) live in its module under `src/protostar/documents/` and are looked up through that package's registries; never branch on a file name inside an engine or hardcode a managed target path elsewhere.

### 5. Domain-Specific Error Handling

- Never throw generic `RuntimeError`, `ValueError`, or `Exception` in pipeline operations.
- Subclass or raise domain exceptions defined in `src/protostar/errors.py` (`ConfigurationError`, `WorkspaceCollisionError`, `MissingDependencyError`, etc.).
- Always preserve exception chains (`raise NewError(...) from e`).
- Supply clear, user-actionable instructions using the `hint` parameter rather than embedding instructions in the primary error message string.

### 6. Built-in Templates: Baseline in Modules, Delta in Templates

Full contract: `docs/developer/built-in-templates.md`. Invariants when touching `src/protostar/templates/*.toml` or tooling module defaults:

- **Modules carry a casual-user baseline; templates carry only the delta.** Never move strict settings (`strict = true`, docstring rules) into a module. Templates must not repeat a module's baseline values.
- **Use additive keys.** Sequences merge atomically, so redefine no baseline list (`select`) where an additive key (`extend-select`) exists. A list with no additive key, such as Ruff's `ignore`, may be redefined only as a strict superset.
- **Tool-bound payloads declare `requires`.** A `[dev.pyproject]` payload that configures a tool is a table `{ requires = "<tool>", content = "..." }` so it is injected only while that tool is enabled. Tool-agnostic payloads stay plain strings. Dev packages only a tool needs go under `[dev.tool_dependencies]` keyed by that tool.
- **Declare all eight quality flags explicitly** (`ruff`, `mypy`, `pytest`, `prek`, `ci`, `rumdl`, `direnv`, `just`) in every built-in.
- **A fresh scaffold must pass the gates its flags enable.** Do not enable `pytest` in a template that ships no test. Product templates (`cli`, `api`) are installable packages (`hatchling`, never `uv_build`).
- **No version pins, no `system_tasks`, and `post_install_tasks` only from the allowlist** in `tests/test_builtin_template_contract.py`. Built-ins are trusted implicitly.
- **Payload comments go outside the payload string.** Comments inside a `[dev.pyproject]` string are copied into every user's `pyproject.toml`.
- **A built-in is a project shape, not a stack.** Do not add a built-in for a stack; the answer is a `--from` template.
- **Regenerate and review snapshots** (`just check-snapshots`) for any template or module-default change.

### 7. CLI Output

- **Text from templates, users, or the filesystem is data.** Render it as `rich.text.Text` or with `rich.markup.escape()`. Never interpolate it into markup.
- **Decorative symbols go through `ui.glyph(symbol, ascii_fallback)`** (`src/protostar/cli/ui.py`). Windows encodes redirected stdout as cp1252. `main()` calls `ui.replace_unencodable_output()`, so characters it can't encode print as `?` instead of crashing, but a bare `✓` would then read as `?`.
- **Test new output against a strict cp1252 stream** (see `tests/test_legacy_encoding.py`). macOS and Linux runs never hit this; only the Windows CI smoke jobs do.

### 8. Template Variables Are Not Secrets

- **Custom template variables are non-secret by definition.** Their values persist in `[tool.protostar.variables]` and render into committed files. `check_variable_names` runs when `TemplateSource.variables` is first read; `check_variable_values` runs in `TemplateSource.render` before anything renders, and in `decode_recipe` for every recorded value. There is exactly one way to supply a value: the recipe, `--var`, or a CLI prompt, never an environment indirection.
- **The guard has no override.** Never add a flag, marker, or allowlist entry that lets a flagged value through, and never echo a checked value in an error, log, or JSON payload; report the variable name and rule id only.
- **The guard ports gitleaks, it doesn't extend it.** Don't add entropy-only or generic heuristics: every block must be near-certain because nothing can bypass it.
- **`src/protostar/_secret_rules.py` is generated.** `scripts/sync_secret_rules.py` builds it from the gitleaks tag pinned in `_fallbacks.py`. Never hand-edit it; run `just sync-secret-rules` whenever that tag changes, and `--dump` to read the rules. Ruff is excluded from it because `--check` compares its text.
- **The rules are stored compressed, never as text.** Their patterns and allowlists quote token prefixes and publicly known keys that every secret scanner (gitleaks, GitHub, scanners of installed wheels) would report. Don't store them readably, and don't add per-scanner ignore files instead.

## Pre-Commit & Pre-Push Hooks (Avoid Redundant Checks)

The repository uses **`prek`** hooks (`.pre-commit-config.yaml`) for automated gating:

- **On `git commit` (pre-commit):** Automatically runs `uv lock --check`, `ruff check --fix`, `ruff format`, `mypy`, `rumdl check/fmt`, `actionlint`, and `renovate schema check`.
- **On `git push` (pre-push):** Automatically runs `pytest`, `zensical build --strict`, `check-doc-links`, `check-schemas`, and `check-snapshots`.

> **Agent Rule:** **Do NOT redundantly run `ruff`, `mypy`, `rumdl`, `just lint`, or `just ci` immediately before committing or pushing.** Let the hooks do the work. If a hook fails or formats a file, inspect the failure, adjust the code, and re-stage. Only run manual commands during active development/debugging (e.g. running a specific test file like `uv run pytest tests/test_foo.py`).

## Development & Inspection Commands

Use these commands when targeted verification or debugging is necessary:

- **Targeted Testing:**

  ```bash
  uv run pytest tests/path/to/test.py  # Run a specific test during active development
  just test-cov                        # Verify coverage thresholds (must stay >= 85%)
  ```

- **Dependency Management:**

  ```bash
  uv add <package>                     # Add a runtime dependency (never edit pyproject.toml manually)
  uv add --dev <package>               # Add a development dependency
  ```

- **Isolated Manual Testing:**

  ```bash
  just sandbox                        # Ephemeral macOS sandbox with sandboxed $HOME
  just sandbox-linux                  # Clean Debian container
  ```

- **Fixture & Documentation Integrity:**

  ```bash
  just check-snapshots                # Regenerate and check snapshot drift in tests/snapshots/ and docs/
  just check-doc-links                # Validate embedded documentation URLs in error hints
  just check-schemas                  # Validate pre-commit, action, renovate, and metaschemas
  just demo-headless                  # Re-record the headless demo cast and GIF
  just demo-wizard                    # Re-record the wizard demo cast and GIF
  just sync-secret-rules              # Regenerate _secret_rules.py after the pinned gitleaks tag changes
  ```

  `check-snapshots` regenerates the terminal SVGs but not the demo casts and GIFs, which go stale silently. Re-record both demos whenever CLI output changes. They do real installs and take several minutes. Don't `git add -A docs` while a recording runs: it leaves `.demo_*.tmp.cast` files there.

- **Full CI Emulation (Debugging only):**

  ```bash
  just ci                             # Run only if debugging CI discrepancies
  ```

## Code & Testing Conventions

1. **Strict Type Safety & Domain Modeling:**
   - Python 3.12+ type hints are enforced across `src/` (`mypy --strict`).
   - **No Stringly-Typed APIs:** Use `enum.StrEnum` or `enum.Enum` for discrete choices, modes, strategies, or status values (e.g., `CollisionStrategy`). Avoid magic strings.
   - **No Data Clumps / Primitive Obsession:** Group related parameters into `@dataclass(frozen=True)` or `TypedDict` models instead of passing loose tuples, untyped dictionaries (`dict[str, Any]`), or 4+ primitive arguments.
   - **Lean Modeling (Avoid Over-Engineering):** Strong typing means precise data structures, *not* elaborate architecture. Avoid speculative generic abstractions, factory classes, or deep inheritance trees. Prefer flat dataclasses, enums, and pure functions.
1. **Google-Style Docstrings:** Required on all public functions, classes, and methods.
1. **Filesystem Isolation in Tests:**
   - **Never** write to the host filesystem during tests. Always inject the `pytest` `tmp_path` fixture.
   - **Never** run live shell commands or package managers (`uv`, `git`, `cargo`) on the host system during tests. Patch `subprocess.run` with `pytest-mock`.
1. **Dependency Management:**
   - **Do NOT manually edit dependencies in `pyproject.toml`:** Always use `uv add <package>` (or `uv add --dev <package>`) to add, update, or remove workspace dependencies so that `uv.lock` remains synchronized.
1. **Markdown Standards (`rumdl`):**
   - ATX headings only (`# Heading`, never underlined).
   - Dash markers (`-`) for unordered lists.
   - `1.` numbering for all ordered list items.

## Pull Request & Architecture Documentation

PR descriptions are the primary historical record of the project's evolution. **Do not merely summarize the `git diff` or list *what* code changed.** You must tell the full story of the PR's planning, decision-making, and architectural impact.

- **Conventional Commit Titles:** Use standard Conventional Commits format for PR titles (e.g., `feat(cli): ...`, `refactor(manifest): ...`).
- **Tell the Story (The "Why" and "How"):** Instead of describing file modifications, explain the original problem, the planning process, and the journey to the final solution.
- **Decision Rationale:** Detail the reasoning behind major technical choices. Explain what alternatives were considered and rejected, and why the final path was chosen.
- **Defend Architectural Boundaries (When Applicable):** When a PR establishes, modifies, or reinforces an architectural boundary, contract, or invariant, it must be explicitly documented. **Do not invent trivial boundaries for minor changes just to check a box.** If no architectural changes occurred, do not mention them.
- **Calibrated Verbosity:** Scale your explanation to the scope of the PR. Minor cleanups should be extremely brief; major architectural shifts require highly verbose, comprehensive narratives.

### Expected PR Structure

Scale or omit these sections based on the scope of the PR.

1. **Summary & Motivation:** A concise summary of the goal and the core problem being solved.
1. **Planning & Key Decisions:** The narrative of the design process. What did we discuss? Why did we build it this way? *(Keep very brief for simple PRs).*
1. **Architectural Invariants (Conditional):** Explicitly define any new boundaries, assumptions, or structural rules established by this PR. **Omit this section entirely if not applicable.**

## Repository Layout Map

- `src/protostar/cli/`: CLI entry points, argument parsers, wizards, and TUI formatting.
- `src/protostar/orchestrator.py`: Coordinates the 2-phase lifecycle (`plan()` and `execute()`).
- `src/protostar/init_draft.py`: Shared init draft and resolver for flags and interactive choices.
- `src/protostar/manifest.py`: `EnvironmentManifest` definition and aggregation state.
- `src/protostar/executor.py`: `SystemExecutor` coordinating transactional side-effects and rollback.
- `src/protostar/progress.py`: `ProgressStep` hook through which the engine names execution steps for the CLI to render.
- `src/protostar/journal.py`: `MutationJournal` tracking filesystem state for rollback.
- `src/protostar/fs_transaction.py`: `TransactionAwareFS` ensuring transactional disk operations.
- `src/protostar/system.py`: `ProcessRunner` managing subprocess lifecycles and process-tree termination.
- `src/protostar/merge.py`: Format-neutral three-way reconciliation kernel shared by every structured format.
- `src/protostar/toml_ast.py`: `tomlkit` aggregation and `TomlDocumentSpec`-driven reconciliation.
- `src/protostar/yaml_ast.py`: Bounded `ruamel.yaml` round-trip codec and `YamlDocumentSpec`-driven reconciliation.
- `src/protostar/jsonc_ast.py`: Stdlib-only lossless JSONC codec, byte-splice editor, and reconciliation adapter.
- `src/protostar/documents/`: One module per managed file (`pyproject`, `pre_commit`, `github_workflows`, `codecov`, `renovate`, `vscode`, `zensical`) owning its target, merge spec, and guards, plus the path registries.
- `tests/snapshots/`: Scenario regression snapshots validated during CI.
- `docs/generated/`: Generated capability tables, schemas, diffs, and trees snippeted into docs.
- `docs/assets/terminals/`: Rendered CLI terminal help SVGs displayed in docs.
- `scripts/`: Snapshot regression runner, doc assets generator, and verification scripts.
