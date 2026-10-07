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
- **Only Protostar's Own Executables Block:** Only `system_deps.REQUIRED` (`uv`, `git`) may fail a run, through `check_required_executables()`, which `plan()` calls for init and sync. A tool's module declares the binaries it runs in `executables`; planning records each one `PATH` lacks in `manifest.missing_tools` (carried by the review and `ExecutionResult`), and the module skips only the steps that run it, with a diagnostic. Look binaries up only through `system_deps.find_executable` (`shutil.which` starts no process, so `plan()` may); never in a module. On Windows a bare lookup searches the working directory first, where a template's `git.bat` would win, so never call `shutil.which` directly or hand the OS an unresolved command name. Tests control the lookup through the `missing_executables` fixture.
- **Process Ownership:** Subprocesses are managed via `ProcessRunner` (`src/protostar/system.py`) in isolated process groups. On error or interrupt (`SIGINT`), active managed subprocesses are terminated and reaped before rollback begins, including the editor probe's, which has a runner of its own because a runner owns one process at a time. Their environment comes from `subprocess_environment()`, which drops the active Python environment and git's repository-local variables (`GIT_DIR` and the rest of `git rev-parse --local-env-vars`), so a declared tree like `.git/` is always the project's own.
- **Bytes-Over-Intent Rollback:** Rollback restores exact original bytes and POSIX file modes captured before first mutation. Created directories are removed only if empty. Symlinks and special filesystem nodes are rejected before transaction-managed mutation (`UnsupportedFilesystemNodeError`).
- **Preview Trees Show Every File a Run Leaves:** `EnvironmentManifest.planned_files()` feeds the dry-run tree, the recipe editor's preview, the change review, and the dry-run JSON `entries`. It adds command outputs (a task's `owned_files`, outside `.git/`), the resolver footprint, and `protostar.lock` to the files Protostar writes. Declare every file a command creates in its task's `owned_files`: `check-snapshots` fails when a scaffold's tree differs from its dry-run plan.
- **Installed Git Hooks Are Clone-Local:** `.git/hooks` is not project state. `init` installs hooks as a post-install task; `sync` converges them through `git_hooks.plan_hooks()` (install when a wanted hook is missing, remove only runner-generated hooks that can now only fail) and never counts them as pending, so `sync --check` passes in a fresh checkout. A failed install on `sync` is a diagnostic, not a rollback.
- **Every Fault Rolls Back:** `tests/test_rollback.py` fails `init` and `sync` before, mid-way through, and after every write, directory, removal, and command, with an error and an interrupt, and requires the project and home directory to come back byte for byte. The commit is a site: an interrupt after it keeps the run and claims no rollback. A restore that fails is named in `RollbackFailedError` while every other path still comes back. Its cases come from the site lists in `tests/rollback_sites/`: a change that adds or moves a site fails until they are regenerated with `--snapshot-update`, so review sees it, and a write made around `TransactionAwareFS` fails the clean-run check. Only `sync`'s hook install may fail without a rollback. Pull requests run two scenarios; nightly runs every template and seed. Each fault test carries the `rollback_fault` marker, and nightly's `--rollback-report` counts them for the metrics dashboard and badge: a count is published only when every job reported, and a failure shows in the badge's text, never its color.
- **Every Command's Cost Is Budgeted:** `tests/test_cost_budgets.py` runs each scenario in `scripts/benchmarks/scenarios.py` in a fresh interpreter, with commands faked as the rollback suite fakes them, and counts what it costs: the commands and other processes it runs, hook registry fetches, YAML, TOML, and JSONC parses, the third-party packages it imports, and its exit code. The counts must equal `tests/cost_budgets/<scenario>.txt`; a change in cost fails until they are regenerated with `--snapshot-update`, and the pull request says why it changed. Count costs, never time them: a duration varies by machine, so no test asserts one. A new kind of cost is wrapped in `scripts/benchmarks/probes.py`, with its seam listed in `SEAMS` so a refactor that moves it fails instead of counting nothing.
- **Rollback Boundary:** Rollback reliably covers paths written directly through Protostar's transaction-aware filesystem layer. Subprocess side effects are strictly disclaimed unless explicitly pre-declared by a module (e.g., `git init` declaring the `.git/` tree, or `pre-commit` declaring specific hook files). Unbounded or externally managed state (like `.venv/` or global caches) falls outside the transacted boundary.

### 2. The Headless Core

