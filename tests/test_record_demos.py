"""Tests for demo recording session lifecycle and process group management."""

from __future__ import annotations

import sys

import pytest

if sys.platform == "win32":
    pytest.skip("PTY demo recording is Unix-specific", allow_module_level=True)

import os
import signal
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from scripts.record_demos import PTYSession


def test_pty_session_start_sets_isolated_process_group(
    tmp_path: Path, monkeypatch
) -> None:
    """Verifies that PTYSession launches the shell with start_new_session=True."""
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("PAGER", "cat")
    monkeypatch.setattr("scripts.record_demos.tempfile.tempdir", str(tmp_path))
    session = PTYSession(workspace=str(tmp_path))

    with (
        patch("scripts.record_demos.pty.openpty", return_value=(10, 11)),
        patch("scripts.record_demos.set_winsize"),
        patch("scripts.record_demos.os.close"),
        patch.object(session, "_silent_write"),
        patch.object(session, "_drain", return_value="\x1b[2Jprompt$ "),
        patch("scripts.record_demos.subprocess.Popen") as mock_popen,
    ):
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_popen.return_value = mock_proc

        session.start()

        mock_popen.assert_called_once()
        _, kwargs = mock_popen.call_args
        assert kwargs.get("start_new_session") is True
        assert "NO_COLOR" not in kwargs["env"]
        assert kwargs["env"]["PAGER"] == "less"
        assert kwargs["env"]["BAT_PAGER"] == "less"
        config_path = Path(kwargs["env"]["DIRENV_CONFIG"])
        assert config_path.parent == tmp_path
        assert (config_path / "direnv.toml").read_text() == (
            '[global]\nlog_format = "-"\n'
        )
        assert session.proc is mock_proc
        assert session.slave_fd == -1
        session.close()
        assert not config_path.exists()


def test_pty_session_close_signals_process_group_when_running(tmp_path: Path) -> None:
    """Verifies that close terminates the entire process group gracefully when still running."""
    session = PTYSession(workspace=str(tmp_path))
    session.master_fd = 42
    mock_proc = MagicMock()
    mock_proc.pid = 8888
    # 1. Initial check: poll() is None (running)
    # 2. Check after exit\n: poll() is None (still running)
    # 3. Check in second close() call: poll() is 0 (exited)
    mock_proc.poll.side_effect = [None, None, 0]
    session.proc = mock_proc

    with (
        patch("scripts.record_demos.os.killpg") as mock_killpg,
        patch("scripts.record_demos.os.close") as mock_close,
        patch.object(session, "_silent_write"),
        patch.object(session, "_drain"),
    ):
        session.close()

        mock_killpg.assert_called_once_with(8888, signal.SIGTERM)
        mock_close.assert_called_once_with(42)
        assert session.master_fd == -1


def test_pty_session_close_escalates_to_sigkill_on_timeout(tmp_path: Path) -> None:
    """Verifies escalation to SIGKILL when SIGTERM does not reap the process group."""
    session = PTYSession(workspace=str(tmp_path))
    session.master_fd = 42
    mock_proc = MagicMock()
    mock_proc.pid = 8888
    mock_proc.poll.return_value = None  # Process remains running
    mock_proc.wait.side_effect = [
        subprocess.TimeoutExpired(cmd="zsh", timeout=0.5),
        None,
    ]
    session.proc = mock_proc

    with (
        patch("scripts.record_demos.os.killpg") as mock_killpg,
        patch("scripts.record_demos.os.close") as mock_close,
        patch.object(session, "_silent_write"),
        patch.object(session, "_drain"),
    ):
        session.close()

        assert mock_killpg.call_count == 2
        mock_killpg.assert_any_call(8888, signal.SIGTERM)
        mock_killpg.assert_any_call(8888, signal.SIGKILL)
        mock_close.assert_called_once_with(42)
        assert session.master_fd == -1


def test_pty_session_context_manager_guarantees_close_on_exception(
    tmp_path: Path,
) -> None:
    """Verifies that entering context and raising an exception guarantees close() is invoked."""
    session = PTYSession(workspace=str(tmp_path))

    def _fail() -> None:
        with session:
            raise RuntimeError("Trial simulation failed")

    with (
        patch.object(session, "start") as mock_start,
        patch.object(session, "close") as mock_close,
    ):
        with pytest.raises(RuntimeError, match="Trial simulation failed"):
            _fail()

        mock_start.assert_called_once()
        mock_close.assert_called_once()


