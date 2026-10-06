"""The split between pull-request and nightly platforms, and the nightly report."""

import itertools
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from scripts.nightly_report import (
    FAILING,
    FLAKY,
    GATE_JOB,
    Job,
    Run,
    Tracker,
    report,
    summarize,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github/workflows"
OPERATING_SYSTEMS = {"ubuntu-latest", "macos-latest", "windows-latest"}

Entry = dict[str, Any]


def expand(matrix: dict[str, Any]) -> list[Entry]:
    """Expands a strategy matrix the way GitHub Actions does.

    An `include` entry extends each original combination it can join without
    changing one of that combination's values, and is added as its own
    combination when it joins none.
    """
    axes = {key: values for key, values in matrix.items() if key != "include"}
    original = [
        dict(zip(axes, values, strict=True))
        for values in itertools.product(*axes.values())
    ]
    combinations = [dict(entry) for entry in original]
    for extra in matrix.get("include", []):
        joined = False
        for base, combination in zip(
            original, combinations[: len(original)], strict=True
        ):
            if all(base.get(key, value) == value for key, value in extra.items()):
                combination.update(extra)
                joined = True
        if not joined:
            combinations.append(dict(extra))
    return combinations


def jobs(workflow: str) -> dict[str, Any]:
    return YAML(typ="safe").load((WORKFLOWS / workflow).read_text(encoding="utf-8"))[
        "jobs"
    ]


def job(workflow: str, name: str) -> dict[str, Any]:
    return jobs(workflow)[name]


def platforms(workflow: str, name: str = "platforms") -> dict[str, list[Entry]]:
    """The expanded `tests` and `smoke` matrices a job hands to platforms.yml."""
    caller = job(workflow, name)
    assert caller["uses"] == "./.github/workflows/platforms.yml"
    return {
        kind: expand(json.loads(caller["with"][kind])) if kind in caller["with"] else []
        for kind in ("tests", "smoke")
    }


def platform(entry: Entry) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted((k, v) for k, v in entry.items() if k in ("os", "python")))


def smoke_runs(matrices: dict[str, list[Entry]]) -> list[tuple[str, str, str]]:
    """Each template a run scaffolds, by OS and Python, in smoke and test jobs."""
    return [
        (entry["os"], entry["python"], template)
        for entry in matrices["smoke"]
        for template in entry["templates"]
    ] + [
        (entry["os"], entry["python"], template)
        for entry in matrices["tests"]
        for template in entry.get("smoke", [])
    ]


def job_count(workflow: str) -> int:
    """How many jobs a run of the workflow starts at once."""
    count = 0
    for name, spec in jobs(workflow).items():
        if spec.get("uses") == "./.github/workflows/platforms.yml":
            count += sum(map(len, platforms(workflow, name).values()))
        elif "strategy" in spec:
            count += len(expand(spec["strategy"]["matrix"]))
        else:
            count += 1
    return count


def macos_jobs(matrices: dict[str, list[Entry]]) -> int:
    return sum(
        entry["os"] == "macos-latest" for kind in matrices.values() for entry in kind
    )


def supported_pythons() -> list[str]:
    classifiers = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["project"][
        "classifiers"
    ]
    versions = {
        match.group(1)
        for c in classifiers
        if (match := re.fullmatch(r"Programming Language :: Python :: (3\.\d+)", c))
    }
    return sorted(versions, key=lambda v: tuple(map(int, v.split("."))))


def built_in_templates() -> set[str]:
    return {
        path.stem for path in (REPO_ROOT / "src/protostar/templates").glob("*.toml")
    }


PULL_REQUEST = platforms("ci.yml")
NIGHTLY = platforms("nightly.yml")
RELEASE = platforms("release.yml", "smoke")
EVERY_PLATFORM = sorted(
    platform({"os": os, "python": python})
    for os in OPERATING_SYSTEMS
    for python in supported_pythons()
)


