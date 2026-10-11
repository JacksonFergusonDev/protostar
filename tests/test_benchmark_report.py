"""The nightly benchmark record: baselines, verdicts, regressions, and comments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts._publish import PublicationError
from scripts.benchmarks import report
from scripts.benchmarks.report import BenchmarkReportError, Status

HEAD = "a" * 40
BEFORE = "b" * 40
OLDER = "c" * 40
STEADY = [0.50, 0.51, 0.49, 0.50, 0.52, 0.48, 0.50, 0.51]


def samples(cpu: list[float]) -> dict[str, list[float]]:
    """One version's samples, with only CPU time varying between tests."""
    return {
        "wall": [1.0] * len(cpu),
        "protostar": [0.6] * len(cpu),
        "cpu": cpu,
        "commands": [0.4] * len(cpu),
    }


def write_result(
    results: Path,
    os: str,
    *,
    commit: str = HEAD,
    against: str = BEFORE,
    candidate: list[float] | None = None,
    artifact: str | None = None,
) -> None:
    """Writes one job's comparison, as the harness does."""
    folder = results / (artifact or f"benchmarks-{os}")
    folder.mkdir(parents=True)
    result = {
        "machine": {"commit": commit, "python": "3.14.0", "platform": "Linux-x86_64"},
        "mode": "compare",
        "baseline": against,
        "runs": len(STEADY),
        "samples": {
            "sync": {
                "baseline": samples(STEADY),
                "candidate": samples(candidate or STEADY),
            }
        },
    }
    (folder / "benchmarks.json").write_text(json.dumps(result), encoding="utf-8")


def entry(
    os: str, commit: str, against: str, status: Status = Status.STEADY
) -> dict[str, Any]:
    return {
        "commit": commit,
        "baseline": against,
        "date": "2026-10-01T00:00:00+00:00",
        "run_id": "1",
        "os": os,
        "scenarios": {"sync": {"status": str(status)}},
    }


SLOWER = [value * 1.2 for value in STEADY]


def test_a_pull_request_is_compared_with_its_base_on_one_runner() -> None:
    assert report.plan("pull_request", HEAD, base=BEFORE) == [
        {
            "os": "ubuntu-latest",
            "baseline": BEFORE,
            "artifact": "benchmarks-ubuntu-latest",
        }
    ]


def test_a_calibration_compares_the_commit_with_itself_repeatedly() -> None:
    jobs = report.plan("workflow_dispatch", HEAD, repeats=2)

    assert {job["baseline"] for job in jobs} == {HEAD}
    assert [job["artifact"] for job in jobs] == [
        "benchmarks-ubuntu-latest-1",
        "benchmarks-ubuntu-latest-2",
    ]


def test_the_first_night_compares_the_commit_with_itself() -> None:
    jobs = report.plan("schedule", HEAD)

    assert [(job["os"], job["baseline"]) for job in jobs] == [
        ("ubuntu-latest", HEAD),
    ]


def test_a_night_compares_with_the_last_recorded_commit_and_skips_one_already_recorded() -> (
    None
):
    history = [
        entry("ubuntu-latest", BEFORE, OLDER),
        entry("macos-latest", HEAD, BEFORE),
    ]

    jobs = report.plan("schedule", HEAD, history=history)

    assert [(job["os"], job["baseline"]) for job in jobs] == [("ubuntu-latest", BEFORE)]
    assert report.plan("schedule", BEFORE, history=history) == []


def test_a_suspect_keeps_its_baseline_so_the_next_night_measures_the_same_change() -> (
    None
):
    """Even with no new commit, a suspect is measured again before it counts."""
    history = [entry("ubuntu-latest", HEAD, BEFORE, Status.SUSPECT)]

    (job,) = report.plan("schedule", HEAD, history=history)

    assert (job["os"], job["baseline"]) == ("ubuntu-latest", BEFORE)


def test_a_baseline_no_longer_behind_the_commit_is_dropped() -> None:
    history = [entry("ubuntu-latest", BEFORE, OLDER)]

    (job,) = report.plan(
        "schedule", HEAD, history=history, is_ancestor=lambda _ancestor, _commit: False
    )

    assert job["baseline"] == HEAD