- The core engine (`Orchestrator`, `SystemExecutor`, `BootstrapModule`, etc.) is **strictly headless**.
- **Never** import or call UI/terminal interaction packages (`rich.console`, `textual`, progress spinners) inside engine modules. `tests/test_headless_boundary.py` enforces this: importing any module outside `protostar.cli` must not load `rich` or `textual`.
- Terminal prompts, recipe editing, interactive conflict resolvers (`Merge`, `Overwrite`, `Abort`), and the progress trail belong exclusively to the CLI layer (`src/protostar/cli/`).
- Engine code communicates via immutable request/result models and raises domain exceptions.
- **The engine never prompts or calls back into the CLI for input.** Missing input is a domain error carrying structured data (e.g., `MissingTemplateVariablesError.variables`), and the CLI decides whether to ask. Split an operation so the CLI can learn what's needed first, as `TemplateSource.load()` / `.variables` / `.render()` do.
- **No Textual app runs while `execute()` runs.** The app exits with an immutable decision result first; execution then runs on the main thread under the Rich progress trail so signal handling and rollback remain intact. The app may call the read-only `plan()` and `prepare_review()` from a worker thread (the live preview and change review do); it never calls `execute()`.
- **Init's previews show one model.** The recipe preview, the change review, and `init --dry-run` (text and JSON) all display the `Review` in `cli/changes.py`. The editor's preview prepares it, and Continue hands it and its hook snapshot to the review. Only the review settles its decisions; the editor and the dry-run never offer a choice about a file. A registry snapshot is taken only for a draft that wants hooks, since only hook pins read it.
- **Conflict choices precede `sync`'s apply.** The conflict screen exits with resolutions keyed by conflict id; `sync` then prepares the review again with them (`PreparedProject.resolve`) and applies that review under the progress trail.
- **A screen opens only for a decision it can settle.** What can be known without the user fails before any screen opens: `plan()` rejects a template the project's state doesn't record, and the CLI checks that before asking for variables. A review that never prepares leaves through `DecisionApp.fail`, and the CLI reports the error with its hint. It never shows as an empty screen.
- **Decisions precede `_run_engine`.** Flags and configuration, or the change review's `InitDecision`, settle collisions, trust, and every conflict and proposal it showed before `cli/ui._run_engine` runs. The review prepares at `review_phase()`: both batches before the resolver when no initializer creates their inputs. Execution passes its choices to both batches and raises `StaleReviewError` unless every choice settled something. It never prompts, only guards. Execution reuses the review's registry snapshot (`Orchestrator.execute(hook_revisions=...)`), and a trust confirmation covers exactly the commands the review listed.
- **An untrusted template runs no command unconfirmed, on `init` or `sync`.** Its files decide what Protostar's own commands do (`uv add` builds the project through its build hooks), so every command counts. Trust comes only from a built-in origin or a `trusted = true` alias naming the same template (`RecipeSource.trusted_by`), never from the recipe or lock. `init` lists `untrusted_commands()`; `sync` confirms `PreparedReview.commands` (resolver, then hook install) on `TrustScreen` after its conflicts are settled. `--trust` allows them for one run and lists them; without it, a headless run raises `SecurityViolationError` before writing anything. `status`, `diff`, `--dry-run`, and `--check` never run a command, so they never ask.
- **Progress crosses the boundary only through `ProgressStep`** (`src/protostar/progress.py`). Wrap each new subprocess or slow operation in `with self.progress("<present-progressive label>"):`. Never use logging as a UI channel.
- **Background work only reads, and nothing outlives the run.** Two things run off the main thread, both daemons, both read-only. `registry.py` starts the hook-registry fetch as a command begins (`prefetch_hook_registry`), so the request overlaps planning; one request serves the run, a caller that arrives during it waits for that result, and an error it raises reaches the first caller that waits. `ide.py` starts the editor's extension listing as `init` executes (`start_ide_probe`), so it overlaps the installs; the executor collects it where it used to run and cancels it before rollback begins. Each touches no project file and no shared state but its own result, and reports through the main thread. Start no other thread to read, write, or run a subprocess without the same properties, and a thread that runs a subprocess gets a `ProcessRunner` of its own that the executor can terminate. Execution itself stays on the main thread.
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
- **A resolution always owns the update.** Settling a conflict records the desired content as the new baseline; the `ResolutionChoice` only picks which bytes stay (`LOCAL`, `DESIRED`, or `BOTH` for text hunks). Resolutions are keyed by the content-addressed `MergeConflict.id`, never by position, and a text file's hunks apply together or not at all. A conflict with no `sides` is settled by hand.
- **Every decision is a `MergeConflict`, in one of three channels.** A review's `conflicts` stay open (local kept, update pending); its `proposals` (`ConflictReason.PROPOSED`) are changes into content Protostar never owned and apply unless kept out; its `preserved` (`ConflictReason.PRESERVED`) are local edits under an unchanged update and stay unless their update is taken. `default_choice()` says which. All share the id scheme, `--resolve`, and `check_resolutions`; a file selector never names a preserved edit.
- **A proposal is an apply into never-owned content.** A file proposes (`MergePolicy.proposing`) while it existed before the run and neither the candidate nor the committed state owns any of it; requirements propose while the committed state owns none of the project's. Keeping a proposal out owns the update without writing it, so it becomes a preserved deletion that sync can restore. Equal foreign content stays unowned.
- **The engine that keeps a local edit reports it.** The kernel (`unchanged()`), `reconcile_text`, `append_marker_blocks`, `select_dependencies`, and the seed writer report each preserved deviation where they keep it, and restore it when its resolution takes the update. A deletion is reported once where the value is gone; an edit leaf by leaf; foreign members of a set are no edit. Never recompute deviations in a separate walk: ids must come from the decision itself.
- **Format engines know no file by name.** `toml_ast`, `yaml_ast`, and `jsonc_ast` reconcile whatever spec they are handed. A file's target path, merge spec, and policy (guards, layout, pin handling) live in its module under `src/protostar/documents/` and are looked up through that package's registries; never branch on a file name inside an engine or hardcode a managed target path elsewhere.
- **Producers render their own content; reconciliation renders only paths.** Whoever writes content knows its syntax, so a module fills in built-in values while planning (`manifest.rendering_context()`) and escapes a value only where it sits inside a quoted string (`interpolation.quoted` or `escaped`). Free text, such as Markdown or a license, gets the value as given. The orchestrator does the same for built-ins a template left unrendered. Never escape by file type or render content inside an engine.
- **Tool signals live on their modules.** Each tooling module declares `signals` (`PathSignal`, `TableSignal`, `SectionSignal`, `RequirementSignal` in `modules/base.py`) showing that an existing project already uses its tool; document modules build theirs from their `documents/` locations. `analysis.py` reads only what modules declare and knows no tool by name.
- **Tool descriptions live on their modules.** Each tooling module's `info` (`ToolInfo` in `modules/base.py`) is the one source for its flag's `--help`, the template schema, and the editor's tooltip and `i` popup. `ToolModule.info` is abstract, so mypy rejects a tool that has none. Write copy for someone who has never heard of the tool, and state consequences, not categories. Never describe a tool anywhere else. `scripts/check_doc_links.py` checks every `docs_url`.
- **Analysis reads, never selects.** `analyze_project()` runs only when no recipe exists, writes nothing, runs no subprocess, and reports an unreadable file as a note instead of raising. Its facts fill recipe values the draft leaves unset, everywhere. Its tools are only offered by the recipe editor, which adds them and never removes a template opinion or configured default (a found hook runner replacing the configured one is the exception); headless runs never select a tool because it was found.

