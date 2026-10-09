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
from scripts._common import SCRIPTS_DIR, CodeLanguage, fixture_environment

INVALID_REVISIONS: tuple[object, ...] = (None, 1, [], {}, "", " \t\n")


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
    prepare_release.main()
    assert "current and committed" in capsys.readouterr().out
    assert run.call_args_list == [
        mocker.call([sys.executable, str(SCRIPTS_DIR / "sync_registry_fallbacks.py")]),
        mocker.call([sys.executable, str(SCRIPTS_DIR / "sync_secret_rules.py")]),
        mocker.call(
            ["git", "status", "--porcelain", "--", *prepare_release.RELEASE_INPUTS],
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

    prepare_release.main()

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
                *prepare_release.RELEASE_INPUTS,
            ],
            capture_output=True,
        ),
        mocker.call(["git", "add", "--", *prepare_release.RELEASE_INPUTS]),
        mocker.call(
            [
                "git",
                "commit",
                "--only",
                "-m",
                "chore(release): refresh generated release inputs",
                "--",
                *prepare_release.RELEASE_INPUTS,
            ]
        ),
        mocker.call(["git", "push"]),
    ]
    assert "Continuing release" in capsys.readouterr().out


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
        prepare_release.main()
    assert error.value.code == 1
    assert run.call_count == 4


def test_noninteractive_review_displays_diff_without_prompting(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    run = _review_commands(mocker)
    mocker.patch("sys.stdin.isatty", return_value=False)
    prompt = mocker.patch("builtins.input")
    with pytest.raises(SystemExit) as error:
        prepare_release.main()
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
        prepare_release.main()
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
    for name in (*prepare_release.RELEASE_INPUTS, "unrelated.py"):
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "initial")
    git("remote", "add", "origin", str(remote))
    git("push", "-u", "origin", "main")
    (workspace / prepare_release.RELEASE_INPUTS[0]).write_text(
        "updated\n", encoding="utf-8"
    )
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
    prepare_release.main()

    assert (
        git("show", "--format=", "--name-only", "HEAD").stdout.strip()
        == prepare_release.RELEASE_INPUTS[0]
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
        prepare_release.main()

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
