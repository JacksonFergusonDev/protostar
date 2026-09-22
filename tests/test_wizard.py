import os
from typing import Any

import pytest

from protostar.cli.wizard import (
    WizardSelections,
    _should_run_wizard,
    prompt_metadata,
    prompt_template_variables,
    run_init_wizard,
)
from protostar.config import UserConfig
from protostar.errors import ExecutionAbortedError
from protostar.modules import TOOLING_MODULES, PreCommitModule, PrekModule


def test_should_run_wizard_tty(mocker):
    """Test the TTY gate correctly identifies interactive terminals."""
    mocker.patch("protostar.cli.wizard.is_interactive", return_value=True)
    assert _should_run_wizard() is True

    mocker.patch("protostar.cli.wizard.is_interactive", return_value=False)
    assert _should_run_wizard() is False


def test_benchmark_env_bypasses_tty_check(mocker):
    """Test that the benchmark env var forcefully passes the TTY gate."""
    mocker.patch.dict(os.environ, {"PROTOSTAR_BENCHMARK_WIZARD": "1"})
    mocker.patch("protostar.system.sys.stdin.isatty", return_value=False)
    assert _should_run_wizard() is True


def test_run_init_wizard_benchmark_abort(mocker):
    """Test that the init wizard correctly intercepts the benchmark flag and exits cleanly."""
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch.dict(os.environ, {"PROTOSTAR_BENCHMARK_WIZARD": "1"})

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "None"

    with pytest.raises(SystemExit) as exc_info:
        run_init_wizard()

    assert exc_info.value.code == 0


def test_run_init_wizard_cancellation(mocker):
    """Test that the init wizard safely handles component checklist cancellation."""
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.cli.wizard.UserConfig.load", return_value=UserConfig())
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
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.cli.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)

    # Ensure templates > 1
    mock_files = mocker.patch("importlib.resources.files")
    mock_file1 = mocker.MagicMock()
    mock_file1.is_file.return_value = True
    mock_file1.name = "fastapi.toml"
    mock_file1.read_text.return_value = 'name = "FastAPI"\ndescription = "Scaffold"\n'
    mock_files.return_value.iterdir.return_value = [mock_file1]

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = None

    with pytest.raises(
        ExecutionAbortedError, match=r"Template selection cancelled by user\."
    ):
        run_init_wizard()


def test_run_init_wizard_success(mocker):
    """Test that the init wizard collects selections and metadata successfully."""
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.cli.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "None"

    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = ["docker"]

    mock_metadata = mocker.patch(
        "protostar.cli.wizard.prompt_metadata", return_value={"description": "Test App"}
    )

    result = run_init_wizard()

    assert result is not None
    assert isinstance(result, WizardSelections)
    assert result.docker is True
    assert result.project_metadata == {"description": "Test App"}
    mock_metadata.assert_called_once()


def test_run_init_wizard_formats_template_choices_with_middle_dot(mocker) -> None:
    """Test that template choices are formatted using display names and a middle dot separator."""
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.cli.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)

    captured_choices: list[Any] = []

    def fake_select(message: str, choices: list[Any], **kwargs: Any) -> Any:
        captured_choices.extend(choices)
        mock_q = mocker.MagicMock()
        mock_q.ask.return_value = "None"
        return mock_q

    mocker.patch("questionary.select", side_effect=fake_select)
    mocker.patch("questionary.checkbox").return_value.ask.return_value = []
    mocker.patch("protostar.cli.wizard.prompt_metadata", return_value={})

    run_init_wizard()

    choice_titles = [
        c.title for c in captured_choices if isinstance(getattr(c, "title", None), str)
    ]
    fastapi_choice = next(t for t in choice_titles if "FastAPI" in t)
    assert " · " in fastapi_choice
    assert "(" not in fastapi_choice
    assert ")" not in fastapi_choice


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


def test_run_init_wizard_resolves_hook_runner_conflict(mocker):
    """Test that selecting both Pre-Commit and Prek prompts the user to resolve the conflict."""
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.cli.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)

    pre_commit_mod = next(m for m in TOOLING_MODULES if isinstance(m, PreCommitModule))
    prek_mod = next(m for m in TOOLING_MODULES if isinstance(m, PrekModule))

    # Template selection: None
    # Then conflict selection: prek_mod
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.side_effect = ["None", prek_mod]

    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = [pre_commit_mod, prek_mod]

    mocker.patch("protostar.cli.wizard.prompt_metadata", return_value={})

    result = run_init_wizard()

    assert result is not None
    assert prek_mod in result.modules
    assert pre_commit_mod not in result.modules


