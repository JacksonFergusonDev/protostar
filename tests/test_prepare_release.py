"""Release preparation refreshes inputs before allowing a version bump."""

import ast
import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from protostar._fallbacks import DEFAULT_REVISIONS
from scripts import prepare_release, sync_registry_fallbacks
from scripts._common import CodeLanguage, fixture_environment
from scripts.nightly_matrix import rollback_matrix
from scripts.release_commits import RELEASE_INPUTS

INVALID_REVISIONS: tuple[object, ...] = (None, 1, [], {}, "", " \t\n")


@pytest.fixture(autouse=True)
def commit_candidates(mocker):
    return mocker.patch.object(
        prepare_release,
        "workflow_commits",
        side_effect=lambda sha: {"ci.yml": [sha], "nightly.yml": [sha]},
    )


def test_nightly_before_refresh_qualifies_but_ci_must_cover_refresh(
    commit_candidates, mocker
):
    commit_candidates.side_effect = None
    commit_candidates.return_value = {
        "ci.yml": ["abc123"],
        "nightly.yml": ["abc123", "parent"],
    }
    read = mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[
            [_passed_run()],
            [],
            [_passed_run(headSha="parent")],
            _nightly_jobs(),
        ],
    )
    prompt = mocker.patch.object(prepare_release, "confirm")
    prepare_release.check_workflows("example/project", "abc123")
    queries = [call.args[0] for call in read.call_args_list[:3]]
    assert [
        (cmd[cmd.index("--workflow") + 1], cmd[cmd.index("--commit") + 1])
        for cmd in queries
    ] == [
        ("ci.yml", "abc123"),
        ("nightly.yml", "abc123"),
        ("nightly.yml", "parent"),
    ]
    prompt.assert_not_called()


def test_waiting_for_parent_nightly_keeps_source_pinned_to_refresh(
    commit_candidates, mocker
):
    commit_candidates.side_effect = None
    commit_candidates.return_value = {
        "ci.yml": ["abc123"],
        "nightly.yml": ["abc123", "parent"],
    }
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[
            [_passed_run()],
            [],
            [_passed_run(headSha="parent", status="in_progress", conclusion="")],
            _passed_run(headSha="parent"),
            _nightly_jobs(),
        ],
    )
    source = mocker.patch.object(prepare_release, "require_source")
    mocker.patch.object(prepare_release, "confirm", return_value=True)
    mocker.patch.object(
        prepare_release, "run_repo_cmd", return_value=subprocess.CompletedProcess([], 0)
    )
    prepare_release.check_workflows("example/project", "abc123")
    assert source.call_args_list == [mocker.call("example/project", "abc123")] * 2


def test_missing_parent_and_refresh_nightly_dispatches_on_current_main(
    commit_candidates, mocker
):
    commit_candidates.side_effect = None
    commit_candidates.return_value = {
        "ci.yml": ["abc123"],
        "nightly.yml": ["abc123", "parent"],
    }
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[
            [_passed_run()],
            [],
            [],
            [_passed_run()],
            _nightly_jobs(),
        ],
    )
    mocker.patch.object(prepare_release, "require_source")
    mocker.patch.object(prepare_release, "confirm", return_value=True)
    dispatch = mocker.patch.object(
        prepare_release, "read_command", return_value="Requested"
    )
    prepare_release.check_workflows("example/project", "abc123")
    cmd = dispatch.call_args.args[0]
    assert cmd[cmd.index("--ref") + 1] == "main"


def test_failed_nightly_on_refresh_cannot_be_hidden_by_parent_success(
    commit_candidates, mocker
):
    commit_candidates.side_effect = None
    commit_candidates.return_value = {
        "ci.yml": ["abc123"],
        "nightly.yml": ["abc123", "parent"],
    }
    read = mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[
            [_passed_run()],
            [_passed_run(conclusion="failure")],
        ],
    )
    with pytest.raises(SystemExit):
        prepare_release.check_workflows("example/project", "abc123")
    assert read.call_count == 2


