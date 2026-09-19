"""Unit tests for snapshot regression drift verification harness."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from scripts._common import DOCS_GENERATED_DIR, SNAPSHOTS_DIR
from scripts.run_snapshots import (
    _extract_and_write_targets,
    check_snapshot_drift,
    main,
)


def _mock_subprocess_run_factory(
    ls_files: Sequence[str] = (),
    diff_name_status: Sequence[str] = (),
    diff_head: str = "",
    no_index_diff: str = "",
) -> Any:
    """Creates a mock subprocess.run function simulating Git command outputs.

    Args:
        ls_files: List of repo-relative paths to return from 'git ls-files'.
        diff_name_status: List of status lines to return from 'git diff HEAD --name-status'.
        diff_head: Output string for 'git diff HEAD --color=never'.
        no_index_diff: Output string for 'git diff --no-index'.

    Returns:
        Callable simulating subprocess.run with deterministic outputs.
    """

    def mock_run(
        cmd: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if "ls-files" in cmd:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="\n".join(ls_files) + ("\n" if ls_files else ""),
                stderr="",
            )
        if "diff" in cmd and "--name-status" in cmd:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="\n".join(diff_name_status) + ("\n" if diff_name_status else ""),
                stderr="",
            )
        if "diff" in cmd and "HEAD" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=diff_head, stderr="")
        if "diff" in cmd and "--no-index" in cmd:
            return subprocess.CompletedProcess(cmd, 1, stdout=no_index_diff, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return mock_run


def test_check_snapshot_drift_empty_targets() -> None:
    """Verifies that an empty target sequence passes immediately without running subprocesses."""
    assert check_snapshot_drift([]) is True


def test_check_snapshot_drift_untracked_nonexistent_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Verifies that an untracked, non-existent target reports clean when Git knows nothing about it."""
    monkeypatch.chdir(tmp_path)
    non_existent = tmp_path / "never_tracked"

    mocker.patch(
        "subprocess.run",
        side_effect=_mock_subprocess_run_factory(
            ls_files=[],
            diff_name_status=[],
        ),
    )

    assert check_snapshot_drift([non_existent]) is True


def test_check_snapshot_drift_deleted_tracked_target_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verifies that a deleted tracked target directory fails drift check even if absent from disk."""
    monkeypatch.chdir(tmp_path)
    cli_dir = tmp_path / "tests" / "snapshots" / "cli"
    # Note: cli_dir is NOT created on disk, simulating it being deleted while tracked

    rel_path = "tests/snapshots/cli/pyproject.toml"

    mocker.patch(
        "subprocess.run",
        side_effect=_mock_subprocess_run_factory(
            ls_files=[rel_path],
            diff_name_status=[f"D\t{rel_path}"],
            diff_head="deleted file mode 100644",
        ),
    )

    result = check_snapshot_drift([cli_dir])
    assert result is False

    captured = capsys.readouterr()
    assert "SNAPSHOT REGRESSION DETECTED" in captured.err
    assert f"D {rel_path}" in captured.err


def test_check_snapshot_drift_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verifies that an untouched working tree with matching index returns True."""
    monkeypatch.chdir(tmp_path)
    file1 = tmp_path / "tests" / "snapshots" / "cli" / "pyproject.toml"
    file1.parent.mkdir(parents=True, exist_ok=True)
    file1.write_text("[project]\nname = 'cli'\n", encoding="utf-8")

    rel_path = "tests/snapshots/cli/pyproject.toml"
    mocker.patch(
        "subprocess.run",
        side_effect=_mock_subprocess_run_factory(
            ls_files=[rel_path],
            diff_name_status=[],
        ),
    )

    result = check_snapshot_drift([tmp_path / "tests" / "snapshots" / "cli"])
    assert result is True

    captured = capsys.readouterr()
    assert "match expected state" in captured.out
    assert captured.err == ""


