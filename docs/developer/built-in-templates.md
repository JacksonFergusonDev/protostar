---
description: "What a built-in Protostar template is, what deserves to ship as one, and the conventions every built-in must follow."
---

# Built-in Templates

Protostar ships five built-in templates: `api`, `astro`, `cli`, `lib`, and `ml`. This page is the contract they share. It exists so that maintainers, contributors, and reviewers can answer three questions the same way every time:

- What deserves to be a built-in template?
- What must a built-in template look like?
- How is that enforced, so the answers don't quietly drift?

If you are writing a template for your own team, see [Authoring Custom Templates](../usage/authoring-templates.md) instead. Built-ins are held to a higher bar because they ship with Protostar, are trusted implicitly, and are the first thing most users try.

## What a Built-in Is

**A built-in template is a project shape, not a stack.**

A shape is a kind of project someone recognizes on sight: a command-line tool, a web service, an analysis workbench for a field. A stack is a particular combination of libraries: FastAPI plus Postgres plus Redis. Shapes belong in Protostar. Stacks belong in a [`--from` template or a global alias](../usage/templates.md).

What earns a shape its place is knowledge a generic scaffolder doesn't have: the ignore patterns for `.fits` files, `nbdime` wired into notebook diffs, a `/health` endpoint with a test that actually runs. Everything a built-in encodes should be something you would otherwise copy from your last project.

| Template | Shape | Default tier |
| :--- | :--- | :--- |
| `cli` | Command-line application (Typer, Rich) | Production |
| `api` | Web service (FastAPI, Uvicorn) | Production |
| `lib` | Reusable library package (pip-installable, PEP 561) | Production |
| `astro` | Astrophysics data analysis (Astropy) | Workbench |
| `ml` | Machine learning and data science (PyTorch, Jupyter) | Workbench |

## Admission Criteria

Every proposed built-in must answer yes to all three questions:

1. **Would most people starting this kind of project want these defaults?** This is the same test [CONTRIBUTING.md](./overview.md) applies to every feature. A template that suits one team's preferences is a team template.
1. **Can a maintainer credibly own its conventions?** A built-in has to stay correct as its ecosystem moves. If nobody on the project can tell whether the ignore patterns, dependencies, or layout are still right, it will rot.
1. **Is it better as a built-in than as a third-party template?** If the answer is "it would work just as well from a URL", it should be a URL.

The default answer to a new-template proposal is therefore "publish it as a `--from` template". The bar is high on purpose:

