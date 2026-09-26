"""The configuration form, driven from the keyboard, and the command around it."""

import argparse
import io
from pathlib import Path

import pytest
from rich.console import Console
from textual.widgets import Button, Checkbox, Input, Select

from protostar.cli import ui
from protostar.cli.main import _config_prefill, handle_config
from protostar.cli.tui.app import DecisionApp
from protostar.cli.tui.config.screen import ConfigScreen
from protostar.cli.tui.keys import LeaveScreen
from protostar.cli.tui.tool_info import ToolInfoScreen
from protostar.config import DEFAULT_CONFIG_CONTENT, UserConfig
from protostar.config_edit import ConfigEdit, OpenInEditor, SaveConfig
from protostar.errors import ConfigurationError, InvalidUsageError
from protostar.modules import MypyModule

PATH = Path("/home/ada/.config/protostar/config.toml")
GIT = {"user.name": "Ada Lovelace", "user.email": "ada@example.com"}


@pytest.fixture(autouse=True)
def git(monkeypatch):
    """Git's global identity, without running git."""
    monkeypatch.setattr("protostar.metadata.get_git_config", GIT.get)


def make_app(content=DEFAULT_CONFIG_CONTENT):
    config = UserConfig.parse(content, str(PATH))
    return DecisionApp(ConfigScreen(content, PATH, _config_prefill(config)))


def text(app, selector):
    console = Console(file=io.StringIO(), width=200, record=True, color_system=None)
    console.print(app.screen.query_one(selector).content)
    return console.export_text()


@pytest.mark.asyncio
async def test_identity_prefills_from_git_and_saving_writes_it():
    app = make_app()
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        assert app.screen.query_one("#author_name", Input).value == "Ada Lovelace"
        assert app.screen.query_one("#author_email", Input).value == "ada@example.com"
        assert "come from Git" in text(app, "#subtitle")
        assert "2 settings will change." in text(app, "#changes-summary")
        await pilot.press("ctrl+s")
    decision = app.return_value
    assert isinstance(decision, SaveConfig)
    assert decision.edit.changed == ("author_name", "author_email")
    assert 'author_name = "Ada Lovelace"' in decision.edit.after


@pytest.mark.asyncio
async def test_the_file_wins_over_git():
    app = make_app('[env]\nauthor_name = "Saved Name"\n')
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        assert app.screen.query_one("#author_name", Input).value == "Saved Name"


@pytest.mark.asyncio
async def test_the_keyboard_sets_a_field_an_editor_and_a_tool():
    app = make_app('[env]\nauthor_name = "Ada"\nauthor_email = "a@b.c"\n')
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert screen.query_one("#save", Button).disabled
        assert "Nothing to save yet." in text(app, "#changes-summary")
        screen.query_one("#github_username", Input).focus()
        await pilot.press(*"ada", "enter")
        assert app.focused is screen.query_one("#ide", Select)
        await pilot.press("space", "down", "down", "enter")
        assert screen.query_one("#ide", Select).value == "cursor"
        screen.query_one("#tool-mypy", Checkbox).focus()
        await pilot.press("space")
        await pilot.press("ctrl+s")
    decision = app.return_value
    assert isinstance(decision, SaveConfig)
    assert decision.edit.changed == ("github_username", "ide", "mypy")


@pytest.mark.asyncio
async def test_an_invalid_value_disables_save_and_says_why():
    app = make_app()
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        app.screen.query_one("#github_username", Input).focus()
        await pilot.press(*"bad name")
        assert "GitHub username" in text(app, "#changes-summary")
        assert app.screen.query_one("#save", Button).disabled
        await pilot.press("ctrl+s")
        assert isinstance(app.screen, ConfigScreen)


@pytest.mark.asyncio
async def test_escape_asks_only_when_something_changed():
    app = make_app()
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        # Git's prefill is a change to save, but not one the user made.
        await pilot.press("escape")
    assert app.return_value is None

    app = make_app()
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        app.screen.query_one("#tool-mypy", Checkbox).focus()
        await pilot.press("space", "escape")
        assert isinstance(app.screen, LeaveScreen)
        await pilot.press("escape")
        assert isinstance(app.screen, ConfigScreen)
        assert app.screen.query_one("#tool-mypy", Checkbox).value
        await pilot.press("escape", "enter")
    assert app.return_value is None


@pytest.mark.asyncio
async def test_e_opens_the_editor_but_types_into_a_field():
    app = make_app()
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        field = app.screen.query_one("#python_version", Input)
        field.focus()
        await pilot.press("end", "e")
        assert field.value == "3.13e"
        assert isinstance(app.screen, ConfigScreen)
        app.screen.query_one("#tool-ruff", Checkbox).focus()
        await pilot.press("e")
        # The typed letter is a change, so leaving for the editor asks.
        assert isinstance(app.screen, LeaveScreen)
        await pilot.press("enter")
    assert isinstance(app.return_value, OpenInEditor)


