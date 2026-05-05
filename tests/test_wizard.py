import os

import pytest

from protostar.config import ProtostarConfig
from protostar.wizard import (
    _should_run_wizard,
    run_discovery_wizard,
    run_init_wizard,
)


def test_should_run_wizard_tty(mocker):
    """Test the TTY gate correctly identifies interactive terminals."""
    # Patch the entire sys module inside the wizard namespace to bypass Pytest's stream capturing
    mock_sys = mocker.patch("protostar.wizard.sys")
    mock_sys.stdin.isatty.return_value = True
    mock_sys.stdout.isatty.return_value = True
    assert _should_run_wizard() is True

    mock_sys.stdin.isatty.return_value = False
    assert _should_run_wizard() is False


def test_discovery_wizard_execution(mocker):
    """Test the discovery multiplexer parses questionary output."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)

    # Mock the chained questionary.select(...).ask() call
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "init"

    result = run_discovery_wizard()
    assert result == "init"


def test_benchmark_env_bypasses_tty_check(mocker):
    """Test that the benchmark env var forcefully passes the TTY gate."""
    mocker.patch.dict(os.environ, {"PROTOSTAR_BENCHMARK_WIZARD": "1"})
    # Even if stdin is not a TTY, the benchmark flag overrides it
    mocker.patch("protostar.wizard.sys.stdin.isatty", return_value=False)
    assert _should_run_wizard() is True


def test_run_init_wizard_benchmark_abort(mocker):
    """Test that the init wizard correctly intercepts the benchmark flag and exits cleanly."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)
    mocker.patch.dict(os.environ, {"PROTOSTAR_BENCHMARK_WIZARD": "1"})

    with pytest.raises(SystemExit) as exc_info:
        run_init_wizard()

    assert exc_info.value.code == 0


def test_run_init_wizard_cancellation(mocker):
    """Test that the init wizard safely handles user cancellation (Ctrl+C)."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)
    mocker.patch(
        "protostar.wizard.ProtostarConfig.load", return_value=ProtostarConfig()
    )
    mocker.patch.dict(os.environ, {}, clear=True)

    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = None

    assert run_init_wizard() is None
