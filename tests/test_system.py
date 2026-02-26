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
    # Simulate a command failure
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["false"], stderr="Command not found"
    )

    with pytest.raises(RuntimeError, match="Command failed during setup: false"):
        run_quiet(["false"], "Testing failure")
