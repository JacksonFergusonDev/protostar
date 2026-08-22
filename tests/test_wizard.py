import os

import pytest

from protostar.config import UserConfig
from protostar.errors import ConfigurationError, ExecutionAbortedError
from protostar.wizard import (
    WizardSelections,
    _should_run_wizard,
    prompt_metadata,
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
    """Test that the init wizard safely handles component checklist cancellation."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "None"

    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = None

    with pytest.raises(
        ExecutionAbortedError, match=r"Component selection cancelled by user\."
    ):
        run_init_wizard()


def test_run_init_wizard_template_cancellation(mocker):
    """Test that cancelling the built-in template selection raises ExecutionAbortedError."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)

    # Ensure templates > 1
    mock_files = mocker.patch("importlib.resources.files")
    mock_file1 = mocker.MagicMock()
    mock_file1.is_file.return_value = True
    mock_file1.name = "fastapi.toml"
    mock_files.return_value.iterdir.return_value = [mock_file1]

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = None

    with pytest.raises(
        ExecutionAbortedError, match=r"Template selection cancelled by user\."
    ):
        run_init_wizard()


def test_run_init_wizard_success(mocker):
    """Test that the init wizard collects selections and metadata successfully."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "None"

    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = ["docker"]

    mock_metadata = mocker.patch(
        "protostar.wizard.prompt_metadata", return_value={"description": "Test App"}
    )

    result = run_init_wizard()

    assert result is not None
    assert isinstance(result, WizardSelections)
    assert result.docker is True
    assert result.project_metadata == {"description": "Test App"}
    mock_metadata.assert_called_once()


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


def test_resolve_missing_variables_cancellation(mocker):
    """Test that cancelling variable resolution raises ExecutionAbortedError."""
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)

    mock_ask = mocker.Mock(return_value=None)
    mock_text = mocker.Mock(return_value=mocker.Mock(ask=mock_ask))
    mocker.patch("questionary.text", mock_text)

    with pytest.raises(
        ExecutionAbortedError, match=r"Variable resolution cancelled by user\."
    ):
        resolve_missing_variables(["project_name"])


def test_prompt_metadata_success(mocker):
    """Test that prompt_metadata successfully gathers text and checkbox input."""
    mocker.patch(
        "protostar.wizard.UserConfig.load",
        return_value=UserConfig(author_name="Alice", supported_os=["Linux"]),
    )

    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = "Alice"

    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = ["Linux"]

    result = prompt_metadata(
        required_keys={"author_name"},
        optional_keys={"supported_os"},
    )

    assert result == {
        "author_name": "Alice",
        "supported_os": ["Linux"],
    }
    mock_text.assert_called_once()
    mock_checkbox.assert_called_once()


def test_prompt_metadata_cancellation_text(mocker):
    """Test that prompt_metadata raises ExecutionAbortedError when text prompt is cancelled."""
    mocker.patch(
        "protostar.wizard.UserConfig.load",
        return_value=UserConfig(),
    )
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = None

    with pytest.raises(
        ExecutionAbortedError, match=r"Metadata configuration cancelled by user\."
    ):
        prompt_metadata(required_keys={"description"})


def test_prompt_metadata_cancellation_checkbox(mocker):
    """Test that prompt_metadata raises ExecutionAbortedError when checkbox prompt is cancelled."""
    mocker.patch(
        "protostar.wizard.UserConfig.load",
        return_value=UserConfig(),
    )
    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = None

    with pytest.raises(
        ExecutionAbortedError, match=r"Metadata configuration cancelled by user\."
    ):
        prompt_metadata(required_keys={"supported_os"})
