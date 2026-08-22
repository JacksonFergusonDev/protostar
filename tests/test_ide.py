import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from protostar.enums import IDEType
from protostar.errors import FileSystemError
from protostar.ide import check_ide_extensions, write_ide_settings
from protostar.manifest import Severity


def test_ide_type_enum_properties():
    assert IDEType.VSCODE.binary_name == "code"
    assert IDEType.CURSOR.binary_name == "cursor"
    assert IDEType.NONE.binary_name is None


def test_ide_extension_check_with_enum(mocker):
    mocker.patch("protostar.ide.shutil.which", return_value="/usr/local/bin/code")
    mock_result = MagicMock()
    mock_result.stdout = "charliermarsh.ruff\n"
    mocker.patch("protostar.ide.subprocess.run", return_value=mock_result)
    diagnostics = []

    check_ide_extensions(
        ide=IDEType.VSCODE,
        ide_extensions={"charliermarsh.ruff", "ms-python.mypy-type-checker"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    assert len(diagnostics) == 1
    msg, sev = diagnostics[0]
    assert sev == Severity.WARNING
    assert "Missing recommended vscode extensions" in msg


def test_ide_extension_check_bypassed_if_wrong_ide(mocker):
    mock_which = mocker.patch("protostar.ide.shutil.which")
    diagnostics = []

    check_ide_extensions(
        ide="none",
        ide_extensions={"charliermarsh.ruff"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    mock_which.assert_not_called()
    assert diagnostics == []


def test_ide_extension_check_bypassed_if_none_enum(mocker):
    mock_which = mocker.patch("protostar.ide.shutil.which")
    diagnostics = []

    check_ide_extensions(
        ide=IDEType.NONE,
        ide_extensions={"charliermarsh.ruff"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    mock_which.assert_not_called()
    assert diagnostics == []


def test_ide_extension_check_bypassed_if_binary_missing(mocker):
    mock_which = mocker.patch("protostar.ide.shutil.which", return_value=None)
    mock_run = mocker.patch("protostar.ide.subprocess.run")
    diagnostics = []

    check_ide_extensions(
        ide="vscode",
        ide_extensions={"charliermarsh.ruff"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    mock_which.assert_called_once_with("code")
    mock_run.assert_not_called()
    assert diagnostics == []


def test_ide_extension_check_succeeds_without_warnings(mocker):
    mocker.patch("protostar.ide.shutil.which", return_value="/usr/local/bin/cursor")

    mock_result = MagicMock()
    mock_result.stdout = (
        "charliermarsh.ruff\nms-python.mypy-type-checker\nsome-other-ext\n"
    )
    mock_run = mocker.patch("protostar.ide.subprocess.run", return_value=mock_result)
    diagnostics = []

    check_ide_extensions(
        ide="cursor",
        ide_extensions={"charliermarsh.ruff", "ms-python.mypy-type-checker"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    mock_run.assert_called_once_with(
        ["cursor", "--list-extensions"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    assert diagnostics == []


def test_ide_extension_check_flags_missing_extensions(mocker):
    mocker.patch("protostar.ide.shutil.which", return_value="/usr/local/bin/code")

    mock_result = MagicMock()
    mock_result.stdout = "charliermarsh.ruff\n"
    mocker.patch("protostar.ide.subprocess.run", return_value=mock_result)
    diagnostics = []

    check_ide_extensions(
        ide="vscode",
        ide_extensions={"charliermarsh.ruff", "ms-python.mypy-type-checker"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    assert len(diagnostics) == 1
    msg, sev = diagnostics[0]
    assert sev == Severity.WARNING
    assert "ms-python.mypy-type-checker" in msg


def test_ide_extension_check_adds_skip_diagnostic_on_subprocess_error(mocker):
    mocker.patch("protostar.ide.shutil.which", return_value="/usr/local/bin/code")
    mocker.patch(
        "protostar.ide.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="code", timeout=5),
    )
    diagnostics = []

    check_ide_extensions(
        ide="vscode",
        ide_extensions={"charliermarsh.ruff"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    assert len(diagnostics) == 1
    msg, sev = diagnostics[0]
    assert sev == Severity.SKIP
    assert "skipped due to an unexpected error" in msg


def test_ide_extension_check_satisfies_primary_in_tuple(mocker):
    mocker.patch("protostar.ide.shutil.which", return_value="/usr/local/bin/code")
    mock_run = mocker.patch("protostar.ide.subprocess.run")
    mock_run.return_value = MagicMock(
        stdout="ms-python.mypy-type-checker\nother.extension\n"
    )
    diagnostics = []

    check_ide_extensions(
        ide="vscode",
        ide_extensions={("ms-python.mypy-type-checker", "matangover.mypy")},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    assert diagnostics == []


def test_ide_extension_check_satisfies_fallback_in_tuple(mocker):
    mocker.patch("protostar.ide.shutil.which", return_value="/usr/local/bin/code")
    mock_run = mocker.patch("protostar.ide.subprocess.run")
    mock_run.return_value = MagicMock(stdout="matangover.mypy\nother.extension\n")
    diagnostics = []

    check_ide_extensions(
        ide="vscode",
        ide_extensions={("ms-python.mypy-type-checker", "matangover.mypy")},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    assert diagnostics == []


def test_ide_extension_check_fails_missing_tuple(mocker):
    mocker.patch("protostar.ide.shutil.which", return_value="/usr/local/bin/code")
    mock_run = mocker.patch("protostar.ide.subprocess.run")
    mock_run.return_value = MagicMock(stdout="charliermarsh.ruff\nother.extension\n")
    diagnostics = []

    check_ide_extensions(
        ide="vscode",
        ide_extensions={
            ("ms-python.mypy-type-checker", "matangover.mypy"),
            "charliermarsh.ruff",
        },
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    assert len(diagnostics) == 1
    msg, sev = diagnostics[0]
    assert sev == Severity.WARNING
    assert "ms-python.mypy-type-checker or matangover.mypy" in msg
    assert "charliermarsh.ruff" not in msg


def test_write_ide_settings_empty(mocker):
    mock_write = mocker.patch("protostar.ide.atomic_write_text")
    diagnostics = []
    touched = []

    write_ide_settings(
        ide_settings={},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
        on_record_touch=lambda p: touched.append(p),
    )

    mock_write.assert_not_called()
    assert diagnostics == []
    assert touched == []


def test_write_ide_settings_merge(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    settings_file = vscode_dir / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "existing.key": "existing_value",
                "files.exclude": {"**/.git": True},
            }
        )
    )

    diagnostics = []
    touched = []

    write_ide_settings(
        ide_settings={  # type: ignore
            "files.exclude": {"**/.venv": True},
            "new.key": "new_value",
        },
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
        on_record_touch=lambda p: touched.append(p),
    )

    assert diagnostics == []
    assert len(touched) == 1
    assert touched[0] == Path(".vscode/settings.json")

    result = json.loads(settings_file.read_text())
    assert result["existing.key"] == "existing_value"
    assert result["new.key"] == "new_value"
    assert result["files.exclude"] == {"**/.git": True, "**/.venv": True}


def test_write_ide_settings_empty_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    settings_file = vscode_dir / "settings.json"
    settings_file.write_text("   \n  \t")

    diagnostics = []
    touched = []

    write_ide_settings(
        ide_settings={"files.exclude": {"**/.venv": True}},  # type: ignore
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
        on_record_touch=lambda p: touched.append(p),
    )

    assert diagnostics == []
    written_data = json.loads(settings_file.read_text())
    assert "**/.venv" in written_data["files.exclude"]


def test_write_ide_settings_skips_malformed_json(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    settings_file = vscode_dir / "settings.json"
    settings_file.write_text(
        "{\n  // comments are invalid standard JSON\n  'key': 'val',\n}"
    )

    diagnostics = []
    touched = []

    write_ide_settings(
        ide_settings={"python.defaultInterpreterPath": "/fake/path"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
        on_record_touch=lambda p: touched.append(p),
    )

    assert len(diagnostics) == 1
    msg, sev = diagnostics[0]
    assert sev == Severity.WARNING
    assert "Skipping IDE settings injection" in msg
    assert touched == []


def test_write_ide_settings_skips_non_dict_json(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    settings_file = vscode_dir / "settings.json"
    settings_file.write_text("['not', 'a', 'dict']")

    diagnostics = []
    touched = []

    write_ide_settings(
        ide_settings={"python.defaultInterpreterPath": "/fake/path"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
        on_record_touch=lambda p: touched.append(p),
    )

    assert len(diagnostics) == 1
    assert "Skipping IDE settings injection" in diagnostics[0][0]
    assert touched == []


def test_write_ide_settings_handles_read_os_error(mocker):
    mocker.patch.object(Path, "exists", return_value=True)
    mocker.patch.object(Path, "read_text", side_effect=OSError(5, "Input/output error"))

    with pytest.raises(FileSystemError) as exc_info:
        write_ide_settings(
            ide_settings={"foo": "bar"},  # type: ignore
            on_diagnostic=lambda msg, sev: None,
            on_record_touch=lambda p: None,
        )

    assert "inspect active IDE settings files" in exc_info.value.operation
    assert "settings.json" in exc_info.value.path


def test_write_ide_settings_handles_write_os_error(mocker):
    mocker.patch.object(Path, "exists", return_value=False)
    mocker.patch.object(Path, "mkdir")
    mocker.patch(
        "protostar.ide.atomic_write_text",
        side_effect=OSError(13, "Permission denied"),
    )

    with pytest.raises(FileSystemError) as exc_info:
        write_ide_settings(
            ide_settings={"foo": "bar"},  # type: ignore
            on_diagnostic=lambda msg, sev: None,
            on_record_touch=lambda p: None,
        )

    assert "synchronize IDE workspace preferences" in exc_info.value.operation
    assert "settings.json" in exc_info.value.path
