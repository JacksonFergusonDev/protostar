"""Runs one cost-budget scenario in a fresh interpreter and writes what it cost.

What a run costs depends on what earlier code in the same interpreter cached or
imported, so ``tests/test_cost_budgets.py`` runs each scenario in a process of
its own, through this file:

    python tests/cost_budget_runner.py SCENARIO PROJECT OUTPUT

Commands are faked as the rollback suite's fake runner fakes them, and every
tool counts as installed, so the counts are the same on every host. The caller
sets ``HOME`` and the offline hook registry in the environment.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

# Run as a script, so the repository root goes on the path for ``scripts`` and
# ``tests``, as pytest's ``pythonpath`` puts it there for the suite.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from scripts.benchmarks import probes
from scripts.benchmarks.scenarios import BY_NAME
from tests.rollback_harness import FaultInjector, Runner


def measure(name: str, project: Path) -> dict[str, object]:
    """Runs a scenario's command in ``project`` and returns what it cost.

    Args:
        name: The scenario.
        project: The project the command runs in, already seeded.

    Returns:
        The exit code, the counts by label, and the third-party packages the
        command imported.
    """
    from protostar import system_deps

    scenario = BY_NAME[name]
    with pytest.MonkeyPatch.context() as patches:
        patches.chdir(project)
        # Rollback restores what is on disk; syncing every write only slows the run.
        patches.setattr(os, "fsync", lambda _descriptor: None)
        # Every tool counts as installed, as in the test suite, so the commands
        # a run skips for a missing tool are the same on every host.
        patches.setattr(system_deps, "installed", lambda _executable: True)
        patches.setattr(sys, "argv", ["protostar", *scenario.argv])
        injector = FaultInjector(project.resolve(), Runner.FAKE)
        injector.install(patches)
        before = frozenset(sys.modules)
        code = 0
        with (
            probes.record(commands=False) as recorder,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            from protostar.cli.main import main

            try:
                main()
            except SystemExit as exit_:
                # A message instead of a number exits 1, as the interpreter does.
                code = (
                    exit_.code
                    if isinstance(exit_.code, int)
                    else int(exit_.code is not None)
                )
            recorder.settle()
        imports = probes.imported_packages(before)
    # The fake runner replaces the command seam, and names each command a site.
    commands = Counter(
        site.partition(":")[2].rpartition("#")[0]
        for site in injector.sites
        if site.startswith("command:")
    )
    counts = recorder.counts + Counter(
        {f"command:{label}": count for label, count in commands.items()}
    )
    return {"exit": code, "counts": dict(counts), "imports": imports}


def main() -> None:
    """Measures the scenario named on the command line and writes the result."""
    name, project, output = sys.argv[1:4]
    result = measure(name, Path(project))
    Path(output).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