def test_expand_follows_github_include_rules():
    assert expand(
        {
            "os": ["a", "b"],
            "python": ["1"],
            "include": [{"os": "a", "python": "1", "coverage": True}, {"os": "c"}],
        }
    ) == [
        {"os": "a", "python": "1", "coverage": True},
        {"os": "b", "python": "1"},
        {"os": "c"},
    ]


@pytest.mark.parametrize("matrices", [PULL_REQUEST, NIGHTLY], ids=["pr", "nightly"])
def test_pull_requests_and_nightly_each_test_every_os_and_python(matrices):
    assert sorted(map(platform, matrices["tests"])) == EVERY_PLATFORM


def test_pull_requests_and_nightly_together_smoke_test_every_template_once():
    assert sorted(smoke_runs(PULL_REQUEST) + smoke_runs(NIGHTLY)) == sorted(
        (os, python, template)
        for os in OPERATING_SYSTEMS
        for python in supported_pythons()
        for template in built_in_templates()
    )


def test_pull_requests_smoke_test_every_template_on_every_os():
    assert {(os, template) for os, _, template in smoke_runs(PULL_REQUEST)} == {
        (os, template) for os in OPERATING_SYSTEMS for template in built_in_templates()
    }


def test_pull_requests_smoke_test_every_template_at_every_python_on_linux():
    assert {
        (python, template)
        for os, python, template in smoke_runs(PULL_REQUEST)
        if os == "ubuntu-latest"
    } == {
        (python, template)
        for python in supported_pythons()
        for template in built_in_templates()
    }


def test_one_pull_request_job_reports_coverage():
    assert [t for t in PULL_REQUEST["tests"] if t.get("coverage")] == [
        {"os": "ubuntu-latest", "python": "3.14", "coverage": True}
    ]
    assert not [t for t in NIGHTLY["tests"] if t.get("coverage")]


def test_a_pull_request_stays_within_the_accounts_runner_limits():
    # The account runs 20 jobs at a time, five of them on macOS, across every
    # open PR and push. Three leave room for a second run on macOS.
    assert job_count("ci.yml") <= 20
    assert macos_jobs(PULL_REQUEST) <= 3


def test_nightly_fails_every_template_at_every_site_on_every_os():
    """Scheduled runs have no runner limit, so each template gets its own job."""
    rollback = job("nightly.yml", "rollback")
    runs = {
        (entry["os"], entry["template"])
        for entry in expand(rollback["strategy"]["matrix"])
    }
    assert runs == {
        (os, template) for os in OPERATING_SYSTEMS for template in built_in_templates()
    }
    (step,) = [
        s for s in rollback["steps"] if s.get("uses") == "./.github/actions/pytest"
    ]
    args = step["with"]["args"].split()
    assert "tests/test_rollback.py" in args
    assert args[args.index("--rollback-scope") + 1] == "full"
    assert args[args.index("--rollback-real") + 1] == "all"


def test_a_release_smoke_tests_the_wheel_it_publishes_on_every_os():
    smoke = job("release.yml", "smoke")
    assert smoke["needs"] == "build"
    assert smoke["with"]["wheel-artifact"] == "dist"
    assert {e["os"] for e in RELEASE["smoke"]} == OPERATING_SYSTEMS
    assert RELEASE["tests"] == []


def test_a_release_publishes_only_after_ci_nightly_and_its_smoke_test_pass():
    assert set(job("release.yml", "publish")["needs"]) == {
        "build",
        "checks-passed",
        "smoke",
    }
    gate = job("release.yml", "checks-passed")["steps"][-1]["run"]
    assert "for workflow in ci.yml nightly.yml" in gate


class FakeGitHub:
    def __init__(self, jobs, flaky=None, open_issues=None, last_passing="a" * 40):
        self._jobs = jobs
        self._flaky = flaky or {}
        self._open = dict(open_issues or {})
        self._last_passing = last_passing
        self.calls: list[tuple[str, object, str]] = []

    def jobs(self, run):
        return self._jobs

    def flaky_lists(self, run):
        return self._flaky

    def last_passing_sha(self, run):
        return self._last_passing

    def open_issue(self, tracker: Tracker):
        return self._open.get(tracker.label)

    def create_issue(self, tracker, body):
        self.calls.append(("create", tracker.label, body))

    def comment(self, number, body):
        self.calls.append(("comment", number, body))

    def close(self, number, body):
        self.calls.append(("close", number, body))


