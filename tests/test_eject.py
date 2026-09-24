"""Project ejection keeps scaffolded files and removes only tracking state."""

import argparse
import stat
import sys
from pathlib import Path

import pytest

from protostar.cli.eject import handle_eject
from protostar.cli.parser import build_parser
from protostar.eject import prepare_ejection
from protostar.errors import (
    ConfigurationError,
    FileSystemError,
    InvalidUsageError,
    StaleReviewError,
    UnsupportedFilesystemNodeError,
)
from protostar.fs_transaction import TransactionAwareFS
from protostar.recipe import remove_recipe

PYPROJECT = (
    '[project]\nname = "demo" # keep this comment\n\n'
    "# ==================================================\n"
    "# Tool Configuration\n"
    "# ==================================================\n\n"
    "# ---- Ruff ---- #\n"
    "[tool.ruff]\nline-length = 88\n\n"
    "# ---- Protostar ---- #\n"
    "[tool.protostar]\nversion = 1\n\n"
    "[tool.protostar.fallback]\nruff = true\n"
)
EXPECTED = (
    '[project]\nname = "demo" # keep this comment\n\n'
    "# ==================================================\n"
    "# Tool Configuration\n"
    "# ==================================================\n\n"
    "# ---- Ruff ---- #\n"
    "[tool.ruff]\nline-length = 88\n"
)


def project(tmp_path: Path) -> None:
    """Creates a tracked project with an unrelated uv dependency lockfile."""
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    (tmp_path / "protostar.lock").write_bytes(b"ownership state\n")
    (tmp_path / "uv.lock").write_bytes(b"resolver state\n")


def test_remove_recipe_preserves_unrelated_toml_and_layout():
    """Removing a recipe also removes its generated heading."""
    assert remove_recipe(PYPROJECT) == EXPECTED
    assert remove_recipe(EXPECTED) == EXPECTED


def test_remove_recipe_clears_orphaned_banner():
    """The tool banner disappears when the recipe was the only tool section."""
    source = (
        '[project]\nname = "demo"\n\n'
        "# ==================================================\n"
        "# Tool Configuration\n"
        "# ==================================================\n\n"
        "# ---- Protostar ---- #\n"
        "[tool.protostar]\nversion = 1\n"
    )
    assert remove_recipe(source) == '[project]\nname = "demo"\n'


def test_remove_recipe_handles_scattered_child_tables():
    """A child table after another tool is removed with the whole recipe."""
    source = (
        "[tool.protostar]\nversion = 1\n\n"
        "[tool.ruff]\nline-length = 88\n\n"
        "[tool.protostar.fallback]\nruff = true\n"
    )
    assert remove_recipe(source) == "[tool.ruff]\nline-length = 88\n\n"


