"""The split between pull-request and nightly platforms, and the nightly report."""

import itertools
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from scripts.nightly_report import (
    FAILING,
    GATE_JOB,
    GhCli,
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


def yaml_workflow(workflow: str) -> dict[str, Any]:
    return YAML(typ="safe").load((WORKFLOWS / workflow).read_text(encoding="utf-8"))


def jobs(workflow: str) -> dict[str, Any]:
    return yaml_workflow(workflow)["jobs"]


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
    assert [
        (t["os"], t["python"]) for t in PULL_REQUEST["tests"] if t.get("coverage")
    ] == [("ubuntu-latest", "3.14")]
    assert not [t for t in NIGHTLY["tests"] if t.get("coverage")]


def test_the_linux_pull_request_jobs_split_every_rollback_fault():
    # Cheap with commands faked on Linux; everywhere else runs the PR scope.
    shards = sorted(
        (entry["os"], entry["rollback"])
        for entry in PULL_REQUEST["tests"]
        if entry.get("rollback")
    )
    assert shards == [("ubuntu-latest", f"{i}/3") for i in (1, 2, 3)]


def test_rollback_slices_cover_every_test_exactly_once():
    import subprocess
    import sys

    def collect(*options: str) -> list[str]:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_rollback.py",
                "--co",
                "-q",
                "-p",
                "no:randomly",
                "--rollback-scope",
                "full",
                *options,
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        )
        return [line for line in result.stdout.splitlines() if "::" in line]

    whole = collect()
    slices = [collect("--rollback-shard", f"{i}/3") for i in (1, 2, 3)]
    assert sorted(test for part in slices for test in part) == sorted(whole)
    assert all(len(part) > len(whole) / 4 for part in slices)


def test_a_pull_request_stays_within_the_accounts_runner_limits():
    # The account runs 20 jobs at a time, five of them on macOS, across every
    # open PR and push. Three leave room for a second run on macOS.
    assert job_count("ci.yml") <= 20
    assert macos_jobs(PULL_REQUEST) <= 3


def test_ci_checks_stacked_pull_requests_without_filtering_their_base_branch():
    trigger = yaml_workflow("ci.yml")["on"]
    assert "pull_request" in trigger
    assert trigger["pull_request"] is None
    assert trigger["push"]["branches"] == ["main", "renovate/**"]


def test_nightly_fails_every_template_at_every_site_on_every_os():
    """Scheduled runs have no runner limit: a job per template, six on Windows."""
    from scripts.nightly_matrix import rollback_matrix

    rollback = job("nightly.yml", "rollback")
    assert "needs.select.outputs.rollback" in rollback["strategy"]["matrix"]
    runs = {
        (entry["os"], entry["template"], entry["slice"])
        for entry in rollback_matrix()["include"]
    }
    assert runs == {
        (os, template, f"{part}/{count}")
        for os in OPERATING_SYSTEMS
        for template in built_in_templates()
        for count in [6 if os == "windows-latest" else 1]
        for part in range(1, count + 1)
    }


def test_a_manual_nightly_can_narrow_the_rollback_jobs():
    from scripts.nightly_matrix import rollback_matrix

    jobs = rollback_matrix("windows-latest", "cli")["include"]
    assert [(j["os"], j["template"]) for j in jobs] == [("windows-latest", "cli")] * 6
    assert {j["slice"] for j in jobs} == {f"{part}/6" for part in range(1, 7)}
    rollback = job("nightly.yml", "rollback")
    (step,) = [
        s for s in rollback["steps"] if s.get("uses") == "./.github/actions/pytest"
    ]
    args = step["with"]["args"].split()
    assert "tests/test_rollback.py" in args
    assert args[args.index("--rollback-scope") + 1] == "full"
    assert args[args.index("--rollback-real") + 1] == "all"


def test_windows_rollback_jobs_run_one_environment_at_a_time():
    step = next(
        s
        for s in job("nightly.yml", "rollback")["steps"]
        if s.get("uses") == "./.github/actions/pytest"
    )
    assert (
        step["with"]["workers"]
        == "${{ matrix.os == 'windows-latest' && '1' || 'auto' }}"
    )
    action = YAML(typ="safe").load(
        (REPO_ROOT / ".github/actions/pytest/action.yml").read_text()
    )
    assert action["inputs"]["workers"]["default"] == "auto"
    run = action["runs"]["steps"][0]
    assert run["env"]["WORKERS"] == "${{ inputs.workers }}"
    assert '-n "$WORKERS"' in run["run"]


def test_every_rollback_job_uploads_its_fault_report_even_when_it_fails():
    rollback = job("nightly.yml", "rollback")
    (run,) = [
        s for s in rollback["steps"] if s.get("uses") == "./.github/actions/pytest"
    ]
    args = run["with"]["args"].split()
    assert args[args.index("--rollback-report") + 1] == "rollback-report/report.json"
    (upload,) = [s for s in rollback["steps"] if "upload-artifact" in s.get("uses", "")]
    assert upload["name"] == "Upload the fault report"
    assert upload["with"]["name"] == "${{ matrix.artifact }}"
    assert upload["with"]["path"] == "rollback-report/report.json"
    assert upload["if"] == "${{ !cancelled() }}"


