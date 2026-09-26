# Approachable Onboarding Plan

Make Protostar usable by people new to Python tooling without adding a single keystroke or line of noise for experienced users. Help is always on demand, never in the way.

**How to use this file:** one PR per agent. Read `AGENTS.md` first, then only your PR's section. Stay inside its scope. Note anything out of scope in the PR description instead of doing it. When a PR merges, collapse its section to a short summary under "Finished".

## Status

| PR | Title | Stack | Status |
|---|---|---|---|
| 1 | `feat(engine)!: missing tools are data, not a fatal pre-flight` | A (base) | Next |
| 2 | `feat(cli): report missing tools before the editor, in review, and after success` | A, on 1 | Planned |
| 3 | `feat(cli): protostar guide and a success line that says what to do next` | A, on 2 | Planned |
| 4 | `feat(tui): tool information on demand` | B (base) | Next |
| 5 | `feat(cli): interactive global configuration editor` | B, on 4 | Planned |
| 6 | `feat(templates): group templates by purpose` | Standalone | Next |
| 7 | `docs: first-project walkthrough and installation paths` | After all | Planned |

## Stacks

Stacks A and B and PR 6 are independent of each other and can run in parallel. Within a stack, each PR branches from the previous one and is retargeted to `main` when its base merges.

- **Stack A (missing tools, then guidance): 1 → 2 → 3.** PR 2 renders the data PR 1 produces. PR 3 reads the same data for the guide and edits the same success output as PR 2, so it stacks on 2 rather than 1 to avoid a conflict in `cli/ui.py`.
- **Stack B (explanations): 4 → 5.** The configuration editor reuses PR 4's tool-information popup and metadata for its tool-default rows.
- **PR 6** touches the template schema and the recipe editor's template picker only.
- **PR 7** documents the finished journey, so it goes last.

## Settled Decisions

- **One workflow, no modes.** There is no beginner or expert mode, profile, or template variant. Help appears when someone asks for it (a key, a hover, a command) and is invisible otherwise.
- **No entry screen in front of the editor.** The "what are you building?" question is the recipe editor's first control: the template picker, grouped by purpose (PR 6). Beginners get the question where they already are, and experienced users lose no keystrokes. That also removes any need for a "skip the entry screen" preference.
- **Purpose, not intensity, steers beginners to lean tooling.** Templates declare whether they are for exploring and analyzing (the lean workbench tier: `ml`, `astro`) or for building something to publish (the product tier: `lib`, `cli`, `api`, with the full quality gate). No tooling presets and no "intensity" control. Tool selection and tool strictness remain separate, and a global setting still never overrides a template's opinion.
- **Only Protostar's own requirements block.**
  - **Required (`uv`, `git`):** nothing useful can happen without them, and they don't depend on the recipe. They are checked before any screen opens, and the run fails immediately with one install command.
  - **Tool-dependent (`direnv`, `just`, and any future tool binary):** these depend on the recipe, and the generated files are correct whether or not the binary is installed. They never block. Planning records them, the review shows them beside their tool, execution skips only the steps that need the binary, and success output ends with one install command.
- **`shutil.which` is not a subprocess.** It searches PATH without starting a process, so checking before the TUI opens costs nothing measurable, and `plan()` may call it: it stays read-only and runs no subprocess.
- **One install command from the platform package manager.** uv can't install git or direnv, so a single uv command is impossible. Use Homebrew where it exists (macOS, or Linux with brew), winget on Windows, and on other Linux systems uv's official installer for uv plus the detected package manager for the rest. Never run the command for the user.
- **Guidance lives in a command, not in generated files.** Experienced users would delete tutorial text from managed files, which would turn every sync into a preserved-edit decision. `protostar guide` prints it on demand, and the success line points to it.
- **The guide reuses `GuideSpec`.** AGENTS.md, CONTRIBUTING.md, and the pull request template already render the project's commands from `GuideSpec` (`workflows.py`), which `Orchestrator.plan()` builds. The guide is a fourth renderer of the same spec, not a second discovery system, so it can never disagree with them.
- **The configuration editor is an easier way in, not a replacement.** The TOML file remains the source of truth and stays editable by hand. The form writes through `tomlkit`, preserving comments and unrelated keys, and shows the change before saving. Git's own configuration is read for prefill, never written.
- **Tool descriptions live on modules.** One metadata record per tooling module feeds `--help`, the TUI tooltip, the `i` popup, and the configuration editor, so they can't drift apart. It replaces `cli_help`.