@pytest.mark.parametrize("use_context", [False, True])
@pytest.mark.parametrize(
    "failure", [RuntimeError("startup failed"), KeyboardInterrupt()]
)
def test_failed_startup_reaps_shell_and_closes_resources(
    use_context: bool,
    failure: BaseException,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("scripts.record_demos.tempfile.tempdir", str(tmp_path))
    workspace = tmp_path / "workspace"
    fixture_paths: list[Path] = []

    def setup(_workspace: Path, fixture: Path) -> dict[str, str]:
        fixture_paths.append(fixture)
        return {}

    session = PTYSession(workspace=str(workspace), setup=setup)

    def start_session() -> None:
        if use_context:
            with session:
                pytest.fail("The session must not enter after startup fails")
        else:
            session.start()

    process = MagicMock()
    process.pid = 9999
    process.poll.side_effect = [None, None, 0]
    real_close = os.close
    with (
        patch("scripts.record_demos.pty.openpty", return_value=(10000, 10001)),
        patch("scripts.record_demos.set_winsize"),
        patch(
            "scripts.record_demos.os.close",
            side_effect=lambda fd: None if fd in (10000, 10001) else real_close(fd),
        ) as close_fd,
        patch("scripts.record_demos.os.killpg") as killpg,
        patch.object(session, "_silent_write"),
        patch.object(session, "_drain", side_effect=[failure, ""]),
        patch("scripts.record_demos.subprocess.Popen", return_value=process) as popen,
    ):
        with pytest.raises(type(failure)) as error:
            start_session()

        assert error.value is failure
        killpg.assert_called_once_with(9999, signal.SIGTERM)
        process.wait.assert_called_once_with(timeout=0.5)
        assert close_fd.call_args_list.count(call(10000)) == 1
        assert close_fd.call_args_list.count(call(10001)) == 1
        assert session.master_fd == session.slave_fd == -1
        assert session._fixture is session._direnv_config is None
        assert not fixture_paths[0].exists()
        assert not Path(popen.call_args.kwargs["env"]["DIRENV_CONFIG"]).exists()
        closed = list(close_fd.call_args_list)
        session.close()
        assert close_fd.call_args_list == closed
        assert killpg.call_count == 1


@pytest.mark.parametrize("phase", ["resize", "spawn"])
def test_startup_before_shell_launch_closes_both_pty_descriptors(
    phase: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("scripts.record_demos.tempfile.tempdir", str(tmp_path))
    session = PTYSession(workspace=str(tmp_path / "workspace"))
    failure = OSError("startup failed")
    real_close = os.close
    with (
        patch("scripts.record_demos.pty.openpty", return_value=(10000, 10001)),
        patch(
            "scripts.record_demos.set_winsize",
            side_effect=failure if phase == "resize" else None,
        ),
        patch("scripts.record_demos.subprocess.Popen", side_effect=failure) as popen,
        patch(
            "scripts.record_demos.os.close",
            side_effect=lambda fd: None if fd in (10000, 10001) else real_close(fd),
        ) as close_fd,
    ):
        with pytest.raises(OSError, match="startup failed") as error:
            session.start()

        assert error.value is failure
        assert close_fd.call_args_list.count(call(10000)) == 1
        assert close_fd.call_args_list.count(call(10001)) == 1
        assert session.master_fd == session.slave_fd == -1
        assert session.proc is None
        assert session._direnv_config is None
        if phase == "resize":
            popen.assert_not_called()
        else:
            assert not Path(popen.call_args.kwargs["env"]["DIRENV_CONFIG"]).exists()
        closed = list(close_fd.call_args_list)
        session.close()
        assert close_fd.call_args_list == closed


def test_pty_session_close_is_idempotent(tmp_path: Path) -> None:
    """Verifies that calling close() multiple times is safe and performs cleanup once."""
    session = PTYSession(workspace=str(tmp_path))
    session.master_fd = 42
    mock_proc = MagicMock()
    mock_proc.pid = 7777
    mock_proc.poll.side_effect = [None, None, 0, 0]
    session.proc = mock_proc

    with (
        patch("scripts.record_demos.os.killpg") as mock_killpg,
        patch("scripts.record_demos.os.close") as mock_close,
        patch.object(session, "_silent_write"),
        patch.object(session, "_drain"),
    ):
        session.close()
        session.close()

        assert mock_killpg.call_count == 1
        assert mock_close.call_count == 1
        assert session.master_fd == -1


def test_one_output_file_is_refused_for_every_scenario(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import record_demos

    monkeypatch.setattr(
        sys, "argv", ["record_demos.py", "all", "--output", "demo.cast"]
    )
    with (
        patch.object(record_demos, "PTYSession") as session,
        pytest.raises(SystemExit) as exit_,
    ):
        record_demos.main()
    assert exit_.value.code == 2
    assert "needs a single scenario" in capsys.readouterr().err
    session.assert_not_called()
