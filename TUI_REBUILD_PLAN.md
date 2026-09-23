# TUI Rebuild Plan

Replace questionary with a Textual TUI, redesigned rather than ported. Each PR is sized for one agent pass.

**How to use this file:** one PR per agent. Read `AGENTS.md` first, then only your PR's section. Stay inside its scope. Note anything out of scope in the PR description instead of doing it. When a PR merges, collapse its section to a short summary under "Finished".

## Status

| PR | Title | Status |
|---|---|---|
| 1 | `refactor(cli): move prompt code out of the engine` | Merged (#301) |
| 2 | `feat(security): secret guard for template variables` | Merged (#302) |
| 3 | `feat(recipe)!: persist template variables and drop --bind` | Merged (#303) |
| 4 | `refactor(cli): single init draft and resolver` | Merged (#304) |
| 5 | `feat(cli): Textual foundation and recipe editor` | Complete |
| 6 | `feat(cli): variables, metadata and live plan preview` | Complete |
| 7 | `feat(cli): change review screen` | Complete |
| 8 | `refactor(cli)!: remove questionary` | Planned |

## Settled Decisions

- **Textual decides, Rich reports.** A Textual app runs only while decisions are being made, and exits with an immutable result through `app.exit(result)`. `execute()` runs afterwards, under the existing Rich progress trail. No Textual app may be running while `execute()` runs:
  - `ProcessRunner` installs signal handlers (`system.py`), which Python allows only on the main thread.
  - Textual's raw mode turns Ctrl+C into a key event, which would break rollback on interrupt.
- **One draft, two front ends.** Flags and the TUI both fill in one `InitDraft`, and a single resolver turns it into modules plus an `InitRequest`. The TUI opens only for decisions the draft leaves open:
  - Bare `protostar init` opens the TUI at the start.
  - A flag-driven init with an unresolved collision or trust decision opens the TUI at the review screen.
  - Fully resolved flags never open it.
  - Every TUI decision keeps a flag or config equivalent, for agents and CI.
- **Two reusable screens.** The *recipe editor* answers "what should this project be?" The *change review* answers "what will change, and how do I decide each item?" Every later feature (conflict resolution, prune, adopt) combines these two.
- **Full-screen, not inline.** Textual's inline mode is not supported on Windows, and Windows is in CI. After the app exits, print a short Rich summary of the choices into scrollback.
- **A one-off yes/no uses `rich.prompt.Confirm`, not Textual** (e.g., `config --reset`).
- **Lazy by design.** Only `cli/tui/launch.py` imports Textual. `help`, `--json`, and non-TTY runs never load it, and engine modules never import it (enforced by `tests/test_headless_boundary.py`).

## Finished

- **PR 1 (#301).** Moved the questionary wrappers and the init wizard out of the engine into `cli/prompts.py` and `cli/wizard.py`. Added `tests/test_headless_boundary.py`, which fails if any module outside `protostar.cli` loads `rich`, `questionary`, `prompt_toolkit`, or `textual`.
- **PR 2 (#302).** Secret guard for template variables (`src/protostar/secret_guard.py`).
  - **Rules:** gitleaks rules at the tag pinned in `_fallbacks.py`, translated from Go to Python regex syntax by `scripts/sync_secret_rules.py` into `src/protostar/_secret_rules.py`. The module stores them compressed so no secret scanner flags it.
  - **Matching:** a rule runs only when one of its keywords appears, and each rule compiles on first use.
  - **Checks:** variable names that read as credentials, and values that match a rule. `SecretDetectedError` never echoes a value. There is no override.
  - **Also added:** `ProtostarError.details()` for error-specific JSON fields.
- **PR 3 (#303).** Template variables are non-secret and persist in `[tool.protostar.variables]`.
  - **Where values come from:** the recipe, then `--var NAME=VALUE`, then a prompt in an interactive terminal.
  - **API:** `TemplateSource.load()` / `.variables` / `.render()` replaced the prompt callback, so the engine never prompts.
  - **Errors:** `MissingTemplateVariablesError` lists every missing name (`missing_variables` in JSON).
  - **Removed:** `--bind`, bindings, and free-form trailing variable flags. argparse now parses strictly.

## PR 4: `refactor(cli): single init draft and resolver`

**Goal:** one input model and one resolver for both init paths, so the TUI (PR 5 onward) edits a draft instead of reimplementing init. Tool constraints and collisions become data a UI can render, instead of errors discovered after the fact. No Textual in this PR, and no behavior change for users beyond the removed duplication.

**Current state:**

- **Two parallel init paths.** `handle_init` in `cli/main.py` (flags) and `intercept_interactive_wizards` in `cli/parser.py` (wizard) each build the recipe, modules, and `InitRequest` their own way.
- **Tool constraints are checked in three places:**
  - `cli/main.py` (pre-commit/prek exclusivity, and Read the Docs requiring Zensical)
  - `Orchestrator.plan()` in `orchestrator.py` (the same two checks)
  - `cli/wizard.py` (a follow-up prompt when both hook managers are picked)
- **Collisions are exception-driven.** `plan()` raises `WorkspaceCollisionError` when `manifest.colliding_files()` is non-empty and neither `force_merge` nor `force_replace` is set. `cli/ui._run_engine` catches it, prompts, rebuilds the engine, and re-plans.

**Steps:**

1. **Constraints as data.** Next to `Tool` in `recipe.py`, declare the exclusive pairs (`PRE_COMMIT`/`PREK`) and requirements (`READTHEDOCS` needs `ZENSICAL`). Add one function, e.g. `validate_tools(enabled: set[Tool])`, raising `ConfigurationError` with the existing messages and hints. Call it from the orchestrator's pre-flight, and delete the copy in `handle_init`. Drive the wizard's follow-up prompt from the same table until PR 5 replaces it.
1. **`InitDraft`.** A frozen dataclass in a new engine module (e.g. `src/protostar/init_draft.py`). It holds:
    - The chosen template: a `TemplateSource` plus `is_external`, `is_user_aliased`, `is_trusted`, grouped in one small dataclass.
    - Tool overrides.
    - Docker and Python version.
    - Metadata.
    - Variable values.
    - `collision_strategy`.
    - The existing recipe, if any, for precedence.

    For tools, reuse `ProjectRecipe.selections()`: `ToolSelection` / `SelectionLayer` already say where each value came from. Don't invent a second provenance scheme for tools. Add a small `ValueSource` enum for metadata and variables only if PR 5/6 labels need it.
1. **One resolver.** A pure `resolve_init(draft, user_config) -> (modules, InitRequest)` in the same module, holding what `handle_init` and `intercept_interactive_wizards` each compute today: recipe establishment, fallbacks, frozen `CURRENT_YEAR` on re-init, tool opinions and overrides, metadata, and variables. Both entry points become "build a draft, then resolve it". Delete the duplicated recipe-building in `parser.py`.
1. **Collisions as data.**
    - Replace `InitRequest.force_merge` / `force_replace` with `collision_strategy: CollisionStrategy | None`. Remove `ABORT` from `CollisionStrategy`; aborting is a CLI outcome (`ExecutionAbortedError`), not an engine strategy.
    - `plan()` records collisions on the manifest instead of raising. One guard, right before execution, raises `WorkspaceCollisionError` when collisions exist and no strategy is set. Keep the error's message, `paths` in `details()`, and exit code, so `--json` behavior is unchanged.
    - `--force-merge` / `--force-replace` map to the strategy.
    - Simplify `_run_engine`'s collision loop: set the strategy on the request and re-plan. Don't rebuild the engine by hand.
1. Update `AGENTS.md`'s layout map with the new module.

**Tests:**

- `resolve_init` gives identical requests for equivalent flag and wizard drafts.
- The constraint table rejects each invalid combination, with a single check site.
- `plan()` with collisions and no strategy returns a manifest listing them.
- The execution guard raises `WorkspaceCollisionError` with the same JSON `paths`.
- Existing init, collision, and wizard tests pass with fixtures updated.

**Done when:**

- `rg "force_merge|force_replace" src` shows only the CLI flags feeding the strategy.
- Constraint checks exist in one place.
- `parser.py` no longer builds a recipe itself.

## PR 5: `feat(cli): Textual foundation and recipe editor`

**Status: complete.** Added the lazy Textual launcher and recipe editor, draft-based bare-init flow, value-source labels, constraint-driven tool controls, Docker, Pilot tests, an SVG snapshot, and lazy-import checks. Metadata and variables remain questionary prompts after the app exits; execution remains under the Rich progress trail. Demos were deliberately not regenerated.

**Goal:** add Textual and build the recipe editor (template and tools). Bare `protostar init` opens it.

**Steps:**

1. **Dependencies.** `uv add textual`; `uv add --dev pytest-asyncio pytest-textual-snapshot`. Never edit dependency lists by hand.
1. **Package.** `src/protostar/cli/tui/`:
    - `launch.py`: the only module the rest of `cli/` imports. It lazily imports Textual and exposes functions like `edit_recipe(draft, catalog) -> InitDraft | None` (None means cancelled, and the CLI raises `ExecutionAbortedError`).
    - `app.py`: base `App` (theme, key bindings, exit-with-result).
    - `protostar.tcss`.
    - `recipe/`: screens and widgets.

    Keep it flat; build no widget framework ahead of need.
1. **Recipe editor screen:**
    - **Template picker:** built-ins, global aliases, and "no template".
    - **Tool matrix:** grouped sensibly. Exclusive pairs render as a radio choice. A tool whose requirement is unmet is disabled, with the reason shown. Both come from PR 4's table.
    - **Value sources:** each tool shows where its value came from ("from template", "from config", "from recipe"), replacing the old "(Enforced by template)" suffix.
    - **Docker toggle.**
1. **Wiring.** `intercept_interactive_wizards` builds a draft from the config and any existing recipe, opens the editor, resolves the result, prints the scrollback summary, then runs execution under the progress trail. Delete the questionary template and tool prompts from `cli/wizard.py`; metadata and variable prompts stay questionary until PR 6.
1. **Benchmark.** Keep the `PROTOSTAR_BENCHMARK_WIZARD` hook working (exit before launching the app) until PR 8 redefines it.
1. **`AGENTS.md`.** Add the invariant "no Textual app runs while `execute()` runs", and the `cli/tui/` layout entry.

**Tests:**

- Pilot tests (`App.run_test()`):
  - picking a template
  - toggling a tool
  - choosing prek clears pre-commit
  - Read the Docs is disabled until Zensical is on
  - cancel returns None
- A `pytest-textual-snapshot` SVG of the editor.
- A subprocess test: `protostar help init` and a `--json` run never load `textual`.
- Existing wizard tests are rewritten against the new flow.

**Notes:**

- Textual draws the terminal directly, so the cp1252 concerns in `AGENTS.md` apply to the Rich summary printed after exit, not inside the app.
- Windows CI runs non-interactively, so the app never launches there.
- `just demo-wizard` drives questionary with raw keys (`scripts/record_demos.py`, `record_wizard`). It goes stale here and is re-recorded in PR 8.

## PR 6: `feat(cli): variables, metadata and live plan preview`

**Status: complete.** The recipe editor now holds template variables (checked by the secret guard on submit or blur, never per keystroke), metadata fields shown by the enabled tools and Docker, and a live preview pane that re-plans in an exclusive, debounced worker (a warm `plan()` measured 1–7 ms, so the debounce is 0.1 s). Template loads run in a worker with a loading line and inline errors. A flag-driven init missing variables in an interactive terminal opens `edit_variables`, the editor's variables step on its own. `cli/wizard.py` is deleted, and the app takes the screen to run (`DecisionApp`). The open question below was settled as names only.

**Goal:** finish the recipe editor. Template variables and project metadata get fields, and a preview of the planned file tree updates as choices change.

**Steps:**

1. **Variable fields** come from `TemplateSource.variables`.
    - Check each on submit with `secret_guard.check_variable_values`, and show the error on that field. Never check per keystroke.
    - A "Saved to pyproject.toml; don't enter secrets" note sits beside the fields.
    - Recorded values pre-fill the fields.
1. **Metadata fields** come from `METADATA_FIELDS` in `metadata.py`. `PromptType` maps to widgets: `TEXT` to `Input`, `SELECT` to `Select`, `CHECKBOX` to `SelectionList`. Defaults come from the auto-resolvers.
1. **Live preview.**
    - Re-run `plan()` in a Textual worker, debounced, with `exclusive=True` so stale runs are cancelled.
    - Show the planned tree (the same data as `ui.print_dry_run_summary`) and any collisions.
    - `plan()` is read-only, so running it off the main thread is safe. Never call `execute()` from the app. Measure `plan()` cost before tuning the debounce.
1. **Remote templates.** Picking a remote alias fetches it in a worker, with a loading state. Errors show inline.
1. **Flag path.** In an interactive terminal, `protostar init --template X` with missing variables opens the editor at the variables step, instead of `prompt_template_variables`. Off a terminal and under `--json`, it's unchanged: `MissingTemplateVariablesError`.
1. **Cleanup.** Delete `prompt_template_variables` and `prompt_metadata` (questionary) from `cli/wizard.py`.

**Tests (Pilot):**

- a credential-shaped value blocks continuing, and the error names the rule
- metadata defaults appear
- toggling a tool updates the preview (await the worker)
- a missing variable on the flag path lands on the variables step
- snapshots of the finished editor

**Open question (settled):** fields are labeled by variable name. Declaring variables with descriptions (e.g. a `[variables]` table) is deferred to a follow-up; see Open Questions.

## PR 7: `feat(cli): change review screen`

**Status: complete.** The recipe editor continues to a change review, and a flag-driven interactive init opens it (`launch.review_changes`) when a collision or trust decision is open.

- **What it shows:** the first file batch from `prepare_review(..., phase=BEFORE_INITIALIZERS)`. Each planned path is marked new, modified, conflict, existing, or after setup, with a unified diff for each first-batch edit, then the commands and packages that follow. A file written later names the command that creates it and shows no guessed content.
- **Decisions:** merge or overwrite re-prepares the batch. An untrusted template needs a checkbox confirming its exact commands.
- **Snapshot and result:** the review takes one registry snapshot in a worker. `InitDecision` (in `init_draft.py`) carries it, the draft, and the confirmed commands. `_run_engine` passes the snapshot through `Orchestrator.execute(hook_revisions=...)` to `SystemExecutor`, and runs an untrusted template only if its commands equal the confirmed ones.
- **Removed:** `_run_engine` no longer prompts; the questionary `select` and `confirm` calls are gone from `cli/ui.py`. Off a terminal and under `--json`, the errors are unchanged.
- **Unchanged:** later file batches are still not simulated, since they depend on command output. Demos were not regenerated.

**Goal:** before anything runs, show what will change, and collect the collision and trust decisions on one screen. This screen is the base that conflict resolution and prune reuse later.

**Steps:**

1. **Engine support.**
    - Compute the first file batch without executing: `prepare_review(manifest, config, hook_revisions=..., policy=ExecutionPolicy.INITIALIZATION, phase=PreparationPhase.BEFORE_INITIALIZERS)` in `preparation.py` is pure.
    - Hook revisions need a registry snapshot (`registry.resolve_hook_revisions()`, which uses the network). Take it once, in a worker, and pass the same snapshot to execution: today `SystemExecutor.__init__` resolves its own, so thread it through.
    - Files written after `git init`, `uv add`, or tasks can't be known in advance. List them with the step that produces them rather than guessing their content.
1. **Screen.** Render `PreparedReview` directly: file tree (create, modify, collides), unified diffs for the first batch (`cli/reviews.unified_diff`), dependencies, and tasks.
    - **Collision choice:** merge, overwrite, or abort, applied globally. Per-file choices belong to conflict resolution, not here.
    - **Trust gate:** an untrusted external template with tasks lists the exact commands and needs explicit confirmation, replacing the `confirm` in `cli/ui._run_engine`.
1. **Entry points.** The recipe editor continues to this screen. A flag-driven init in an interactive terminal opens it directly when the collision strategy or trust is unresolved. Off a terminal and under `--json`: unchanged errors.
1. **Cleanup.** Delete the questionary collision `select` and trust `confirm` from `cli/ui.py`.

**Tests:**

- the review shows the expected diffs for a collision fixture
- choosing merge versus overwrite changes the strategy passed to execution
- the trust gate blocks until confirmed
- preview and execution use the same hook snapshot
- snapshots

## PR 8: `refactor(cli)!: remove questionary`

**Goal:** questionary is gone, and the benchmarks, demos, and docs match the new TUI.

**Steps:**

1. **`config --reset`** uses `rich.prompt.Confirm`, and `--force` still skips it.
1. **Delete questionary:** `uv remove questionary`, delete `cli/prompts.py` and `tests/test_prompts.py`, and remove any remaining `questionary` patches in tests.
1. **Benchmark.** Redefine `PROTOSTAR_BENCHMARK_WIZARD` as time to first frame (the app exits right after its first refresh when set). Update the README's performance section, and `benchmark.yml` if names change.
1. **Demos.** Rewrite `record_wizard` in `scripts/record_demos.py` for the Textual key flow. Re-record with `just demo-wizard` (and `just demo-headless` if output changed). This takes minutes and does real installs. Don't `git add -A docs` while it runs.
1. **Docs assets.** Generate TUI screenshots with Textual's `export_screenshot()` (e.g. from `generate_docs_assets.py` via `App.run_test()`) into `docs/assets/terminals/`. Then run `just check-snapshots`.
1. **Docs text** that still mentions questionary or the old prompts:
    - `README.md` (performance and install notes)
    - `docs/getting-started.md`
    - `docs/developer/testing.md` (benchmark hook)
    - `docs/usage/init.md` ("Interactive Wizard & Metadata", including the old collision prompt)
    - `docs/usage/templates.md` and `docs/usage/troubleshooting.md` (the old `[y/N]` trust dialog, replaced by the change review's trust gate in PR 7)
    - `CONTRIBUTING.md`
    - `AGENTS.md`'s headless-core package list

**Done when:** `rg -i questionary` finds nothing outside the changelog or history, and demos and screenshots show the new TUI.

## After the TUI

Order: three-way merge, then conflict resolution, then prune, then adopt.

- **Three-way merge extension.** Engine-only. `merge.py` is already a three-way kernel for structured files (keep-local, apply-remote, or conflict, against the lock baseline). Define the gap first (e.g., plain-text files). Can start any time.
- **Interactive conflict resolution.**
  - Build it as a separate command, so `sync` stays prompt-free.
  - The change review screen gains a decision column per `MergeConflict`.
  - It needs an engine resolution model plus a non-interactive form (a flag or resolution file) for `--json` and agents.
- **Prune.** Find contributions orphaned by a disabled producer. The review screen gets a keep/remove decision per item, reusing conflict resolution's decision column. Transactional, like every other mutation.
- **Adopt.** Detection fills an `InitDraft` with values marked as detected, then the recipe editor, then the change review. It writes the recipe and lock baselines without overwriting existing files.

## Open Questions

- **Credentials inside URLs.** gitleaks has no general rule for `scheme://user:password@host`, and local-dev values like `postgres://postgres:postgres@localhost/app` are legitimate. Decide before adding a first-party rule.
- **Declared template variables with descriptions.** Deferred at PR 6, which labels fields by name. A later PR could add an optional `[variables]` table; the field widget takes a description without restructuring.
- **What the wizard benchmark measures** (PR 8; time to first frame is the likely answer).