def _passed_run(**updates):
    return {
        "databaseId": 123,
        "headSha": "abc123",
        "status": "completed",
        "conclusion": "success",
        "url": "https://github.com/example/project/actions/runs/123",
        **updates,
    }


def _nightly_jobs():
    return {
        "jobs": [
            {"name": name, "conclusion": "success"}
            for name in (
                "Platforms / Test on ubuntu-latest / Python 3.14",
                *(
                    f"Rollback ({entry['os']} / {entry['template']}"
                    + (f" {entry['slice']}" if entry["slice"] != "1/1" else "")
                    + ")"
                    for entry in rollback_matrix()["include"]
                ),
            )
        ]
    }


@pytest.mark.parametrize(
    "run",
    [
        [],
        [_passed_run(status="queued", conclusion="")],
        [_passed_run(status="in_progress", conclusion="")],
        [_passed_run(conclusion="failure")],
        [_passed_run(conclusion="cancelled")],
        [_passed_run(conclusion="skipped")],
        [_passed_run(headSha="older")],
    ],
)
def test_workflow_preflight_rejects_missing_pending_failed_or_wrong_commit(
    run, mocker, capsys
):
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[run, [_passed_run()], _nightly_jobs()],
    )
    with pytest.raises(SystemExit):
        prepare_release.check_workflows("example/project", "abc123")
    assert "Version bump stopped" in capsys.readouterr().err


def test_workflow_preflight_queries_latest_run_for_exact_sha(mocker):
    read = mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[[_passed_run()], [_passed_run()], _nightly_jobs()],
    )
    prepare_release.check_workflows("example/project", "abc123")
    for call in read.call_args_list[:2]:
        command = call.args[0]
        assert command[command.index("--commit") + 1] == "abc123"
        assert command[command.index("--limit") + 1] == "1"
        assert (
            "--status" not in command
        )  # An older success cannot hide a newer failure.


@pytest.mark.parametrize("missing", ["platforms", "rollback"])
def test_narrowed_nightly_cannot_approve_release(missing, mocker):
    jobs = _nightly_jobs()
    if missing == "platforms":
        jobs["jobs"] = jobs["jobs"][1:]
    else:
        jobs["jobs"].pop()
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[[_passed_run()], [_passed_run()], jobs],
    )
    with pytest.raises(SystemExit):
        prepare_release.check_workflows("example/project", "abc123")


def test_waiting_for_ci_watches_specific_run_and_checks_its_result(mocker):
    mocker.patch.object(prepare_release, "confirm", return_value=True)
    source = mocker.patch.object(prepare_release, "require_source")
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[
            [_passed_run(status="in_progress", conclusion="")],
            _passed_run(),
            [_passed_run()],
            _nightly_jobs(),
        ],
    )
    run = mocker.patch.object(
        prepare_release, "run_repo_cmd", return_value=subprocess.CompletedProcess([], 0)
    )
    prepare_release.check_workflows("example/project", "abc123")
    run.assert_called_once_with(
        [
            "gh",
            "run",
            "watch",
            "123",
            "--repo",
            "example/project",
            "--exit-status",
            "--interval",
            "10",
        ]
    )
    assert source.call_args_list == [mocker.call("example/project", "abc123")] * 2


@pytest.mark.parametrize(
    "result",
    [
        _passed_run(conclusion="failure"),
        _passed_run(conclusion="cancelled"),
        _passed_run(conclusion="skipped"),
        _passed_run(headSha="other"),
        _passed_run(status="in_progress", conclusion=""),
    ],
)
def test_successful_watch_exit_cannot_hide_unsuccessful_or_wrong_commit(result, mocker):
    mocker.patch.object(prepare_release, "confirm", return_value=True)
    mocker.patch.object(prepare_release, "require_source")
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[
            [_passed_run(status="queued", conclusion="")],
            result,
        ],
    )
    mocker.patch.object(
        prepare_release, "run_repo_cmd", return_value=subprocess.CompletedProcess([], 0)
    )
    with pytest.raises(SystemExit):
        prepare_release.check_workflows("example/project", "abc123")


