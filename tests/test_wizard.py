import os

import pytest

from protostar.config import ProtostarConfig
from protostar.errors import ConfigurationError
from protostar.wizard import (
    _should_run_wizard,
    resolve_missing_variables,
    run_init_wizard,
)


def test_should_run_wizard_tty(mocker):
    """Test the TTY gate correctly identifies interactive terminals."""
    mocker.patch("protostar.wizard.is_interactive", return_value=True)
    assert _should_run_wizard() is True

    mocker.patch("protostar.wizard.is_interactive", return_value=False)
    assert _should_run_wizard() is False


def test_benchmark_env_bypasses_tty_check(mocker):
    """Test that the benchmark env var forcefully passes the TTY gate."""
    mocker.patch.dict(os.environ, {"PROTOSTAR_BENCHMARK_WIZARD": "1"})
    mocker.patch("protostar.system.sys.stdin.isatty", return_value=False)
    assert _should_run_wizard() is True


def test_run_init_wizard_benchmark_abort(mocker):
    """Test that the init wizard correctly intercepts the benchmark flag and exits cleanly."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)
    mocker.patch.dict(os.environ, {"PROTOSTAR_BENCHMARK_WIZARD": "1"})

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "None"

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

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "None"

    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = None

    assert run_init_wizard() is None


def test_resolve_missing_variables_non_interactive(mocker):
    """Test that resolving variables fails in a non-interactive environment."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=False)

    with pytest.raises(
        ConfigurationError, match="Non-interactive environment detected"
    ):
        resolve_missing_variables(["project_name", "author"])


def test_resolve_missing_variables_interactive(mocker):
    """Test that questionary successfully collects missing variables."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)

    mock_ask = mocker.Mock(return_value="Orbit App")
    mock_text = mocker.Mock(return_value=mocker.Mock(ask=mock_ask))
    mocker.patch("questionary.text", mock_text)

    context = resolve_missing_variables(["project_name"])

    assert context == {"project_name": "Orbit App"}
    mock_text.assert_called_once_with("project_name:")
