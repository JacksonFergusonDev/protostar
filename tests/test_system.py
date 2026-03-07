import subprocess

import pytest

from protostar.system import execute_subprocess


def test_execute_subprocess_success(mocker):
    """Test that execute_subprocess executes successfully without raising exceptions."""
    mock_run = mocker.patch("protostar.system.subprocess.run")

    execute_subprocess(["echo", "hello"])

    mock_run.assert_called_once_with(
        ["echo", "hello"],
        check=True,
        capture_output=True,
        text=True,
    )


def test_execute_subprocess_failure(mocker):
    """Test that execute_subprocess intercepts subprocess errors and raises a clean RuntimeError."""
    mock_run = mocker.patch("protostar.system.subprocess.run")
    # Simulate a command failure with captured stderr
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["false"], stderr="Network timeout during package resolution"
    )

    # Verify the exception message contains the correctly formatted stderr details
    with pytest.raises(
        RuntimeError,
        match="Diagnostics:\n--- STDERR ---\nNetwork timeout during package resolution",
    ):
        execute_subprocess(["false"])


def test_execute_subprocess_uv_python_error_hint(mocker):
    """Test that uv python resolution errors raise a contextual hint."""
    mock_run = mocker.patch("protostar.system.subprocess.run")
    # Simulate uv failing because it can't download the python version
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["uv", "init"],
        stderr="error: python-downloads is set to 'never'",
    )

    with pytest.raises(
        RuntimeError,
        match="uv.*encountered an error resolving the requested Python version",
    ):
        execute_subprocess(["uv", "init"])