def test_check_snapshot_drift_unstaged_modification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verifies that an unstaged tracked file modification returns False and prints diffs."""
    monkeypatch.chdir(tmp_path)
    target_file = tmp_path / "tests" / "snapshots" / "cli" / "pyproject.toml"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("[project]\nname = 'modified'\n", encoding="utf-8")

    rel_path = "tests/snapshots/cli/pyproject.toml"
    diff_snippet = (
        "--- a/tests/snapshots/cli/pyproject.toml\n"
        "+++ b/tests/snapshots/cli/pyproject.toml\n"
        "@@ -1,2 +1,2 @@\n"
        "-[project]\nname = 'cli'\n"
        "+[project]\nname = 'modified'\n"
    )

    mocker.patch(
        "subprocess.run",
        side_effect=_mock_subprocess_run_factory(
            ls_files=[rel_path],
            diff_name_status=[f"M\t{rel_path}"],
            diff_head=diff_snippet,
        ),
    )

    result = check_snapshot_drift([tmp_path / "tests" / "snapshots" / "cli"])
    assert result is False

    captured = capsys.readouterr()
    assert "SNAPSHOT REGRESSION DETECTED" in captured.err
    assert f"M {rel_path}" in captured.err
    assert diff_snippet in captured.err


def test_check_snapshot_drift_staged_addition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verifies that a staged index change against HEAD returns False."""
    monkeypatch.chdir(tmp_path)
    new_file = tmp_path / "tests" / "snapshots" / "constraints.txt"
    new_file.parent.mkdir(parents=True, exist_ok=True)
    new_file.write_text("astropy==8.0.1\n", encoding="utf-8")

    rel_path = "tests/snapshots/constraints.txt"
    diff_snippet = (
        "--- /dev/null\n"
        "+++ b/tests/snapshots/constraints.txt\n"
        "@@ -0,0 +1 @@\n"
        "+astropy==8.0.1\n"
    )

    mocker.patch(
        "subprocess.run",
        side_effect=_mock_subprocess_run_factory(
            ls_files=[rel_path],
            diff_name_status=[f"A\t{rel_path}"],
            diff_head=diff_snippet,
        ),
    )

    result = check_snapshot_drift([tmp_path / "tests" / "snapshots"])
    assert result is False

    captured = capsys.readouterr()
    assert "SNAPSHOT REGRESSION DETECTED" in captured.err
    assert f"A {rel_path}" in captured.err


def test_check_snapshot_drift_untracked_and_gitignored_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verifies that an untracked disk file is caught even if omitted from Git index."""
    monkeypatch.chdir(tmp_path)
    ignored_file = tmp_path / "tests" / "snapshots" / "ml" / ".env"
    ignored_file.parent.mkdir(parents=True, exist_ok=True)
    ignored_file.write_text("SECRET=123\n", encoding="utf-8")

    no_index_diff = (
        "diff --git a/dev/null b/tests/snapshots/ml/.env\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/tests/snapshots/ml/.env\n"
        "@@ -0,0 +1 @@\n"
        "+SECRET=123\n"
    )

    mocker.patch(
        "subprocess.run",
        side_effect=_mock_subprocess_run_factory(
            ls_files=[],
            diff_name_status=[],
            no_index_diff=no_index_diff,
        ),
    )

    result = check_snapshot_drift([tmp_path / "tests" / "snapshots" / "ml"])
    assert result is False

    captured = capsys.readouterr()
    assert "SNAPSHOT REGRESSION DETECTED" in captured.err
    assert "?? tests/snapshots/ml/.env" in captured.err
    assert no_index_diff in captured.err


def test_check_snapshot_drift_deleted_tracked_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verifies that a file tracked by Git but missing from disk returns False."""
    monkeypatch.chdir(tmp_path)
    snapshot_dir = tmp_path / "tests" / "snapshots" / "cli"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    rel_path = "tests/snapshots/cli/deleted_file.txt"

    mocker.patch(
        "subprocess.run",
        side_effect=_mock_subprocess_run_factory(
            ls_files=[rel_path],
            diff_name_status=[f"D\t{rel_path}"],
            diff_head="deleted file mode 100644",
        ),
    )

    result = check_snapshot_drift([snapshot_dir])
    assert result is False

    captured = capsys.readouterr()
    assert "SNAPSHOT REGRESSION DETECTED" in captured.err
    assert f"D {rel_path}" in captured.err


