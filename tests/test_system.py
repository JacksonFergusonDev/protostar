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
        timeout=None,
    )


def test_execute_subprocess_with_timeout(mocker):
    """Test that explicitly provided timeouts are passed down to the subprocess layer."""
    mock_run = mocker.patch("protostar.system.subprocess.run")

    execute_subprocess(["sleep", "1"], timeout=15)

    mock_run.assert_called_once_with(
        ["sleep", "1"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_execute_subprocess_timeout_expired(mocker):
    """Test that execution timeouts are intercepted and raise a contextual RuntimeError."""
    mock_run = mocker.patch("protostar.system.subprocess.run")
    mock_run.side_effect = subprocess.TimeoutExpired(
        cmd=["uv", "add", "heavy-pkg"], timeout=600
    )

    with pytest.raises(
        RuntimeError,
        match="Command timed out after 600 seconds: uv add heavy-pkg",
    ):
        execute_subprocess(["uv", "add", "heavy-pkg"], timeout=600)


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
        match=r"uv.*encountered an error resolving the requested Python version",
    ):
        execute_subprocess(["uv", "init"])