def test_rollback_metrics_are_recorded_apart_from_nightly_for_scheduled_and_manual_runs():
    """A publishing failure must not fail the run a release requires."""
    workflow = yaml_workflow("rollback-metrics.yml")
    trigger = workflow["on"]["workflow_run"]
    assert trigger["workflows"] == ["Nightly"]
    assert "rollback-metrics.yml" not in (WORKFLOWS / "nightly.yml").read_text()
    record = workflow["jobs"]["record"]
    assert '"schedule", "workflow_dispatch"' in record["if"]
    assert "head_branch == 'main'" in record["if"]
    assert record["permissions"]["contents"] == "write"
    (download,) = [
        s for s in record["steps"] if "download-artifact" in s.get("uses", "")
    ]
    assert download["with"]["pattern"] == "rollback-*"
    assert download["with"]["run-id"] == "${{ github.event.workflow_run.id }}"
    (step,) = [s for s in record["steps"] if s.get("id") == "record"]
    # Only a manual run may end quietly when the matrix was narrowed.
    assert 'EVENT" == workflow_dispatch' in step["run"]
    assert workflow["jobs"]["publish-pages"]["uses"] == "./.github/workflows/pages.yml"
    assert workflow["jobs"]["refresh-site"]["needs"] == "publish-pages"


def test_benchmarks_run_apart_from_nightly_so_a_slowdown_never_blocks_a_release():
    workflow = yaml_workflow("benchmark.yml")
    assert workflow["on"]["schedule"]
    assert "benchmark" not in (WORKFLOWS / "nightly.yml").read_text()
    measure = workflow["jobs"]["measure"]
    assert measure["strategy"]["matrix"] == "${{ fromJSON(needs.plan.outputs.matrix) }}"
    (compare,) = [
        s for s in measure["steps"] if "scripts.benchmarks compare" in s.get("run", "")
    ]
    assert '"$BASELINE" --all' in compare["run"]
    (upload,) = [s for s in measure["steps"] if "upload-artifact" in s.get("uses", "")]
    assert upload["with"]["name"] == "${{ matrix.artifact }}"
    assert upload["if"] == "${{ !cancelled() }}"


def test_a_pull_request_is_benchmarked_only_when_labelled_and_never_recorded():
    """A labelled pull request takes one runner at a time and only gets a comment."""
    from scripts.benchmarks.report import plan

    workflow = yaml_workflow("benchmark.yml")
    assert workflow["on"]["pull_request"]["types"] == ["labeled"]
    assert (
        "github.event.label.name == 'run-benchmark'" in workflow["jobs"]["plan"]["if"]
    )
    assert [job["os"] for job in plan("pull_request", "a" * 40, base="b" * 40)] == [
        "ubuntu-latest"
    ]
    jobs = workflow["jobs"]
    assert "github.event_name == 'pull_request'" in jobs["comment"]["if"]
    for name in ("record", "calibration"):
        assert "pull_request" not in jobs[name]["if"]


def test_only_a_complete_comparison_on_main_is_recorded_and_published():
    jobs = yaml_workflow("benchmark.yml")["jobs"]
    record = jobs["record"]
    assert "needs.measure.result == 'success'" in record["if"]
    assert "github.ref == 'refs/heads/main'" in record["if"]
    assert "!inputs.calibrate" in record["if"]
    assert record["permissions"] == {"contents": "write", "issues": "write"}
    (download,) = [
        s for s in record["steps"] if "download-artifact" in s.get("uses", "")
    ]
    assert download["with"]["pattern"] == "benchmarks-*"
    (issue,) = [s for s in record["steps"] if "report issue" in s.get("run", "")]
    assert issue["if"] == "steps.record.outputs.published == 'true'"
    assert jobs["publish-pages"]["uses"] == "./.github/workflows/pages.yml"
    assert "inputs.calibrate" in jobs["calibration"]["if"]


def test_a_pull_request_is_never_failed_by_a_timing():
    """Timing varies by runner; the cost budgets are the pull request's check."""
    ci = (WORKFLOWS / "ci.yml").read_text()
    assert "hyperfine" not in ci
    assert "github-action-benchmark" not in ci


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
        self.bodies: dict[int, list[str]] = {}
        self.tracked: list[Run] = []

    def jobs(self, run):
        return self._jobs

    def flaky_lists(self, run):
        return self._flaky

    def track_tests(self, run):
        self.tracked.append(run)

    def last_passing_sha(self, run):
        return self._last_passing

    def open_issue(self, tracker: Tracker):
        return self._open.get(tracker.label)

    def create_issue(self, tracker, body):
        self.calls.append(("create", tracker.label, body))
        number = len(self._open) + 100
        self._open[tracker.label] = number
        self.bodies[number] = [body]

    def has_report(self, number, body):
        return body in self.bodies.get(number, [])

    def comment(self, number, body):
        self.calls.append(("comment", number, body))
        self.bodies.setdefault(number, []).append(body)

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