@pytest.mark.parametrize("exit_code", [1, 130])
def test_watch_failure_stops_without_dispatching_nightly(exit_code, mocker):
    mocker.patch.object(prepare_release, "confirm", return_value=True)
    mocker.patch.object(prepare_release, "require_source")
    read = mocker.patch.object(
        prepare_release,
        "read_json",
        return_value=[_passed_run(status="queued", conclusion="")],
    )
    run = mocker.patch.object(
        prepare_release,
        "run_repo_cmd",
        return_value=subprocess.CompletedProcess([], exit_code),
    )
    with pytest.raises(SystemExit):
        prepare_release.check_workflows("example/project", "abc123")
    assert read.call_count == 1
    assert run.call_count == 1
    assert run.call_args.args[0][:3] == ["gh", "run", "watch"]


def test_freshly_pushed_ci_is_discovered_before_watching(mocker):
    mocker.patch.object(prepare_release, "confirm", return_value=True)
    mocker.patch.object(prepare_release, "require_source")
    sleep = mocker.patch("scripts.prepare_release.time.sleep")
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[
            [],
            [],
            [_passed_run(status="queued", conclusion="")],
            _passed_run(),
            [_passed_run()],
            _nightly_jobs(),
        ],
    )
    run = mocker.patch.object(
        prepare_release, "run_repo_cmd", return_value=subprocess.CompletedProcess([], 0)
    )
    prepare_release.check_workflows("example/project", "abc123")
    sleep.assert_called_once_with(prepare_release.RUN_DISCOVERY_INTERVAL)
    assert run.call_args.args[0][:4] == ["gh", "run", "watch", "123"]


def test_run_discovery_times_out_without_releasing(mocker, capsys):
    mocker.patch.object(prepare_release, "confirm", return_value=True)
    mocker.patch.object(prepare_release, "require_source")
    mocker.patch.object(prepare_release, "RUN_DISCOVERY_ATTEMPTS", 3)
    sleep = mocker.patch("scripts.prepare_release.time.sleep")
    latest = mocker.patch.object(prepare_release, "latest_run", return_value=None)
    run = mocker.patch.object(prepare_release, "run_repo_cmd")
    with pytest.raises(SystemExit):
        prepare_release.wait_for_workflow(
            "example/project", "ci.yml", "abc123", None, source_sha="abc123"
        )
    assert latest.call_count == 3
    assert sleep.call_count == 2
    run.assert_not_called()
    assert "no CI run appeared" in capsys.readouterr().err


def test_missing_nightly_offers_dispatch_and_wait_separately(mocker):
    prompt = mocker.patch.object(prepare_release, "confirm", side_effect=[True, True])
    mocker.patch.object(prepare_release, "require_source")
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[
            [_passed_run()],
            [],
            [_passed_run(status="queued", conclusion="")],
            _passed_run(),
            _nightly_jobs(),
        ],
    )
    dispatch = mocker.patch.object(
        prepare_release, "read_command", return_value="Requested"
    )
    watch = mocker.patch.object(
        prepare_release, "run_repo_cmd", return_value=subprocess.CompletedProcess([], 0)
    )
    prepare_release.check_workflows("example/project", "abc123")
    dispatch.assert_called_once_with(
        [
            "gh",
            "workflow",
            "run",
            "nightly.yml",
            "--repo",
            "example/project",
            "--ref",
            "main",
            "-f",
            "rollback-only=false",
            "-f",
            "os=all",
            "-f",
            "template=all",
        ]
    )
    assert prompt.call_args_list == [
        mocker.call("Trigger full Nightly on main at abc123?"),
        mocker.call("Wait for Nightly to pass and automatically continue?"),
    ]
    assert watch.call_args.args[0][:4] == ["gh", "run", "watch", "123"]