RUN = Run(repo="owner/name", run_id="42", sha="b" * 40)
PASSED = [
    Job(GATE_JOB, "success"),
    Job("Platforms / Test on macos-latest / Python 3.13", "success"),
]
FAILED = [
    Job(GATE_JOB, "success"),
    Job("Platforms / Test on macos-latest / Python 3.13", "failure"),
    Job("Platforms / Template Hooks Smoke (windows-latest / api)", "success"),
]


def test_a_skipped_run_files_nothing():
    github = FakeGitHub(
        [Job(GATE_JOB, "success"), Job("Platforms", "skipped")],
        open_issues={FAILING.label: 7},
    )
    assert not report(github, RUN).ran
    assert github.calls == []


def test_a_failure_opens_an_issue_with_the_failing_jobs_and_commit_range():
    github = FakeGitHub(FAILED)
    report(github, RUN)
    [(action, label, body)] = github.calls
    assert (action, label) == ("create", FAILING.label)
    assert "- Platforms / Test on macos-latest / Python 3.13" in body
    assert "Smoke" not in body
    assert f"https://github.com/owner/name/compare/{'a' * 40}...{'b' * 40}" in body


def test_a_failure_with_no_earlier_pass_says_so():
    github = FakeGitHub(FAILED, last_passing=None)
    report(github, RUN)
    assert "No earlier nightly run has passed." in github.calls[0][2]


def test_a_repeated_failure_comments_on_the_open_issue():
    github = FakeGitHub(FAILED, open_issues={FAILING.label: 7})
    report(github, RUN)
    assert [call[:2] for call in github.calls] == [("comment", 7)]


def test_a_failed_gate_counts_as_a_failure():
    github = FakeGitHub([Job(GATE_JOB, "failure"), *PASSED[1:]])
    assert report(github, RUN).failed == (GATE_JOB,)


@pytest.mark.parametrize("open_issues", [{}, {FAILING.label: 7}])
def test_a_pass_closes_the_open_failure_issue(open_issues):
    github = FakeGitHub(PASSED, open_issues=open_issues)
    report(github, RUN)
    assert [call[:2] for call in github.calls] == (
        [("close", 7)] if open_issues else []
    )


def test_flaky_tests_are_filed_apart_from_failures_even_when_the_run_passes():
    flaky = {
        "flaky-tests-macos-latest-py3.13": "tests/test_tui.py::test_a\n",
        "flaky-tests-windows-latest-py3.13": "tests/test_tui.py::test_a\ntests/test_tui.py::test_b\n",
    }
    github = FakeGitHub(PASSED, flaky=flaky, open_issues={FAILING.label: 7})
    report(github, RUN)
    assert [call[:2] for call in github.calls] == [
        ("close", 7),
        ("create", FLAKY.label),
    ]
    body = github.calls[1][2]
    assert (
        "- `tests/test_tui.py::test_a` (macos-latest-py3.13, windows-latest-py3.13)"
        in body
    )
    assert "- `tests/test_tui.py::test_b` (windows-latest-py3.13)" in body


def test_flaky_tests_comment_on_the_open_flaky_issue():
    github = FakeGitHub(
        PASSED,
        flaky={"flaky-tests-macos-latest-py3.13": "tests/test_x.py::test_y\n"},
        open_issues={FLAKY.label: 9},
    )
    report(github, RUN)
    assert [call[:2] for call in github.calls] == [("comment", 9)]


def test_summarize_ignores_blank_lines_in_flaky_lists():
    outcome = summarize(PASSED, {"flaky-tests-ubuntu-latest-py3.12": "\n t::a \n\n"})
    assert outcome.flaky == {"t::a": ("ubuntu-latest-py3.12",)}
