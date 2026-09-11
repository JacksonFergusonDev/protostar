import pytest

from protostar.errors import CommandExecutionError
from protostar.system import execute_subprocess


def test_execute_subprocess_success(mocker):
    mock_popen = mocker.MagicMock()
    mock_popen.communicate.return_value = ("out", "err")
    mock_popen.returncode = 0
    mocker.patch("subprocess.Popen", return_value=mock_popen)
    execute_subprocess(["uv", "sync"])


def test_execute_subprocess_failure(mocker):
    mock_popen = mocker.MagicMock()
    mock_popen.communicate.return_value = ("out", "err")
    mock_popen.returncode = 1
    mocker.patch("subprocess.Popen", return_value=mock_popen)
    with pytest.raises(CommandExecutionError):
        execute_subprocess(["uv", "add", "nonexistent"])