### 5. Domain-Specific Error Handling

- Never throw generic `RuntimeError`, `ValueError`, or `Exception` in pipeline operations.
- Subclass or raise domain exceptions defined in `src/protostar/errors.py` (`ConfigurationError`, `WorkspaceCollisionError`, `MissingDependencyError`, etc.).
- Always preserve exception chains (`raise NewError(...) from e`).
- Supply clear, user-actionable instructions using the `hint` parameter rather than embedding instructions in the primary error message string.

### 6. Built-in Templates: Baseline in Modules, Delta in Templates

Full contract: `docs/developer/built-in-templates.md`. Invariants when touching `src/protostar/templates/*.toml` or tooling module defaults:

- **Modules carry a casual-user baseline; templates carry only the delta.** Never move strict settings (`strict = true`, docstring rules) into a module. Templates must not repeat a module's baseline values.
- **Use additive keys.** Sequences merge atomically, so redefine no baseline list (`select`) where an additive key (`extend-select`) exists. A list with no additive key, such as Ruff's `ignore`, may be redefined only as a strict superset.
- **Tool-bound payloads declare `requires`.** A `[dev.pyproject]` payload that configures a tool is a table `{ requires = "<tool>", content = "..." }` so it is injected only while that tool is enabled. Tool-agnostic payloads stay plain strings. Dev packages only a tool needs go in an `[[optional]]` block with `requires = "<tool>"`.
- **Declare every quality flag explicitly** (`ruff`, `mypy`, `pytest`, `prek`, `ci`, `rumdl`, `direnv`, `just`) in every built-in.
- **A fresh scaffold must pass the gates its flags enable.** Do not enable `pytest` in a template that ships no test. Product templates (`cli`, `api`) are installable packages (`hatchling`, never `uv_build`).
- **No version pins, no `system_tasks`, and `post_install_tasks` only from the allowlist** in `tests/test_builtin_template_contract.py`. Built-ins are trusted implicitly.
- **Payload comments go outside the payload string.** Comments inside a `[dev.pyproject]` string are copied into every user's `pyproject.toml`.
- **A built-in is a project shape, not a stack.** Do not add a built-in for a stack; the answer is a `--from` template.
- **Regenerate and review snapshots** (`just check-snapshots`) for any template or module-default change.