@pytest.mark.parametrize("trigger", [False, True])
def test_declining_nightly_trigger_or_wait_stops_preflight(trigger, mocker):
    mocker.patch.object(prepare_release, "confirm", side_effect=[trigger, False])
    mocker.patch.object(prepare_release, "require_source")
    mocker.patch.object(prepare_release, "read_json", side_effect=[[_passed_run()], []])
    dispatch = mocker.patch.object(
        prepare_release, "read_command", return_value="Requested"
    )
    watch = mocker.patch.object(prepare_release, "run_repo_cmd")
    with pytest.raises(SystemExit):
        prepare_release.check_workflows("example/project", "abc123")
    assert dispatch.call_count == int(trigger)
    watch.assert_not_called()


def test_existing_nightly_is_watched_without_dispatching_again(mocker):
    prompt = mocker.patch.object(prepare_release, "confirm", return_value=True)
    mocker.patch.object(prepare_release, "require_source")
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[
            [_passed_run()],
            [_passed_run(status="queued", conclusion="")],
            _passed_run(),
            _nightly_jobs(),
        ],
    )
    dispatch = mocker.patch.object(prepare_release, "read_command")
    mocker.patch.object(
        prepare_release, "run_repo_cmd", return_value=subprocess.CompletedProcess([], 0)
    )
    prepare_release.check_workflows("example/project", "abc123")
    prompt.assert_called_once_with(
        "Wait for Nightly to pass and automatically continue?"
    )
    dispatch.assert_not_called()


@pytest.mark.parametrize("workflow", ["ci.yml", "nightly.yml"])
def test_noninteractive_checks_never_prompt_dispatch_or_wait(workflow, mocker):
    mocker.patch("sys.stdin.isatty", return_value=False)
    prompt = mocker.patch("builtins.input")
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=(
            [
                [],
            ]
            if workflow == "ci.yml"
            else [[_passed_run()], []]
        ),
    )
    run = mocker.patch.object(prepare_release, "run_repo_cmd")
    with pytest.raises(SystemExit):
        prepare_release.check_workflows("example/project", "abc123")
    prompt.assert_not_called()
    run.assert_not_called()


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("y", True), ("YES", True), ("", False), ("n", False), (EOFError(), False)],
)
def test_confirmation_defaults_to_no_and_handles_eof(answer, expected, mocker):
    mocker.patch("sys.stdin.isatty", return_value=True)
    mocker.patch("builtins.input", side_effect=["maybe", answer])
    assert prepare_release.confirm("Continue?") is expected


def test_branch_moving_while_prompting_prevents_dispatch(mocker):
    mocker.patch.object(prepare_release, "confirm", return_value=True)
    mocker.patch.object(
        prepare_release, "check_checkout", return_value=("example/project", "moved")
    )
    mocker.patch.object(prepare_release, "read_json", side_effect=[[_passed_run()], []])
    dispatch = mocker.patch.object(prepare_release, "read_command")
    with pytest.raises(SystemExit):
        prepare_release.check_workflows("example/project", "abc123")
    dispatch.assert_not_called()


def test_branch_moving_during_watch_prevents_continuation(mocker):
    mocker.patch.object(prepare_release, "confirm", return_value=True)
    mocker.patch.object(
        prepare_release,
        "check_checkout",
        side_effect=[
            ("example/project", "abc123"),
            ("example/project", "moved"),
        ],
    )
    mocker.patch.object(
        prepare_release,
        "read_json",
        side_effect=[
            [_passed_run(status="queued", conclusion="")],
            _passed_run(),
        ],
    )
    mocker.patch.object(
        prepare_release, "run_repo_cmd", return_value=subprocess.CompletedProcess([], 0)
    )
    with pytest.raises(SystemExit):
        prepare_release.check_workflows("example/project", "abc123")


