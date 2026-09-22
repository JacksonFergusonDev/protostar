"""The remaining questionary prompts and draft completion."""

import pytest

from protostar.cli.wizard import (
    complete_init_draft,
    prompt_metadata,
    prompt_template_variables,
)
from protostar.config import TemplateSource, UserConfig
from protostar.errors import ExecutionAbortedError
from protostar.init_draft import DraftTemplate, InitDraft


def test_prompt_template_variables_collects_each_value(mocker, capsys):
    """Each variable is asked for in order, after a note that values are saved."""
    answers = iter(["Orbit App", "eu-west-1"])
    mock_text = mocker.Mock(
        side_effect=lambda *_: mocker.Mock(ask=mocker.Mock(return_value=next(answers)))
    )
    mocker.patch("questionary.text", mock_text)

    values = prompt_template_variables(["project_title", "region"])

    assert values == {"project_title": "Orbit App", "region": "eu-west-1"}
    assert [c.args[0] for c in mock_text.call_args_list] == [
        "project_title:",
        "region:",
    ]
    assert "saved to pyproject.toml" in capsys.readouterr().out


def test_prompt_template_variables_cancellation(mocker):
    """Cancelling a prompt aborts instead of rendering with a missing value."""
    mock_ask = mocker.Mock(return_value=None)
    mocker.patch(
        "questionary.text", mocker.Mock(return_value=mocker.Mock(ask=mock_ask))
    )

    with pytest.raises(
        ExecutionAbortedError, match=r"Variable entry cancelled by user\."
    ):
        prompt_template_variables(["project_title"])


def test_prompt_metadata_success(mocker):
    """Test that prompt_metadata successfully gathers text and checkbox input."""
    mocker.patch(
        "protostar.cli.wizard.UserConfig.load",
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
        "protostar.cli.wizard.UserConfig.load",
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
        "protostar.cli.wizard.UserConfig.load",
        return_value=UserConfig(),
    )
    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = None

    with pytest.raises(
        ExecutionAbortedError, match=r"Metadata configuration cancelled by user\."
    ):
        prompt_metadata(required_keys={"supported_os"})


def test_complete_draft_prompts_only_for_missing_variables(mocker, tmp_path):
    path = tmp_path / "template.toml"
    path.write_text('name = "<% REGION %> <% TEAM %>"')
    draft = InitDraft(
        template=DraftTemplate(TemplateSource.load(str(path))),
        variables=(("REGION", "eu"),),
        tool_choices=(),
        docker=True,
    )
    prompt = mocker.patch(
        "protostar.cli.wizard.prompt_template_variables", return_value={"TEAM": "orbit"}
    )
    metadata = mocker.patch(
        "protostar.cli.wizard.prompt_metadata", return_value={"minimum_python": "3.13"}
    )
    result = complete_init_draft(draft)
    prompt.assert_called_once_with(["TEAM"])
    assert dict(result.variables) == {"REGION": "eu", "TEAM": "orbit"}
    assert result.python_version == "3.13"
    assert "docker_port" in metadata.call_args.args[1]