## Rejected Alternatives

- **A goal-oriented entry screen before the editor.** It costs experienced users a screen on every run, and the escape hatch would need a preference to find. Grouping the picker gives the same guidance in place.
- **A global beginner/expert or intensity setting.** It bundles unrelated decisions (interface detail, tool choice, strictness) and would need reinterpreting whenever defaults change.
- **Blocking on every missing binary.** Today a missing direnv raises inside `plan()`, so a TUI user makes every choice, watches the review fail, exits, installs, and starts over. That is the worst possible point to fail.
- **Warnings only, including for uv and git.** Execution cannot succeed without them, so letting someone reach the review first only wastes their choices.
- **Tutorial text in README, CONTRIBUTING, or the justfile.** Noise for experienced users, and it breaks the non-destructive contract as soon as they delete it.
- **A generic starter template.** The purpose grouping plus the existing "No template" choice cover someone who doesn't recognize a stack.
- **A "remember as my default" toggle in the recipe editor, instead of PR 5.** Beginners find editing TOML in a terminal editor intimidating. A dedicated form, with the same on-demand explanations, answers that directly.

## Cross-Cutting Requirements

- **Headless and JSON:** every new output has a structured equivalent (`missing_tools`, `guide` payloads). `stdout` stays pure in `--json`. Nothing new prompts in machine mode.
- **Headless boundary:** engine additions (`system_deps.py`, guide discovery) import no Rich or Textual. `tests/test_headless_boundary.py` must stay green.
- **Terminal output:** render data as `Text` or escaped markup, put decorative symbols through `ui.glyph`, and test new output against a strict cp1252 stream.
- **TUI:** build on `KeyboardScreen` and `cli/tui/keys.py`. Every action has a key shown on its control and listed in the screen's `KEYS` so `?` shows it. Drive tests with `pilot.press`.
- **Snapshots:** each PR regenerates the SVG and scenario snapshots its output changes (`just check-snapshots`).
- **Demos:** re-record both demos once, in PR 7, as during the TUI rebuild. Intermediate PRs leave them stale on purpose, and say so in their descriptions.

## Finished

Nothing yet.

## PR 1: `feat(engine)!: missing tools are data, not a fatal pre-flight`

**Goal:** the engine distinguishes binaries Protostar needs from binaries a selected tool needs. It reports the second group as data instead of raising, and builds install commands in one pure function. No CLI rendering changes beyond what the new error and result fields require.

**Current state:**

- **Checks are imperative `pre_flight()` bodies.**
  - `PythonCore` (`modules/lang_layer.py`) checks for uv.
  - `SystemWorkspaceModule` (`modules/system_layer.py`) checks for git only when `.git` is absent.
  - `PreCommitModule` and `PrekModule` (`modules/tooling_layer.py`) check for git.
  - `DirenvModule` checks for direnv.
- **All failures are fatal.** `Orchestrator.plan()` collects every `MissingDependencyError` into `AggregatedDependencyError` and raises inside planning, so the TUI's review preparation fails after the user has made every choice.
- **Initialization only.** Checks run only under `ExecutionPolicy.INITIALIZATION`. `sync` never checks.
- **`just` isn't in `GlobalExecutable`.** Every built-in enables it, and nothing notices when it's missing.
- **The install command is built inside `AggregatedDependencyError.__init__`** (`errors.py`). Its gaps:
  - `sudo apt install uv` fails: uv isn't packaged in Debian or Ubuntu.
  - Multiple winget ids in one command is unverified.
  - It always prints a shell-reload hint, which Homebrew installs don't need.

**Steps:**