def test_interrupt_stops_preparation_without_building_or_cancelling_remote_run(
    mocker, capsys
):
    mocker.patch.object(
        prepare_release, "check_checkout", return_value=("example/project", "abc123")
    )
    mocker.patch.object(prepare_release, "prepare_inputs", return_value=False)
    mocker.patch.object(prepare_release, "confirm", return_value=True)
    mocker.patch.object(
        prepare_release,
        "read_json",
        return_value=[_passed_run(status="queued", conclusion="")],
    )
    run = mocker.patch.object(
        prepare_release, "run_repo_cmd", side_effect=KeyboardInterrupt
    )
    build = mocker.patch.object(prepare_release, "check_local_builds")
    with pytest.raises(SystemExit):
        prepare_release.main()
    assert run.call_count == 1
    build.assert_not_called()
    assert "continue on GitHub" in capsys.readouterr().err


@pytest.mark.parametrize(
    "outputs",
    [
        ["feature"],
        ["main", " M file"],
        ["main", "", "abc123", "older\trefs/heads/main"],
    ],
)
def test_checkout_preflight_blocks_wrong_branch_dirty_or_unpushed_source(
    outputs, mocker
):
    mocker.patch.object(prepare_release, "read_command", side_effect=outputs)
    with pytest.raises(SystemExit):
        prepare_release.check_checkout()


def test_checkout_uses_live_remote_not_stale_tracking_ref(mocker):
    read = mocker.patch.object(
        prepare_release,
        "read_command",
        side_effect=[
            "main",
            "",
            "abc123",
            "abc123\trefs/heads/main",
            "example/project",
        ],
    )
    assert prepare_release.check_checkout() == ("example/project", "abc123")
    assert read.call_args_list[3].args[0] == [
        "git",
        "ls-remote",
        "origin",
        "refs/heads/main",
    ]


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("gh"),
        subprocess.CompletedProcess([], 1, stderr="not authenticated"),
    ],
)
def test_command_failure_cannot_approve_release(failure, mocker):
    mocker.patch.object(
        prepare_release,
        "run_repo_cmd",
        side_effect=failure if isinstance(failure, Exception) else None,
        return_value=failure,
    )
    with pytest.raises(SystemExit):
        prepare_release.read_command(["gh", "repo", "view"])


def test_invalid_github_json_cannot_approve_release(mocker):
    mocker.patch.object(prepare_release, "read_command", return_value="not JSON")
    with pytest.raises(SystemExit):
        prepare_release.read_json(["gh"])


def test_refreshed_commit_is_verified_before_builds_and_bump(mocker):
    mocker.patch.object(
        prepare_release,
        "check_checkout",
        side_effect=[
            ("example/project", "abc123"),
            ("example/project", "newsha"),
            ("example/project", "newsha"),
            ("example/project", "newsha"),
        ],
    )
    checks = mocker.patch.object(prepare_release, "check_workflows")
    mocker.patch.object(prepare_release, "prepare_inputs", return_value=True)
    build = mocker.patch.object(prepare_release, "check_local_builds")
    prepare_release.main()
    checks.assert_called_once_with("example/project", "newsha")
    build.assert_called_once_with()


def test_inputs_are_refreshed_before_spending_time_on_workflow_checks(mocker):
    mocker.patch.object(
        prepare_release, "check_checkout", return_value=("example/project", "abc123")
    )
    prepare = mocker.patch.object(prepare_release, "prepare_inputs", return_value=False)

    def failed_checks(*args):
        prepare.assert_called_once_with()
        raise SystemExit(1)

    mocker.patch.object(prepare_release, "check_workflows", side_effect=failed_checks)
    build = mocker.patch.object(prepare_release, "check_local_builds")
    with pytest.raises(SystemExit):
        prepare_release.main()
    build.assert_not_called()


