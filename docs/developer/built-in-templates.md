---
description: "What a built-in Protostar template is, what deserves to ship as one, and the conventions every built-in must follow."
---

# Built-in Templates

Protostar ships six built-in templates: `api`, `astro`, `cli`, `dsp`, `embedded`, and `ml`. This page is the contract they share. It exists so that maintainers, contributors, and reviewers can answer three questions the same way every time:

- What deserves to be a built-in template?
- What must a built-in template look like?
- How is that enforced, so the answers don't quietly drift?

If you are writing a template for your own team, see [Authoring Custom Templates](../usage/authoring-templates.md) instead. Built-ins are held to a higher bar because they ship with Protostar, are trusted implicitly, and are the first thing most users try.

## What a Built-in Is

**A built-in template is a project shape, not a stack.**

A shape is a kind of project someone recognizes on sight: a command-line tool, a web service, an analysis workbench for a field. A stack is a particular combination of libraries: FastAPI plus Postgres plus Redis. Shapes belong in Protostar. Stacks belong in a [`--from` template or a global alias](../usage/templates.md).

What earns a shape its place is knowledge a generic scaffolder doesn't have: the ignore patterns for `.fits` files or `.uf2` firmware images, `nbdime` wired into notebook diffs, a `/health` endpoint with a test that actually runs. Everything a built-in encodes should be something you would otherwise copy from your last project.

| Template | Shape | Tier |
| :--- | :--- | :--- |
| `cli` | Published command-line application (Typer, Rich) | Product |
| `api` | Deployed web service (FastAPI, Uvicorn) | Product |
| `astro` | Astrophysics data analysis (Astropy) | Workbench |
| `ml` | Machine learning and data science (PyTorch, Jupyter) | Workbench |
| `dsp` | Digital signal processing and audio | Workbench |
| `embedded` | MicroPython and microcontroller development | Workbench |

## Admission Criteria

Every proposed built-in must answer yes to all three questions:

1. **Would most people starting this kind of project want these defaults?** This is the same test [CONTRIBUTING.md](./overview.md) applies to every feature. A template that suits one team's preferences is a team template.
1. **Can a maintainer credibly own its conventions?** A built-in has to stay correct as its ecosystem moves. If nobody on the project can tell whether the ignore patterns, dependencies, or layout are still right, it will rot.
1. **Is it better as a built-in than as a third-party template?** If the answer is "it would work just as well from a URL", it should be a URL.

The default answer to a new-template proposal is therefore "publish it as a `--from` template". The bar is high on purpose:

