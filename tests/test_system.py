import subprocess

import pytest

from protostar.errors import CommandExecutionError, CommandTimeoutError
from protostar.system import execute_subprocess


@pytest.fixture(autouse=True)
def mock_shutil_which(mocker):
    mocker.patch("protostar.system.shutil.which", side_effect=lambda x: x)


def test_execute_subprocess_with_timeout(mocker):
    """Test that explicitly provided timeouts are passed down to the subprocess layer."""
    mock_run = mocker.patch("protostar.system.subprocess.run")

    execute_subprocess(["sleep", "1"], timeout=15)

    mock_run.assert_called_once_with(
        ["sleep", "1"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )


def test_execute_subprocess_timeout_expired(mocker):
    """Test that execution timeouts are intercepted and raise a contextual CommandTimeoutError."""
    mock_run = mocker.patch("protostar.system.subprocess.run")
    mock_run.side_effect = subprocess.TimeoutExpired(
        cmd=["uv", "add", "heavy-pkg"], timeout=600
    )

    with pytest.raises(CommandTimeoutError) as exc_info:
        execute_subprocess(["uv", "add", "heavy-pkg"], timeout=600)

    assert exc_info.value.command == ["uv", "add", "heavy-pkg"]
    assert exc_info.value.timeout == 600


def test_execute_subprocess_failure(mocker):
    """Test that execute_subprocess intercepts subprocess errors and preserves diagnostic metadata."""
    mock_run = mocker.patch("protostar.system.subprocess.run")
    # Simulate a command failure with captured stderr
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["false"], stderr="Network timeout during package resolution"
    )

    with pytest.raises(CommandExecutionError) as exc_info:
        execute_subprocess(["false"])

    assert exc_info.value.command == ["false"]
    assert exc_info.value.returncode == 1
    assert "Network timeout" in exc_info.value.stderr


def test_execute_subprocess_success(mocker):
    mock_run = mocker.patch("subprocess.run")
    execute_subprocess(["uv", "version"])
    mock_run.assert_called_once_with(
        ["uv", "version"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=None,
    )


def test_execute_subprocess_timeout(mocker):
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["uv", "sync"], timeout=5),
    )

    with pytest.raises(CommandTimeoutError) as exc_info:
        execute_subprocess(["uv", "sync"], timeout=5)

    assert exc_info.value.command == ["uv", "sync"]
    assert exc_info.value.timeout == 5


def test_execute_subprocess_failed_execution(mocker):
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(
            returncode=1, cmd=["uv", "add", "nonexistent"], output="out", stderr="err"
        ),
    )

    with pytest.raises(CommandExecutionError) as exc_info:
        execute_subprocess(["uv", "add", "nonexistent"])

    assert exc_info.value.command == ["uv", "add", "nonexistent"]
    assert exc_info.value.returncode == 1
    assert exc_info.value.stdout == "out"
    assert exc_info.value.stderr == "err"
