# Approachable Onboarding Plan

Make Protostar usable by people new to Python tooling without adding a single keystroke or line of noise for experienced users. Help is always on demand, never in the way.

**How to use this file:** one PR per agent. Read `AGENTS.md` first, then only your PR's section. Stay inside its scope. Note anything out of scope in the PR description instead of doing it. When a PR merges, collapse its section to a short summary under "Finished".

## Status

| PR | Title | Stack | Status |
|---|---|---|---|
| 1 | `feat(engine)!: missing tools are data, not a fatal pre-flight` | A (base) | Merged (#345) |
| 2 | `feat(cli): report missing tools before the editor, in review, and after success` | A, on 1 | Merged (#346) |
| 3 | `feat(cli): protostar guide and a success line that says what to do next` | A, on 2 | Merged (#347) |
| 4 | `feat(tui): tool information on demand` | B (base) | Merged (#350) |
| 5 | `feat(cli): interactive global configuration editor` | B, on 4 | Merged (#351) |
| 6 | `feat(templates): workbench and production tiers` | C (base) | Merged (#354) |
| 7 | `feat(templates): every built-in offers both tiers` | C, on 6 | Done (#355) |
| 8 | `feat(tui): choose the tier beside the template` | C, on 7 | Next |
| 9 | `docs: first-project walkthrough and installation paths` | After all | Planned |

## Stacks

Within a stack, each PR branches from the previous one and is retargeted to `main` when its base merges.

- **Stack A (missing tools, then guidance): 1 → 2 → 3.** PR 2 renders the data PR 1 produces. PR 3 reads the same data for the guide and edits the same success output as PR 2, so it stacks on 2 rather than 1 to avoid a conflict in `cli/ui.py`.
- **Stack B (explanations): 4 → 5.** The configuration editor reuses PR 4's tool-information popup and metadata for its tool-default rows.
- **Stack C (tiers): 6 → 7 → 8.** PR 6 adds the tier to the template schema, the recipe, the command line, and resolution, with no built-in declaring one yet. PR 7 gives every built-in both tiers, which needs real content, not just flags. PR 8 shows the tier in the recipe editor, and stacks on 7 so its tests and snapshots exercise the built-ins.
- **PR 9** documents the finished journey, so it goes last.

## Settled Decisions

- **One workflow, no modes.** There is no beginner or expert mode or profile. Help appears when someone asks for it (a key, a hover, a command) and is invisible otherwise.
- **No entry screen in front of the editor.** The "what are you building?" question is the recipe editor's first control: the template picker, with the tier directly beneath it (PR 8). Beginners get the question where they already are, and experienced users lose no keystrokes. That also removes any need for a "skip the entry screen" preference.
- **The tier is a switch beside the template, not a property of it.** A template is a project *shape* (a CLI, a service, an astro workbench); the tier is how much tooling that shape starts with. Tying them together made a workbench CLI or a production-grade astro project impossible to ask for. A template may declare two tiers, `workbench` (lean: exploring and analyzing) and `production` (the full quality gate: building something to publish), each a set of tool opinions, plus which one it defaults to. The shape decides structure, dependencies, and files; the tier decides tool opinions, and strictness follows the tools through `requires`. This reverses the original PR 6, which grouped templates by a fixed purpose.
- **Exactly two tiers, named by Protostar.** A template declares both or neither, since a switch with one position means nothing. Fixed names give the command line (`--tier`), the recipe editor, the docs, and `protostar guide` one vocabulary across every template, external ones included. A template without tiers shows no tier control.
- **The tier's precedence sits inside the template's opinion.** An explicit tool flag beats the recipe, which beats the template's opinion, which is its root flags with the chosen tier's flags on top. The recipe records a tier only when it was pinned (`--tier`) or differs from the template's default, exactly like options, so a project that never chose follows the template's default.
- **Every built-in keeps a default tier** (`cli`, `api`, `lib` → production; `astro`, `ml` → workbench), so nobody gains a keystroke. No global "default tier" setting: a global setting still never overrides a template's opinion.
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
- **A global beginner/expert or intensity setting.** It bundles unrelated decisions (interface detail, tool choice, strictness) and would need reinterpreting whenever defaults change. A tier differs: its template's author declares and owns it, and it is scoped to that template.
- **Grouping the template picker by purpose (the original PR 6).** It fixed the tier to the template, so a workbench CLI or a production astro project had no path. Once the tier is its own control, grouping by purpose repeats it.
- **Letting any option set tool opinions.** More general, but two options could disagree about the same tool and would need a precedence rule, and free-form names give the interface nothing shared to say. Two fixed tiers cover the need.
- **Blocking on every missing binary.** Today a missing direnv raises inside `plan()`, so a TUI user makes every choice, watches the review fail, exits, installs, and starts over. That is the worst possible point to fail.
- **Warnings only, including for uv and git.** Execution cannot succeed without them, so letting someone reach the review first only wastes their choices.
- **Tutorial text in README, CONTRIBUTING, or the justfile.** Noise for experienced users, and it breaks the non-destructive contract as soon as they delete it.
- **A generic starter template.** The tier plus the existing "No template" choice cover someone who doesn't recognize a stack.
- **A "remember as my default" toggle in the recipe editor, instead of PR 5.** Beginners find editing TOML in a terminal editor intimidating. A dedicated form, with the same on-demand explanations, answers that directly.

## Cross-Cutting Requirements

- **Headless and JSON:** every new output has a structured equivalent (`missing_tools`, `guide` payloads). `stdout` stays pure in `--json`. Nothing new prompts in machine mode.
- **Headless boundary:** engine additions (`system_deps.py`, guide discovery) import no Rich or Textual. `tests/test_headless_boundary.py` must stay green.
- **Terminal output:** render data as `Text` or escaped markup, put decorative symbols through `ui.glyph`, and test new output against a strict cp1252 stream.
- **TUI:** build on `KeyboardScreen` and `cli/tui/keys.py`. Every action has a key shown on its control and listed in the screen's `KEYS` so `?` shows it. Drive tests with `pilot.press`.
- **Snapshots:** each PR regenerates the SVG and scenario snapshots its output changes (`just check-snapshots`).
- **Demos:** re-record both demos once, in PR 9, as during the TUI rebuild. Intermediate PRs leave them stale on purpose, and say so in their descriptions.

## Finished

- **Stack A (PRs 1–3), merged as #345, #346, and #347.**
  - **PR 1 (#345):** only `system_deps.REQUIRED` (`uv`, `git`) blocks, through `check_required_executables()`, which `plan()` calls for init and sync. Modules declare tool binaries in `executables`. Planning records the missing ones as `missing_tools` on the manifest, review, and `ExecutionResult`, and `DirenvModule` skips `direnv allow` with a diagnostic. `install_command()` is pure and takes the detected package managers. Deviations: `pre_flight()` and `AggregatedDependencyError` are deleted (one `MissingDependencyError` carries every missing binary), `plan(policy=)` became `plan(check_executables=)`, and tests control lookups through the `missing_executables` fixture.
  - **PR 2 (#346):** `init` and `sync` check required binaries before any screen. Missing tools show a `not installed` marker in the editor, a preview note, and a **Skipped** section in the review. Success ends with a **Not installed** block and one install command. JSON carries `missing_tools` and `install_commands`.
  - **PR 3 (#347):** `protostar guide` renders `GuideSpec` (now `EnvironmentManifest.guide_spec()`, with `just_recipes()`/`check_commands()` shared in `workflows.py`) and `[project.scripts]`, planning through `plan_project` as `sync` does. The success line is `Project ready.` plus the run command and a pointer to the guide. Remote templates are never cached, so an unreachable one yields a partial guide with a note. The `cd <name>` step was dropped because `init` always scaffolds in the current directory.
- **Stack B (PRs 4–5).**
  - **PR 4 (#350):** `ToolInfo` (`summary`, `adds`, `workflow`, `docs_url`) on every tooling module replaced `cli_help`; the summary is the flag help, the template schema description, and the tooltip. `cli/tui/tool_info.py` holds `ToolInfoScreen` (`esc` closes, `o` opens the docs), `TOOL_GROUPS`, and the tool controls that bind `i` only while focused: `ToolToggle`, `ToolRadio`, and `ToolChoice`, which offers `i` only while a tool, not "None", is highlighted. The Tools heading shows `Tool info  i`. `check_doc_links.py` requests every `docs_url` and fails on an HTTP error, and its hook now runs when `src/protostar/modules/` changes.
  - **PR 5 (#351):** bare `protostar config` opens `ConfigScreen` (`cli/tui/config/`): identity, editor, default Python, and tool defaults, with the same `i` popup and a live **Changes** diff of the file. `config_edit.edit_config()` applies the values through `tomlkit`, writing only keys whose effective value changed, each after its commented example when the file has one. The app exits with `SaveConfig` or `OpenInEditor`, and the CLI writes (refusing if the file changed meanwhile) or opens `$EDITOR`. Identity prefills through `resolve_auto_metadata`, so Git's name and email appear until saved. `--edit` keeps the old behavior; non-interactive and `--json` runs of bare `config` raise `InvalidUsageError` pointing to it. `UserConfig.parse()` is the public text parser.
- **Stack C (PRs 6–7).**
  - **PR 6 (#354):** `tiers.py` holds `Tier`, `TemplateTiers`, `parse_tiers`, `template_opinions`, and `resolve_tier`. A template declares a root `tier` default and `[tiers.workbench]`/`[tiers.production]` tool-flag tables (any tool or `docker`; both tiers set the same tools; a tool set there can't also be set at the root). `TemplateBlueprint.opinions(tier)` and `TemplateSource.opinions(tier)` replace every direct read of `tooling_overrides`. The tier is a first-class recipe field, `[tool.protostar] tier`, deliberately not an option, since options only choose content; it is recorded only when pinned by `--tier`, and `sync` drops it once the template stops declaring tiers. `requires = "tier=production"` gates content, and options may not be named `tier`. `--tier` on `init` and `sync` is an `InvalidUsageError` for a template without tiers. `TemplateInfo.tiers` feeds the listing JSON, and the text table gains a tier column once any template has tiers. The editor already follows a pinned or recorded tier's opinions; `InitDraft.tier` carries the flag.
  - **PR 7 (#355):** every built-in declares both tiers. The rule for where a flag goes, from the maintainer: production infrastructure goes in the tiers (all off in workbench, all on in production); what the user wants in the project either way (`ruff`, `direnv`, `just`) stays at the root. So `release`, `readthedocs`, `zensical`, `codecov`, and `community` (`cli`, `lib`) and `docker` (`api`) are production-only. Strict `mypy`, docstring `ruff`, and the coverage threshold require `tier=production` as well as their tool. Tests ship only while `pytest` is on. Production `astro`/`ml` ship a small `src/` package and a test, and point pytest at `src/` (`pythonpath` joined `ATOMIC_LISTS_WITHOUT_ADDITIVE_KEY`). `check-template` plans every tier. The contract tests require both tiers, the right defaults, and all-off/all-on tiers. By the maintainer's choice, CI still scaffolds only default tiers; new snapshot scenarios cover `astro_production` and `cli_workbench`, and every non-default tier was scaffolded and gated by hand. Found on the way: the generated `check-added-large-files` hook rejected a scientific stack's `uv.lock` (over 500 KB), so it now excludes `uv.lock`. The contract doc's enforcement table was stale (it cited the exhaustive suite removed in #282) and was rewritten.

## PR 8: `feat(tui): choose the tier beside the template`

**Goal:** the recipe editor asks "which template?" and then "workbench or production?" in place, with no extra keystroke for someone who accepts the default.

**Steps:**

1. **Control.** A two-choice `ChoiceGroup` (`Workbench`, `Production`) directly under the template picker, shown only while the chosen template declares tiers, preselected to the recorded tier or the template's default.
1. **Explanation.** `i` on the tier control opens the same `ToolInfoScreen`-style popup, explaining what each tier turns on for this template (its actual flag differences), written for someone who has never heard of a quality gate.
1. **Tools follow the tier.** Switching tier resets the tool toggles to the new tier's opinions, the same way switching template does, and the live preview updates. The draft records the tier only when it differs from the template's default.
1. **Keys.** List the control in the screen's `KEYS` so `?` shows it. `Tab` treats the group as one control.

**Tests:** driven by `pilot.press`: the control appears only for templates with tiers; its default and recorded preselection; switching tier flips exactly the tier's tools; the draft records a tier only when non-default; `i` opens the popup. Regenerate the editor SVG snapshots.

**Done when:** a first-time user who picks `astro` sees Workbench selected, can switch to Production with one key, and the review shows the production tools.

## PR 9: `docs: first-project walkthrough and installation paths`

**Goal:** one page takes a newcomer from nothing installed to a project they have run, changed, and checked.

**Steps:**

1. **Installation page.** One recommended path per platform, written for someone with no Python setup.
    - The page states which path gets `uv` and `git` for the reader and which doesn't.
    - Move pip into a note for people installing into an existing environment.
    - **Out of repository:** have the Homebrew formula in `jacksonfergusondev/homebrew-tap` declare `depends_on "uv"` and `depends_on "git"`, so brew users never see PR 2's blocking check. Record this in the PR description; it is not part of this diff.
1. **Walkthrough page.** On a clean machine, the reader:
    - Installs.
    - Runs `protostar init`, picks `astro`, and keeps the workbench tier.
    - Uses `i` on one tool.
    - Reads the success line and runs `protostar guide`.
    - Runs the project.
    - Makes an edit.
    - Runs the checks, fixes a deliberate lint failure, and reruns.

    Define terms (virtual environment, lint, pre-commit hook) where they first matter, with links to the reference pages rather than inline detail.
1. **Reference updates.** Document tool information, the configuration editor, `protostar guide`, and missing-tool reporting on their reference pages.
1. **Demos.** Re-record both demos (`just demo-headless`, `just demo-wizard`), since stacks A, B, and C changed CLI output.
1. **Validation.** Walk the page on a fresh macOS sandbox (`just sandbox`) and a clean Debian container (`just sandbox-linux`). Record in the PR description anything that needed coaching.

**Done when:** the walkthrough completes on both sandboxes with no step that isn't on the page, and `zensical build --strict` and `check-doc-links` pass.
