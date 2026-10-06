"""The rollback fault count: what the plugin writes, and what is published."""

import argparse
import json
from types import SimpleNamespace

import pytest

from scripts.nightly_matrix import rollback_matrix
from scripts.rollback_report import badge, combine, record
from tests.rollback_report import RollbackReport, scenario_of


def report(nodeid, *, when="call", outcome="passed", marked=True):
    return SimpleNamespace(
        nodeid=nodeid,
        when=when,
        failed=outcome == "failed",
        skipped=outcome == "skipped",
        keywords={"rollback_fault": 1} if marked else {},
    )


def finish(plugin, status=pytest.ExitCode.OK, worker=False):
    config = SimpleNamespace(**({"workerinput": {}} if worker else {}))
    plugin.pytest_sessionfinish(SimpleNamespace(config=config), status)


FAULT = "tests/test_rollback.py::test_rollback_restores_the_seed[cli-adopted:write:a#1:after:error]"
OTHER = "tests/test_rollback.py::test_a_failed_restore_is_reported[sync-cli-retooled:a.toml]"


@pytest.mark.parametrize(
    ("nodeid", "scenario"),
    [
        (FAULT, "cli-adopted"),
        (OTHER, "sync-cli-retooled"),
        ("tests/test_rollback.py::test_x[lib-empty]", "lib-empty"),
    ],
)
def test_a_fault_belongs_to_the_scenario_its_id_starts_with(nodeid, scenario):
    assert scenario_of(nodeid) == scenario


def test_counts_each_fault_once_per_scenario_with_its_template(tmp_path):
    path = tmp_path / "out" / "report.json"
    plugin = RollbackReport(path)
    for nodeid in (FAULT, OTHER):
        plugin.pytest_runtest_logreport(report(nodeid, when="setup"))
        plugin.pytest_runtest_logreport(report(nodeid))
    plugin.pytest_runtest_logreport(
        report("tests/other.py::t[cli-adopted]", marked=False)
    )
    finish(plugin)
    assert json.loads(path.read_text()) == {
        "scenarios": {
            "cli-adopted": {"template": "cli", "passed": 1, "failed": []},
            "sync-cli-retooled": {"template": "cli", "passed": 1, "failed": []},
        }
    }


def test_a_failure_in_any_phase_fails_the_fault_and_a_skip_counts_for_nothing(tmp_path):
    path = tmp_path / "report.json"
    plugin = RollbackReport(path)
    plugin.pytest_runtest_logreport(report(FAULT))
    plugin.pytest_runtest_logreport(report(FAULT, when="teardown", outcome="failed"))
    plugin.pytest_runtest_logreport(report(OTHER, when="setup", outcome="skipped"))
    finish(plugin, pytest.ExitCode.TESTS_FAILED)
    assert json.loads(path.read_text())["scenarios"] == {
        "cli-adopted": {"template": "cli", "passed": 0, "failed": [FAULT]}
    }


def test_a_retry_replaces_a_failure_with_its_last_outcome(tmp_path):
    path = tmp_path / "report.json"
    first = RollbackReport(path)
    first.pytest_runtest_logreport(report(FAULT, outcome="failed"))
    first.pytest_runtest_logreport(report(OTHER))
    finish(first, pytest.ExitCode.TESTS_FAILED)
    retry = RollbackReport(path)
    retry.pytest_runtest_logreport(report(FAULT))
    finish(retry)
    assert json.loads(path.read_text())["scenarios"] == {
        "cli-adopted": {"template": "cli", "passed": 1, "failed": []},
        "sync-cli-retooled": {"template": "cli", "passed": 1, "failed": []},
    }


@pytest.mark.parametrize(
    ("status", "worker"),
    [
        (pytest.ExitCode.INTERRUPTED, False),
        (pytest.ExitCode.INTERNAL_ERROR, False),
        (pytest.ExitCode.OK, True),
    ],
)
def test_nothing_is_written_when_the_result_is_unknown_or_the_worker_ends(
    tmp_path, status, worker
):
    path = tmp_path / "report.json"
    plugin = RollbackReport(path)
    plugin.pytest_runtest_logreport(report(FAULT))
    finish(plugin, status, worker)
    assert not path.exists()


# ------------------------------------------------------------ publishing -- #

MATRIX = rollback_matrix("all", "cli")["include"]
ONE = [entry for entry in MATRIX if entry["os"] != "windows-latest"]


