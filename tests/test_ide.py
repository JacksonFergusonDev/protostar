import subprocess
from unittest.mock import MagicMock

from protostar.ide import IDEType, check_ide_extensions
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
