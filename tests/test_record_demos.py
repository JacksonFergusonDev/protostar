"""Tests for demo recording session lifecycle and process group management."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.record_demos import PTYSession


def test_pty_session_start_sets_isolated_process_group(tmp_path: Path) -> None:
    """Verifies that PTYSession launches the shell with start_new_session=True."""
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
        assert session.proc is mock_proc
        assert session.slave_fd == -1


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