@pytest.mark.parametrize("selected", [False, True])
def test_a_skipped_run_files_nothing(selected):
    github = FakeGitHub(
        [
            Job(GATE_JOB, "success"),
            *([Job("Select rollback jobs", "success")] if selected else []),
            Job("Platforms", "skipped"),
            Job("Rollback", "skipped"),
        ],
        open_issues={FAILING.label: 7},
    )
    assert not report(github, RUN).ran
    assert github.calls == []
    assert github.tracked == []


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


@pytest.mark.parametrize("preparation", [GATE_JOB, "Select rollback jobs"])
def test_a_failed_preparation_is_reported_even_when_every_check_skips(preparation):
    github = FakeGitHub([Job(preparation, "failure"), Job("Platforms", "skipped")])
    outcome = report(github, RUN)
    assert outcome.ran
    assert outcome.failed == (preparation,)
    assert github.calls[0][:2] == ("create", FAILING.label)


@pytest.mark.parametrize("open_issues", [{}, {FAILING.label: 7}])
def test_a_pass_closes_the_open_failure_issue(open_issues):
    github = FakeGitHub(PASSED, open_issues=open_issues)
    report(github, RUN)
    assert [call[:2] for call in github.calls] == (
        [("close", 7)] if open_issues else []
    )


def test_flaky_tests_are_handed_to_the_per_test_tracker_even_when_the_run_passes():
    github = FakeGitHub(PASSED, flaky={"flaky-tests-windows-py3.14": "t::a\n"})
    assert report(github, RUN).flaky == {"t::a": ("windows-py3.14",)}
    assert github.calls == []
    assert github.tracked == [RUN]


def test_summarize_ignores_blank_lines_in_flaky_lists():
    outcome = summarize(PASSED, {"flaky-tests-ubuntu-latest-py3.12": "\n t::a \n\n"})
    assert outcome.flaky == {"t::a": ("ubuntu-latest-py3.12",)}


@pytest.mark.parametrize("existing", [False, True], ids=["new-issue", "open-issue"])
def test_reporting_the_same_run_twice_does_not_repeat_its_report(existing):
    github = FakeGitHub(
        FAILED,
        open_issues={FAILING.label: 7} if existing else {},
    )
    report(github, RUN)
    first = list(github.calls)
    report(github, RUN)
    assert github.calls == first
    report(github, Run(repo=RUN.repo, run_id="43", sha=RUN.sha))
    assert len(github.calls) == len(first) * 2


@pytest.mark.parametrize("location", ["body", "first-page", "second-page", "absent"])
def test_report_lookup_reads_the_issue_body_and_every_comment_page(
    monkeypatch, location
):
    github = GhCli("owner/name")
    responses = iter(
        [
            {"body": "report\n" if location == "body" else "other run"},
            [
                [{"body": "report" if location == "first-page" else "other run"}],
                [{"body": "report" if location == "second-page" else "other run"}],
            ],
        ]
    )
    calls = []

    def gh(*args):
        calls.append(args)
        return json.dumps(next(responses))

    monkeypatch.setattr(github, "_gh", gh)
    assert github.has_report(9, "report\n") == (location != "absent")
    assert calls[-1] == (
        "api",
        "repos/owner/name/issues/9/comments?per_page=100",
        "--paginate",
        "--slurp",
    )


@pytest.mark.skipif(sys.platform == "win32", reason="The gate runs in bash")
@pytest.mark.parametrize(
    ("last", "pending", "changed"),
    [("same", "0", False), ("same", "1", True), ("older", "0", True)],
)
def test_scheduled_nightly_keeps_running_while_a_fix_awaits_verification(
    tmp_path, last, pending, changed
):
    import os
    import shutil
    import subprocess
    import sys

    gate = job("nightly.yml", "gate")
    assert gate["permissions"]["issues"] == "read"
    step = gate["steps"][0]
    gh = tmp_path / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "if sys.argv[1:3] == ['run', 'list']:\n"
        "    print(os.environ['LAST'])\n"
        "else:\n"
        "    assert sys.argv[1:3] == ['issue', 'list'], sys.argv\n"
        "    assert sys.argv[sys.argv.index('--label') + 1] == 'awaiting-verification'\n"
        "    print(os.environ['PENDING'])\n"
    )
    gh.chmod(0o755)
    output = tmp_path / "output"
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(
        [bash, "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            "REPO": "owner/repo",
            "GITHUB_SHA": "same",
            "GITHUB_OUTPUT": str(output),
            "LAST": last,
            "PENDING": pending,
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output.read_text() == f"changed={str(changed).lower()}\n"
