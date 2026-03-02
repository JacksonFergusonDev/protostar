import subprocess

import pytest

from protostar.system import run_quiet


def test_run_quiet_success(mocker):
    """Test that run_quiet executes successfully without raising exceptions."""
    mock_run = mocker.patch("protostar.system.subprocess.run")

    run_quiet(["echo", "hello"], "Testing echo")

    mock_run.assert_called_once_with(
        ["echo", "hello"],
        check=True,
        capture_output=True,
        text=True,
    )


def test_run_quiet_failure(mocker):
    """Test that run_quiet intercepts subprocess errors and raises a clean RuntimeError."""
    mock_run = mocker.patch("protostar.system.subprocess.run")
    # Simulate a command failure with captured stderr
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["false"], stderr="Network timeout during package resolution"
    )

    # Verify the exception message contains the surfaced stderr details
    with pytest.raises(
        RuntimeError, match="Details:\nNetwork timeout during package resolution"
    ):
        run_quiet(["false"], "Testing failure")


def test_run_quiet_uv_python_error_hint(mocker):
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
        run_quiet(["uv", "init"], "Testing uv error")
