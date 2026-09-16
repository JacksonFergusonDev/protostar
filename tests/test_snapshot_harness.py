"""Unit tests for snapshot regression drift verification harness."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from scripts.run_snapshots import check_snapshot_drift


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


def test_check_snapshot_drift_empty_targets(tmp_path: Path) -> None:
    """Verifies that non-existent or empty target sequences pass immediately."""
    non_existent = tmp_path / "does_not_exist"
    assert check_snapshot_drift([non_existent]) is True
    assert check_snapshot_drift([]) is True


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
