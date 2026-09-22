"""Recipe decisions, lazy CLI boundary, and terminal presentation."""

import io
import os
import subprocess
import sys
from dataclasses import replace

import pytest
from rich.console import Console
from textual.widgets import Button, Checkbox, RadioButton, Select

from protostar.cli import parser, ui
from protostar.cli.tui.app import RecipeApp
from protostar.cli.tui.recipe.screen import _TemplateChoice
from protostar.config import TemplateAliasConfig, UserConfig
from protostar.errors import ExecutionAbortedError
from protostar.init_draft import InitDraft, resolve_init
from protostar.recipe import Tool, establish_recipe
from protostar.templates import discover_templates


def make_app(draft=None, config=None):
    config = config or UserConfig()
    return RecipeApp(draft or InitDraft(), discover_templates(config), config)


@pytest.mark.asyncio
async def test_template_picker_and_docker():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        app.screen.query_one("#template", Select).value = next(
            item for item in app.recipe_screen.catalog if item.alias == "api"
        )
        await pilot.pause()
        assert app.screen.query_one("#docker", Checkbox).value
        assert (
            "from template" in app.screen.query_one("#tool-ruff", Checkbox).label.plain
        )
        await pilot.click("#continue")
    assert app.return_value.template.source.reference.locator == "api"
    _, request = resolve_init(replace(app.return_value, metadata=()), UserConfig())
    assert request.template_reference is not None
    assert request.template_reference.origin.value == "built-in"


@pytest.mark.asyncio
async def test_tools_constraints_and_provenance():
    app = make_app(
        config=UserConfig(
            pre_commit=True, prek=False, zensical=False, readthedocs=False
        )
    )
    async with app.run_test(size=(110, 55)) as pilot:
        rtd = app.screen.query_one("#tool-readthedocs", Checkbox)
        assert rtd.disabled
        assert "requires Zensical" in rtd.label.plain
        await pilot.click("#tool-zensical")
        assert not rtd.disabled
        await pilot.click("#tool-readthedocs")
        await pilot.click("#tool-zensical")
        assert rtd.disabled
        assert not rtd.value
        await pilot.click("#tool-ruff")
        assert "your choice" in app.screen.query_one("#tool-ruff", Checkbox).label.plain
        app.screen.query_one("#tool-prek", RadioButton).scroll_visible(immediate=True)
        await pilot.pause()
        await pilot.click("#tool-prek")
        assert not app.screen.query_one("#tool-pre_commit", RadioButton).value
        await pilot.click("#continue")
    choices = dict(app.return_value.tool_choices)
    assert choices[Tool.PREK]
    assert not choices[Tool.PRE_COMMIT]
    assert not choices[Tool.READTHEDOCS]


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["escape", "ctrl+c"])
async def test_cancel(key):
    app = make_app()
    async with app.run_test() as pilot:
        await pilot.press(key)
    assert app.return_value is None


@pytest.mark.asyncio
async def test_recorded_values_and_template_switch_preserve_choices():
    config = UserConfig(ruff=False)
    recipe = replace(establish_recipe(config), tools=((Tool.RUFF, True),), docker=True)
    app = make_app(InitDraft(existing_recipe=recipe), config)
    async with app.run_test(size=(110, 45)) as pilot:
        assert "from recipe" in app.screen.query_one("#tool-ruff", Checkbox).label.plain
        assert app.screen.query_one("#docker", Checkbox).value
        await pilot.click("#tool-ruff")
        app.screen.query_one("#template", Select).value = next(
            item for item in app.recipe_screen.catalog if item.alias == "api"
        )
        await pilot.pause()
        assert not app.screen.query_one("#tool-ruff", Checkbox).value
        app.screen.query_one("#template", Select).value = _TemplateChoice.NONE
        await pilot.pause()
        assert not app.screen.query_one("#tool-ruff", Checkbox).value
        assert app.recipe_screen.draft.template is None


@pytest.mark.asyncio
async def test_alias_and_load_error(tmp_path):
    source = tmp_path / "template.toml"
    source.write_text('name = "Team"\nruff = false\ndocker = true\n')
    config = UserConfig(
        templates={
            "team": TemplateAliasConfig(source=str(source), trusted=False),
            "missing": TemplateAliasConfig(source=str(tmp_path / "missing")),
        }
    )
    app = make_app(config=config)
    async with app.run_test() as pilot:
        app.screen.query_one("#template", Select).value = next(
            item for item in app.recipe_screen.catalog if item.alias == "missing"
        )
        await pilot.pause()
        assert app.screen.query_one("#continue", Button).disabled
        app.screen.query_one("#template", Select).value = next(
            item for item in app.recipe_screen.catalog if item.alias == "team"
        )
        await pilot.pause()
        assert not app.screen.query_one("#continue", Button).disabled
        await pilot.click("#continue")
    assert app.return_value.template.is_external
    assert app.return_value.template.is_user_aliased
    assert not app.return_value.template.is_trusted
    assert app.return_value.docker


def test_editor_snapshot(snap_compare, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = make_app()
    assert snap_compare(app, terminal_size=(110, 50))


@pytest.mark.parametrize(
    "args", [["help", "init"], ["init", "--json", "--dry-run"], ["init", "--dry-run"]]
)
def test_non_tui_cli_never_imports_textual(tmp_path, args):
    # A fresh interpreter is essential: the Pilot tests above import Textual.
    probe = """
import sys
from protostar.cli.main import main
try:
    main()
except SystemExit:
    pass
assert not any(name == "textual" or name.startswith("textual.") for name in sys.modules)
"""
    env = {**os.environ, "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path)}
    env.pop("PROTOSTAR_BENCHMARK_WIZARD", None)
    result = subprocess.run(
        [sys.executable, "-c", probe, *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_benchmark_exits_before_launch(mocker, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROTOSTAR_BENCHMARK_WIZARD", "1")
    monkeypatch.setattr(sys, "argv", ["protostar", "init"])
    mocker.patch.object(UserConfig, "load", return_value=UserConfig())
    launch = mocker.patch.object(parser, "edit_recipe")
    with pytest.raises(SystemExit) as exc:
        parser.intercept_interactive_wizards(mocker.Mock())
    assert exc.value.code == 0
    launch.assert_not_called()


def test_cancelled_editor_never_executes(mocker, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["protostar", "init"])
    mocker.patch.object(parser, "is_interactive", return_value=True)
    mocker.patch.object(UserConfig, "load", return_value=UserConfig())
    mocker.patch.object(parser, "edit_recipe", return_value=None)
    execute = mocker.patch.object(ui, "_run_engine")
    with pytest.raises(ExecutionAbortedError):
        parser.intercept_interactive_wizards(mocker.Mock())
    execute.assert_not_called()


def test_summary_is_literal_and_cp1252_safe(mocker):
    from protostar.intent import TemplateOrigin, TemplateReference
    from protostar.models import InitRequest

    output = io.BytesIO()
    stream = io.TextIOWrapper(output, encoding="cp1252", errors="strict")
    mocker.patch.object(ui, "console", Console(file=stream, force_terminal=False))
    request = InitRequest(
        template_reference=TemplateReference(
            TemplateOrigin.BUILT_IN, "api", "digest", "[red]API[/red]"
        )
    )
    ui.print_recipe_summary(request)
    stream.flush()
    assert "[red]API[/red]" in output.getvalue().decode("cp1252")
