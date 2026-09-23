"""Recipe decisions, lazy CLI boundary, and terminal presentation."""

import contextlib
import io
import os
import random
import shutil
import string
import subprocess
import sys
import threading
from dataclasses import replace

import pytest
from rich.console import Console
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    RadioButton,
    Select,
    SelectionList,
    Static,
)
from textual.worker import WorkerCancelled

from protostar.cli import parser, ui
from protostar.cli.tui.app import DecisionApp
from protostar.cli.tui.recipe.screen import RecipeScreen, _TemplateChoice
from protostar.cli.tui.recipe.variables import VariablesScreen
from protostar.config import TemplateAliasConfig, TemplateSource, UserConfig
from protostar.errors import ExecutionAbortedError
from protostar.init_draft import DraftTemplate, InitDraft, resolve_init
from protostar.recipe import Tool, establish_recipe
from protostar.templates import discover_templates


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    """Plan in an empty directory, with no git subprocess and every tool installed."""
    # A fixed directory name keeps the planned project name stable in snapshots.
    project = tmp_path / "orbit"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setattr("protostar.metadata.get_git_config", lambda key: None)
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    return project


def make_app(draft=None, config=None):
    config = config or UserConfig()
    return DecisionApp(
        RecipeScreen(draft or InitDraft(), discover_templates(config), config)
    )


def template_draft(path, text, **changes):
    path.write_text(text)
    source = TemplateSource.load(str(path), display_name="orbit-template")
    return InitDraft(template=DraftTemplate(source), **changes)


async def settle(pilot):
    """Wait for workers, including those a finishing worker starts."""
    # Handle pending messages first: they are what start the workers.
    await pilot.pause()
    for _ in range(10):
        workers = list(pilot.app.workers)
        if not workers:
            break
        for worker in workers:
            # A newer exclusive run supersedes a debounced one; that is expected.
            with contextlib.suppress(WorkerCancelled):
                await worker.wait()
        await pilot.pause()
    await pilot.pause()


def plain(app, selector):
    console = Console(file=io.StringIO(), width=200, record=True, color_system=None)
    console.print(app.screen.query_one(selector, Static).content)
    return console.export_text()


def github_token():
    # Built at test time, never written as a literal: secret scanners flag them.
    rng = random.Random(20260922)
    alphabet = string.ascii_letters + string.digits
    return "ghp_" + "".join(rng.choice(alphabet) for _ in range(36))


@pytest.mark.asyncio
async def test_template_picker_and_docker():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        app.screen.query_one("#template", Select).value = next(
            item for item in app.decision_screen.catalog if item.alias == "api"
        )
        await settle(pilot)
        assert app.screen.query_one("#docker", Checkbox).value
        assert (
            "from template" in app.screen.query_one("#tool-ruff", Checkbox).label.plain
        )
        await pilot.click("#continue")
    assert app.return_value.template.source.reference.locator == "api"
    _, request = resolve_init(app.return_value, UserConfig())
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
        rtd.scroll_visible(immediate=True)
        await pilot.pause()
        await pilot.click("#tool-zensical")
        assert not rtd.disabled
        await pilot.click("#tool-readthedocs")
        await pilot.click("#tool-zensical")
        assert rtd.disabled
        assert not rtd.value
        app.screen.query_one("#tool-ruff").scroll_visible(immediate=True)
        await pilot.pause()
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
    recipe = replace(
        establish_recipe(config),
        tools=((Tool.RUFF, True),),
        docker=True,
        metadata=(("description", "Recorded"),),
    )
    app = make_app(InitDraft(existing_recipe=recipe), config)
    async with app.run_test(size=(110, 45)) as pilot:
        assert "from recipe" in app.screen.query_one("#tool-ruff", Checkbox).label.plain
        assert app.screen.query_one("#docker", Checkbox).value
        assert app.screen.query_one("#meta-description", Input).value == "Recorded"
        app.screen.query_one("#tool-ruff").scroll_visible(immediate=True)
        await pilot.pause()
        await pilot.click("#tool-ruff")
        app.screen.query_one("#template", Select).value = next(
            item for item in app.decision_screen.catalog if item.alias == "api"
        )
        await settle(pilot)
        assert not app.screen.query_one("#tool-ruff", Checkbox).value
        app.screen.query_one("#template", Select).value = _TemplateChoice.NONE
        await settle(pilot)
        assert not app.screen.query_one("#tool-ruff", Checkbox).value
        assert app.decision_screen.draft.template is None


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
            item for item in app.decision_screen.catalog if item.alias == "missing"
        )
        await settle(pilot)
        assert app.screen.query_one("#continue", Button).disabled
        assert "not found" in plain(app, "#template-status")
        app.screen.query_one("#template", Select).value = next(
            item for item in app.decision_screen.catalog if item.alias == "team"
        )
        await settle(pilot)
        assert not app.screen.query_one("#continue", Button).disabled
        await pilot.click("#continue")
    assert app.return_value.template.is_external
    assert app.return_value.template.is_user_aliased
    assert not app.return_value.template.is_trusted
    assert app.return_value.docker


