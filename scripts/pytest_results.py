"""Write explicit per-test evidence for the nightly flaky-test tracker.

Loaded by the pytest action with ``-p scripts.pytest_results``. Each attempt
writes separately, so passing on retry can never count as a clean pass.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


class Results:
    """Collect one pytest attempt, including setup and teardown failures."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.tests: dict[str, str] = {}

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Record failures in any phase, and successful calls or skips."""
        if report.failed:
            self.tests[report.nodeid] = "failed"
        elif self.tests.get(report.nodeid) != "failed":
            if report.skipped:
                self.tests[report.nodeid] = "skipped"
            elif report.when == "call":
                self.tests[report.nodeid] = "passed"

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Only the controller of a normally finished session publishes evidence."""
        if hasattr(session.config, "workerinput") or exitstatus not in (0, 1):
            return
        system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, sys.platform)
        platform = f"{system}-py{sys.version_info.major}.{sys.version_info.minor}"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"platform": platform, "tests": dict(sorted(self.tests.items()))}
            )
            + "\n",
            encoding="utf-8",
        )


def pytest_configure(config: pytest.Config) -> None:
    """Enable evidence only when the action supplies an output path."""
    if target := os.environ.get("PROTOSTAR_TEST_RESULTS"):
        config.pluginmanager.register(Results(Path(target)), "nightly-test-results")