@pytest.mark.parametrize("moved", [False, True])
def test_preflight_rechecks_source_after_builds(moved, mocker, capsys):
    mocker.patch.object(
        prepare_release,
        "check_checkout",
        side_effect=[
            ("example/project", "abc123"),
            ("example/project", "abc123"),
            ("example/project", "new" if moved else "abc123"),
        ],
    )
    mocker.patch.object(prepare_release, "check_workflows")
    mocker.patch.object(prepare_release, "prepare_inputs", return_value=False)
    mocker.patch.object(prepare_release, "check_local_builds")
    if moved:
        with pytest.raises(SystemExit):
            prepare_release.main()
    else:
        prepare_release.main()
        assert "Release preflight passed" in capsys.readouterr().out


@pytest.mark.parametrize("failed_step", [None, 0, 1, 2, 3])
def test_local_build_preflight_checks_artifacts_and_stops_on_failure(
    failed_step, mocker
):
    commands = []
    artifact_paths = []

    def run(command):
        commands.append(command)
        index = len(commands) - 1
        if index == failed_step:
            return subprocess.CompletedProcess(command, 1)
        if command[:2] == ["uv", "build"]:
            dist = Path(command[-1])
            dist.mkdir()
            (dist / ".gitignore").write_text("*\n", encoding="utf-8")
            for name in ("protostar.whl", "protostar.tar.gz"):
                path = dist / name
                path.write_bytes(b"artifact")
                artifact_paths.append(path)
        return subprocess.CompletedProcess(command, 0)

    mocker.patch.object(prepare_release, "run_repo_cmd", side_effect=run)
    if failed_step is not None:
        with pytest.raises(SystemExit):
            prepare_release.check_local_builds()
        assert len(commands) == failed_step + 1
    else:
        prepare_release.check_local_builds()
        assert commands[0] == ["uv", "lock", "--check"]
        assert commands[2][-2:] == sorted(str(path) for path in artifact_paths)
        assert commands[3][-2:] == ["build", "--strict"]
    assert all(not path.exists() for path in artifact_paths)


def _review_commands(mocker: MockerFixture, *, changed: bool = True) -> MagicMock:
    """Fake refreshes and Git reads before any release mutation."""
    return mocker.patch(
        "scripts.prepare_release.run_repo_cmd",
        side_effect=[
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess(
                [],
                0,
                stdout=" M src/protostar/_fallbacks.py\n" if changed else "",
                stderr="",
            ),
            *(
                [subprocess.CompletedProcess([], 0, stdout="-old\n+new\n", stderr="")]
                if changed
                else []
            ),
            *[subprocess.CompletedProcess([], 0) for _ in range(3)],
        ],
    )