def test_ejection_changes_only_named_files_and_keeps_file_mode(tmp_path: Path):
    """The lock is deleted and the unrelated dependency lock remains byte exact."""
    project(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.chmod(0o640)
    prepared = prepare_ejection(tmp_path)
    assert prepared.changed_paths == ("protostar.lock", "pyproject.toml")
    assert pyproject.read_text() == PYPROJECT

    prepared.apply()

    assert pyproject.read_text() == EXPECTED
    if sys.platform != "win32":
        assert stat.S_IMODE(pyproject.stat().st_mode) == 0o640
    assert not (tmp_path / "protostar.lock").exists()
    assert (tmp_path / "uv.lock").read_bytes() == b"resolver state\n"
    assert prepare_ejection(tmp_path).changed_paths == ()


def test_ejection_rejects_stale_review_before_mutation(tmp_path: Path):
    """A changed project file invalidates the preview and retains the lock."""
    project(tmp_path)
    prepared = prepare_ejection(tmp_path)
    (tmp_path / "pyproject.toml").write_text(PYPROJECT + "# later edit\n")

    with pytest.raises(StaleReviewError):
        prepared.apply()

    assert (tmp_path / "protostar.lock").read_bytes() == b"ownership state\n"


def test_ejection_rejects_invalid_toml_before_deleting_lock(tmp_path: Path):
    """A malformed pyproject leaves both tracking files untouched."""
    project(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.protostar\n")
    with pytest.raises(ConfigurationError):
        prepare_ejection(tmp_path)
    assert (tmp_path / "protostar.lock").exists()


def test_ejection_rejects_a_linked_lockfile(tmp_path: Path):
    """The command will not follow or unlink a symbolic lockfile."""
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    (tmp_path / "elsewhere").write_text("owned elsewhere")
    (tmp_path / "protostar.lock").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(UnsupportedFilesystemNodeError):
        prepare_ejection(tmp_path)


def test_ejection_rolls_back_deleted_lock_when_pyproject_write_fails(
    tmp_path: Path, mocker
):
    """A late write failure restores both original files and their modes."""
    project(tmp_path)
    lock = tmp_path / "protostar.lock"
    lock.chmod(0o600)
    prepared = prepare_ejection(tmp_path)
    mocker.patch.object(TransactionAwareFS, "write_bytes", side_effect=OSError("full"))

    with pytest.raises(FileSystemError, match="full"):
        prepared.apply()

    assert lock.read_bytes() == b"ownership state\n"
    if sys.platform != "win32":
        assert stat.S_IMODE(lock.stat().st_mode) == 0o600
    assert (tmp_path / "pyproject.toml").read_text() == PYPROJECT


def test_eject_requires_confirmation_in_noninteractive_mode(
    tmp_path: Path, monkeypatch, mocker
):
    """Automation cannot erase tracking files without an explicit --yes."""
    project(tmp_path)
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.cli.eject.is_interactive", return_value=False)

    with pytest.raises(InvalidUsageError, match="requires confirmation"):
        handle_eject(argparse.Namespace(dry_run=False, yes=False))

    assert (tmp_path / "protostar.lock").exists()


def test_eject_interactive_decline_keeps_files(tmp_path: Path, monkeypatch, mocker):
    """The default-no confirmation leaves the tracked project untouched."""
    project(tmp_path)
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.cli.eject.is_interactive", return_value=True)
    confirm = mocker.patch("protostar.cli.eject.Confirm.ask", return_value=False)

    handle_eject(argparse.Namespace(dry_run=False, yes=False))

    assert confirm.call_args.kwargs["default"] is False
    assert (tmp_path / "protostar.lock").exists()
    assert (tmp_path / "pyproject.toml").read_text() == PYPROJECT


def test_eject_dry_run_json_reports_diff_without_writing(
    tmp_path: Path, monkeypatch, mocker
):
    """Machine preview returns one JSON payload with the exact TOML removal."""
    project(tmp_path)
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.cli.eject.ui.is_json_mode", True)
    emit = mocker.patch("protostar.cli.eject.ui.emit_json")

    handle_eject(argparse.Namespace(dry_run=True, yes=False))

    payload = emit.call_args.args[0]
    assert payload["status"] == "planned"
    assert payload["changed_paths"] == ["protostar.lock", "pyproject.toml"]
    assert "-[tool.protostar]" in payload["pyproject_diff"]
    assert (tmp_path / "protostar.lock").exists()


def test_eject_yes_applies_without_prompt(tmp_path: Path, monkeypatch, mocker):
    """An explicit yes applies the reviewed changes in a noninteractive run."""
    project(tmp_path)
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.cli.eject.is_interactive", return_value=False)
    confirm = mocker.patch("protostar.cli.eject.Confirm.ask")

    handle_eject(argparse.Namespace(dry_run=False, yes=True))

    confirm.assert_not_called()
    assert not (tmp_path / "protostar.lock").exists()
    assert (tmp_path / "pyproject.toml").read_text() == EXPECTED


def test_eject_parser_accepts_preview_and_explicit_confirmation():
    """Both automation flags are available on the public subcommand."""
    args = build_parser().parse_args(["eject", "--dry-run", "--yes"])
    assert args.command == "eject"
    assert args.dry_run is True
    assert args.yes is True
