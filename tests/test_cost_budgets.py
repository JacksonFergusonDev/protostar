"""What each command costs, counted exactly and checked in.

Each scenario in ``scripts/benchmarks/scenarios.py`` runs in a fresh interpreter
(``cost_budget_runner.py``) with commands faked as in the rollback suite. The
run's cost is its exit code, every managed command and other process, hook
registry fetch, and YAML, TOML, or JSONC parse by count, and the third-party
packages it imports. It must equal ``cost_budgets/<scenario>.txt``.

Counting needs no clock, so a budget never flakes. A change that adds or
removes a cost fails until the budgets are regenerated with
``--snapshot-update``, so review sees it.
"""

from __future__ import annotations

import difflib
import functools
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.benchmarks import probes
from scripts.benchmarks.scenarios import SCENARIOS, Scenario, Start
from tests.rollback_harness import Runner, Workspace, run
from tests.rollback_harness import Scenario as SeedScenario

BUDGETS = Path(__file__).parent / "cost_budgets"
RUNNER = Path(__file__).parent / "cost_budget_runner.py"
REGENERATE = "uv run pytest tests/test_cost_budgets.py --snapshot-update"


def render(scenario: Scenario, result: dict[str, object]) -> str:
    """Writes a run's cost as its budget file reads.

    Args:
        scenario: The scenario that ran.
        result: What the runner measured.

    Returns:
        The file's text: a header, the exit code, then one cost per line.
    """
    counts = result["counts"]
    imports = result["imports"]
    assert isinstance(counts, dict)
    assert isinstance(imports, list)
    lines = sorted(
        [f"{label} {count}" for label, count in counts.items()]
        + [f"import:{package}" for package in imports]
    )
    header = (
        f"# What `protostar {' '.join(scenario.argv)}` costs.\n"
        f"# Regenerate with: {REGENERATE}\n"
    )
    return header + f"exit {result['exit']}\n" + "".join(f"{line}\n" for line in lines)


def _environment(home: Path) -> dict[str, str]:
    """The runner's environment: an empty home, no registry, no outer repository."""
    from protostar.system import GIT_REPOSITORY_VARIABLES

    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in GIT_REPOSITORY_VARIABLES
        and name not in {"VIRTUAL_ENV", "PROTOSTAR_CONFIG"}
    }
    environment.update(
        HOME=str(home),
        USERPROFILE=str(home),
        # Fallback pins: the same files, and so the same parses, on every host.
        PROTOSTAR_OFFLINE_HOOK_REGISTRY="1",
    )
    return environment


@pytest.fixture(scope="session")
def initialized(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A project the lib template initialized with the fake runner, built once.

    Its installed hooks are made to read as prek's, as a real install leaves
    them: the fake runner writes placeholders no hook manager made, and ``sync``
    would install hooks again over them. The project then has nothing to update.
    """
    from protostar import git_hooks, system_deps
    from protostar.system import GIT_REPOSITORY_VARIABLES
    from protostar.workflows import HookRunner

    root = tmp_path_factory.mktemp("cost-budget-project")
    start = SeedScenario("lib", "empty")
    workspace = Workspace.seed(root, start, Runner.FAKE, root / "cache")
    with pytest.MonkeyPatch.context() as patches:
        for name in GIT_REPOSITORY_VARIABLES:
            patches.delenv(name, raising=False)
        patches.setattr(system_deps, "installed", lambda _executable: True)
        outcome = run(workspace, start, Runner.FAKE, patches)
    assert outcome.code == 0, outcome.payload
    hooks = sorted((workspace.project / git_hooks.HOOKS_DIR).iterdir())
    assert hooks, "the fake init installed no hooks"
    for hook in hooks:
        hook.write_text(
            f"#!/bin/sh\n{git_hooks._MARKERS[HookRunner.PREK]}\n", encoding="utf-8"
        )
        assert git_hooks.generator(hook) is HookRunner.PREK
    return workspace.project


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
def test_a_command_costs_what_its_budget_records(
    scenario: Scenario, tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    project = tmp_path / "project"
    if scenario.start is Start.INITIALIZED:
        shutil.copytree(request.getfixturevalue("initialized"), project, symlinks=True)
    else:
        project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    output = tmp_path / "cost.json"

    process = subprocess.run(
        [sys.executable, str(RUNNER), scenario.name, str(project), str(output)],
        env=_environment(home),
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert process.returncode == 0, process.stderr
    measured = render(scenario, json.loads(output.read_text(encoding="utf-8")))
    budget = BUDGETS / f"{scenario.name}.txt"
    if request.config.getoption("--snapshot-update"):
        budget.write_text(measured, encoding="utf-8")
        return
    recorded = budget.read_text(encoding="utf-8") if budget.exists() else ""
    if measured != recorded:
        difference = "".join(
            difflib.unified_diff(
                recorded.splitlines(keepends=True),
                measured.splitlines(keepends=True),
                f"tests/cost_budgets/{budget.name} (recorded)",
                "this run (measured)",
            )
        )
        pytest.fail(
            f"`protostar {' '.join(scenario.argv)}` no longer costs what its "
            f"budget records:\n\n{difference}\nIf the change is intended, "
            f"regenerate the budgets with `{REGENERATE}` and say why in the "
            "pull request.",
            pytrace=False,
        )


def test_every_budget_names_a_scenario() -> None:
    """A removed scenario takes its budget with it."""
    recorded = {budget.stem for budget in BUDGETS.glob("*.txt")}

    assert recorded == {scenario.name for scenario in SCENARIOS}


@pytest.mark.parametrize(
    ("module", "attribute"), probes.SEAMS, ids=lambda part: str(part)
)
def test_every_seam_the_probes_wrap_still_exists(module: str, attribute: str) -> None:
    """A moved seam fails here instead of leaving a budget counting nothing."""
    owner = importlib.import_module(module)
    parent = functools.reduce(getattr, attribute.split(".")[:-1], owner)

    assert hasattr(parent, attribute.rpartition(".")[2])