def test_a_pull_request_run_needs_its_base() -> None:
    with pytest.raises(BenchmarkReportError, match="needs its base"):
        report.plan("pull_request", HEAD)


@pytest.mark.parametrize(
    ("low", "high", "status"),
    [
        (0.95, 1.05, Status.STEADY),
        (1.05, 1.15, Status.STEADY),
        (1.10, 1.20, Status.SUSPECT),
        (0.80, 0.90, Status.FASTER),
    ],
)
def test_only_a_whole_interval_past_the_threshold_counts(
    low: float, high: float, status: Status
) -> None:
    change = {"ratio": (low + high) / 2, "low": low, "high": high}

    assert report.classify(change, "sync", BEFORE, None) is status


def test_a_slowdown_is_a_regression_only_when_found_again_against_the_same_baseline() -> (
    None
):
    slower = {"ratio": 1.2, "low": 1.15, "high": 1.25}
    suspect = entry("ubuntu-latest", HEAD, BEFORE, Status.SUSPECT)

    assert report.classify(slower, "sync", BEFORE, suspect) is Status.REGRESSION
    assert report.classify(slower, "sync", OLDER, suspect) is Status.SUSPECT
    assert report.classify(slower, "status", BEFORE, suspect) is Status.SUSPECT


def test_two_nights_confirm_a_slowdown_and_then_move_the_baseline_on(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    write_result(first, "ubuntu-latest", candidate=SLOWER)
    history, regressions = report.record(
        first, [], commit=HEAD, date="2026-10-02T00:00:00+00:00", run_id="1"
    )
    assert history[0]["scenarios"]["sync"]["status"] == "suspect"
    assert regressions == []
    (job,) = [
        j
        for j in report.plan("schedule", HEAD, history=history)
        if j["os"] == "ubuntu-latest"
    ]
    assert job["baseline"] == BEFORE

    second = tmp_path / "second"
    write_result(second, "ubuntu-latest", candidate=SLOWER)
    history, regressions = report.record(
        second, history, commit=HEAD, date="2026-10-03T00:00:00+00:00", run_id="2"
    )

    assert history[1]["scenarios"]["sync"]["status"] == "regression"
    assert [(item.os, item.scenario, item.baseline) for item in regressions] == [
        ("ubuntu-latest", "sync", BEFORE)
    ]
    assert report.plan("schedule", HEAD, history=history) == []


def test_a_recorded_run_keeps_medians_in_milliseconds_and_its_cpu_change(
    tmp_path: Path,
) -> None:
    write_result(tmp_path, "ubuntu-latest")

    (run,), _ = report.record(
        tmp_path, [], commit=HEAD, date="2026-10-02T00:00:00+00:00", run_id="7"
    )

    sync = run["scenarios"]["sync"]
    assert (sync["wall"], sync["cpu"], sync["commands"]) == (1000.0, 500.0, 400.0)
    assert sync["change"]["ratio"] == 1.0
    assert (run["os"], run["baseline"], run["run_id"], run["python"]) == (
        "ubuntu-latest",
        BEFORE,
        "7",
        "3.14.0",
    )


def test_recording_the_same_workflow_run_again_adds_nothing(tmp_path: Path) -> None:
    write_result(tmp_path, "ubuntu-latest")
    history, _ = report.record(
        tmp_path, [], commit=HEAD, date="2026-10-02T00:00:00+00:00", run_id="1"
    )

    again, _ = report.record(
        tmp_path, history, commit=HEAD, date="2026-10-02T00:00:00+00:00", run_id="1"
    )

    assert again == history


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        (
            lambda path: write_result(path, "ubuntu-latest", commit=BEFORE),
            "another commit",
        ),
        (lambda path: write_result(path, "windows-latest"), "Unexpected"),
        (lambda path: write_result(path, "macos-latest"), "Unexpected"),
        (lambda path: (path / "benchmarks-ubuntu-latest").mkdir(), "Missing"),
        (lambda path: None, "No benchmark results"),
    ],
)
def test_incomplete_or_foreign_results_record_nothing(
    tmp_path: Path, setup: Any, message: str
) -> None:
    setup(tmp_path)

    with pytest.raises(BenchmarkReportError, match=message):
        report.record(
            tmp_path, [], commit=HEAD, date="2026-10-02T00:00:00+00:00", run_id="1"
        )