@pytest.mark.asyncio
async def test_remote_template_loads_in_a_worker(tmp_path, mocker):
    local = tmp_path / "remote.toml"
    local.write_text('name = "Remote"\ndocker = true\n')
    release = threading.Event()
    load = TemplateSource.load

    def slow_load(target, **kwargs):
        release.wait(timeout=5)
        return load(str(local), **kwargs)

    mocker.patch(
        "protostar.cli.tui.recipe.screen.TemplateSource.load", side_effect=slow_load
    )
    config = UserConfig(
        templates={"remote": TemplateAliasConfig(source="https://example.com/t.git")}
    )
    app = make_app(config=config)
    async with app.run_test() as pilot:
        app.screen.query_one("#template", Select).value = next(
            item for item in app.decision_screen.catalog if item.alias == "remote"
        )
        await pilot.pause()
        # The UI stays responsive while the fetch runs, and cannot continue.
        assert "Loading" in plain(app, "#template-status")
        assert app.screen.query_one("#continue", Button).disabled
        release.set()
        await settle(pilot)
        assert plain(app, "#template-status").strip() == ""
        assert app.screen.query_one("#docker", Checkbox).value
        assert not app.screen.query_one("#continue", Button).disabled


@pytest.mark.asyncio
async def test_reselecting_the_current_template_abandons_a_load(tmp_path, mocker):
    local = tmp_path / "remote.toml"
    local.write_text('name = "Remote"\ndocker = true\n')
    release = threading.Event()
    load = TemplateSource.load
    mocker.patch(
        "protostar.cli.tui.recipe.screen.TemplateSource.load",
        side_effect=lambda target, **kwargs: (
            release.wait(timeout=5) and load(str(local), **kwargs)
        ),
    )
    config = UserConfig(
        templates={"remote": TemplateAliasConfig(source="https://example.com/t.git")}
    )
    app = make_app(config=config)
    async with app.run_test() as pilot:
        select = app.screen.query_one("#template", Select)
        select.value = next(
            item for item in app.decision_screen.catalog if item.alias == "remote"
        )
        await pilot.pause()
        select.value = _TemplateChoice.NONE
        await pilot.pause()
        assert not app.screen.query_one("#continue", Button).disabled
        release.set()
        await settle(pilot)
        assert app.decision_screen.draft.template is None
        assert not app.screen.query_one("#docker", Checkbox).value


@pytest.mark.asyncio
async def test_credential_value_blocks_continue_and_names_the_rule(tmp_path):
    draft = template_draft(tmp_path / "t.toml", 'name = "<% ORG %>"\n')
    app = make_app(draft)
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        assert "Waiting for values: ORG" in plain(app, "#preview-summary")
        field = app.screen.query_one("#var-ORG", Input)
        field.focus()
        field.value = github_token()
        await pilot.press("enter")
        await settle(pilot)
        assert "gitleaks rule github-pat" in plain(app, "#var-ORG-error")
        assert field.has_class("-invalid")
        # A rejected value never reaches the preview.
        assert "Waiting for values: ORG" in plain(app, "#preview-summary")
        await pilot.click("#continue")
        assert app.is_running
        field.value = "orbit"
        await pilot.press("enter")
        await settle(pilot)
        await pilot.click("#continue")
        await settle(pilot)
    assert dict(app.return_value.variables) == {"ORG": "orbit"}