1. **Two kinds of executable.** In `system_deps.py`, add `JUST` to `GlobalExecutable` and a `REQUIRED` set (`UV`, `GIT`). Everything else is tool-dependent. Keep per-platform package ids on the enum.
1. **Modules declare executables.** Add `executables: ClassVar[tuple[GlobalExecutable, ...]]` to `BootstrapModule`, matching how modules declare `signals`. Declare direnv on `DirenvModule` and just on `JustModule`. Delete the `which` checks from every `pre_flight()`. Delete `pre_flight()` itself if nothing else uses it (pre-1.0: no shim).
1. **Required check.** A pure `check_required_executables() -> None` in `system_deps.py` raises `AggregatedDependencyError` for missing required binaries. `Orchestrator.plan()` calls it for initialization and sync, so API and headless callers are covered. PR 2 calls the same function earlier from the CLI.
1. **Missing tools as data.** `plan()` records `missing_tools: frozenset[MissingTool]` on the manifest: each entry is a frozen dataclass holding the executable and the `Tool` that needs it. Only enabled modules count. The prepared review and `ExecutionResult` carry it, and `to_dict()` serializes it sorted as `missing_tools`. This runs for sync as well as initialization.
1. **Skip only what needs the binary.** When direnv is missing, `DirenvModule.build()` still writes `.envrc` but declares no `direnv allow` task. It records a non-fatal diagnostic saying the workspace needs `direnv allow` once direnv is installed. Nothing executes `just`, so it needs no change.
1. **Install command builder.** A pure `install_command(missing, platform, available) -> InstallCommand | None` in `system_deps.py`. `available` is the set of package managers found on PATH (brew, winget, apt, dnf, pacman), which the caller supplies so the function stays testable.
    - `InstallCommand` holds a list of command lines and whether a shell reload is needed.
    - Rules: brew when present, on any platform. winget on Windows, with one command per id if multi-id install is not supported. On other Linux systems, uv's official installer for uv plus the detected manager for the rest. No command, just the tool names and the docs link, when nothing is detected.
    - A reload hint only where a fresh PATH entry needs it (Windows, and uv's installer).
    - `AggregatedDependencyError` uses it for its hint instead of building text itself.
1. **`AGENTS.md`.** Replace the pre-flight wording where it appears, and state the rule: only `system_deps.REQUIRED` may block, and tool-dependent binaries are reported.

**Tests:**

- `install_command` for each platform and manager combination, including none detected and brew on Linux. No real `which` calls: pass `available` explicitly.
- A missing direnv or just yields `missing_tools` in the manifest and the result, with `.envrc` written and no `direnv allow` task.
- A missing uv or git raises `AggregatedDependencyError` from `plan()` for both init and sync.
- `sync` reports `missing_tools`.
- JSON serialization is sorted and deterministic.
- Patch `shutil.which` in every test. Never depend on the host's PATH.

**Done when:**

- `rg "shutil.which" src/protostar/modules` finds nothing.
- `rg "def pre_flight" src` finds only what still has a non-executable reason to exist.
- A recipe with direnv and just enabled plans on a PATH without them.

## PR 2: `feat(cli): report missing tools before the editor, in review, and after success`

**Goal:** the user learns about a missing binary at the one moment they can act on it without losing work.

**Steps:**

1. **Before any screen.** `init` and `sync` call `check_required_executables()` before launching the TUI or planning. On failure, render the existing error panel with the install command. In JSON mode, the error envelope carries the missing names and command lines in `details()`.
1. **In the recipe editor and review.** A tool whose binary is missing shows a quiet `not installed` marker beside its row. The preview's diagnostics say what will be skipped (for direnv, the `direnv allow` step). The user can untick the tool or keep it. Nothing blocks.
1. **After success.** When the result's `missing_tools` is non-empty, end the output with a short block: which tools are missing, the single install command from `install_command`, and the reload hint if any. Print it after the TUI has exited, as plain terminal text the user can copy.
1. **JSON.** The success payload includes `missing_tools` and, when a command exists, `install_commands`. No extra output on stderr.

**Tests:**

- Missing uv exits with `ExitCode.UNAVAILABLE` before the TUI launches: assert the launch function is never called.
- The review renders the `not installed` marker, driven by `pilot.press`.
- Success output with missing tools, as an SVG snapshot and under strict cp1252.
- The JSON payload shape for both success and error.

**Done when:** a run with direnv and just enabled on a bare PATH succeeds, and ends with one copyable install command.

## PR 3: `feat(cli): protostar guide and a success line that says what to do next`

**Goal:** answer "how do I work on this project?" on demand, and make the success line point there.

**Steps:**

1. **Discovery (engine).** A new `src/protostar/guide.py` builds a `ProjectGuide` from:
    - **`GuideSpec`:** from planning the recorded recipe, exactly as `sync` plans it. `plan()` is read-only.
    - **Entrypoints:** `[project.scripts]` in `pyproject.toml`, and the module or file each one points to, so the guide can name the starting source file.
    - **`missing_tools`:** from PR 1.

    It runs no project command and imports no project code. A recipe that can't be planned offline (for example, a remote template that isn't cached) yields a guide with the static parts and a note, not an error. Verify how `sync` acquires templates and reuse that path.