### 7. CLI Output

- **Text from templates, users, or the filesystem is data.** Render it as `rich.text.Text` or with `rich.markup.escape()`. Never interpolate it into markup.
- **Decorative symbols go through `ui.glyph(symbol, ascii_fallback)`** (`src/protostar/cli/ui.py`). Windows encodes redirected stdout as cp1252. `main()` calls `ui.replace_unencodable_output()`, so characters it can't encode print as `?` instead of crashing, but a bare `✓` would then read as `?`.
- **Test new output against a strict cp1252 stream** (see `tests/test_legacy_encoding.py`). macOS and Linux runs never hit this; only the Windows CI smoke jobs do.
- **Decisions read in plain words.** Reason codes (`diverged`, `retracted`, …) and bare choice names (`local`, `desired`) are for JSON only. Every screen that shows a conflict, proposal, or kept edit takes its sentence from `cli/decisions.py`, says what happens by default, and prints the full `--resolve` command for each choice. Don't show engine vocabulary (ownership, provenance, resolver footprint) in human output.

### 8. Template Variables Are Not Secrets

- **Custom template variables are non-secret by definition.** Their values persist in `[tool.protostar.variables]` and render into committed files. There is exactly one way to supply a value: the recipe, `--var`, or the TUI, never an environment indirection.
- **The secret guard is a safety net, not load-bearing.** `credential_named` only warns (in the TUI beside the field, and on the terminal). `check_variable_values` runs in `resolve_init`, before anything renders, on values that differ from the recorded ones. Recorded values are never re-checked, so neither `decode_recipe` nor `sync` can be blocked by the guard.
- **A bypass is explicit and per variable.** The only way past a flagged value is `InitDraft.allowed_secrets`, filled by `--allow-secret NAME` or the TUI's per-field confirmation, which resets when the value changes. Never add a global switch, an in-value marker (`gitleaks:allow` stays ignored), or a persisted allowlist. Never echo a checked value in an error, log, or JSON payload; report the variable name and rule id only.
- **The guard ports gitleaks, it doesn't extend it.** Don't add entropy-only or generic heuristics: every flag interrupts the user, so it must be near-certain.
- **`src/protostar/_secret_rules.py` is generated.** `scripts/sync_secret_rules.py` builds it from the gitleaks tag pinned in `_fallbacks.py`. Never hand-edit it; run `just sync-secret-rules` whenever that tag changes, and `--dump` to read the rules. Ruff is excluded from it because `--check` compares its text.
- **The rules are stored compressed, never as text.** Their patterns and allowlists quote token prefixes and publicly known keys that every secret scanner (gitleaks, GitHub, scanners of installed wheels) would report. Don't store them readably, and don't add per-scanner ignore files instead.

### 9. Keyboard-First TUI