def test_run_init_wizard_hook_runner_conflict_cancellation(mocker):
    """Test that cancelling the hook runner conflict prompt raises ExecutionAbortedError."""
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.cli.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)

    pre_commit_mod = next(m for m in TOOLING_MODULES if isinstance(m, PreCommitModule))
    prek_mod = next(m for m in TOOLING_MODULES if isinstance(m, PrekModule))

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.side_effect = ["None", None]

    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = [pre_commit_mod, prek_mod]

    with pytest.raises(
        ExecutionAbortedError, match=r"Hook runner selection cancelled by user\."
    ):
        run_init_wizard()


def test_run_init_wizard_preselects_docker_when_the_template_asks_for_it(mocker):
    """Built-in templates that declare docker = true arrive with it pre-checked."""
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.cli.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)
    mocker.patch("questionary.select").return_value.ask.return_value = "api"
    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = []
    mocker.patch("protostar.cli.wizard.prompt_metadata", return_value={})

    run_init_wizard()

    choices = mock_checkbox.call_args.kwargs["choices"]
    docker = next(c for c in choices if getattr(c, "value", None) == "docker")
    assert docker.checked is True
    assert "Enforced by template" in docker.title


def test_run_init_wizard_leaves_docker_unchecked_without_a_template(mocker):
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.cli.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)
    mocker.patch("questionary.select").return_value.ask.return_value = "None"
    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = []
    mocker.patch("protostar.cli.wizard.prompt_metadata", return_value={})

    run_init_wizard()

    choices = mock_checkbox.call_args.kwargs["choices"]
    docker = next(c for c in choices if getattr(c, "value", None) == "docker")
    assert not docker.checked
    assert "Enforced by template" not in docker.title


def test_run_init_wizard_preselects_recorded_recipe(mocker, tmp_path, monkeypatch):
    """A project recipe supplies the defaults for an interactive re-init."""
    from dataclasses import replace

    from protostar.recipe import Tool, edit_recipe, establish_recipe

    monkeypatch.chdir(tmp_path)
    recipe = replace(
        establish_recipe(UserConfig()),
        docker=True,
        tools=((Tool.RUFF, True),),
    )
    (tmp_path / "pyproject.toml").write_text(edit_recipe("", recipe))
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.cli.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch.dict(os.environ, {}, clear=True)
    mocker.patch("questionary.select").return_value.ask.return_value = "None"
    mock_checkbox = mocker.patch("questionary.checkbox")
    mock_checkbox.return_value.ask.return_value = []
    mocker.patch("protostar.cli.wizard.prompt_metadata", return_value={})

    run_init_wizard()

    choices = mock_checkbox.call_args.kwargs["choices"]
    docker = next(c for c in choices if getattr(c, "value", None) == "docker")
    ruff = next(c for c in choices if getattr(c.value, "config_key", None) == "ruff")
    assert docker.checked is True
    assert ruff.checked is True


def test_run_init_wizard_prompts_for_template_variables(mocker, tmp_path) -> None:
    """A template's variables are asked for once, then rendered and returned."""
    from protostar.config import TemplateAliasConfig

    template = tmp_path / "team.toml"
    template.write_text('[files]\n"region.txt" = "<% REGION %>"\n')
    config = UserConfig(templates={"team": TemplateAliasConfig(source=str(template))})
    mocker.patch("protostar.cli.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.cli.wizard.UserConfig.load", return_value=config)
    mocker.patch.dict(os.environ, {}, clear=True)
    mocker.patch("questionary.select").return_value.ask.return_value = "team"
    mocker.patch("questionary.checkbox").return_value.ask.return_value = []
    mocker.patch("protostar.cli.wizard.prompt_metadata", return_value={})
    prompt = mocker.patch(
        "protostar.cli.wizard.prompt_template_variables", return_value={"REGION": "eu"}
    )

    selections = run_init_wizard()

    assert selections is not None
    prompt.assert_called_once_with(["REGION"])
    assert selections.variables == {"REGION": "eu"}
    assert selections.blueprint is not None
    assert selections.blueprint.files["region.txt"] == "eu"