def test_check_snapshot_drift_excludes_cache_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verifies that __pycache__, .pytest_cache, and .DS_Store are ignored during scan."""
    monkeypatch.chdir(tmp_path)
    base_dir = tmp_path / "tests" / "snapshots" / "cli"
    base_dir.mkdir(parents=True, exist_ok=True)

    # Valid tracked file
    valid_file = base_dir / "valid.txt"
    valid_file.write_text("valid\n", encoding="utf-8")

    # Ephemeral caches that should not be detected as untracked drift
    pycache = base_dir / "__pycache__" / "temp.cpython-313.pyc"
    pycache.parent.mkdir(parents=True, exist_ok=True)
    pycache.write_bytes(b"bytecode")

    ds_store = base_dir / ".DS_Store"
    ds_store.write_bytes(b"macOS metadata")

    pytest_cache = base_dir / ".pytest_cache" / "v"
    pytest_cache.parent.mkdir(parents=True, exist_ok=True)
    pytest_cache.write_bytes(b"cache")

    rel_path = "tests/snapshots/cli/valid.txt"
    mocker.patch(
        "subprocess.run",
        side_effect=_mock_subprocess_run_factory(
            ls_files=[rel_path],
            diff_name_status=[],
        ),
    )

    result = check_snapshot_drift([base_dir])
    assert result is True

    captured = capsys.readouterr()
    assert "match expected state" in captured.out
    assert captured.err == ""


def test_check_snapshot_drift_filtered_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Verifies that checking a filtered scenario targets only its relevant paths."""
    monkeypatch.chdir(tmp_path)
    cli_dir = tmp_path / "tests" / "snapshots" / "cli"
    cli_dir.mkdir(parents=True, exist_ok=True)
    (cli_dir / "file.txt").write_text("content\n", encoding="utf-8")

    tree_doc = tmp_path / "docs" / "generated" / "tree_cli.txt"
    tree_doc.parent.mkdir(parents=True, exist_ok=True)
    tree_doc.write_text(".\n└── file.txt\n", encoding="utf-8")

    captured_cmds: list[list[str]] = []
    real_factory = _mock_subprocess_run_factory(
        ls_files=["tests/snapshots/cli/file.txt", "docs/generated/tree_cli.txt"]
    )

    def spy_run(cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        captured_cmds.append(cmd)
        return real_factory(cmd, *args, **kwargs)

    mocker.patch("subprocess.run", side_effect=spy_run)

    targets = [cli_dir, tree_doc]
    assert check_snapshot_drift(targets) is True

    # Assert that git ls-files and git diff were called targeting only these paths
    ls_call = next(cmd for cmd in captured_cmds if "ls-files" in cmd)
    assert "tests/snapshots/cli" in ls_call
    assert "docs/generated/tree_cli.txt" in ls_call
    # Other scenarios like ml or dsp should not be present in the command
    assert "tests/snapshots/ml" not in ls_call


def test_extract_and_write_targets_preserves_exact_bytes(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """Verifies that target extraction preserves exact bytes including CRLF, whitespace, and binary data."""
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)

    # 1. CRLF line endings
    crlf_bytes = b"first_line\r\nsecond_line\r\n"
    (source_dir / "crlf.txt").write_bytes(crlf_bytes)

    # 2. Trailing whitespace without rstrip
    ws_bytes = b"trailing_space   \ntrailing_tabs\t\t\n"
    (source_dir / "trailing_ws.txt").write_bytes(ws_bytes)

    # 3. 0-byte empty file
    empty_bytes = b""
    (source_dir / "empty.txt").write_bytes(empty_bytes)

    # 4. Arbitrary binary bytes
    bin_bytes = bytes([0x00, 0xFF, 0xFE, 0x80, 0x12, 0x34])
    (source_dir / "binary.bin").write_bytes(bin_bytes)

    # 5. Pre-commit config fixture renaming
    precommit_bytes = (
        b"repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
    )
    (source_dir / ".pre-commit-config.yaml").write_bytes(precommit_bytes)

    # 6. Excluded cache directories and lockfiles
    cache_file = source_dir / "__pycache__" / "temp.cpython-313.pyc"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_bytes(b"cache")

    venv_file = source_dir / ".venv" / "bin" / "python"
    venv_file.parent.mkdir(parents=True)
    venv_file.write_bytes(b"venv")

    lock_file = source_dir / "uv.lock"
    lock_file.write_bytes(b"lock")

    fake_snapshots_dir = tmp_path / "snapshots"
    fake_docs_dir = tmp_path / "docs_generated"
    mocker.patch("scripts.run_snapshots.SNAPSHOTS_DIR", fake_snapshots_dir)
    mocker.patch("scripts.run_snapshots.DOCS_GENERATED_DIR", fake_docs_dir)
    mocker.patch("scripts.run_snapshots.generate_tree", return_value="mock tree\n")

    fixture_root = fake_snapshots_dir / "my_fixture"
    fixture_root.mkdir(parents=True)
    obsolete_file = fixture_root / "obsolete.txt"
    obsolete_file.write_bytes(b"old")
    obsolete_empty_dir = fixture_root / "obsolete_nested" / "deep_dir"
    obsolete_empty_dir.mkdir(parents=True)
    obsolete_nested_file = obsolete_empty_dir / "deep_file.txt"
    obsolete_nested_file.write_bytes(b"nested_old")

    _extract_and_write_targets(source_dir, "my_fixture")

    # Assert exact byte preservation
    assert (fixture_root / "crlf.txt").read_bytes() == crlf_bytes
    assert (fixture_root / "trailing_ws.txt").read_bytes() == ws_bytes
    assert (fixture_root / "empty.txt").read_bytes() == empty_bytes
    assert (fixture_root / "binary.bin").read_bytes() == bin_bytes
    assert (
        fixture_root / "pre-commit-config.fixture.yaml"
    ).read_bytes() == precommit_bytes
    assert not (fixture_root / ".pre-commit-config.yaml").exists()

    # Assert excluded caches were omitted
    assert not (fixture_root / "__pycache__").exists()
    assert not (fixture_root / ".venv").exists()
    assert not (fixture_root / "uv.lock").exists()

    # Assert obsolete file and empty directories were pruned
    assert not obsolete_file.exists()
    assert not (fixture_root / "obsolete_nested").exists()

    # Assert tree file written
    assert (fake_docs_dir / "tree_my_fixture.txt").read_text(
        encoding="utf-8"
    ) == "mock tree\n"


def test_harness_main_filtered_scenario_scope(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Verifies that running the main entrypoint with --scenario targets only that scenario."""
    monkeypatch.setattr("sys.argv", ["run_snapshots.py", "--scenario", "cli"])
    mock_build = mocker.patch("scripts.run_snapshots.build_snapshots")
    mock_docs = mocker.patch("scripts.run_snapshots.generate_docs_assets")
    mock_diff = mocker.patch("scripts.run_snapshots.generate_diff_fixtures")
    mock_check = mocker.patch(
        "scripts.run_snapshots.check_snapshot_drift", return_value=True
    )

    main()

    mock_build.assert_called_once_with(scenario_name="cli")
    mock_docs.assert_not_called()
    mock_diff.assert_not_called()
    mock_check.assert_called_once_with(
        [
            SNAPSHOTS_DIR / "cli",
            DOCS_GENERATED_DIR / "tree_cli.txt",
        ]
    )


def test_harness_main_nonzero_exit_on_drift(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Verifies that the main entrypoint exits with code 1 when drift is detected."""
    monkeypatch.setattr("sys.argv", ["run_snapshots.py", "--scenario", "cli"])
    mocker.patch("scripts.run_snapshots.build_snapshots")
    mocker.patch("scripts.run_snapshots.check_snapshot_drift", return_value=False)

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_harness_main_scenario_failure(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Verifies that a failure during snapshot generation propagates."""
    monkeypatch.setattr("sys.argv", ["run_snapshots.py", "--scenario", "cli"])
    mocker.patch(
        "scripts.run_snapshots.build_snapshots",
        side_effect=RuntimeError("Subprocess failed"),
    )

    with pytest.raises(RuntimeError, match="Subprocess failed"):
        main()


def test_harness_main_no_check_flag(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Verifies that --no-check skips git drift verification."""
    monkeypatch.setattr(
        "sys.argv", ["run_snapshots.py", "--scenario", "cli", "--no-check"]
    )
    mocker.patch("scripts.run_snapshots.build_snapshots")
    mock_check = mocker.patch("scripts.run_snapshots.check_snapshot_drift")

    main()

    mock_check.assert_not_called()


def test_generated_lifecycle_examples_use_real_decisions_and_are_repeatable(
    tmp_path, monkeypatch, mocker
):
    """Generated review/check examples separate accepted bytes from conflicts."""
    import json

    from scripts import generate_docs_assets as assets

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(assets, "DOCS_GENERATED_DIR", tmp_path / "generated")
    import tempfile

    temporary_directory = tempfile.TemporaryDirectory
    mocker.patch(
        "scripts.generate_docs_assets.tempfile.TemporaryDirectory",
        side_effect=lambda: temporary_directory(dir=tmp_path),
    )
    mocker.patch("subprocess.run", side_effect=AssertionError("subprocess"))
    mocker.patch("subprocess.Popen", side_effect=AssertionError("subprocess"))
    assets.generate_agent_payloads()
    reviewed = json.loads(
        (tmp_path / "generated/agent_payload_reviewed.json").read_text()
    )
    checked = json.loads((tmp_path / "generated/agent_payload_check.json").read_text())
    assert checked == {**reviewed, "check_passed": False}
    assert [item["path"] for item in reviewed["diffs"]] == ["safe.txt"]
    assert reviewed["review"]["conflicts"][0]["file"] == ".github/renovate.json"
    before = {
        path.name: path.read_bytes() for path in (tmp_path / "generated").iterdir()
    }
    assets.generate_agent_payloads()
    assert {
        path.name: path.read_bytes() for path in (tmp_path / "generated").iterdir()
    } == before