- **The keyboard is the primary path through every screen; the mouse is secondary.** Build screens on `KeyboardScreen` and the widgets in `src/protostar/cli/tui/keys.py` (`Form`, `ChoiceGroup`, `ActionBar`, `Toggle`, `Field`, `Picker`, `Choice`, `Checklist`), not on bare Textual widgets.
- **Moving never changes a value.** `↑`/`↓` move between rows, and a list hands off to the next row at its edges instead of wrapping. Only `Space` and `Enter` change values. `Tab` moves between controls, and a `ChoiceGroup` counts as one.
- **Every action has a key, shown on its own control** through `key_label`. The footer is the legend for moving. List each new key in the screen's `KEYS` or `key_rows()` so `?` shows it.
- **Explanations are on demand.** A tool control binds `i` to `ToolInfoScreen` (`cli/tui/tool_info.py`) only while focused, so a text field never loses the letter. Build tool rows from `ToolToggle`, `ToolRadio`, and `ToolChoice`, and add `TOOL_INFO_KEY` to the screen's `KEYS`.
- **`Esc` asks before leaving (`LeaveScreen`); `Ctrl+C` quits at once and never asks.**
- **Spacing belongs to the layout.** Place a screen's panels, sections, and action bar in `Columns` and `Column` (`cli/tui/chrome.py`), and never give them margins of their own: blocks stand one cell apart across and one row apart down, and a panel under a panel shares its rule. Every TUI snapshot also measures its screen against this (`check_layout` in `tests/conftest.py`), so give each new screen a snapshot.
- **Decisions read as a checklist.** Every screen that settles decisions lists them with `DecisionList` (`cli/tui/conflicts/decision_list.py`): files with conflicts first, each row led by what happens to it, and a row never moves once shown. Settling a conflict moves on to the next open one; `n` jumps there.
- **A screen's first frame is complete.** Render everything the CLI already knows before the first paint: pass it into the screen and fill it in `compose()` or a synchronous `on_mount()`, and decide whether a conditional panel shows while composing it, not after mounting. Planning is pure and needs no network, so a screen may plan once before its first paint (the recipe editor's existing-files panel does). A worker is only for what can't be known yet, such as a re-review after a choice or the registry snapshot. Snapshots wait for workers, so each screen also tests its first frame unsettled (`test_the_first_frame_is_complete_without_reviewing_again`, `test_the_existing_files_panel_is_in_place_on_the_first_frame`).
- **A list that scrolls keeps the wheel.** An open `Picker` or a `Checklist` taller than its space stops the wheel at its ends instead of scrolling the form behind it (`HoldsWheel` in `keys.py`).
- **All TUI source uses `cli/tui/code.py`.** Render code, structured configuration, and source diffs through its shared renderers and palette. Pass the actual display language when serialization differs from the filename. Language selection is presentation-only; screens never choose their own syntax themes. Keep the Pygments adapter lazy so opening the recipe editor loads no lexers.
- **Color comes from the theme.** `cli/tui/theme.py` is the TUI's one source of color: the stylesheet names its variables, and TUI code styles text with its constants (`TEXT_FAINT`, `ACCENT`, `KEY`, …), never an ANSI name (Textual Content reads `cyan` as the CSS color), a `$variable`, or `dim`. The printed renderers the TUI also shows keep their ANSI names and `dim`; `PaletteColors` lands both on the palette. `tests/test_tui_theme.py` enforces this.
- **Drive TUI tests with `pilot.press`.** Use `pilot.click` only in tests that are about the mouse.

### 10. Documentation