def test_preparation_refreshes_both_inputs_before_review(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    run = _review_commands(mocker, changed=False)
    prepare_release.prepare_inputs()
    assert "current and committed" in capsys.readouterr().out
    assert run.call_args_list == [
        mocker.call([sys.executable, "-m", "scripts.sync_registry_fallbacks"]),
        mocker.call([sys.executable, "-m", "scripts.sync_secret_rules"]),
        mocker.call(
            ["git", "status", "--porcelain", "--", *RELEASE_INPUTS],
            capture_output=True,
        ),
    ]


def test_accepting_diff_commits_only_release_inputs_and_pushes(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    run = _review_commands(mocker)
    mocker.patch("sys.stdin.isatty", return_value=True)
    prompt = mocker.patch("builtins.input", side_effect=["maybe", "Y"])
    render = mocker.spy(prepare_release, "report_code")

    prepare_release.prepare_inputs()

    render.assert_called_once_with("-old\n+new", CodeLanguage.DIFF)
    assert prompt.call_count == 2
    assert run.call_args_list[3:] == [
        mocker.call(
            [
                "git",
                "diff",
                "--no-ext-diff",
                "--no-color",
                "HEAD",
                "--",
                *RELEASE_INPUTS,
            ],
            capture_output=True,
        ),
        mocker.call(["git", "add", "--", *RELEASE_INPUTS]),
        mocker.call(
            [
                "git",
                "commit",
                "--only",
                "-m",
                "chore(release): refresh generated release inputs",
                "--",
                *RELEASE_INPUTS,
            ]
        ),
        mocker.call(["git", "push"]),
    ]
    assert "Verify this new commit" in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["", "n", "NO", EOFError(), KeyboardInterrupt()])
def test_declining_or_cancelling_review_never_commits_or_pushes(
    answer: str | BaseException, mocker: MockerFixture
) -> None:
    run = _review_commands(mocker)
    mocker.patch("sys.stdin.isatty", return_value=True)
    mocker.patch(
        "builtins.input",
        side_effect=answer if isinstance(answer, BaseException) else None,
        return_value=answer,
    )
    with pytest.raises(SystemExit) as error:
        prepare_release.prepare_inputs()
    assert error.value.code == 1
    assert run.call_count == 4


def test_noninteractive_review_displays_diff_without_prompting(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    run = _review_commands(mocker)
    mocker.patch("sys.stdin.isatty", return_value=False)
    prompt = mocker.patch("builtins.input")
    with pytest.raises(SystemExit) as error:
        prepare_release.prepare_inputs()
    assert error.value.code == 1
    prompt.assert_not_called()
    assert run.call_count == 4
    output = capsys.readouterr()
    assert "-old\n+new" in output.out
    assert "interactive review" in output.err


def test_empty_diff_cannot_be_accepted(mocker: MockerFixture) -> None:
    run = _review_commands(mocker)
    run.side_effect = [
        subprocess.CompletedProcess([], 0, stdout="changed", stderr=""),
        subprocess.CompletedProcess([], 0),
        subprocess.CompletedProcess([], 0, stdout="changed", stderr=""),
        subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    ]
    prompt = mocker.patch("builtins.input")
    with pytest.raises(SystemExit) as error:
        prepare_release.prepare_inputs()
    assert error.value.code == 1
    prompt.assert_not_called()
    assert run.call_count == 4


@pytest.mark.integration
def test_release_commit_and_push_leave_unrelated_staged_changes_alone(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **fixture_environment(),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "XDG_CONFIG_HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
        "GIT_AUTHOR_NAME": "Release test",
        "GIT_AUTHOR_EMAIL": "release@example.invalid",
        "GIT_COMMITTER_NAME": "Release test",
        "GIT_COMMITTER_EMAIL": "release@example.invalid",
    }

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

    remote = tmp_path / "remote.git"
    git("init", "--bare", str(remote))
    git("init", "-b", "main")
    git("config", "core.hooksPath", str(tmp_path / "no-hooks"))
    for name in (*RELEASE_INPUTS, "unrelated.py"):
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "initial")
    git("remote", "add", "origin", str(remote))
    git("push", "-u", "origin", "main")
    (workspace / RELEASE_INPUTS[0]).write_text("updated\n", encoding="utf-8")
    (workspace / "unrelated.py").write_text("staged edit\n", encoding="utf-8")
    git("add", "unrelated.py")

    def run(
        command: list[str], *, capture_output: bool = False
    ) -> subprocess.CompletedProcess[str]:
        if command[0] != "git":
            return subprocess.CompletedProcess(command, 0)
        return subprocess.run(
            command,
            cwd=workspace,
            env=env,
            text=True,
            capture_output=capture_output,
        )

    mocker.patch.object(prepare_release, "run_repo_cmd", side_effect=run)
    mocker.patch("sys.stdin.isatty", return_value=True)
    mocker.patch("builtins.input", return_value="y")
    prepare_release.prepare_inputs()

    assert (
        git("show", "--format=", "--name-only", "HEAD").stdout.strip()
        == RELEASE_INPUTS[0]
    )
    assert git("diff", "--cached", "--name-only").stdout.strip() == "unrelated.py"
    assert git("show", "HEAD:unrelated.py").stdout == "original\n"
    assert git("rev-parse", "HEAD").stdout == git("rev-parse", "origin/main").stdout


@pytest.mark.parametrize("failed_step", range(7))
def test_preparation_stops_on_generation_review_commit_or_push_failure(
    failed_step: int, mocker: MockerFixture
) -> None:
    mocker.patch("sys.stdin.isatty", return_value=True)
    mocker.patch("builtins.input", return_value="y")
    results = [
        subprocess.CompletedProcess([], 0, stdout="changed", stderr="")
        for _ in range(failed_step)
    ]
    results.append(subprocess.CompletedProcess([], 2, stdout="", stderr="failed\n"))
    run = mocker.patch("scripts.prepare_release.run_repo_cmd", side_effect=results)

    with pytest.raises(SystemExit) as error:
        prepare_release.prepare_inputs()

    assert error.value.code == 2
    assert run.call_count == failed_step + 1


@pytest.mark.parametrize("check", [False, True])
def test_fallback_refresh_writes_successfully_while_check_only_reports_drift(
    check: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    target = tmp_path / "_fallbacks.py"
    target.write_text("original\n", encoding="utf-8")
    revisions = dict(DEFAULT_REVISIONS)
    revisions[next(iter(revisions))] = "v99.0.0"
    payload = json.dumps({"schema_version": 1, "hooks": revisions}).encode()
    mocker.patch(
        "scripts._common.urllib.request.urlopen",
        return_value=io.BytesIO(payload),
    )
    monkeypatch.setattr(sync_registry_fallbacks, "FALLBACKS_FILE", target)
    monkeypatch.setattr(
        sys, "argv", ["sync_registry_fallbacks.py", *(["--check"] if check else [])]
    )

    if check:
        with pytest.raises(SystemExit) as error:
            sync_registry_fallbacks.main()
        assert error.value.code == 1
        assert target.read_text(encoding="utf-8") == "original\n"
    else:
        sync_registry_fallbacks.main()
        assert target.read_text(
            encoding="utf-8"
        ) == sync_registry_fallbacks.generate_fallbacks_content(revisions)


@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize(
    "hooks",
    [
        None,
        [],
        "not a mapping",
        {},
        {next(iter(DEFAULT_REVISIONS)): "v1.0.0"},
        *[
            {**DEFAULT_REVISIONS, next(iter(DEFAULT_REVISIONS)): revision}
            for revision in INVALID_REVISIONS
        ],
    ],
)
def test_invalid_registry_cannot_replace_release_fallbacks(
    check: bool,
    hooks: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "_fallbacks.py"
    target.write_bytes(b"original fallback bytes\n")
    monkeypatch.setattr(sync_registry_fallbacks, "FALLBACKS_FILE", target)
    monkeypatch.setattr(
        sys, "argv", ["sync_registry_fallbacks.py", *(["--check"] if check else [])]
    )
    mocker.patch.object(
        sync_registry_fallbacks,
        "fetch_bytes",
        return_value=json.dumps({"schema_version": 1, "hooks": hooks}).encode(),
    )

    with pytest.raises(SystemExit) as error:
        sync_registry_fallbacks.main()

    assert error.value.code == 1
    assert target.read_bytes() == b"original fallback bytes\n"
    assert "registry" in capsys.readouterr().err


def test_fallback_generator_escapes_revisions_and_sorts_entries() -> None:
    revisions = {
        "https://example.invalid/z": 'tag"with\\escapes\nand newline',
        "https://example.invalid/a": "v1.0.0",
    }

    source = sync_registry_fallbacks.generate_fallbacks_content(revisions)
    assignment = ast.parse(source).body[1]
    assert isinstance(assignment, ast.AnnAssign)
    assert assignment.value is not None
    restored = ast.literal_eval(assignment.value)

    assert restored == revisions
    assert list(restored) == sorted(revisions)