1. **Content.** Grouped actions, each with a short plain-language explanation:
    - Run the app.
    - Where the code starts.
    - Run the tests.
    - Check and format.
    - Build or preview the docs.
    - Everything else: `just --list`, when just is enabled.

    Show an action only when the spec supports it. When a recommended command's binary is missing, show the `uv run …` form and say how to install the missing tool. Commands come from `GuideSpec`, never recomputed.
1. **Command.** Add `protostar guide` to `parser.py` with help text, shell completion, and `--json` (a `guide` payload following the existing envelope). For a directory with no recorded recipe, say what the guide can't know and point to `protostar init`. Never invent commands.
1. **Success line.** Replace "Accretion disk stabilized. Environment ready." with a plain line, then one next step:
    - `cd <name>` when the project was created in a new directory.
    - The run command when an entrypoint exists.
    - `protostar guide` as the pointer for the rest.

    Keep it to two or three lines. The PR 2 missing-tools block stays below it.
1. **`AGENTS.md`.** Add `guide.py` to the layout map, with the rule that guide content comes only from `GuideSpec` and recorded project facts.

**Tests:**

- Guide output for a lib, a cli, and a workbench recipe (SVG snapshots).
- A project with just disabled.
- A project with just enabled but missing.
- An edited `pyproject.toml` whose entrypoint was removed: the action disappears.
- A directory with no recipe.
- JSON payload determinism.
- The subprocess and import boundaries: patch `subprocess.run` and assert it is never called.

**Done when:** the guide's commands match AGENTS.md's commands for every built-in snapshot scenario.

## PR 4: `feat(tui): tool information on demand`

**Goal:** anyone can learn what a tool does and what it will change, from the keyboard or the mouse, without adding permanent text to the editor.

**Steps:**

1. **Metadata.** A frozen `ToolInfo` on each tooling module, replacing `cli_help`:
    - `summary`: one line, used for `--help` and the tooltip.
    - `adds`: what enabling it adds or changes in the project.
    - `workflow`: the practical consequence, for example "checks run when you commit, and a failing check stops the commit".
    - `docs_url`: official documentation.

    Delete `cli_help` and derive the flag help from `summary`. Write the copy for someone who has never heard of the tool, and state consequences, not categories.
1. **Link checking.** Add `docs_url` values to `scripts/check_doc_links.py`, so a dead link fails the pre-push hook.
1. **Tooltip.** Each tool control in the recipe editor gets its `summary` as a Textual tooltip.
1. **`i` popup.** A modal on `KeyboardScreen` showing the full `ToolInfo`, bound to `i` only while a tool control has focus. The binding must not fire in `Input` or `Field` text entry. Check it doesn't collide with `Picker`, `ChoiceGroup`, or `Checklist` bindings.
    - Show `i Tool info` on the control through `key_label`, and add it to the screen's `KEYS`.
    - `Esc` closes the popup and restores focus without changing any value.
    - The docs link opens only on an explicit key in the popup.
1. **Reusable.** Put the popup in `cli/tui/` (not under `recipe/`) so PR 5 can use it.

**Tests:**

- `i` on a focused tool opens the popup, and `Esc` returns focus to the same control with its value unchanged.
- `i` typed into a text field inserts the letter.
- Every tooling module has complete `ToolInfo`: a contract test, so a new module can't ship without it.
- `--help` output snapshots regenerate.

**Done when:** every tool row answers "what does this do to my project?" in two keys.

## PR 5: `feat(cli): interactive global configuration editor`

**Goal:** a beginner can set their identity, editor, Python version, and tool defaults through a clear form, without opening a TOML file.

**Current state:** `protostar config` seeds `config.toml` if missing and opens it in `$EDITOR`, and `--reset` restores the default. The file already holds `author_name`, `author_email`, `github_username`, `ide`, `python_version`, and tool toggles. `metadata.py` falls back to `git config user.name` and `user.email` when author fields are unset.

**Steps:**

1. **Command surface.**
    - In an interactive terminal, bare `protostar config` opens the form.
    - `protostar config --edit` opens `$EDITOR` as today, and the form's action bar offers the same with `e`.
    - `--reset` is unchanged.
    - In non-interactive or `--json` runs, bare `config` raises `InvalidUsageError` with a hint pointing to `--edit`.