@pytest.mark.asyncio
async def test_metadata_defaults_follow_config_tools_and_docker():
    config = UserConfig(
        author_name="Ada Lovelace", license="Apache-2.0", supported_os=["Linux"]
    )
    app = make_app(config=config)
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        screen = app.screen
        assert screen.query_one("#meta-author_name", Input).value == "Ada Lovelace"
        assert screen.query_one("#meta-license", Select).value == "Apache-2.0"
        assert screen.query_one("#meta-minimum_python", Input).value == "3.13"
        assert not screen.query_one("#meta-supported_os-row").display
        assert not screen.query_one("#meta-docker_port-row").display
        screen.query_one("#tool-ci", Checkbox).value = True
        screen.query_one("#docker", Checkbox).value = True
        await settle(pilot)
        assert screen.query_one("#meta-supported_os-row").display
        assert screen.query_one("#meta-supported_os", SelectionList).selected == [
            "Linux"
        ]
        assert screen.query_one("#meta-docker_port", Input).value == "8000"
        await pilot.click("#continue")
    metadata = dict(app.return_value.metadata)
    assert metadata["author_name"] == "Ada Lovelace"
    assert metadata["supported_os"] == ("Linux",)
    assert metadata["docker_port"] == "8000"
    assert app.return_value.python_version == "3.13"


@pytest.mark.asyncio
async def test_toggling_a_tool_updates_the_preview():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        assert "pyproject.toml" in plain(app, "#preview-tree")
        assert "zensical.toml" not in plain(app, "#preview-tree")
        app.screen.query_one("#tool-zensical", Checkbox).value = True
        await settle(pilot)
        assert "zensical.toml" in plain(app, "#preview-tree")


@pytest.mark.asyncio
async def test_preview_lists_collisions(workspace):
    (workspace / "pyproject.toml").write_text('[project]\nname = "existing"\n')
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        assert "Already exist: pyproject.toml" in plain(app, "#preview-collisions")


@pytest.mark.asyncio
async def test_variables_step_focuses_the_missing_value(tmp_path):
    draft = template_draft(
        tmp_path / "t.toml",
        '[files]\n"custom.txt" = "<% REGION %> <% TIER %>"\n',
        variables=(("REGION", "eu"),),
    )
    app = DecisionApp(VariablesScreen(draft, UserConfig()))
    async with app.run_test(size=(110, 30)) as pilot:
        await settle(pilot)
        assert app.focused is app.screen.query_one("#var-TIER", Input)
        assert app.screen.query_one("#var-REGION", Input).value == "eu"
        assert "Waiting for values: TIER" in plain(app, "#preview-summary")
        await pilot.press(*"gold", "enter")
        await settle(pilot)
        assert "custom.txt" in plain(app, "#preview-tree")
        await pilot.click("#continue")
    result = app.return_value
    assert result is not None
    assert dict(result.variables) == {"REGION": "eu", "TIER": "gold"}


def test_editor_snapshot(snap_compare, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = make_app(config=UserConfig(author_name="Ada Lovelace"))
    assert snap_compare(app, terminal_size=(110, 50), run_before=settle)


def test_editor_details_snapshot(snap_compare, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = make_app(
        InitDraft(docker=True), UserConfig(ci=True, author_name="Ada Lovelace")
    )

    async def details(pilot):
        await settle(pilot)
        pilot.app.screen.query_one("#editor").scroll_end(animate=False)
        await pilot.pause()

    assert snap_compare(app, terminal_size=(110, 50), run_before=details)


def test_variables_step_snapshot(snap_compare, monkeypatch, tmp_path):
    monkeypatch.delenv("NO_COLOR", raising=False)
    draft = template_draft(
        tmp_path / "t.toml",
        'name = "Orbit"\n[files]\n"<% REGION %>/app.txt" = "<% TIER %>"\n',
        variables=(("REGION", "eu"),),
    )
    app = DecisionApp(VariablesScreen(draft, UserConfig()))
    assert snap_compare(app, terminal_size=(110, 30), run_before=settle)


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
        encoding="utf-8",
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
