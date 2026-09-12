import signal
import subprocess

import pytest

from protostar.errors import (
    CommandExecutionError,
    CommandTimeoutError,
    ProcessTerminationError,
)
from protostar.system import ProcessRunner, execute_subprocess, shield_sigint


def _mock_process(mocker, *, returncode=0, output=("out", "err")):
    process = mocker.MagicMock()
    process.communicate.return_value = output
    process.returncode = returncode
    process.poll.return_value = returncode
    return process


def test_process_runner_success(mocker):
    process = _mock_process(mocker)
    popen = mocker.patch("protostar.system.subprocess.Popen", return_value=process)

    runner = ProcessRunner()
    runner.run(["uv", "sync"])

    assert runner.active_process is None
    assert popen.call_args.kwargs["start_new_session"] is True
    assert popen.call_args.kwargs["encoding"] == "utf-8"


def test_process_runner_failure_preserves_output(mocker):
    process = _mock_process(mocker, returncode=1, output=("out", "err"))
    mocker.patch("protostar.system.subprocess.Popen", return_value=process)

    with pytest.raises(CommandExecutionError) as exc_info:
        ProcessRunner().run(["uv", "add", "nonexistent"])

    assert exc_info.value.stdout == "out"
    assert exc_info.value.stderr == "err"
    assert exc_info.value.returncode == 1


def test_process_runner_sanitizes_environment(mocker, monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", "/caller/.venv")
    monkeypatch.setenv("PYTHONHOME", "/caller/python")
    monkeypatch.setenv("KEEP_ME", "yes")
    process = _mock_process(mocker)
    popen = mocker.patch("protostar.system.subprocess.Popen", return_value=process)

    ProcessRunner().run(["uv", "sync"], env={"VIRTUAL_ENV": "/target/.venv"})

    child_env = popen.call_args.kwargs["env"]
    assert child_env["VIRTUAL_ENV"] == "/target/.venv"
    assert "PYTHONHOME" not in child_env
    assert child_env["KEEP_ME"] == "yes"


def test_process_runner_timeout_terminates_escalates_and_reaps(mocker):
    process = _mock_process(mocker)
    process.pid = 123
    process.communicate.side_effect = subprocess.TimeoutExpired(["uv"], 10)
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired(["uv"], 2), None]
    mocker.patch("protostar.system.subprocess.Popen", return_value=process)
    mocker.patch("protostar.system.os.getpgid", return_value=456)
    kill_group = mocker.patch("protostar.system.os.killpg")

    with pytest.raises(CommandTimeoutError):
        ProcessRunner(termination_grace_seconds=2).run(["uv", "sync"], timeout=10)

    assert kill_group.call_args_list == [
        mocker.call(456, signal.SIGTERM),
        mocker.call(456, signal.SIGKILL),
    ]
    assert process.wait.call_args_list == [
        mocker.call(timeout=2),
        mocker.call(timeout=2),
    ]


def test_process_runner_keyboard_interrupt_terminates_before_reraising(mocker):
    process = _mock_process(mocker)
    process.pid = 123
    process.communicate.side_effect = KeyboardInterrupt
    process.poll.return_value = None
    process.wait.return_value = None
    mocker.patch("protostar.system.subprocess.Popen", return_value=process)
    mocker.patch("protostar.system.os.getpgid", return_value=456)
    kill_group = mocker.patch("protostar.system.os.killpg")

    runner = ProcessRunner()
    with pytest.raises(KeyboardInterrupt):
        runner.run(["uv", "sync"])

    kill_group.assert_called_once_with(456, signal.SIGTERM)
    process.wait.assert_called_once_with(timeout=2.0)
    assert runner.active_process is None


def test_process_runner_retains_unreaped_process_after_termination_failure(mocker):
    process = _mock_process(mocker)
    process.pid = 123
    process.communicate.side_effect = KeyboardInterrupt
    process.poll.return_value = None
    process.terminate.side_effect = OSError("cannot terminate")
    mocker.patch("protostar.system.subprocess.Popen", return_value=process)
    mocker.patch("protostar.system.os.getpgid", return_value=456)
    mocker.patch("protostar.system.os.killpg", side_effect=OSError("no group"))

    runner = ProcessRunner()
    with pytest.raises(ProcessTerminationError):
        runner.run(["uv", "sync"])

    assert runner.active_process is process


def test_process_runner_windows_process_group(mocker, monkeypatch):
    monkeypatch.setattr("protostar.system.sys.platform", "win32")
    mocker.patch("protostar.system.shutil.which", return_value="uv")
    monkeypatch.setattr(
        "protostar.system.subprocess.CREATE_NEW_PROCESS_GROUP", 512, raising=False
    )
    process = _mock_process(mocker)
    popen = mocker.patch("protostar.system.subprocess.Popen", return_value=process)

    ProcessRunner().run(["uv", "sync"])

    assert popen.call_args.kwargs["creationflags"] == 512


def test_shield_sigint_restores_previous_handler(mocker):
    original = object()
    mocker.patch("protostar.system.signal.getsignal", return_value=original)
    set_handler = mocker.patch("protostar.system.signal.signal")

    with shield_sigint():
        pass

    assert set_handler.call_args_list[0].args[0] == signal.SIGINT
    assert set_handler.call_args_list[-1] == mocker.call(signal.SIGINT, original)


def test_shield_sigint_ignores_reentrant_interrupt(mocker):
    mocker.patch(
        "protostar.system.signal.getsignal", return_value=signal.default_int_handler
    )
    set_handler = mocker.patch("protostar.system.signal.signal")

    with shield_sigint():
        installed_handler = set_handler.call_args_list[0].args[1]
        installed_handler(signal.SIGINT, None)


def test_execute_subprocess_uses_short_lived_runner(mocker):
    run = mocker.patch("protostar.system.ProcessRunner.run")

    execute_subprocess(["uv", "sync"], timeout=30)

    run.assert_called_once_with(["uv", "sync"], timeout=30, env=None)