1. **The form** (`cli/tui/config/`), built from `Form`, `Field`, `Picker`, and `Toggle`:
    - **Identity:** name, email, and an optional GitHub username. Prefill from the file, then Git, through the existing resolver in `metadata.py`. Don't write a second resolver.
    - **Environment:** IDE and default Python version.
    - **Tool defaults:** one toggle per tool, with PR 4's tooltip and `i` popup. State in the section's help that a template's own choices win over these defaults.
1. **Save.** A pure engine function applies the form's values to the parsed `tomlkit` document, preserving comments and unrelated keys. It writes only keys whose value changed. Before writing, show the change as a diff through `cli/tui/code.py`. Write only after confirmation, and never touch Git's configuration.
1. **Docs.** Update the configuration page and the `config` help text.

**Tests:**

- Round-trip preserving comments and unknown keys.
- Only changed keys are written.
- Git prefill when the file has no identity; patch the git call.
- `Esc` asks before leaving with unsaved changes.
- The non-interactive `config` error.
- `--edit` keeps today's behavior.
- A cp1252 run of the saved-summary output.

**Done when:** someone can go from no config file to a saved identity and IDE without seeing TOML.

## PR 6: `feat(templates): group templates by purpose`

**Goal:** the first question in the editor becomes "are you exploring or building something to publish?", and a beginner's answer leads to lean tooling.

**Current state:** each built-in's tier exists only as a comment on its first line ("Product tier" or "Workbench tier"). `TemplateInfo` has no purpose field, and the editor's template picker is a flat list followed by "No template".

**Steps:**

1. **Schema.** An optional root key `purpose` (a `StrEnum`: `explore`, `publish`) in template TOML, parsed in `config.py`, exposed on `TemplateInfo`, and included in the exported JSON schema. External templates may omit it.
1. **Built-ins.** Set `purpose` on every built-in, following its tier comment: `ml` and `astro` explore, `lib`, `cli`, and `api` publish. Extend `tests/test_builtin_template_contract.py` to require it, and update `docs/developer/built-in-templates.md`.
1. **Picker.** Group the recipe editor's template picker under plain-language headings, for example "Explore and analyze" and "Build something to publish". Templates without a purpose go under "Other templates", then "No template". Each option shows the template's description. Keep the recorded-template choice first when one exists. Arrow keys move across group headings without stopping on them.
1. **Listing.** `--list-templates` groups the same way, and its JSON output includes `purpose`.

**Tests:**

- Picker grouping and order, driven by `pilot.press`.
- A template without `purpose` lands in "Other templates".
- An invalid `purpose` value is a `ConfigurationError` with a hint.
- Schema and listing snapshots regenerate.

**Done when:** a first-time user picking from the top group gets a workbench-tier recipe.

## PR 7: `docs: first-project walkthrough and installation paths`

**Goal:** one page takes a newcomer from nothing installed to a project they have run, changed, and checked.

**Steps:**

1. **Installation page.** One recommended path per platform, written for someone with no Python setup.
    - The page states which path gets `uv` and `git` for the reader and which doesn't.
    - Move pip into a note for people installing into an existing environment.
    - **Out of repository:** have the Homebrew formula in `jacksonfergusondev/homebrew-tap` declare `depends_on "uv"` and `depends_on "git"`, so brew users never see PR 2's blocking check. Record this in the PR description; it is not part of this diff.
1. **Walkthrough page.** On a clean machine, the reader:
    - Installs.
    - Runs `protostar init` and picks from the explore group.
    - Uses `i` on one tool.
    - Reads the success line and runs `protostar guide`.
    - Runs the project.
    - Makes an edit.
    - Runs the checks, fixes a deliberate lint failure, and reruns.

    Define terms (virtual environment, lint, pre-commit hook) where they first matter, with links to the reference pages rather than inline detail.
1. **Reference updates.** Document tool information, the configuration editor, `protostar guide`, and missing-tool reporting on their reference pages.
1. **Demos.** Re-record both demos (`just demo-headless`, `just demo-wizard`), since stacks A and B changed CLI output.
1. **Validation.** Walk the page on a fresh macOS sandbox (`just sandbox`) and a clean Debian container (`just sandbox-linux`). Record in the PR description anything that needed coaching.

**Done when:** the walkthrough completes on both sandboxes with no step that isn't on the page, and `zensical build --strict` and `check-doc-links` pass.