def test_a_run_older_than_the_latest_or_without_a_utc_date_is_refused(
    tmp_path: Path,
) -> None:
    write_result(tmp_path, "ubuntu-latest")
    later = [
        {**entry("ubuntu-latest", BEFORE, OLDER), "date": "2026-10-05T00:00:00+00:00"}
    ]

    with pytest.raises(PublicationError, match="older"):
        report.record(
            tmp_path, later, commit=HEAD, date="2026-10-02T00:00:00+00:00", run_id="1"
        )
    with pytest.raises(PublicationError, match="UTC"):
        report.record(tmp_path, [], commit=HEAD, date="2026-10-02T00:00:00", run_id="1")


def test_a_pull_request_comment_is_marked_so_a_later_run_replaces_it(
    tmp_path: Path,
) -> None:
    write_result(tmp_path, "ubuntu-latest", candidate=SLOWER)
    result = json.loads(
        (tmp_path / "benchmarks-ubuntu-latest/benchmarks.json").read_text()
    )

    body = report.comment_body(result, BEFORE, HEAD)

    assert body.startswith(report.COMMENT_MARKER)
    assert "| `sync` | +0.0% | +20.0%" in body
    assert body.rstrip().splitlines()[-1].endswith("the `run-benchmark` label.")
    assert "| slower |" in body


def test_a_calibration_reports_the_widest_noise_against_the_threshold(
    tmp_path: Path,
) -> None:
    for repeat in (1, 2):
        write_result(
            tmp_path,
            "ubuntu-latest",
            against=HEAD,
            artifact=f"benchmarks-ubuntu-latest-{repeat}",
        )

    body = report.calibration_body(tmp_path)

    assert "The widest interval bound is" in body
    assert "| ubuntu-latest-2 | `sync` |" in body


class Issues:
    """Records the issue operations a filing makes."""

    def __init__(self, open_number: int | None = None, reported: bool = False) -> None:
        self.open_number = open_number
        self.reported = reported
        self.created: list[str] = []
        self.comments: list[str] = []

    def open_issue(self, tracker: object) -> int | None:
        return self.open_number

    def has_report(self, number: int, body: str) -> bool:
        return self.reported

    def create_issue(self, tracker: object, body: str) -> None:
        self.created.append(body)

    def comment(self, number: int, body: str) -> None:
        self.comments.append(body)


def _regressions(tmp_path: Path, found: bool) -> Path:
    path = tmp_path / "regressions.json"
    items = (
        [
            {
                "os": "ubuntu-latest",
                "scenario": "sync",
                "baseline": BEFORE,
                "commit": HEAD,
                "change": {"ratio": 1.2, "low": 1.15, "high": 1.25},
            }
        ]
        if found
        else []
    )
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def test_a_confirmed_regression_opens_an_issue_with_the_commit_range(
    tmp_path: Path,
) -> None:
    github = Issues()

    report.file_regressions(_regressions(tmp_path, True), "o/r", "https://run", github)

    (body,) = github.created
    assert f"https://github.com/o/r/compare/{BEFORE}...{HEAD}" in body
    assert "+20.0%" in body


def test_a_regression_comments_on_the_open_issue_once(tmp_path: Path) -> None:
    fresh, repeated = Issues(open_number=5), Issues(open_number=5, reported=True)

    report.file_regressions(_regressions(tmp_path, True), "o/r", "https://run", fresh)
    report.file_regressions(
        _regressions(tmp_path, True), "o/r", "https://run", repeated
    )

    assert (len(fresh.comments), len(repeated.comments)) == (1, 0)


def test_a_night_without_a_regression_files_nothing(tmp_path: Path) -> None:
    github = Issues()

    report.file_regressions(_regressions(tmp_path, False), "o/r", "https://run", github)

    assert github.created == github.comments == []


def test_the_dashboard_states_the_threshold_the_report_uses() -> None:
    page = (Path(__file__).parent.parent / "metrics" / "index.html").read_text(
        encoding="utf-8"
    )

    assert f"at least {report.THRESHOLD:.0%} slower" in page