- **Built-ins are trusted implicitly.** They skip the [remote trust dialog](../usage/templates.md#security-model-the-remote-trust-dialog), so every task a built-in declares runs without confirmation.
- **Built-ins are maintained forever.** Each one adds a snapshot, a scaffold in the CI smoke matrix, and continuous integration time.
- **Built-ins set expectations.** Users infer what "the Protostar way" means from what ships.

## The Two Tiers

A template is a shape; how much tooling that shape starts with is a separate switch. Every built-in declares two [tiers](../usage/authoring-templates.md#template-tiers), and a user picks either one with `--tier`:

- **Workbench** is lean, for exploring and analyzing. It does not want typing, CI, or commit-hook opinions on day one: an analysis notebook that fails a strict type check is friction, not safety.
- **Production** is the full quality gate, for building something to publish. A published package or a deployed service should not need a second pass to become production-ready.

**The test for where a tool belongs:** is it part of production infrastructure, or something the user would want in this project no matter what? What they want either way is set at the template's root; production infrastructure is set in the tiers, all off in workbench and all on in production.

| Flag | Where | `cli`, `lib` | `api` | `astro`, `ml` |
| :--- | :--- | :---: | :---: | :---: |
| `ruff`, `direnv`, `just` | root | on | on | on |
| `mypy`, `pytest`, `prek`, `ci`, `rumdl`, `commitizen`, `renovate` | tiers | production | production | production |
| `codecov`, `zensical`, `readthedocs`, `release`, `community` | tiers | production | not set | not set |
| `docker` | tiers | not set | production | not set |

`cli` and `lib` turn on the publishing tools in production because they are packages people install and contribute to. `api` turns on `docker` because a production service is deployed in a container.

The default tier follows what most people starting the shape want: `cli`, `api`, and `lib` start in production, and `astro` and `ml` in workbench.

!!! note "Tiers are defaults, not restrictions"
    Protostar's tri-state toggling still applies within a tier. `protostar init -t astro --tier production --no-ci` is valid, and so is `protostar init -t api --mypy`. A tier describes what a built-in *starts* with, not what it allows.

### Tier-Specific Content

Strictness is production polish. The strict `mypy` and docstring `ruff` payloads of `cli` and `lib`, and their coverage threshold, require both their tool and `tier=production`, so a workbench project that turns `mypy` on gets the casual baseline.

A tier must also pass the gates it enables. Production `astro` and `ml` ship a small package under `src/` and a test for it (`requires = "tier=production"` for the package, and `pytest` plus the tier for the test), and point pytest at `src/`, since analysis projects have no build backend to install their package. Tests in `cli`, `lib`, and `api` ship only while `pytest` is on, so a workbench scaffold has none.

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

A payload that configures a tool declares it with `requires`, so `protostar init -t cli --no-mypy` writes no `[tool.mypy]`. Dev packages that only a tool needs (such as `pytest-cov`) go in an `[[optional]]` block that requires that tool, so `--no-pytest` does not install them. Payloads that no tool toggle should remove, such as a `[build-system]` table, stay plain strings and are always injected. Tool-bound payloads are also attributed to their tool in lifecycle reviews, so a project's recipe opt-out treats them like the tool's own configuration.

## Conventions Every Built-in Follows

1. **Declare every quality flag explicitly.** Each built-in sets `ruff`, `mypy`, `pytest`, `prek`, `ci`, `rumdl`, `direnv`, and `just` to `true` or `false`, at the root or in both tiers. A reader should see every choice and never infer one from an omission.
1. **Declare both tiers.** Each built-in declares `[tiers.workbench]` and `[tiers.production]` and its default `tier`. The tiers name only production infrastructure: workbench sets every one of them off and production sets every one on.
1. **A fresh scaffold passes its own gates, in both tiers.** If a tier turns on `ruff`, `mypy`, or `pytest`, then `ruff check`, `ruff format --check`, `mypy .`, and `pytest` must succeed on a brand-new project. If there is no code to test, do not enable `pytest`. `pytest` exits with an error when it collects nothing, and a generated CI workflow would fail on its first run.
1. **Package shapes are installable packages.** `cli`, `api`, and `lib` are installable in either tier. They use a `src/` layout and a real build backend, so tests import the package the way any consumer would, the console script exists, and the container build can install the project. Use `hatchling` with an explicit `packages` entry, and ship the `README.md` the generated `pyproject.toml` already references. Avoid `uv_build`: uv generates a version bound tied to the exact uv release, which goes stale in a static template.
1. **No version pins.** Dependencies are passed to `uv` so the environment resolves the latest compatible versions when the project is created.
1. **Keep tasks to a minimum.** No `system_tasks`. A `post_install_tasks` entry is allowed only when the domain truly needs it (`nbdime` for notebook diffs), and it must be on the allowlist in the contract test, because built-ins run without a trust prompt.
1. **Generated code formats cleanly for any project name.** Do not interpolate `<% PROJECT_NAME %>` into a line that `ruff format` would wrap for longer names. The `cli` template defines an `APP_NAME` constant for this reason: a version line that embedded the name failed `ruff format --check` for names over about 16 characters.
1. **Tool configuration and tool packages declare the tool they need.** Test plugins such as `pytest-cov` go in an `[[optional]]` block with `requires = "pytest"`, so disabling the tool installs none of them.
1. **Development tooling goes in the dev group; the docs group is for the documentation toolchain.** Built-ins declare no `docs_dependencies` at all, because the Zensical module supplies `zensical` and `mkdocstrings`. `uv sync` installs the dev group by default but not docs, so a notebook tool placed in the docs group is removed by the first `just sync`.
1. **A new tool table needs a layout entry.** If a template writes a `[tool.<name>]` that `TOOL_SECTIONS` in `documents/pyproject_layout.py` does not list, it sorts unlabelled after the known tools. See [The pyproject.toml Layout](./pyproject-layout.md).
1. **Tool configuration declares the tool it needs.** A payload that configures `ruff`, `mypy`, `pytest`, or another tool is a table with `requires = "<tool>"`, so disabling the tool leaves none of its configuration behind. Tool-agnostic payloads, such as `[build-system]`, stay plain strings.
1. **Explain decisions in the template file, not the payload.** A comment inside a `[dev.pyproject]` string is copied into every user's `pyproject.toml`. Put maintainer-facing comments above the payload instead.
1. **Web services expose `<package>.main:app`.** The generated `Dockerfile` starts `uvicorn <package>.main:app`. For projects that are not from the `api` template but list FastAPI or Uvicorn, this is the best available guess. If it is wrong for a project, the container fails at start with a clear `ModuleNotFoundError`.

## Adding, Changing, and Retiring a Built-in

**Adding one.** Open an issue that answers the three [admission questions](#admission-criteria) and names the tier. Then:

1. Write `src/protostar/templates/<name>.toml`, following the conventions above.
1. Add it to the `template-hooks-smoke` matrix in `.github/workflows/ci.yml`.
1. Add a `RegressionScenario` to `scripts/run_snapshots.py` and its name to `SCENARIO_FIXTURES` in `tests/test_snapshots.py`, then run `just check-snapshots` and review every generated file by hand.

The contract tests, template discovery, the wizard, shell completion, and the generated template table pick it up automatically.

**Changing one.** Treat a flag flip as a behavior change: it alters what every future user of that template gets. Regenerate snapshots and read the diff, including lock files and generated trees. CI scaffolds only each built-in's default tier, so after changing the other tier, scaffold it with `--tier` and run its gates by hand. When a change tightens a module baseline, update the guard in `tests/test_modules.py` deliberately and check that no template now repeats the new value.

**Retiring one.** Protostar is pre-1.0, so delete cleanly. Do not leave aliases, deprecation shims, or compatibility layers (see `AGENTS.md`).

## How the Contract Is Enforced

Most of the contract is checked by tests, parametrized over discovered built-ins, so a new template is held to it without anyone remembering to add it.

| Rule | Enforced by |
| :--- | :--- |
| All eight quality flags declared explicitly | `test_declares_every_quality_flag_explicitly` |
| Both tiers declared, with the right default | `test_offers_both_tiers_with_its_default` |
| The tiers switch production infrastructure as a whole | `test_tiers_switch_production_infrastructure_as_a_whole` |
| No version pins | `test_dependencies_carry_no_version_pins` |
| Tasks stay within the trusted allowlist | `test_tasks_stay_within_the_trusted_allowlist` |
| The docs group is left to the docs tooling | `test_docs_group_is_left_to_the_docs_tooling` |
| Every rule for template authors, warnings included, planned in both tiers | `test_passes_the_template_check_strictly` |
| Every tool table a template writes has a layout entry | `test_every_tool_table_a_built_in_template_writes_has_a_layout_entry` in `tests/test_pyproject_layout.py` |
| Module baselines stay casual | `test_ruff_module_baseline_stays_casual`, `test_mypy_module_baseline_stays_casual` in `tests/test_modules.py` |
| No trailing whitespace in scaffolded files | `test_builtin_templates_no_trailing_whitespace` in `tests/test_blueprint_loader.py` |
| The `api` Dockerfile targets an importable app | `test_api_dockerfile_targets_an_importable_app` in `tests/test_integration.py` |
| A fresh default scaffold passes its commit hooks | The `template-hooks-smoke` CI job |
| The `cli` and `api` images build and run | The `template-docker-build` CI job |

Unless another file is named, the tests live in `tests/test_builtin_template_contract.py`. The strict template check is the one [`protostar check-template`](../usage/authoring-templates.md#checking-a-template) runs for any author: it covers the name and description, flags that name real tools, payloads that state only the delta from module baselines, and tool configuration and packages bound to their tool with `requires`. It plans a default `init` in each tier, so a tier that cannot be planned fails the contract.

The CI jobs scaffold each built-in's default tier for real. The other tier is planned by the template check and snapshotted for `astro` (production) and `cli` (workbench), but not scaffolded in CI, which keeps the matrix fast. Check it by hand when you change it.

Some conventions rely on review rather than tests: which tier a tool belongs in, the package shapes being installable, and keeping maintainer comments out of payloads.

## Related Pages

- **[Authoring Custom Templates](../usage/authoring-templates.md):** Writing templates for your own team, including the same baseline-and-delta habit.
- **[Templates](../usage/templates.md):** Using built-ins, aliases, and remote templates, and the trust model behind them.
- **[The Module Architecture](../mechanics/modules.md):** How modules declare their baseline into the manifest.
- **[Design Principles](../design-principles.md):** Why baselines live in modules and shape lives in templates.
- **[Testing Architecture & Philosophy](./testing.md):** The unit, integration, and exhaustive tiers behind the enforcement above.