The docs site (`docs/`, built by Zensical) shares its look and its rules with jacksonferguson.me and the other project sites through [house-style](https://github.com/JacksonFergusonDev/house-style). Its `GUIDELINES.md`, vendored at `docs/house/GUIDELINES.txt` for the pinned tag, is the source of truth for design and documentation rules. Read it before changing any page, and change a rule there rather than here.

#### Writing Pages

- **Every page has a one-sentence `description`** in its front matter.
- **Only top-level pages carry a navigation icon.** A page listed directly in the `zensical.toml` nav sets `icon:`; a page inside a section sets none, and no two pages share one.
- **Cards at the top of a page are optional.** Add them only when they genuinely help the reader choose where to go or see the page's main points. When they're used, use two, four, or six, and each card must earn its place: drop to the lower count rather than pad.
- **Show terminal output, don't paste it.** Use a recording or a generated screenshot in the house terminal window; keep code blocks for what the reader types.
- **Every standalone link carries a house-style icon** saying where it goes: `arrow-down` within the page, `arrow-right` to a related page, `arrow-up-right` to another site, and brand icons for GitHub and jacksonferguson.me. Draw icons only with house-style's `.hs-icon` classes or its `icons/` files, never a text arrow.

`check_docs_drift.py` enforces the description, navigation-icon, and card-count rules.

#### The Site's Machinery

- **`docs/house/` is vendored, never edited.** It is a tagged house-style release: palette, fonts, icons, components, scripts, and guidelines. Change a shared style there and tag a release. Then bump `HOUSE_STYLE_TAG` in `scripts/sync_house_style.py` and run `just sync-house-style`. CI fails when the copy differs from the tag. Never load house-style from another origin at runtime.
- **The docs restyle house-style; they don't redefine it.** `stylesheets/extra.css` hands the house tokens to Zensical's theme. `stylesheets/home.css`, loaded only by `overrides/home.html`, lays out the landing page with house components. A style every project site would want belongs in house-style, not here.
- **Terminal visuals are one window.** Recordings use house-style's `.hs-terminal` markup and `docs/javascripts/casts.js`, which loads the player only when a recording nears the viewport. Generated SVGs draw the same window in `scripts/generate_docs_assets/svg.py`, and `test_render_and_write_svg_draws_the_house_terminal_window` checks its colors against the vendored `terminal.css`.
- **Every page carries the share card.** `overrides/main.html` gives each page Open Graph and Twitter tags pointing at `docs/assets/og-card.png`, and the landing page's title and JSON-LD live in `overrides/home.html`. The card draws the name and tagline from `zensical.toml`; re-render it with `just og-card` when they or the mark change.
- **The bare URLs are the docs' one address.** `scripts/prepare_pages.py` serves the latest release at `/usage/init/` and points every versioned copy's canonical link, `og:url`, and structured data there, marking pages the latest release dropped `noindex`. Link to bare URLs, never to `/<version>/` or `/latest/`.
- **Script-added files go in `<body>`.** Instant navigation drops any `<head>` element the next page doesn't declare, so a stylesheet or script added at runtime to `<head>` vanishes on the next page. This once broke every recording.
- **The landing page's first screen is text.** No image, recording, or player loads before the reader scrolls toward it. The hero's Dadras attractor (`docs/javascripts/field.js`, three.js from jsDelivr) loads only after the page has. It follows house-style's motion rules: faint, paused off screen, still for reduced motion, and with a pause control.

## Flaky-Test Issues & Verification

- **A fix awaits verification; it does not close the issue.** After a flaky-test fix lands on `main`, agents must add the `awaiting-verification` label to the test's GitHub issue and leave it open. Link the fix commit or PR and identify the exact test ids and affected platforms so later nightly runs can verify the right behavior. Local passes and a merged PR alone do not establish that the flakiness is resolved.
- **Track verification per test.** Use the reporter-created issue for each flaky test. The nightly reporter splits existing aggregate issues into individual issues, links the replacements, and retains the aggregate as closed history. Follow those links to mark the fixed tests; do not mark an aggregate as awaiting verification while some tests still need fixes, or create duplicate issues without a managed tracking block.
- **Require three consecutive clean nightly runs after the fix.** Count a run only when the fixed test actually ran and passed on every affected platform without a retry. Skipped tests, narrowed runs that omit an affected platform, and missing results provide no verification. Keep the issue open with `awaiting-verification` until all three qualifying runs pass; retain the issue and comments as history when it closes.
- **A recurrence needs attention.** If the test fails or flakes during verification, reset its clean-run count, remove `awaiting-verification`, and return it to work needing a fix. If it recurs after closure, reopen its issue. The nightly reporter handles verification counts, closure, and reopening from explicit per-test results. Agents must mark the issue after the fix lands, link the fix, and leave the managed tracking block intact; never assume that an absent flaky-test report means the test ran cleanly.

## Pre-Commit & Pre-Push Hooks (Avoid Redundant Checks)

The repository uses **`prek`** hooks (`.pre-commit-config.yaml`) for automated gating:

- **On `git commit` (pre-commit):** Automatically runs `uv lock --check`, `ruff check --fix`, `ruff format`, `mypy`, `rumdl check --fix`, `actionlint`, `renovate schema check`, and `gitleaks`.
- **On `git push` (pre-push):** Automatically runs `pytest`, `zensical build --strict`, `check-doc-links`, `check-docs-drift`, `check-schemas`, and `check-snapshots`.

> **Agent Rule:** **Do NOT redundantly run `ruff`, `mypy`, `rumdl`, `just lint`, or `just ci` immediately before committing or pushing.** Let the hooks do the work. If a hook fails or formats a file, inspect the failure, adjust the code, and re-stage. Only run manual commands during active development/debugging (e.g. running a specific test file like `uv run pytest tests/test_foo.py`).
>
> **Agent Rule:** **Do NOT regenerate demos (`just demo-init-headless`, `just demo-init-interactive`, `just demo-sync`, `just demo-all`) unless explicitly prompted to do so.** Re-recording demos runs multi-trial live installations and takes several minutes; agents must never run demo generation autonomously.

## CI Runner Budget

- **Workflows triggered by a pull request or a push to `main` stay within 20 runners, at most 5 of them macOS**, so every job in a run starts at once. Count matrix expansions and jobs from reusable workflows. `ci.yml` is already at the limit, so a new check on those triggers rides inside an existing job (usually the pytest suite) rather than adding a runner.
- **Scheduled workflows (`nightly.yml`, `mutation.yml`) have no runner limit.** They run overnight, when nothing waits on them, so give them as many runners, macOS included, as the work needs. Exhaustive or slow checks belong there, with a quick representative subset in the pull request suite.

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
  just docs                           # Build documentation site in strict mode (zensical build --strict)
  just secrets                        # Scan repository for hardcoded secrets with Gitleaks
  just check-snapshots                # Regenerate and check snapshot drift in tests/snapshots/ and docs/
  just check-doc-links                # Validate embedded documentation URLs in error hints
  just check-docs-drift               # Fail when hand-written docs disagree with the code (errors, exit codes, templates, paths, commands, sample output)
  just check-schemas                  # Validate pre-commit, action, renovate, and metaschemas
  just demo-init-headless           # Re-record the headless init demo cast and GIF (explicit prompt only)
  just demo-init-interactive        # Re-record the interactive init demo cast and GIF (explicit prompt only)
  just demo-sync                    # Re-record the sync conflict demo cast and GIF (explicit prompt only)
  just sync-secret-rules              # Regenerate _secret_rules.py after the pinned gitleaks tag changes
  just sync-house-style               # Vendor the house-style tag pinned in scripts/sync_house_style.py into docs/house/
  ```

  `check-snapshots` regenerates the terminal SVGs but not the demo casts and GIFs. **Do NOT regenerate demos (`just demo-init-headless`, `just demo-init-interactive`, `just demo-sync`, `just demo-all`) unless explicitly prompted to.** They perform real installs across multiple trials and take several minutes. When explicitly requested to record demos, don't `git add -A docs` while a recording runs: it leaves `.demo_*.tmp.cast` files there.

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
   - Ordinary tests write only under `pytest`'s `tmp_path` and mock external commands at the boundary they exercise (`ProcessRunner`, `subprocess.run`, or `subprocess.Popen`).
   - Tests explicitly marked `integration` may run real commands to verify the CLI and its tool integrations. Keep these few and focused on behavior mocks cannot establish. Isolate their workspace, home directory, and user configuration under `tmp_path`; never let them operate on the caller's repository. These tests may access the network when installing dependencies. The `real_tool_env` fixture deliberately shares uv's host cache to avoid repeated downloads; that cache is the only intentional test-owned write outside `tmp_path`.
   - Keep the full suite, including integration tests, in pre-push and CI checks. Run it locally with `just test` or `uv run pytest -n auto --dist worksteal`. The `integration` mark classifies real-process tests; excluding those few tests is not a useful speed shortcut. During development, run the relevant test module or cases. If a partial run excludes snapshot tests and reports unused snapshots, `--snapshot-warn-unused` downgrades that report to a warning; do not use it for the full suite.
1. **Cross-Platform Test Invariants (Windows Compatibility):**
   - **No Hardcoded POSIX File Mode Assertions:** Windows NTFS and Python's Windows runtime do not support POSIX permission bits (`0o755`, `0o640`, `0o600`). Calling `os.chmod()` on Windows only toggles the read-only attribute (`0o444` vs `0o666`), and writable files always report mode `0o666` (`438`). Never assert specific octal permission values without guarding behind `if sys.platform != "win32":`, or assert relative mode invariance (`stat().st_mode == before`) instead of hardcoded octals. Tests mutating file modes must `pytest.skip(...)` on `sys.platform == "win32"`.
   - **Path Representations:** Always use `pathlib.Path` objects or `.as_posix()` when asserting paths. Never compare raw string paths with `/` against `str(path)`.
   - **Mandatory Windows File Locking:** Windows prohibits deleting, renaming, or unlinking open files. Always ensure file handles are closed (via context managers) before asserting rollbacks, ejections, or deletions; unclosed handles cause `PermissionError` during cleanup or transaction replay.
   - **Invalid Filename Characters:** Do not use `<`, `>`, `:`, `"`, `|`, `?`, or `*` in test fixture file names.
1. **Dependency Management:**
   - **Do NOT manually edit dependencies in `pyproject.toml`:** Always use `uv add <package>` (or `uv add --dev <package>`) to add, update, or remove workspace dependencies so that `uv.lock` remains synchronized.
1. **Markdown Standards (`rumdl`):**
   - **Never hard-wrap Markdown prose.** Write each paragraph and each list item's prose on one physical line, regardless of length; use editor soft wrapping for readability. Preserve structural newlines in code blocks, tables, HTML, front matter, directives, and nested lists, and keep intentional Markdown hard line breaks only where the rendered content requires them. This applies to all Markdown files, including documentation, agent instructions, templates, and generated Markdown.
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

- `src/protostar/cli/tui/`: Decision-only Textual app (recipe editor, change review, sync conflict resolution, and the configuration form), accessed by the CLI exclusively through the lazy `launch.py` entry point.
- `src/protostar/cli/`: CLI entry points, argument parsers, interactive screens, and TUI formatting.
- `src/protostar/cli/decisions.py`: How a decision reads in plain words: one sentence per conflict reason, the TUI's short tags, and the lines `status`, `diff`, `sync`, and `init --dry-run` print with the command for each choice.
- `src/protostar/cli/changes.py`: What init changes: the `Review` model (plan, prepare, classify each path) and its Rich renderers, shared by the recipe preview, the change review, and `init --dry-run`. `sync`, `status`, and `diff` draw their pending paths with the same `classify` and `entry_tree`.
- `src/protostar/orchestrator.py`: Coordinates the 2-phase lifecycle (`plan()` and `execute()`).
- `src/protostar/config_edit.py`: The configuration form's save: applies its values to the file's text through `tomlkit`, writing only keys whose value changed. Pure; the CLI writes the result after the form exits, and never touches Git's configuration.
- `src/protostar/init_draft.py`: Shared init draft and resolver for flags and interactive choices.
- `src/protostar/guide.py`: `protostar guide`'s content: a fourth renderer of the `GuideSpec` AGENTS.md and CONTRIBUTING.md render from. Its commands come only from that spec and recorded project facts (`[project.scripts]`, `missing_tools`); it plans the recorded recipe as `sync` does, runs nothing, and never recomputes a command.
- `src/protostar/analysis.py`: Read-only analysis of a project with no recipe yet: the tools it uses (from module signals) and the facts that pre-fill its first recipe.
- `src/protostar/manifest.py`: `EnvironmentManifest` definition and aggregation state.
- `src/protostar/executor.py`: `SystemExecutor` coordinating transactional side-effects and rollback.
- `src/protostar/progress.py`: `ProgressStep` hook through which the engine names execution steps for the CLI to render.
- `src/protostar/journal.py`: `MutationJournal` tracking filesystem state for rollback.
- `src/protostar/fs_transaction.py`: `TransactionAwareFS` ensuring transactional disk operations.
- `src/protostar/system.py`: `ProcessRunner` managing subprocess lifecycles and process-tree termination.
- `src/protostar/git_hooks.py`: The hook install task, and the read-only plan by which `sync` installs missing hooks and removes generated hooks that can only fail.
- `src/protostar/system_deps.py`: The executables Protostar and its tools run, the required-executable check, and the pure install-command builder.
- `src/protostar/merge.py`: Format-neutral three-way reconciliation kernel shared by every structured format.
- `src/protostar/text_merge.py`: Pure line-based three-way text merge (diff3 over patience diff) for free-form managed files.
- `src/protostar/toml_ast.py`: `tomlkit` aggregation and `TomlDocumentSpec`-driven reconciliation.
- `src/protostar/yaml_ast.py`: Bounded `ruamel.yaml` round-trip codec and `YamlDocumentSpec`-driven reconciliation.
- `src/protostar/jsonc_ast.py`: Stdlib-only lossless JSONC codec, byte-splice editor, and reconciliation adapter.
- `src/protostar/documents/`: One module per managed file (`pyproject`, `pre_commit`, `github_workflows`, `codecov`, `renovate`, `vscode`, `zensical`, and the `community` health files) owning its target, merge spec, and guards, plus the path registries.
- `src/protostar/community/`: Generators for the community health files that depend only on metadata, and the bundled Contributor Covenant.
- `tests/snapshots/`: Scenario regression snapshots validated during CI.
- `tests/rollback_sites/`: The sites each rollback scenario passes, from which `tests/test_rollback.py` generates its fault cases.
- `tests/cost_budgets/`: What each scenario in `scripts/benchmarks/scenarios.py` costs, which `tests/test_cost_budgets.py` checks.
- `scripts/benchmarks/`: The scenarios whose cost is budgeted and benchmarked, and the probes that count what a command does.
- `docs/generated/`: Generated capability tables, schemas, diffs, and trees snippeted into docs.
- `docs/assets/terminals/`: Rendered CLI terminal help SVGs displayed in docs.
- `docs/house/`: The vendored house-style release (tokens, fonts, components, scripts) the docs share with jacksonferguson.me.
- `overrides/`: Zensical theme overrides; `home.html` loads the landing page's own stylesheets.
- `scripts/`: Snapshot regression runner, doc assets generator, and verification scripts.
