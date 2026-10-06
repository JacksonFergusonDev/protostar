"""Counts the faults a rollback run injected, for the metrics dashboard.

Every test marked ``rollback_fault`` raises one fault (an error or an
interrupt, around a write, directory, removal, command, or the commit, or
while a restore fails) and requires the project to come back as it was. With
``--rollback-report PATH`` this plugin writes how many of them passed, and
which failed, per scenario. A run that retries its failures (the nightly's
second pass) updates the same file: a fault that failed and then passed is
moved from the failed list to the passed count, so the report always holds each
fault's last outcome.

A run that stops early (interrupted, or killed) writes nothing, so a missing
report means the result is unknown, never that it passed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.rollback_harness import SCENARIOS

MARKER = "rollback_fault"
_TEMPLATE_BY_SCENARIO = {scenario.name: scenario.template for scenario in SCENARIOS}


def scenario_of(nodeid: str) -> str:
    """Returns the scenario a fault test ran, from its parametrized id.

    Every fault test's id starts with its scenario's name: a case's id is
    ``<scenario>:<site>:<position>:<fault>``, a failed restore's is
    ``<scenario>:<path>``, and a scenario's own id is its name.
    """
    return nodeid.split("[", 1)[1].rstrip("]").split(":", 1)[0]


class RollbackReport:
    """Collects each fault test's outcome and writes the counts when the run ends."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.failed: dict[str, bool] = {}

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Records a fault test's outcome: failed in any phase, or passed its call."""
        if MARKER not in report.keywords or report.skipped:
            return
        if report.failed:
            self.failed[report.nodeid] = True
        elif report.when == "call":
            self.failed.setdefault(report.nodeid, False)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Writes the counts of a run that finished, passing or failing."""
        if hasattr(session.config, "workerinput") or exitstatus not in (
            pytest.ExitCode.OK,
            pytest.ExitCode.TESTS_FAILED,
        ):
            return
        scenarios: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            scenarios = json.loads(self.path.read_text(encoding="utf-8"))["scenarios"]
        for nodeid, failed in sorted(self.failed.items()):
            name = scenario_of(nodeid)
            entry = scenarios.setdefault(
                name,
                {"template": _TEMPLATE_BY_SCENARIO[name], "passed": 0, "failed": []},
            )
            if failed:
                if nodeid not in entry["failed"]:
                    entry["failed"].append(nodeid)
            else:
                entry["passed"] += 1
                if nodeid in entry["failed"]:
                    entry["failed"].remove(nodeid)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"scenarios": dict(sorted(scenarios.items()))}, indent=2) + "\n",
            encoding="utf-8",
        )