def write_results(root, matrix, failed=(), passed=10):
    for entry in matrix:
        folder = root / entry["artifact"]
        folder.mkdir(parents=True)
        (folder / "report.json").write_text(
            json.dumps(
                {
                    "scenarios": {
                        f"{entry['template']}-adopted": {
                            "template": entry["template"],
                            "passed": passed,
                            "failed": list(failed),
                        }
                    }
                }
            )
        )


@pytest.fixture
def run(tmp_path):
    write_results(tmp_path / "results", ONE)
    return argparse.Namespace(
        results=tmp_path / "results",
        matrix=json.dumps({"include": ONE}),
        history=tmp_path / "pages/metrics/rollback-history.json",
        latest=tmp_path / "pages/metrics/rollback-latest.json",
        commit="a" * 40,
        date="2026-10-06T05:30:00+00:00",
    )


def test_every_matrix_job_names_its_artifact():
    artifacts = [entry["artifact"] for entry in rollback_matrix()["include"]]
    assert len(set(artifacts)) == len(artifacts) == 2 * 5 + 5 * 6
    assert "rollback-windows-latest-cli-3of6" in artifacts
    assert "rollback-ubuntu-latest-ml-1of1" in artifacts


def test_a_green_run_adds_a_history_point_and_the_count_to_the_badge(run):
    record(run)
    assert json.loads(run.history.read_text()) == [
        {
            "commit": "a" * 40,
            "date": "2026-10-06T05:30:00+00:00",
            "cells": [
                {"os": "macos", "template": "cli", "passed": 10},
                {"os": "ubuntu", "template": "cli", "passed": 10},
            ],
        }
    ]
    assert json.loads(run.latest.read_text()) == {
        "schemaVersion": 1,
        "label": "rollback faults restored",
        "message": "20",
        "color": "22d3ee",
        "labelColor": "0A0A0A",
    }


def test_slices_of_one_cell_add_up(tmp_path):
    matrix = [e for e in MATRIX if e["os"] == "windows-latest"]
    write_results(tmp_path, matrix, passed=7)
    assert combine(tmp_path, matrix) == (
        [{"os": "windows", "template": "cli", "passed": 42}],
        0,
    )


def test_a_failure_changes_the_badge_but_not_the_history(run):
    write_json = run.history
    write_json.parent.mkdir(parents=True)
    write_json.write_text("[]")
    for entry in ONE[:1]:
        report_path = run.results / entry["artifact"] / "report.json"
        data = json.loads(report_path.read_text())
        data["scenarios"]["cli-adopted"]["failed"] = ["a", "b"]
        report_path.write_text(json.dumps(data))
    record(run)
    assert json.loads(run.history.read_text()) == []
    assert json.loads(run.latest.read_text())["message"] == "2 failing"


def test_a_retried_commit_is_recorded_once(run):
    record(run)
    record(run)
    assert len(json.loads(run.history.read_text())) == 1


def test_an_older_run_is_refused(run):
    record(run)
    run.commit = "b" * 40
    run.date = "2026-10-05T05:30:00+00:00"
    with pytest.raises(SystemExit, match="older"):
        record(run)


@pytest.mark.parametrize(
    "problem", ["missing", "extra", "empty", "foreign", "no-report"]
)
def test_an_incomplete_run_publishes_nothing(run, problem):
    first = run.results / ONE[0]["artifact"]
    if problem == "missing":
        for child in first.iterdir():
            child.unlink()
        first.rmdir()
    elif problem == "extra":
        (run.results / "rollback-other").mkdir()
    elif problem == "empty":
        (first / "report.json").write_text('{"scenarios": {}}')
    elif problem == "foreign":
        (first / "report.json").write_text(
            '{"scenarios": {"x": {"template": "lib", "passed": 1, "failed": []}}}'
        )
    else:
        (first / "report.json").unlink()
    with pytest.raises(SystemExit):
        record(run)
    assert not run.history.exists()
    assert not run.latest.exists()


@pytest.mark.parametrize(
    ("commit", "date"),
    [("abc", "2026-10-06T05:30:00+00:00"), ("a" * 40, "2026-10-06T05:30:00-07:00")],
)
def test_a_bad_commit_or_local_time_is_refused(run, commit, date):
    run.commit, run.date = commit, date
    with pytest.raises(SystemExit):
        record(run)


def test_the_badge_says_failing_in_words_and_keeps_the_house_colors():
    assert badge(5214, 0)["message"] == "5,214"
    assert badge(5214, 1)["message"] == "1 failing"
    assert badge(1, 0)["color"] == "22d3ee"