@pytest.mark.asyncio
async def test_i_explains_a_tool_default():
    app = make_app()
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        mypy = app.screen.query_one("#tool-mypy", Checkbox)
        mypy.focus()
        await pilot.press("i")
        assert isinstance(app.screen, ToolInfoScreen)
        assert app.screen.module.info == MypyModule.info
        await pilot.press("escape")
        assert app.focused is mypy
        assert not mypy.value


@pytest.mark.asyncio
async def test_one_hook_manager_at_most():
    app = make_app()
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        app.screen.query_one("#hook-manager").focus()
        await pilot.press("down", "space")
        assert app.screen.values()["pre_commit"]
        await pilot.press("down", "space")
        values = app.screen.values()
        assert values["prek"]
        assert not values["pre_commit"]


def test_config_form_snapshot(snap_compare, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = make_app()
    assert snap_compare(app, terminal_size=(120, 50))


# --- The command ----------------------------------------------------------


@pytest.fixture
def config_file(mocker, tmp_path, monkeypatch):
    path = tmp_path / "protostar" / "config.toml"
    mocker.patch("protostar.config.CONFIG_FILE", path)
    mocker.patch("protostar.cli.main.is_interactive", return_value=True)
    monkeypatch.setattr(ui, "is_json_mode", False)
    return path


def test_bare_config_opens_the_form_and_saves_its_change(mocker, config_file):
    config_file.parent.mkdir()
    config_file.write_text("[env]\n# keep me\nruff = true\n")

    def save(content, path, prefill):
        assert path == config_file
        assert prefill["author_name"] == "Ada Lovelace"
        assert prefill["ruff"] is True
        edit = ConfigEdit(content, content.replace("true", "false"), ("ruff",))
        return SaveConfig(edit)

    mocker.patch("protostar.cli.main.edit_settings", side_effect=save)
    run = mocker.patch("subprocess.run")
    handle_config(argparse.Namespace())
    assert config_file.read_text() == "[env]\n# keep me\nruff = false\n"
    run.assert_not_called()


def test_a_missing_file_starts_from_the_default_and_is_written_on_save(
    mocker, config_file
):
    def save(content, path, prefill):
        assert content == DEFAULT_CONFIG_CONTENT
        return SaveConfig(ConfigEdit(content, content + "mypy = true\n", ("mypy",)))

    mocker.patch("protostar.cli.main.edit_settings", side_effect=save)
    handle_config(argparse.Namespace())
    assert config_file.read_text().endswith("mypy = true\n")


def test_cancelling_the_form_writes_nothing(mocker, config_file):
    mocker.patch("protostar.cli.main.edit_settings", return_value=None)
    handle_config(argparse.Namespace())
    assert not config_file.exists()


def test_the_form_hands_off_to_the_editor(mocker, config_file):
    mocker.patch("protostar.cli.main.edit_settings", return_value=OpenInEditor())
    mocker.patch.dict("os.environ", {"EDITOR": "nano"})
    mocker.patch("shutil.which", return_value="/usr/bin/nano")
    run = mocker.patch("subprocess.run")
    handle_config(argparse.Namespace())
    run.assert_called_once_with(["nano", str(config_file)], check=True)
    assert config_file.read_text() == DEFAULT_CONFIG_CONTENT


def test_a_file_changed_while_the_form_was_open_is_not_overwritten(mocker, config_file):
    config_file.parent.mkdir()
    config_file.write_text("[env]\n")

    def save(content, path, prefill):
        config_file.write_text("[env]\nmypy = true\n")
        return SaveConfig(ConfigEdit(content, "[env]\nide = 'none'\n", ("ide",)))

    mocker.patch("protostar.cli.main.edit_settings", side_effect=save)
    with pytest.raises(ConfigurationError, match="changed while the form was open"):
        handle_config(argparse.Namespace())
    assert config_file.read_text() == "[env]\nmypy = true\n"


@pytest.mark.parametrize(
    ("interactive", "json_mode"),
    [(False, False), (True, True)],
    ids=["non-interactive", "json"],
)
def test_bare_config_needs_an_interactive_terminal(
    mocker, monkeypatch, config_file, interactive, json_mode
):
    mocker.patch("protostar.cli.main.is_interactive", return_value=interactive)
    monkeypatch.setattr(ui, "is_json_mode", json_mode)
    form = mocker.patch("protostar.cli.main.edit_settings")
    with pytest.raises(InvalidUsageError, match="interactive terminal") as caught:
        handle_config(argparse.Namespace())
    assert "protostar config --edit" in (caught.value.hint or "")
    form.assert_not_called()
    assert not config_file.exists()


@pytest.mark.asyncio
async def test_question_mark_lists_every_key_and_buttons_show_theirs():
    app = make_app()
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        labels = {button.id: str(button.label) for button in app.screen.query(Button)}
        assert labels == {
            "cancel": "Cancel  esc",
            "edit-file": "Edit file  e",
            "save": "Save  ^s",
        }
        app.screen.query_one("#tool-ruff", Checkbox).focus()
        await pilot.press("?")
        rows = dict(app.screen.rows)
        assert rows["e"] == "Open the file in $EDITOR instead"
        assert rows["^s"] == "Save the change shown beside the form"
        assert "i" in rows