- **Built-ins are trusted implicitly.** They skip the [remote trust dialog](../usage/templates.md#security-model-the-remote-trust-dialog), so every task a built-in declares runs without confirmation.
- **Built-ins are maintained forever.** Each one adds a snapshot, a scaffold in the exhaustive suite, and continuous integration time.
- **Built-ins set expectations.** Users infer what "the Protostar way" means from what ships.

## The Two Tiers

Built-ins fall into two tiers that differ in how much tooling they turn on by default.

| Flag | Product (`cli`, `api`) | Workbench (`astro`, `ml`, `dsp`, `embedded`) |
| :--- | :---: | :---: |
| `ruff`, `direnv`, `just` | on | on |
| `mypy` | on | off |
| `pytest` | on | off |
| `prek`, `commitizen`, `renovate` | on | off |
| `ci` | on | off |
| `rumdl` | on | off |

`cli` also turns on `release`, `readthedocs`, `zensical`, and `codecov`, because it is a package people install. `api` turns on `docker`, because it is a service people deploy.

**Product templates default to the full quality gate**, because a published package or a deployed service should not need a second pass to become production-ready.

**Workbench templates default to lean**, because exploratory work does not want typing, CI, or commit-hook opinions on day one. An analysis notebook that fails a strict type check is friction, not safety.

!!! note "Tiers are defaults, not restrictions"
    Protostar's tri-state toggling still applies. `protostar init -t astro --mypy` is valid, and so is `protostar init -t api --no-ci`. The tiers describe what a built-in *starts* with, not what it allows.

### Container Scaffolding

Docker follows the same precedence as the tooling flags. In order: an explicit `--docker` or `--no-docker`, then the project's saved recipe, then the template's `docker` opinion, then off. A template that declares `docker = true` (the `api` template does) scaffolds a `Dockerfile` by default, and an already-initialized project keeps its saved choice even if the template later changes its mind.

## Baseline in Modules, Delta in Templates

**Modules ship a baseline tuned for casual projects. Templates state only the delta that defines their shape.**

Imagine someone picks `ruff` and `mypy` because they are writing a small script and want it modern and clean. If those modules shipped a production-grade strict configuration, they would land in a project full of docstring and typing errors they never asked for, and they would blame Protostar. So the modules stay gentle:

| Module | Baseline |
| :--- | :--- |
| `ruff` | Line length 88. Selects `A`, `B`, `C4`, `E`, `F`, `I`, `RUF`, and `UP`. |
| `mypy` | `check_untyped_defs`, `warn_return_any`, and `warn_unused_configs`. **Not** `strict`. |

Strictness belongs where it defines a shape. The `cli` template is a published package, so it adds strict typing and docstring rules on top:

```toml
[dev.pyproject.cli_ruff_config]
requires = "ruff"
content = '''
[tool.ruff.lint]
extend-select = ["D", "N", "PT", "RET", "SIM", "T20"]
'''

[dev.pyproject.cli_mypy_config]
requires = "mypy"
content = '''
[tool.mypy]
strict = true
'''
```

The template states `strict = true` and nothing else about mypy, because the module already supplies the rest. Each payload also declares the tool it configures with `requires`, so it is injected only while that tool is enabled.

### Why Templates Use Additive Keys

Sequences merge atomically. If a template redefines `select`, its list *replaces* the module's rather than joining it, so the template silently restates the baseline and drifts the next time the module changes. Use the tool's additive key (`extend-select` for Ruff) whenever it has one.

A few lists have no additive key. Ruff's `ignore` is the current example. A template may redefine such a list only if it keeps every baseline entry, so it is a strict superset. `cli.toml` repeats `E501` alongside its docstring exemptions for exactly this reason.

### Tool Configuration Follows the Tool

A payload that configures a tool declares it with `requires`, so `protostar init -t cli --no-mypy` writes no `[tool.mypy]`. Dev packages that only a tool needs (such as `pytest-cov`) go under `[dev.tool_dependencies]`, keyed by that tool, so `--no-pytest` does not install them. Payloads that no tool toggle should remove, such as a `[build-system]` table, stay plain strings and are always injected. Tool-bound payloads are also attributed to their tool in lifecycle reviews, so a project's recipe opt-out treats them like the tool's own configuration.

## Conventions Every Built-in Follows

1. **Declare every quality flag explicitly.** Each built-in sets `ruff`, `mypy`, `pytest`, `prek`, `ci`, `rumdl`, `direnv`, and `just` to `true` or `false`. A reader should see every choice and never infer one from an omission.
1. **A fresh scaffold passes its own gates.** If a template turns on `ruff`, `mypy`, or `pytest`, then `ruff check`, `ruff format --check`, `mypy .`, and `pytest` must succeed on a brand-new project. If there is no code to test, do not enable `pytest`. `pytest` exits with an error when it collects nothing, and a generated CI workflow would fail on its first run.
1. **Product templates are installable packages.** They use a `src/` layout and a real build backend, so tests import the package the way any consumer would, the console script exists, and the container build can install the project. Use `hatchling` with an explicit `packages` entry, and ship the `README.md` the generated `pyproject.toml` already references. Avoid `uv_build`: uv generates a version bound tied to the exact uv release, which goes stale in a static template.
1. **No version pins.** Dependencies are passed to `uv` so the environment resolves the latest compatible versions when the project is created.
1. **Keep tasks to a minimum.** No `system_tasks`. A `post_install_tasks` entry is allowed only when the domain truly needs it (`nbdime` for notebook diffs), and it must be on the allowlist in the contract test, because built-ins run without a trust prompt.
1. **Generated code formats cleanly for any project name.** Do not interpolate `<% PROJECT_NAME %>` into a line that `ruff format` would wrap for longer names. The `cli` template defines an `APP_NAME` constant for this reason: a version line that embedded the name failed `ruff format --check` for names over about 16 characters.
1. **Tool configuration and tool packages declare the tool they need.** Test plugins such as `pytest-cov` go under `[dev.tool_dependencies]`, so disabling the tool installs none of them.
1. **Development tooling goes in the dev group; the docs group is for the documentation toolchain.** Built-ins declare no `docs_dependencies` at all, because the Zensical module supplies `zensical` and `mkdocstrings`. `uv sync` installs the dev group by default but not docs, so a notebook tool placed in the docs group is removed by the first `just sync`.
1. **A new tool table needs a layout entry.** If a template writes a `[tool.<name>]` that `TOOL_SECTIONS` in `toml_layout.py` does not list, it sorts unlabelled after the known tools. See [The pyproject.toml Layout](./pyproject-layout.md).
1. **Tool configuration declares the tool it needs.** A payload that configures `ruff`, `mypy`, `pytest`, or another tool is a table with `requires = "<tool>"`, so disabling the tool leaves none of its configuration behind. Tool-agnostic payloads, such as `[build-system]`, stay plain strings.
1. **Explain decisions in the template file, not the payload.** A comment inside a `[dev.pyproject]` string is copied into every user's `pyproject.toml`. Put maintainer-facing comments above the payload instead.
1. **Web services expose `<package>.main:app`.** The generated `Dockerfile` starts `uvicorn <package>.main:app`. For projects that are not from the `api` template but list FastAPI or Uvicorn, this is the best available guess. If it is wrong for a project, the container fails at start with a clear `ModuleNotFoundError`.

## Adding, Changing, and Retiring a Built-in

**Adding one.** Open an issue that answers the three [admission questions](#admission-criteria) and names the tier. Then:

1. Write `src/protostar/templates/<name>.toml`, following the conventions above.
1. Add its marker dependency to `TEMPLATE_DEPENDENCY_MARKERS` in `tests/test_exhaustive.py`.
1. Add a `RegressionScenario` to `scripts/run_snapshots.py` and its name to `SCENARIO_FIXTURES` in `tests/test_snapshots.py`, then run `just check-snapshots` and review every generated file by hand.

The contract tests, template discovery, the wizard, shell completion, and the generated template table pick it up automatically.

**Changing one.** Treat a flag flip as a behavior change: it alters what every future user of that template gets. Regenerate snapshots and read the diff, including lock files and generated trees. When a change tightens a module baseline, update the guard in `tests/test_modules.py` deliberately and check that no template now repeats the new value.

**Retiring one.** Protostar is pre-1.0, so delete cleanly. Do not leave aliases, deprecation shims, or compatibility layers (see `AGENTS.md`).

## How the Contract Is Enforced

Most of the contract is checked by tests, parametrized over discovered built-ins, so a new template is held to it without anyone remembering to add it.

| Rule | Enforced by |
| :--- | :--- |
| All eight quality flags declared explicitly | `test_declares_every_quality_flag_explicitly` |
| Flags name real tooling modules | `test_root_flags_name_real_tools` |
| Name and description present | `test_declares_name_and_description` |
| No version pins | `test_dependencies_carry_no_version_pins` |
| Tasks stay within the trusted allowlist | `test_tasks_stay_within_the_trusted_allowlist` |
| Payloads state only the delta from module baselines | `test_pyproject_payloads_state_only_the_delta` |
| Tool configuration declares its tool with `requires` | `test_tool_configuration_declares_the_tool_it_needs` |
| Tool packages are installed only with their tool | `test_tool_packages_are_installed_only_with_their_tool` |
| The docs group is left to the docs tooling | `test_docs_group_is_left_to_the_docs_tooling` |
| Every tool table a template writes has a layout entry | `test_every_tool_table_a_built_in_template_writes_has_a_layout_entry` in `tests/test_toml_layout.py` |
| Module baselines stay casual | `test_ruff_module_baseline_stays_casual`, `test_mypy_module_baseline_stays_casual` |
| A fresh scaffold passes its enabled gates | `test_individual_template_scaffolding` (with `KNOWN_GATE_GAPS`) |
| A plain `uv sync` keeps every package the template declares | `test_individual_template_scaffolding` |
| The `api` Dockerfile targets an importable app | `test_api_dockerfile_targets_an_importable_app` |
| No trailing whitespace in scaffolded files | `test_builtin_templates_no_trailing_whitespace` |

The first nine live in `tests/test_builtin_template_contract.py`. The module baseline guards live in `tests/test_modules.py`, and the scaffold checks live in `tests/test_exhaustive.py` (an integration-level suite, so a full run scaffolds every template, including the ML environment).

`KNOWN_GATE_GAPS` in the exhaustive suite is an exact-match ratchet. It is currently empty. A new failing gate fails the test, and fixing a recorded gap forces its removal, so gaps cannot grow silently.

Some conventions rely on review rather than tests: the tier choice, product templates being installable packages, and keeping maintainer comments out of payloads.

## Related Pages

- **[Authoring Custom Templates](../usage/authoring-templates.md):** Writing templates for your own team, including the same baseline-and-delta habit.
- **[Templates](../usage/templates.md):** Using built-ins, aliases, and remote templates, and the trust model behind them.
- **[The Module Architecture](../mechanics/modules.md):** How modules declare their baseline into the manifest.
- **[Design Principles](../design-principles.md):** Why baselines live in modules and shape lives in templates.
- **[Testing Architecture & Philosophy](./testing.md):** The unit, integration, and exhaustive tiers behind the enforcement above.
