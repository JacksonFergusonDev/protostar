import pytest

from protostar.errors import CommandTimeoutError, ProcessTerminationError
from protostar.ide import IDEType, check_ide_extensions
from protostar.manifest import Severity
from protostar.system import ProcessRunner


def test_ide_type_enum_properties():
    assert IDEType.VSCODE.binary_name == "code"
    assert IDEType.CURSOR.binary_name == "cursor"
    assert IDEType.NONE.binary_name is None


def test_ide_extension_probe_propagates_termination_failure(mocker, progress):
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/code")
    runner = ProcessRunner()
    error = ProcessTerminationError(123, "process remained active")
    mocker.patch.object(runner, "run", side_effect=error)
    diagnostic = mocker.Mock()

    with pytest.raises(ProcessTerminationError) as caught:
        check_ide_extensions(
            IDEType.VSCODE,
            {"charliermarsh.ruff"},
            diagnostic,
            process_runner=runner,
            progress=progress,
        )

    assert caught.value is error
    diagnostic.assert_not_called()


def test_ide_extension_check_with_enum(mocker):
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/code")
    mocker.patch.object(ProcessRunner, "run", return_value="charliermarsh.ruff\n")
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


def test_ide_extension_probe_runs_inside_a_step(mocker, progress):
    """The IDE CLI probe is bracketed by a progress step."""
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/code")
    mocker.patch.object(
        ProcessRunner,
        "run",
        side_effect=lambda *_, **__: (
            progress.events.append(("run", "")) or "charliermarsh.ruff\n"
        ),
    )

    check_ide_extensions(
        ide=IDEType.VSCODE,
        ide_extensions={"charliermarsh.ruff"},
        on_diagnostic=lambda msg, sev: None,
        progress=progress,
    )

    assert progress.events == [
        ("start", "Checking editor extensions"),
        ("run", ""),
        ("done", "Checking editor extensions"),
    ]


def test_ide_extension_probe_failure_completes_the_step(mocker, progress):
    """A crashed probe is a skip diagnostic, so its step completes rather than fails."""
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/code")
    mocker.patch.object(
        ProcessRunner,
        "run",
        side_effect=CommandTimeoutError(["code"], 5),
    )
    diagnostics = []

    check_ide_extensions(
        ide=IDEType.VSCODE,
        ide_extensions={"charliermarsh.ruff"},
        on_diagnostic=lambda msg, sev: diagnostics.append(sev),
        progress=progress,
    )

    assert diagnostics == [Severity.SKIP]
    assert progress.steps() == ["Checking editor extensions"]


def test_ide_extension_check_without_cli_has_no_step(mocker, progress):
    """No step is shown when the IDE CLI is absent and nothing is probed."""
    mocker.patch("protostar.ide.find_executable", return_value=None)

    check_ide_extensions(
        ide=IDEType.VSCODE,
        ide_extensions={"charliermarsh.ruff"},
        on_diagnostic=lambda msg, sev: None,
        progress=progress,
    )

    assert progress.events == []


def test_ide_extension_check_bypassed_if_wrong_ide(mocker):
    mock_which = mocker.patch("protostar.ide.find_executable")
    diagnostics = []

    check_ide_extensions(
        ide="none",
        ide_extensions={"charliermarsh.ruff"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    mock_which.assert_not_called()
    assert diagnostics == []


def test_ide_extension_check_bypassed_if_none_enum(mocker):
    mock_which = mocker.patch("protostar.ide.find_executable")
    diagnostics = []

    check_ide_extensions(
        ide=IDEType.NONE,
        ide_extensions={"charliermarsh.ruff"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    mock_which.assert_not_called()
    assert diagnostics == []


def test_ide_extension_check_bypassed_if_binary_missing(mocker):
    mock_which = mocker.patch("protostar.ide.find_executable", return_value=None)
    mock_run = mocker.patch.object(ProcessRunner, "run")
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
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/cursor")

    mock_run = mocker.patch.object(
        ProcessRunner,
        "run",
        return_value="charliermarsh.ruff\nms-python.mypy-type-checker\nsome-other-ext\n",
    )
    diagnostics = []

    check_ide_extensions(
        ide="cursor",
        ide_extensions={"charliermarsh.ruff", "ms-python.mypy-type-checker"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    mock_run.assert_called_once_with(
        ["/usr/local/bin/cursor", "--list-extensions"],
        timeout=5,
    )
    assert diagnostics == []


def test_ide_extension_check_flags_missing_extensions(mocker):
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/code")

    mocker.patch.object(ProcessRunner, "run", return_value="charliermarsh.ruff\n")
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
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/code")
    mocker.patch.object(
        ProcessRunner,
        "run",
        side_effect=CommandTimeoutError(["code"], 5),
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
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/code")
    mocker.patch.object(
        ProcessRunner,
        "run",
        return_value="ms-python.mypy-type-checker\nother.extension\n",
    )
    diagnostics = []

    check_ide_extensions(
        ide="vscode",
        ide_extensions={("ms-python.mypy-type-checker", "matangover.mypy")},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    assert diagnostics == []


def test_ide_extension_check_satisfies_fallback_in_tuple(mocker):
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/code")
    mocker.patch.object(
        ProcessRunner,
        "run",
        return_value="matangover.mypy\nother.extension\n",
    )
    diagnostics = []

    check_ide_extensions(
        ide="vscode",
        ide_extensions={("ms-python.mypy-type-checker", "matangover.mypy")},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
    )

    assert diagnostics == []


def test_ide_extension_check_fails_missing_tuple(mocker):
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/code")
    mocker.patch.object(
        ProcessRunner,
        "run",
        return_value="charliermarsh.ruff\nother.extension\n",
    )
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


def test_ide_extension_check_uses_provided_process_runner(mocker):
    mocker.patch("protostar.ide.find_executable", return_value="/usr/local/bin/code")
    runner = ProcessRunner()
    mock_run = mocker.patch.object(runner, "run", return_value="charliermarsh.ruff\n")
    diagnostics = []

    check_ide_extensions(
        ide="vscode",
        ide_extensions={"charliermarsh.ruff"},
        on_diagnostic=lambda msg, sev: diagnostics.append((msg, sev)),
        process_runner=runner,
    )

    mock_run.assert_called_once_with(
        ["/usr/local/bin/code", "--list-extensions"], timeout=5
    )
    assert diagnostics == []
