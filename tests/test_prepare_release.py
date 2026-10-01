"""Release preparation refreshes inputs before allowing a version bump."""

import ast
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protostar._fallbacks import DEFAULT_REVISIONS
from scripts import prepare_release, sync_registry_fallbacks
from scripts._common import SCRIPTS_DIR

INVALID_REVISIONS: tuple[object, ...] = (None, 1, [], {}, "", " \t\n")


@pytest.mark.parametrize(
    "status",
    [
        "",
        " M src/protostar/_fallbacks.py\n",
        "M  src/protostar/_secret_rules.py\n",
        "?? src/protostar/_secret_rules.py\n",
    ],
)
def test_preparation_refreshes_both_inputs_before_review(
    status: str, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    run = mocker.patch(
        "scripts.prepare_release.run_repo_cmd",
        side_effect=[
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0, stdout=status, stderr=""),
        ],
    )

    if status:
        with pytest.raises(SystemExit) as error:
            prepare_release.main()
        assert error.value.code == 1
        output = capsys.readouterr().out
        assert "Review required" in output
        assert "commit the changes and rerun" in output
        assert "just bump <part>" in output
    else:
        prepare_release.main()
        assert "current and committed" in capsys.readouterr().out

    assert run.call_args_list == [
        mocker.call(
            [
                sys.executable,
                str(SCRIPTS_DIR / "sync_registry_fallbacks.py"),
            ]
        ),
        mocker.call([sys.executable, str(SCRIPTS_DIR / "sync_secret_rules.py")]),
        mocker.call(
            ["git", "status", "--porcelain", "--", *prepare_release.RELEASE_INPUTS],
            capture_output=True,
        ),
    ]


@pytest.mark.parametrize("failed_step", [0, 1, 2])
def test_preparation_stops_on_generation_or_git_failure(
    failed_step: int, mocker: MockerFixture
) -> None:
    results: list[subprocess.CompletedProcess[str]] = [
        subprocess.CompletedProcess([], 0) for _ in range(failed_step)
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
