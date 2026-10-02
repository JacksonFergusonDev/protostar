"""The split between pull-request and nightly platforms, and the nightly report."""

import json
import re
import tomllib
from pathlib import Path

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


def platforms(workflow: str) -> dict[str, list[dict[str, object]]]:
    """The `tests` and `smoke` lists a workflow hands to platforms.yml."""
    jobs = YAML(typ="safe").load((WORKFLOWS / workflow).read_text(encoding="utf-8"))[
        "jobs"
    ]
    inputs = jobs["platforms"]["with"]
    assert jobs["platforms"]["uses"] == "./.github/workflows/platforms.yml"
    return {name: json.loads(inputs[name]) for name in ("tests", "smoke")}


def supported_pythons() -> set[str]:
    classifiers = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["project"][
        "classifiers"
    ]
    return {
        match.group(1)
        for c in classifiers
        if (match := re.fullmatch(r"Programming Language :: Python :: (3\.\d+)", c))
    }


def built_in_templates() -> set[str]:
    return {
        path.stem for path in (REPO_ROOT / "src/protostar/templates").glob("*.toml")
    }


PULL_REQUEST = platforms("ci.yml")
NIGHTLY = platforms("nightly.yml")


def test_every_os_and_python_is_tested_by_pull_requests_or_nightly():
    tested = [(t["os"], t["python"]) for t in PULL_REQUEST["tests"] + NIGHTLY["tests"]]
    assert sorted(tested) == sorted(
        (os, python) for os in OPERATING_SYSTEMS for python in supported_pythons()
    )


def test_pull_requests_test_every_os_at_the_oldest_and_newest_python():
    pythons = sorted(supported_pythons(), key=lambda v: tuple(map(int, v.split("."))))
    tested = {(t["os"], t["python"]) for t in PULL_REQUEST["tests"]}
    assert {
        (os, python) for os in OPERATING_SYSTEMS for python in (pythons[0], pythons[-1])
    } <= tested


def test_one_pull_request_job_reports_coverage():
    assert [t for t in PULL_REQUEST["tests"] if t.get("coverage")] == [
        {"os": "ubuntu-latest", "python": "3.14", "coverage": True}
    ]
    assert not [t for t in NIGHTLY["tests"] if t.get("coverage")]


def test_pull_requests_smoke_test_every_built_in_template_on_linux():
    on_linux = {
        s["template"] for s in PULL_REQUEST["smoke"] if s["os"] == "ubuntu-latest"
    }
    assert on_linux == built_in_templates()


def test_nightly_repeats_no_pull_request_platform():
    def key(entry):
        return tuple(sorted((k, v) for k, v in entry.items() if k != "coverage"))

    for kind in ("tests", "smoke"):
        assert not {key(e) for e in PULL_REQUEST[kind]} & {
            key(e) for e in NIGHTLY[kind]
        }


def test_pull_requests_stay_within_two_macos_jobs():
    # The account runs five macOS jobs at a time across every open PR and push.
    macos = [
        e
        for kind in ("tests", "smoke")
        for e in PULL_REQUEST[kind]
        if e["os"] == "macos-latest"
    ]
    assert len(macos) <= 2


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
