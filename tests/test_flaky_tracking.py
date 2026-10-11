"""A fixed flake stays pending until explicit, later nightly passes verify it."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.flaky_tracking import (
    AWAITING,
    Flake,
    Issue,
    IssueStore,
    Nightly,
    Result,
    body_for,
    decode,
    evidence_from,
    track,
)
from scripts.pytest_results import Results

TEST = "tests/test_rollback.py::test_real_commands_roll_back[astro-empty:write:a#1:after:error]"
WIN = "windows-py3.14"
LINUX = "linux-py3.14"
MARKED = "2026-10-06T12:00:00Z"


def nightly(number, created="2026-10-06T13:00:00Z"):
    return Nightly(
        number,
        "a" * 40,
        created,
        f"https://github.com/owner/repo/actions/runs/{number}",
    )


class FakeStore:
    def __init__(self, *issues):
        self.items = {i.number: i for i in issues}
        self.notes: dict[int, list[str]] = {}
        self.calls = []
        self.fail = None

    def issues(self):
        return list(self.items.values())

    def comments(self, number):
        return self.notes.get(number, [])

    def create(self, flake, body):
        number = max(self.items, default=0) + 1
        item = Issue(number, f"Flaky test: {flake.test}", body)
        self.items[number] = item
        self.calls.append(("create", number))
        return item

    def update(self, number, body):
        self.items[number] = replace(self.items[number], body=body)
        self.calls.append(("update", number))

    def comment_once(self, number, body):
        if body not in self.items[number].body and body not in self.comments(number):
            self.notes.setdefault(number, []).append(body)
            self.calls.append(("comment", number))

    def reopen(self, number):
        self.items[number] = replace(self.items[number], closed=False)
        self.calls.append(("reopen", number))

    def close(self, number):
        if self.fail == "close":
            self.fail = None
            raise OSError("GitHub unavailable")
        self.items[number] = replace(self.items[number], closed=True)
        self.calls.append(("close", number))

    def remove_awaiting(self, number):
        if self.fail == "remove":
            self.fail = None
            raise OSError("GitHub unavailable")
        self.items[number] = replace(self.items[number], awaiting_since=None)
        self.calls.append(("remove", number))


def pending(platforms=(WIN,), runs=()):
    flake = Flake(TEST, platforms, runs, MARKED if runs else None, max(runs, default=0))
    return Issue(
        1,
        "Flaky test",
        body_for(flake, "Agent notes: fix in PR #123."),
        awaiting_since=MARKED,
    )


def state(store):
    result = decode(store.items[1].body)
    assert result is not None
    return result


def test_each_flaky_test_gets_one_issue_and_repeat_runs_preserve_history():
    store = FakeStore()
    evidence = {TEST: {WIN: Result.FLAKY}, "tests/t.py::another": {LINUX: Result.FLAKY}}
    track(store, nightly(1), evidence)
    assert len(store.items) == 2
    calls = list(store.calls)
    track(store, nightly(1), evidence)
    assert len(store.items) == 2
    # Repeating the same run may reconcile state, but never adds another comment.
    notes = dict(store.notes)
    track(store, nightly(1), evidence)
    assert store.notes == notes
    track(store, nightly(2), evidence)
    assert len(store.items) == 2
    assert all(len(v) == 1 for v in store.notes.values())
    assert sum(action == "create" for action, _ in calls) == 2


def test_three_distinct_clean_runs_close_the_issue_and_keep_agent_notes():
    store = FakeStore(pending((WIN, LINUX)))
    for number in (1, 2, 3):
        track(
            store, nightly(number), {TEST: {WIN: Result.PASSED, LINUX: Result.PASSED}}
        )
        assert store.items[1].closed == (number == 3)
        assert state(store).clean_runs == tuple(range(1, number + 1))
        track(
            store, nightly(number), {TEST: {WIN: Result.PASSED, LINUX: Result.PASSED}}
        )
        assert len(store.comments(1)) == number
    assert store.items[1].awaiting_since is None
    assert "Agent notes: fix in PR #123." in store.items[1].body
    assert "3/3" in store.items[1].body


@pytest.mark.parametrize(
    "evidence",
    [{}, {TEST: {}}, {TEST: {WIN: Result.SKIPPED}}, {TEST: {LINUX: Result.PASSED}}],
)
def test_missing_skipped_or_wrong_platform_results_do_not_count(evidence):
    store = FakeStore(pending())
    track(store, nightly(1), evidence)
    assert state(store).clean_runs == ()
    assert not store.items[1].closed
    assert store.calls == []


@pytest.mark.parametrize("created", ["2026-10-06T11:00:00Z", MARKED])
def test_a_run_started_before_the_fix_was_marked_never_verifies_it(created):
    store = FakeStore(pending())
    track(store, nightly(1, created), {TEST: {WIN: Result.PASSED}})
    assert state(store).clean_runs == ()


def test_a_local_or_unmarked_fix_does_not_start_verification():
    store = FakeStore(replace(pending(), awaiting_since=None))
    for number in (1, 2, 3):
        track(store, nightly(number), {TEST: {WIN: Result.PASSED}})
    assert not store.items[1].closed
    assert state(store).clean_runs == ()


@pytest.mark.parametrize("result", [Result.FLAKY, Result.FAILED])
def test_recurrence_resets_verification_and_requires_another_fix(result):
    store = FakeStore(pending(runs=(1, 2)))
    track(store, nightly(3), {TEST: {WIN: result}})
    assert state(store).clean_runs == ()
    assert store.items[1].awaiting_since is None
    assert not store.items[1].closed
    assert "needs a fix" in store.comments(1)[0]
    track(store, nightly(4), {TEST: {WIN: Result.PASSED}})
    assert state(store).clean_runs == ()


def test_a_closed_issue_reopens_on_another_platform_and_retains_its_history():
    store = FakeStore(
        replace(pending(runs=(1, 2, 3)), closed=True, awaiting_since=None)
    )
    track(store, nightly(4), {TEST: {LINUX: Result.FLAKY}})
    assert not store.items[1].closed
    assert state(store).platforms == tuple(sorted((WIN, LINUX)))
    assert state(store).clean_runs == ()
    assert "Agent notes" in store.items[1].body
    assert len(store.items) == 1


def test_a_new_label_event_starts_a_new_verification_sequence():
    store = FakeStore(
        replace(pending(runs=(1, 2)), awaiting_since="2026-10-06T12:30:00Z")
    )
    track(store, nightly(3), {TEST: {WIN: Result.PASSED}})
    assert state(store).clean_runs == (3,)


def test_an_older_run_cannot_reset_or_extend_newer_verification():
    store = FakeStore(pending(runs=(4,)))
    track(store, nightly(3), {TEST: {WIN: Result.FLAKY}})
    assert state(store).clean_runs == (4,)
    assert store.calls == []


@pytest.mark.parametrize("failure", ["remove", "close"])
def test_a_reporter_retry_finishes_a_partially_applied_closure(failure):
    store = FakeStore(pending(runs=(1, 2)))
    store.fail = failure
    with pytest.raises(OSError, match="GitHub unavailable"):
        track(store, nightly(3), {TEST: {WIN: Result.PASSED}})
    track(store, nightly(3), {TEST: {WIN: Result.PASSED}})
    assert store.items[1].closed
    assert store.items[1].awaiting_since is None
    assert state(store).clean_runs == (1, 2, 3)
    assert len(store.comments(1)) == 1


def test_state_encoding_handles_special_test_ids_and_preserves_body_notes():
    flake = Flake('t::test[quotes" --> unicode λ]', (WIN,))
    body = body_for(flake, "Notes before") + "\nNotes after"
    updated = body_for(replace(flake, clean_runs=(1,)), body)
    assert updated.startswith("Notes before")
    assert updated.endswith("Notes after")
    assert decode(updated) == replace(flake, clean_runs=(1,))


def artifact(first, retry=None, platform=WIN):
    files = {"first.json": json.dumps({"platform": platform, "tests": first})}
    if retry is not None:
        files["retry.json"] = json.dumps({"platform": platform, "tests": retry})
    return files


def test_evidence_distinguishes_clean_recovered_persistent_and_skipped_tests():
    data = {
        "job": artifact(
            {
                "clean": "passed",
                "flaky": "failed",
                "broken": "failed",
                "skip": "skipped",
            },
            {"flaky": "passed", "broken": "failed"},
        )
    }
    assert evidence_from(data) == {
        "clean": {WIN: Result.PASSED},
        "flaky": {WIN: Result.FLAKY},
        "broken": {WIN: Result.FAILED},
        "skip": {WIN: Result.SKIPPED},
    }


def test_another_shards_pass_does_not_hide_a_failure_or_a_retry():
    assert (
        evidence_from(
            {
                "one": artifact({TEST: "passed"}),
                "two": artifact({TEST: "failed"}, {TEST: "passed"}),
            }
        )[TEST][WIN]
        is Result.FLAKY
    )
    assert (
        evidence_from(
            {"one": artifact({TEST: "passed"}), "two": artifact({TEST: "failed"})}
        )[TEST][WIN]
        is Result.FAILED
    )
    assert (
        evidence_from(
            {
                "one": {
                    "retry.json": json.dumps(
                        {"platform": WIN, "tests": {TEST: "passed"}}
                    )
                }
            }
        )
        == {}
    )


def report(nodeid=TEST, when="call", outcome="passed"):
    return SimpleNamespace(
        nodeid=nodeid,
        when=when,
        failed=outcome == "failed",
        skipped=outcome == "skipped",
    )


def finish(plugin, status=0, worker=False):
    plugin.pytest_sessionfinish(
        SimpleNamespace(
            config=SimpleNamespace(**({"workerinput": {}} if worker else {}))
        ),
        status,
    )


def test_pytest_evidence_requires_a_passed_call_and_preserves_teardown_failures(
    tmp_path,
):
    plugin = Results(tmp_path / "first.json")
    plugin.pytest_runtest_logreport(report("clean", when="setup"))
    plugin.pytest_runtest_logreport(report("clean"))
    plugin.pytest_runtest_logreport(report("broken"))
    plugin.pytest_runtest_logreport(report("broken", when="teardown", outcome="failed"))
    plugin.pytest_runtest_logreport(report("skip", when="setup", outcome="skipped"))
    plugin.pytest_runtest_logreport(report("never-called", when="setup"))
    finish(plugin, status=1)
    assert json.loads(plugin.path.read_text())["tests"] == {
        "clean": "passed",
        "broken": "failed",
        "skip": "skipped",
    }


@pytest.mark.parametrize(
    ("status", "worker"), [(2, False), (3, False), (4, False), (5, False), (0, True)]
)
def test_interrupted_incomplete_and_worker_results_are_not_verification(
    tmp_path, status, worker
):
    plugin = Results(tmp_path / "first.json")
    plugin.pytest_runtest_logreport(report())
    finish(plugin, status, worker)
    assert not plugin.path.exists()


def test_issue_store_reads_closed_issues_and_latest_label_event_across_pages():
    responses = iter(
        [
            [
                [
                    {
                        "number": 1,
                        "title": "test",
                        "body": "notes",
                        "state": "closed",
                        "labels": [{"name": AWAITING}],
                    }
                ],
                [],
            ],
            [
                [
                    {
                        "event": "labeled",
                        "label": {"name": AWAITING},
                        "created_at": "old",
                    }
                ],
                [
                    {
                        "event": "labeled",
                        "label": {"name": AWAITING},
                        "created_at": MARKED,
                    }
                ],
            ],
        ]
    )
    calls = []

    def gh(*args):
        calls.append(args)
        return json.dumps(next(responses))

    store = IssueStore("owner/repo", gh)
    assert store.issues() == [Issue(1, "test", "notes", True, MARKED)]
    assert all("--paginate" in c for c in calls)
    assert "state=all" in calls[0][1]


def test_issue_writes_preserve_literal_multiline_text_without_shell_interpolation():
    body = 'Notes with `$HOME` and $(command)\n\nLiteral "quotes"\n'
    captured = []

    def gh(*args):
        data = json.loads(Path(args[args.index("--input") + 1]).read_text())
        captured.append(data)
        return json.dumps({"number": 1, "title": "test"})

    IssueStore("owner/repo", gh).update(1, body)
    assert captured == [{"body": body}]


def test_a_delayed_pre_fix_failure_does_not_reset_a_marked_fix():
    store = FakeStore(pending(runs=(1,)))
    track(store, nightly(2, "2026-10-06T11:00:00Z"), {TEST: {WIN: Result.FLAKY}})
    assert state(store).clean_runs == (1,)
    assert store.items[1].awaiting_since == MARKED
    assert store.calls == []


def test_relabeling_a_manually_reopened_issue_does_not_reuse_old_verification():
    store = FakeStore(
        replace(pending(runs=(1, 2, 3)), awaiting_since="2026-10-06T12:30:00Z")
    )
    track(store, nightly(4), {TEST: {WIN: Result.PASSED}})
    assert not store.items[1].closed
    assert state(store).clean_runs == (4,)


@pytest.mark.integration
def test_real_pytest_and_xdist_publish_separate_attempts_with_all_phase_failures(
    tmp_path,
):
    import os
    import subprocess
    import sys

    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\n")
    tests = tmp_path / "test_example.py"
    tests.write_text(
        "import os, pytest\n"
        "def test_clean(): pass\n"
        "def test_flaky(): assert os.environ['ATTEMPT'] == 'retry'\n"
        "@pytest.fixture\n"
        "def broken():\n"
        "    yield\n"
        "    raise AssertionError('teardown failed')\n"
        "def test_broken(broken): pass\n"
        "@pytest.mark.skip(reason='no evidence')\n"
        "def test_skipped(): pass\n"
    )
    files = {}
    for attempt in ("first", "retry"):
        target = tmp_path / f"{attempt}.json"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(config),
            str(tests),
            "-n",
            "2",
            "-p",
            "scripts.pytest_results",
        ]
        if attempt == "retry":
            command += ["-k", "flaky or broken"]
        result = subprocess.run(
            command,
            cwd=tmp_path,
            env={
                **os.environ,
                "ATTEMPT": attempt,
                "PROTOSTAR_TEST_RESULTS": str(target),
                "HOME": str(tmp_path),
                "USERPROFILE": str(tmp_path),
                "PYTHONPATH": str(Path(__file__).resolve().parent.parent),
            },
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stdout + result.stderr
        files[f"{attempt}.json"] = target.read_text()
    evidence = evidence_from({"job": files})
    by_name = {
        test.rsplit("::", 1)[-1]: next(iter(platforms.values()))
        for test, platforms in evidence.items()
    }
    assert by_name == {
        "test_clean": Result.PASSED,
        "test_flaky": Result.FLAKY,
        "test_broken": Result.FAILED,
        "test_skipped": Result.SKIPPED,
    }


@pytest.mark.parametrize("available", ["fresh", "stale", "expired", "missing"])
def test_reporter_uses_only_unexpired_results_from_the_current_run_attempt(
    monkeypatch, available
):
    from scripts.nightly_report import GhCli, Run

    run = Run("owner/repo", "3", "a" * 40)
    store = FakeStore(pending(runs=(1, 2)))
    monkeypatch.setattr(store, "ensure_labels", lambda: None, raising=False)
    monkeypatch.setattr("scripts.flaky_tracking.IssueStore", lambda repo, gh: store)
    name = "test-results-flaky-tests-job"
    artifact_entry = {
        "name": name,
        "expired": available == "expired",
        "created_at": "2026-10-06T13:01:00Z"
        if available == "fresh"
        else "2026-10-06T11:00:00Z",
    }
    downloads = []

    def gh(*args):
        if args[0] == "api" and args[1].endswith("/runs/3"):
            return json.dumps(
                {
                    "created_at": "2026-10-06T13:00:00Z",
                    "run_started_at": "2026-10-06T13:00:00Z",
                }
            )
        if args[0] == "api" and "/artifacts?" in args[1]:
            assert "--paginate" in args
            return json.dumps(
                [
                    {"artifacts": [] if available == "missing" else [artifact_entry]},
                    {"artifacts": []},
                ]
            )
        assert args[:2] == ("run", "download")
        downloads.append(args)
        assert args[-2:] == ("--name", name)
        directory = Path(args[args.index("--dir") + 1])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "first.json").write_text(artifact({TEST: "passed"})["first.json"])
        return ""

    client = GhCli(run.repo)
    monkeypatch.setattr(client, "_gh", gh)
    client.track_tests(run)
    assert store.items[1].closed == (available == "fresh")
    assert bool(downloads) == (available == "fresh")
