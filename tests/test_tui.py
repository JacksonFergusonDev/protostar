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
from pathlib import Path

import pytest
from rich.console import Console
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    RadioButton,
    RadioSet,
    Select,
    SelectionList,
    Static,
    Tree,
)
from textual.worker import WorkerCancelled

from protostar.analysis import analyze_project
from protostar.cli import parser, ui
from protostar.cli.tui.app import DecisionApp
from protostar.cli.tui.keys import KeybindingsScreen, LeaveScreen
from protostar.cli.tui.recipe.screen import RecipeScreen, _TemplateChoice
from protostar.cli.tui.recipe.variables import VariablesScreen
from protostar.cli.tui.review.screen import ReviewScreen
from protostar.cli.tui.tool_info import ToolInfoScreen
from protostar.config import TemplateAliasConfig, TemplateSource, UserConfig
from protostar.errors import ConfigurationError, ExecutionAbortedError
from protostar.executor import SystemExecutor
from protostar.init_draft import DraftTemplate, InitDraft, resolve_init
from protostar.intent import TemplateOrigin, TemplateReference
from protostar.manifest import CollisionStrategy
from protostar.merge import ResolutionChoice
from protostar.modules import MypyModule, PrekModule
from protostar.orchestrator import Orchestrator
from protostar.recipe import Tool, establish_recipe
from protostar.registry import PinProvenance, RemoteHook, ResolvedHookRevision
from protostar.sync_state import SyncState, serialize_state
from protostar.system_deps import GlobalExecutable
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
    monkeypatch.setenv("PROTOSTAR_OFFLINE_HOOK_REGISTRY", "1")
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


async def apply(pilot, *, trust=False):
    """Continue from the editor, then apply the change review, by key."""
    await pilot.press("ctrl+s")
    await settle(pilot)
    assert isinstance(pilot.app.screen, ReviewScreen)
    if trust:
        await pilot.press("t")
    await pilot.press("a")


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
        await settle(pilot)
        app.screen.query_one("#template", Select).value = next(
            item for item in app.decision_screen.catalog if item.alias == "api"
        )
        await settle(pilot)
        assert app.screen.query_one("#docker", Checkbox).value
        assert (
            "from template" in app.screen.query_one("#tool-ruff", Checkbox).label.plain
        )
        await apply(pilot)
    draft = app.return_value.draft
    assert draft.template.source.reference.locator == "api"
    _, request = resolve_init(draft, UserConfig())
    assert request.template_reference is not None
    assert request.template_reference.origin.value == "built-in"


@pytest.mark.asyncio
async def test_missing_tools_are_marked_and_never_block(missing_executables):
    missing_executables.update({GlobalExecutable.DIRENV, GlobalExecutable.JUST})
    app = make_app(config=UserConfig(direnv=True, just=True))
    async with app.run_test(size=(110, 55)) as pilot:
        await settle(pilot)
        for tool in ("direnv", "just"):
            label = app.screen.query_one(f"#tool-{tool}", Checkbox).label.plain
            assert "not installed" in label
        ruff = app.screen.query_one("#tool-ruff", Checkbox).label.plain
        assert "not installed" not in ruff
        assert "Skipping `direnv allow`" in plain(app, "#preview-notes")
        await pilot.press("ctrl+s")
        await settle(pilot)
        assert isinstance(app.screen, ReviewScreen)
        steps = plain(app, "#steps-list")
        assert "Skipped" in steps
        assert "direnv allow" in steps
        await pilot.press("a")
    assert app.return_value is not None


@pytest.mark.asyncio
async def test_tools_constraints_and_provenance():
    app = make_app(
        config=UserConfig(
            pre_commit=True, prek=False, zensical=False, readthedocs=False
        )
    )
    async with app.run_test(size=(110, 55)) as pilot:
        await settle(pilot)
        rtd = app.screen.query_one("#tool-readthedocs", Checkbox)
        assert rtd.disabled
        assert "requires Zensical" in rtd.label.plain
        rtd.scroll_visible(immediate=True)
        await pilot.pause()
        await pilot.click("#tool-zensical")
        await pilot.pause()
        assert not rtd.disabled
        await pilot.click("#tool-readthedocs")
        await pilot.pause()
        await pilot.click("#tool-zensical")
        await pilot.pause()
        assert rtd.disabled
        assert not rtd.value
        app.screen.query_one("#tool-ruff").scroll_visible(immediate=True)
        await pilot.pause()
        await pilot.click("#tool-ruff")
        await pilot.pause()
        assert "your choice" in app.screen.query_one("#tool-ruff", Checkbox).label.plain
        app.screen.query_one("#tool-prek", RadioButton).scroll_visible(immediate=True)
        await pilot.pause()
        await pilot.click("#tool-prek")
        await pilot.pause()
        assert not app.screen.query_one("#tool-pre_commit", RadioButton).value
        await apply(pilot)
    choices = dict(app.return_value.draft.tool_choices)
    assert choices[Tool.PREK]
    assert not choices[Tool.PRE_COMMIT]
    assert not choices[Tool.READTHEDOCS]


@pytest.mark.asyncio
async def test_a_template_replaces_the_chosen_hook_manager():
    app = make_app(config=UserConfig(pre_commit=False, prek=False))
    async with app.run_test(size=(110, 55)) as pilot:
        await settle(pilot)
        prek = app.screen.query_one("#tool-prek", RadioButton)
        pre_commit = app.screen.query_one("#tool-pre_commit", RadioButton)
        pre_commit.scroll_visible(immediate=True)
        await pilot.pause()
        await pilot.click("#tool-pre_commit")
        await settle(pilot)
        assert pre_commit.value
        app.screen.query_one("#template", Select).value = next(
            item for item in app.decision_screen.catalog if item.alias == "cli"
        )
        await settle(pilot)
        assert prek.value
        assert "from template" in prek.label.plain
        assert not pre_commit.value
        assert not app.screen.query_one("#continue", Button).disabled
        assert not app.screen.query_one("#preview-summary", Static).has_class("-error")
        # Choosing again after the template is loaded is kept.
        await pilot.click("#tool-pre_commit")
        await settle(pilot)
        assert pre_commit.value
        assert not prek.value
        await apply(pilot)
    choices = dict(app.return_value.draft.tool_choices)
    assert choices[Tool.PRE_COMMIT]
    assert not choices[Tool.PREK]


@pytest.mark.asyncio
async def test_invalid_recorded_tools_show_only_in_the_preview():
    recipe = replace(
        establish_recipe(UserConfig()),
        tools=((Tool.PRE_COMMIT, True), (Tool.PREK, True)),
    )
    app = make_app(InitDraft(existing_recipe=recipe))
    async with app.run_test(size=(110, 55)) as pilot:
        await settle(pilot)
        assert app.screen.query_one("#continue", Button).disabled
        assert "pre-commit" in plain(app, "#preview-summary")
        assert not app.screen.query("#constraints")


@pytest.mark.asyncio
async def test_tool_provenance_reverts_when_aligned_with_config_or_template():
    app = make_app(config=UserConfig(ruff=True, pytest=False))
    async with app.run_test(size=(110, 55)) as pilot:
        await settle(pilot)
        ruff = app.screen.query_one("#tool-ruff", Checkbox)
        assert ruff.value
        assert "from config" in ruff.label.plain

        # Toggling ruff away from config makes it "your choice".
        ruff.focus()
        await pilot.press("space")
        await settle(pilot)
        assert not ruff.value
        assert "your choice" in ruff.label.plain

        # Toggling ruff back to its config value reverts provenance to "from config".
        await pilot.press("space")
        await settle(pilot)
        assert ruff.value
        assert "from config" in ruff.label.plain

        # Selecting a template sets declared tools to "from template".
        app.screen.query_one("#template", Select).value = next(
            item for item in app.decision_screen.catalog if item.alias == "api"
        )
        await settle(pilot)
        pytest_box = app.screen.query_one("#tool-pytest", Checkbox)
        assert pytest_box.value
        assert "from template" in pytest_box.label.plain

        # Toggling a template tool away from the template makes it "your choice".
        pytest_box.focus()
        await pilot.press("space")
        await settle(pilot)
        assert not pytest_box.value
        assert "your choice" in pytest_box.label.plain

        # Toggling it back so it aligns with the template reverts it to "from template".
        await pilot.press("space")
        await settle(pilot)
        assert pytest_box.value
        assert "from template" in pytest_box.label.plain

        # Exclusive git hook manager: api template declares prek = true.
        prek = app.screen.query_one("#tool-prek", RadioButton)
        pre_commit = app.screen.query_one("#tool-pre_commit", RadioButton)
        assert prek.value
        assert "from template" in prek.label.plain
        assert not pre_commit.value
        assert "from config" in pre_commit.label.plain

        # Selecting pre_commit marks both as "your choice".
        await pilot.click("#tool-pre_commit")
        await settle(pilot)
        assert not prek.value
        assert "your choice" in prek.label.plain
        assert pre_commit.value
        assert "your choice" in pre_commit.label.plain

        # Selecting prek again aligns back with the template opinions.
        await pilot.click("#tool-prek")
        await settle(pilot)
        assert prek.value
        assert "from template" in prek.label.plain
        assert not pre_commit.value
        assert "from config" in pre_commit.label.plain


@pytest.mark.asyncio
async def test_escape_asks_before_leaving():
    app = make_app()
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("escape")
        assert isinstance(app.screen, LeaveScreen)
        assert labels(app) == {"stay": "Stay  esc", "leave": "Leave  enter"}
        await pilot.press("escape")
        assert isinstance(app.screen, RecipeScreen)
        assert app.is_running
        # Escape from a text field asks too, rather than losing the recipe.
        app.screen.query_one("#meta-description", Input).focus()
        await pilot.press("escape")
        assert isinstance(app.screen, LeaveScreen)
        await pilot.press("enter")
        assert not app.is_running
    assert app.return_value is None


@pytest.mark.asyncio
@pytest.mark.parametrize("confirming", [False, True])
async def test_ctrl_c_quits_without_asking(confirming):
    app = make_app()
    async with app.run_test() as pilot:
        await settle(pilot)
        if confirming:
            await pilot.press("escape")
        await pilot.press("ctrl+c")
        assert not app.is_running
    assert app.return_value is None


def labels(app):
    """Each shown button's label, by id."""
    return {
        button.id: str(button.label)
        for button in app.screen.query(Button)
        if button.display
    }


def legend(app):
    """The footer's entries: a group's description, or a lone binding's."""
    return {
        (active.binding.group or active.binding).description
        for active in app.screen.active_bindings.values()
        if active.binding.show
    }


@pytest.mark.asyncio
async def test_arrows_walk_every_row_without_changing_a_value():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        screen = app.screen
        template = screen.query_one("#template", Select)
        assert app.focused is template
        editor = screen.query_one("#editor")
        rows = [w.id for w in screen.focus_chain if editor in w.ancestors]
        before = screen._current_draft()
        visited = [app.focused.id]
        for _ in range(len(rows) + 5):
            await pilot.press("down")
            if app.focused.id != visited[-1]:
                visited.append(app.focused.id)
        # Past the last row, the cursor lands on the primary button and stays.
        assert visited == [*rows, "continue"]
        for _ in range(len(rows) + 5):
            await pilot.press("up")
        assert app.focused is template
        assert not template.expanded
        await settle(pilot)
        assert screen._current_draft() == before


@pytest.mark.asyncio
async def test_menus_open_on_space_and_close_on_escape():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        template = app.screen.query_one("#template", Select)
        assert legend(app) == {"Open", "Move", "Next", "Keybindings"}
        await pilot.press("space")
        assert template.expanded
        await pilot.press("escape")
        assert not template.expanded
        assert isinstance(app.screen, RecipeScreen)


@pytest.mark.asyncio
async def test_tab_treats_the_tools_as_one_stop():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        await pilot.press("tab")
        assert app.focused.id == "docker"
        assert legend(app) == {"Toggle", "Move", "Next", "Keybindings"}
        await pilot.press("down", "down")
        assert app.focused.id == "tool-mypy"
        await pilot.press("tab")
        assert app.focused.id == "exclusive-0"
        await pilot.press("shift+tab")
        assert app.focused.id == "docker"
        await pilot.press("shift+tab")
        assert app.focused.id == "template"


@pytest.mark.asyncio
async def test_arrows_move_a_choice_highlight_and_space_chooses():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        screen = app.screen
        choice = screen.query_one("#exclusive-0", RadioSet)

        def highlighted():
            return [b.id for b in choice.query(RadioButton) if b.has_class("-selected")]

        screen.query_one("#tool-community").focus()
        await pilot.press("down")
        assert app.focused is choice
        assert highlighted() == ["none-0"]
        assert legend(app) == {"Move", "Choose", "Next", "Keybindings"}
        await pilot.press("down", "down")
        assert highlighted() == ["tool-prek"]
        assert choice.pressed_button.id == "none-0"
        await pilot.press("space")
        assert choice.pressed_button.id == "tool-prek"
        assert screen.enabled[Tool.PREK]
        # The ends hand off to the neighbouring rows instead of wrapping.
        await pilot.press("down")
        assert app.focused.id == "meta-description"
        await pilot.press("up")
        assert app.focused is choice
        assert highlighted() == ["tool-prek"]


@pytest.mark.asyncio
async def test_a_whole_init_from_the_keyboard():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        await pilot.press("tab", "space")  # Docker
        await pilot.press("tab", "down", "down", "space")  # prek
        await pilot.press("tab")
        assert legend(app) == {"Move", "Accept", "Next"}
        await pilot.press(*"Orbit", "enter")
        assert app.focused.id == "meta-license"
        await settle(pilot)
        await apply(pilot)
    draft = app.return_value.draft
    assert draft.docker
    assert dict(draft.tool_choices)[Tool.PREK]
    assert dict(draft.metadata)["description"] == "Orbit"


@pytest.mark.asyncio
async def test_buttons_show_their_keys_and_question_mark_lists_them_all():
    app = make_app()
    async with app.run_test() as pilot:
        await settle(pilot)
        assert labels(app) == {"cancel": "Cancel  esc", "continue": "Continue  ^s"}
        await pilot.press("?")
        assert isinstance(app.screen, KeybindingsScreen)
        assert ("^s", "Continue") in app.screen.rows
        assert ("?", "Show this list") in app.screen.rows
        await pilot.press("escape")
        assert isinstance(app.screen, RecipeScreen)
        # f1 still acts as a secondary fallback binding
        await pilot.press("f1")
        assert isinstance(app.screen, KeybindingsScreen)
        await pilot.press("question_mark")
        assert isinstance(app.screen, RecipeScreen)


@pytest.mark.asyncio
async def test_i_explains_the_focused_tool_and_esc_returns_to_it(mocker):
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        screen = app.screen
        mypy = screen.query_one("#tool-mypy", Checkbox)
        assert mypy.tooltip == MypyModule.info.summary
        mypy.focus()
        await pilot.pause()
        assert "Tool info" in legend(app)
        before = mypy.value
        await pilot.press("i")
        assert isinstance(app.screen, ToolInfoScreen)
        assert app.screen.module.info == MypyModule.info
        assert labels(app) == {"close": "Close  esc", "docs": "Open docs  o"}
        opened = mocker.patch.object(app, "open_url")
        await pilot.press("o")
        opened.assert_called_once_with(MypyModule.info.docs_url)
        await pilot.press("escape")
        assert isinstance(app.screen, RecipeScreen)
        assert app.focused is mypy
        assert mypy.value == before
        assert screen.enabled[Tool.MYPY] == before


@pytest.mark.asyncio
async def test_i_explains_the_highlighted_hook_manager_but_not_none():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        screen = app.screen
        choice = screen.query_one("#exclusive-0", RadioSet)
        screen.query_one("#tool-community").focus()
        await pilot.press("down")
        assert app.focused is choice
        assert "Tool info" not in legend(app)
        await pilot.press("i")
        assert app.screen is screen
        await pilot.press("down", "down")
        assert "Tool info" in legend(app)
        await pilot.press("i")
        assert isinstance(app.screen, ToolInfoScreen)
        assert app.screen.module.info == PrekModule.info
        await pilot.press("escape")
        assert app.focused is choice
        assert choice.pressed_button.id == "none-0"


@pytest.mark.asyncio
async def test_i_typed_into_a_text_field_is_a_letter():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        field = app.screen.query_one("#meta-description", Input)
        field.focus()
        await pilot.press(*"ci")
        assert field.value == "ci"
        assert isinstance(app.screen, RecipeScreen)


@pytest.mark.asyncio
async def test_the_keybindings_list_names_tool_info():
    app = make_app()
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("?")
        assert ("i", "What the focused tool does to the project") in app.screen.rows


def test_tool_info_snapshot(snap_compare, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = make_app(config=UserConfig(author_name="Ada Lovelace"))

    async def popup(pilot):
        await settle(pilot)
        pilot.app.screen.query_one("#tool-ruff").focus()
        await pilot.press("i")
        await pilot.pause()

    assert snap_compare(app, terminal_size=(110, 50), run_before=popup)


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
        await settle(pilot)
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
        await settle(pilot)
        app.screen.query_one("#template", Select).value = next(
            item for item in app.decision_screen.catalog if item.alias == "missing"
        )
        await settle(pilot)
        assert app.screen.query_one("#continue", Button).disabled
        # A hard error shows in the preview and nowhere else.
        assert "not found" in plain(app, "#preview-summary")
        assert not app.screen.query_one("#template-status", Static).display
        # Editing another field keeps the error in place of a stale plan.
        app.screen.query_one("#tool-ruff", Checkbox).toggle()
        await settle(pilot)
        assert "not found" in plain(app, "#preview-summary")
        await pilot.press("ctrl+s")
        assert isinstance(app.screen, RecipeScreen)
        app.screen.query_one("#template", Select).value = next(
            item for item in app.decision_screen.catalog if item.alias == "team"
        )
        await settle(pilot)
        assert not app.screen.query_one("#continue", Button).disabled
        await apply(pilot, trust=True)
    draft = app.return_value.draft
    assert draft.template.is_external
    assert draft.template.is_user_aliased
    assert not draft.template.is_trusted
    assert draft.docker


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
        await settle(pilot)
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
        await settle(pilot)
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
        # The editor opens on the value it is waiting for.
        assert app.focused is field
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
        await apply(pilot)
    assert dict(app.return_value.draft.variables) == {"ORG": "orbit"}


@pytest.mark.asyncio
async def test_confirming_a_flagged_value_keeps_it(tmp_path):
    draft = template_draft(tmp_path / "t.toml", 'name = "<% ORG %>"\n')
    token = github_token()
    app = make_app(draft)
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        screen = app.screen
        allow = screen.query_one("#var-ORG-allow", Checkbox)
        assert not allow.display
        field = screen.query_one("#var-ORG", Input)
        field.focus()
        field.value = token
        await pilot.press("enter")
        await settle(pilot)
        assert allow.display
        allow.value = True
        await settle(pilot)
        assert not screen.query_one("#var-ORG-error").display
        assert "Waiting for values" not in plain(app, "#preview-summary")
        # Editing the value withdraws the confirmation it was given for.
        field.value = token + "x"
        await pilot.pause()
        assert not allow.value
        field.value = token
        await pilot.pause()
        await pilot.click("#continue")
        await settle(pilot)
        assert "gitleaks rule github-pat" in plain(app, "#var-ORG-error")
        allow.value = True
        await settle(pilot)
        await apply(pilot)
    result = app.return_value.draft
    assert dict(result.variables) == {"ORG": token}
    assert result.allowed_secrets == frozenset({"ORG"})


@pytest.mark.asyncio
async def test_fields_show_descriptions_and_credential_names(tmp_path):
    draft = template_draft(
        tmp_path / "t.toml",
        '[variables.REGION]\ndescription = "Deployment region, e.g. eu-west-1"\n'
        '[files]\n"custom.txt" = "<% REGION %> <% api_token %>"\n',
    )
    app = make_app(draft)
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        text = "\n".join(
            str(widget.content) for widget in app.screen.query("VariableFields Static")
        )
        assert "Deployment region, e.g. eu-west-1" in text
        assert "Named like a credential" in text
        assert len(app.screen.query(".field-warning")) == 1


@pytest.mark.asyncio
async def test_variables_step_keeps_a_value_allowed_by_flag(tmp_path):
    token = github_token()
    draft = template_draft(
        tmp_path / "t.toml",
        '[files]\n"custom.txt" = "<% ORG %> <% TIER %>"\n',
        variables=(("ORG", token),),
        allowed_secrets=frozenset({"ORG"}),
    )
    app = DecisionApp(VariablesScreen(draft, UserConfig()))
    async with app.run_test(size=(110, 30)) as pilot:
        await settle(pilot)
        assert app.screen.query_one("#var-ORG-allow", Checkbox).value
        await pilot.press(*"gold", "enter")
        await settle(pilot)
        await pilot.click("#continue")
    result = app.return_value
    assert result is not None
    assert dict(result.variables) == {"ORG": token, "TIER": "gold"}
    assert result.allowed_secrets == frozenset({"ORG"})


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
        await apply(pilot)
    draft = app.return_value.draft
    metadata = dict(draft.metadata)
    assert metadata["author_name"] == "Ada Lovelace"
    assert metadata["supported_os"] == ("Linux",)
    assert metadata["docker_port"] == "8000"
    assert draft.python_version == "3.13"


def existing_project(root):
    """A project Protostar has not seen: hooks, a justfile, Docker, facts."""
    (root / "pyproject.toml").write_text(
        '[project]\nname = "orbit"\nrequires-python = ">=3.12"\n'
        'authors = [{ name = "Ada Lovelace", email = "ada@example.com" }]\n'
        'classifiers = ["License :: OSI Approved :: Apache Software License"]\n\n'
        '[dependency-groups]\ndev = ["prek"]\n'
    )
    (root / "justfile").write_text("test:\n    pytest\n")
    (root / ".pre-commit-config.yaml").write_text("repos: []\n")
    (root / ".readthedocs.yaml").write_text("version: 2\n")
    (root / "Dockerfile").write_text("FROM python:3.12\n")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "deploy.yml").write_text("name: Deploy\n")
    return analyze_project(root)


@pytest.mark.asyncio
async def test_an_existing_project_prefills_its_tools_and_details(workspace):
    config = UserConfig(
        ruff=True,
        just=False,
        prek=False,
        pre_commit=False,
        zensical=False,
        readthedocs=False,
    )
    app = make_app(InitDraft(analysis=existing_project(workspace)), config)
    async with app.run_test(size=(110, 55)) as pilot:
        await settle(pilot)
        screen = app.screen
        assert "Existing project" in plain(app, "#subtitle")
        just = screen.query_one("#tool-just", Checkbox)
        assert just.value
        assert "found · justfile" in just.label.plain
        prek = screen.query_one("#tool-prek", RadioButton)
        assert prek.value
        assert "found · .pre-commit-config.yaml" in prek.label.plain
        # Found tools are only added: a configured default stays on.
        ruff = screen.query_one("#tool-ruff", Checkbox)
        assert ruff.value
        assert "from config" in ruff.label.plain
        # Read the Docs needs Zensical, which the project does not use.
        rtd = screen.query_one("#tool-readthedocs", Checkbox)
        assert not rtd.value
        assert "found · .readthedocs.yaml" in rtd.label.plain
        assert "requires Zensical" in rtd.label.plain
        docker = screen.query_one("#docker", Checkbox)
        assert docker.value
        assert "found · Dockerfile" in docker.label.plain
        assert "deploy.yml" in plain(app, "#analysis-notes")
        assert screen.query_one("#meta-author_name", Input).value == "Ada Lovelace"
        assert screen.query_one("#meta-author_email", Input).value == "ada@example.com"
        assert screen.query_one("#meta-license", Select).value == "Apache-2.0"
        assert screen.query_one("#meta-minimum_python", Input).value == "3.12"
        just.focus()
        await pilot.press("space")
        await settle(pilot)
        assert not just.value
        assert "your choice" in just.label.plain
        await apply(pilot)
    draft = app.return_value.draft
    choices = dict(draft.tool_choices)
    assert choices[Tool.PREK]
    assert not choices[Tool.PRE_COMMIT]
    assert not choices[Tool.JUST]
    assert draft.docker
    assert draft.python_version == "3.12"


@pytest.mark.asyncio
async def test_a_found_hook_runner_replaces_the_configured_one(workspace):
    config = UserConfig(pre_commit=True, prek=False)
    app = make_app(InitDraft(analysis=existing_project(workspace)), config)
    async with app.run_test(size=(110, 55)) as pilot:
        await settle(pilot)
        pre_commit = app.screen.query_one("#tool-pre_commit", RadioButton)
        assert not pre_commit.value
        assert "off · Prek found" in pre_commit.label.plain
        assert app.screen.query_one("#tool-prek", RadioButton).value


@pytest.mark.asyncio
async def test_a_template_keeps_its_opinions_beside_found_tools(workspace):
    (workspace / "justfile").write_text("test:\n")
    draft = template_draft(
        workspace / "template.toml",
        'name = "Orbit"\ndescription = "Orbit"\njust = false\nmypy = true\n',
        analysis=analyze_project(workspace),
    )
    app = make_app(draft, UserConfig(mypy=False))
    async with app.run_test(size=(110, 55)) as pilot:
        await settle(pilot)
        just = app.screen.query_one("#tool-just", Checkbox)
        mypy = app.screen.query_one("#tool-mypy", Checkbox)
        assert just.value
        assert "found · justfile" in just.label.plain
        assert mypy.value
        assert "from template" in mypy.label.plain


@pytest.mark.asyncio
async def test_a_recorded_recipe_ignores_analysis(workspace):
    config = UserConfig(just=False)
    draft = InitDraft(
        existing_recipe=establish_recipe(config),
        analysis=existing_project(workspace),
    )
    app = make_app(draft, config)
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        assert "Existing project" not in plain(app, "#subtitle")
        assert not app.screen.query_one("#tool-just", Checkbox).value
        assert not app.screen.query("#analysis-notes")


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
async def test_invalid_minimum_python_shows_actionable_preview_error():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        field = app.screen.query_one("#meta-minimum_python", Input)
        field.focus()
        field.value = "invalid"
        await pilot.press("enter")
        await settle(pilot)
        summary = plain(app, "#preview-summary")
        assert "Invalid Python version: 'invalid'." in summary
        assert "Write the Python version as major.minor, such as '3.13'." in summary
        field.focus()
        field.value = "2.7"
        await pilot.press("enter")
        await settle(pilot)
        summary = plain(app, "#preview-summary")
        assert "Unsupported Python version: '2.7'." in summary
        assert "Protostar scaffolds Python 3 projects" in summary


@pytest.mark.asyncio
async def test_any_python_3_minimum_or_none_is_accepted():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        continue_btn = app.screen.query_one("#continue", Button)
        field = app.screen.query_one("#meta-minimum_python", Input)
        # Clearing the field falls back to the default, like an old or new
        # Python, is never an error.
        for value in ("3.7", "3.15", ""):
            field.focus()
            field.value = value
            await pilot.press("enter")
            await settle(pilot)
            assert "Invalid" not in plain(app, "#preview-summary")
            assert not continue_btn.disabled


@pytest.mark.asyncio
async def test_invalid_github_username_shows_actionable_preview_error():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        field = app.screen.query_one("#meta-github_username", Input)
        field.focus()
        field.value = "@octocat"
        await pilot.press("enter")
        await settle(pilot)
        summary = plain(app, "#preview-summary")
        assert "Invalid GitHub username: '@octocat'." in summary
        assert "Drop the leading '@': use 'octocat'." in summary


@pytest.mark.asyncio
async def test_invalid_docker_port_shows_actionable_preview_error():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        app.screen.query_one("#docker", Checkbox).value = True
        await settle(pilot)
        field = app.screen.query_one("#meta-docker_port", Input)
        field.focus()
        field.value = "notaport"
        await pilot.press("enter")
        await settle(pilot)
        summary = plain(app, "#preview-summary")
        assert "Invalid container port: 'notaport'." in summary
        assert "Container port must be a whole number, such as '8000'." in summary


@pytest.mark.asyncio
async def test_fatal_recipe_issues_block_continue_and_ctrl_s():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        continue_btn = app.screen.query_one("#continue", Button)
        assert not continue_btn.disabled

        field = app.screen.query_one("#meta-minimum_python", Input)
        field.focus()
        field.value = "invalid"
        await pilot.press("enter")
        await settle(pilot)

        assert continue_btn.disabled
        await pilot.press("ctrl+s")
        await settle(pilot)
        assert isinstance(app.screen, RecipeScreen)

        # Fix the field and verify Continue is re-enabled and ctrl+s works
        field.focus()
        field.value = "3.13"
        await pilot.press("enter")
        await settle(pilot)

        assert not continue_btn.disabled
        await pilot.press("ctrl+s")
        await settle(pilot)
        assert isinstance(app.screen, ReviewScreen)


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


@pytest.mark.asyncio
async def test_variables_step_opens_on_a_flagged_value(tmp_path):
    token = github_token()
    draft = template_draft(
        tmp_path / "t.toml",
        '[files]\n"custom.txt" = "<% ORG %>"\n',
        variables=(("ORG", token),),
    )
    app = DecisionApp(VariablesScreen(draft, UserConfig(), flagged=("ORG",)))
    async with app.run_test(size=(110, 30)) as pilot:
        await settle(pilot)
        screen = app.screen
        assert "Values look like credentials" in plain(app, "#title")
        assert app.focused is screen.query_one("#var-ORG", Input)
        assert "gitleaks rule github-pat" in plain(app, "#var-ORG-error")
        # A flagged value stays out of the preview until it is settled.
        assert "Waiting for values: ORG" in plain(app, "#preview-summary")
        allow = screen.query_one("#var-ORG-allow", Checkbox)
        assert allow.display
        await pilot.press("tab", "space")
        await settle(pilot)
        assert allow.value
        await pilot.press("ctrl+s")
    result = app.return_value
    assert result is not None
    assert dict(result.variables) == {"ORG": token}
    assert result.allowed_secrets == frozenset({"ORG"})


@pytest.mark.asyncio
async def test_enter_through_the_last_field_reaches_continue(tmp_path):
    draft = template_draft(
        tmp_path / "t.toml", '[files]\n"custom.txt" = "<% REGION %> <% TIER %>"\n'
    )
    app = DecisionApp(VariablesScreen(draft, UserConfig()))
    async with app.run_test(size=(110, 30)) as pilot:
        await settle(pilot)
        await pilot.press(*"eu", "enter", *"gold", "enter")
        assert app.focused is app.screen.query_one("#continue", Button)
        await pilot.press("enter")
    result = app.return_value
    assert result is not None
    assert dict(result.variables) == {"REGION": "eu", "TIER": "gold"}


def test_editor_snapshot(snap_compare, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = make_app(config=UserConfig(author_name="Ada Lovelace"))
    assert snap_compare(app, terminal_size=(110, 50), run_before=settle)


def test_existing_project_snapshot(snap_compare, monkeypatch, workspace):
    monkeypatch.delenv("NO_COLOR", raising=False)
    config = UserConfig(just=False, prek=False, pre_commit=False)
    app = make_app(InitDraft(analysis=existing_project(workspace)), config)

    async def tools(pilot):
        # A slow runner can plan the preview, or re-plan it after the scroll,
        # later than one settle; capture only once both have finished.
        for _ in range(2):
            await settle(pilot)
            while "Planning" in plain(pilot.app, "#preview-summary"):
                await pilot.pause(0.05)
            notes = pilot.app.screen.query_one("#analysis-notes")
            notes.scroll_visible(top=True, animate=False, immediate=True)
        await settle(pilot)

    assert snap_compare(app, terminal_size=(110, 50), run_before=tools)


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
        'name = "Orbit"\n[files]\n"<% REGION %>/app.txt" = "<% TIER %>"\n'
        '[variables.TIER]\ndescription = "Service tier: free or gold"\n',
        variables=(("REGION", "eu"),),
    )
    app = DecisionApp(VariablesScreen(draft, UserConfig()))
    assert snap_compare(app, terminal_size=(110, 30), run_before=settle)


REMOTE_TASK = ("uv", "run", "nbdime", "config-git", "--enable")


def make_review(draft=None, config=None):
    return DecisionApp(ReviewScreen(draft or InitDraft(), config or UserConfig()))


def untrusted_draft(path):
    """An external template that is not trusted, with its own post-install task."""
    draft = template_draft(
        path,
        f'name = "Remote"\npost_install_tasks = [{list(REMOTE_TASK)!r}]\n'.replace(
            "'", '"'
        )
        + '[files]\n"notes.txt" = "Launch checklist\\n"\n',
    )
    return replace(draft, template=replace(draft.template, is_external=True))


@pytest.fixture
def collisions(workspace):
    """An unmanaged justfile, pre-commit config, and pyproject.toml already exist."""
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "existing"\n', newline="\n"
    )
    (workspace / "justfile").write_text("default:\n    echo hi\n", newline="\n")
    (workspace / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: mine\n"
        "        name: mine\n        entry: mine\n        language: system\n",
        newline="\n",
    )
    return UserConfig(ci=True, just=True, prek=True)


def file_nodes(app):
    """Each planned path's tree node, by path."""
    nodes, stack = {}, [app.screen.query_one("#files", Tree).root]
    while stack:
        node = stack.pop()
        stack.extend(node.children)
        if node.data is not None:
            nodes[node.data.path] = node
    return nodes


async def highlight(pilot, path):
    pilot.app.screen.query_one("#files", Tree).move_cursor(file_nodes(pilot.app)[path])
    await pilot.pause()


def execute_decision(decision, config, mocker):
    """Runs the CLI's execution path for a decision; the executor applies nothing."""
    execute = mocker.patch.object(SystemExecutor, "execute", autospec=True)
    modules, request = resolve_init(decision.draft, config)
    ui._run_engine(Orchestrator(modules, config, request=request), request, decision)
    return execute.call_args.args[0]


@pytest.mark.asyncio
async def test_review_marks_collisions_and_shows_first_batch_diffs(collisions):
    app = make_review(config=collisions)
    async with app.run_test(size=(120, 45)) as pilot:
        await settle(pilot)
        assert {path: node.label.plain for path, node in file_nodes(app).items()} == {
            ".github/workflows": "workflows/  new",
            ".github/workflows/ci.yml": "ci.yml  new",
            ".gitignore": ".gitignore  after setup",
            ".pre-commit-config.yaml": ".pre-commit-config.yaml  modified",
            "justfile": "justfile  conflict",
            # No command creates it, so its merge shows before any runs.
            "pyproject.toml": "pyproject.toml  modified",
        }
        assert "Already in the workspace: .pre-commit-config.yaml, justfile, " in (
            plain(app, "#collision-note")
        )
        await highlight(pilot, ".pre-commit-config.yaml")
        diff = plain(app, "#diff")
        assert "+++ b/.pre-commit-config.yaml" in diff
        assert "\n   - repo: local\n" in diff
        assert "+    repo: https://github.com/gitleaks/gitleaks" in diff
        await highlight(pilot, "justfile")
        diff = plain(app, "#diff")
        assert "Whole file  It was already there before Protostar managed it." in diff
        assert "--- yours\n+++ update\n" in diff
        assert "-    echo hi" in diff
        await highlight(pilot, "pyproject.toml")
        diff = plain(app, "#diff")
        assert "Changes to content you already have." in diff
        assert "adds      dependencies.dev ruff" in diff
        assert "adds      tool\n" in diff
        assert "+++ b/pyproject.toml" in diff
        await highlight(pilot, ".gitignore")
        assert "so it can't be shown yet" in plain(app, "#diff")

        await highlight(pilot, "justfile")
        await pilot.click("#strategy-overwrite")
        await settle(pilot)
        assert file_nodes(app)["justfile"].label.plain == "justfile  modified"
        # The highlighted file stays in view while the batch is re-prepared.
        diff = plain(app, "#diff")
        assert "-    echo hi" in diff
        assert "+    @just --list" in diff


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "label", "choice"),
    [
        ("k", "justfile  existing · resolved", ResolutionChoice.LOCAL),
        ("u", "justfile  modified · resolved", ResolutionChoice.DESIRED),
    ],
)
async def test_review_settles_a_conflict_and_execution_applies_the_choice(
    collisions, mocker, key, label, choice
):
    app = make_review(config=collisions)
    async with app.run_test(size=(120, 45)) as pilot:
        await settle(pilot)
        await highlight(pilot, ".gitignore")
        assert not app.screen.query_one("#conflict-choice").display
        # A key whose control is hidden does nothing.
        await pilot.press("k")
        assert not app.screen.choices
        await highlight(pilot, "justfile")
        assert app.screen.query_one("#conflict-choice").display
        assert app.screen.query_one("#resolve-both", RadioButton).disabled
        await pilot.press(key)
        await settle(pilot)
        assert file_nodes(app)["justfile"].label.plain == label
        assert "Resolved the file: " in plain(app, "#diff")
        lit = [b.id for b in app.screen.query("#resolution RadioButton") if b.value]
        assert lit == [f"resolve-{choice.value}"]
        await pilot.press("a")
    decision = app.return_value
    (conflict_id, chosen), *_ = decision.resolutions.items()
    assert len(decision.resolutions) == 1
    assert chosen is choice
    executor = execute_decision(decision, collisions, mocker)
    assert executor.reviewed_resolutions == {conflict_id: choice}


@pytest.mark.asyncio
async def test_changes_to_an_existing_file_can_be_kept_out(collisions, mocker):
    app = make_review(config=collisions)
    async with app.run_test(size=(120, 45)) as pilot:
        await settle(pilot)
        await highlight(pilot, "pyproject.toml")
        heading = app.screen.query_one("#conflict-choice .choice-heading")
        assert heading.label == "Changes to your file"
        lit = [b.id for b in app.screen.query("#resolution RadioButton") if b.value]
        # A proposal applies unless kept out, so it is never left open.
        assert lit == ["resolve-desired"]
        assert app.screen.query_one("#resolve-open", RadioButton).disabled
        await pilot.press("x")
        assert not app.screen.choices
        await pilot.press("k")
        await settle(pilot)
        label = file_nodes(app)["pyproject.toml"].label.plain
        # Every change kept out, the file is left as it is.
        assert label.startswith("pyproject.toml  existing · ")
        assert label.endswith(" kept out")
        assert "kept out  dependencies.dev ruff" in plain(app, "#diff")
        await pilot.press("a")
    decision = app.return_value
    proposals = [
        c for c in decision.resolutions.values() if c is ResolutionChoice.LOCAL
    ]
    assert proposals
    executor = execute_decision(decision, collisions, mocker)
    assert executor.reviewed_resolutions == decision.resolutions


@pytest.mark.asyncio
async def test_keep_all_mine_keeps_every_existing_file_as_it_is(collisions):
    app = make_review(config=collisions)
    async with app.run_test(size=(120, 45)) as pilot:
        await settle(pilot)
        assert "changes to your files" in plain(app, "#subtitle")
        await pilot.press("K")
        await settle(pilot)
        labels_by_path = {
            path: node.label.plain for path, node in file_nodes(app).items()
        }
        assert labels_by_path["justfile"] == "justfile  existing · resolved"
        assert labels_by_path["pyproject.toml"].endswith("kept out")
        edits = {edit.path for edit in app.screen.review.prepared.edits}
        # Nothing Protostar writes before a command touches an existing file.
        assert not edits & {"justfile", ".pre-commit-config.yaml", "pyproject.toml"}
        await pilot.press("a")
    decision = app.return_value
    assert decision.resolutions
    assert set(decision.resolutions.values()) == {ResolutionChoice.LOCAL}


@pytest.mark.asyncio
async def test_leaving_a_conflict_open_drops_its_choice(collisions):
    app = make_review(config=collisions)
    async with app.run_test(size=(120, 45)) as pilot:
        await settle(pilot)
        await highlight(pilot, "justfile")
        await pilot.press("k")
        await settle(pilot)
        await pilot.press("x")
        await settle(pilot)
        assert file_nodes(app)["justfile"].label.plain == "justfile  conflict"
        await pilot.press("a")
    assert app.return_value.resolutions == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", list(CollisionStrategy))
async def test_the_chosen_strategy_reaches_execution(collisions, mocker, strategy):
    app = make_review(config=collisions)
    async with app.run_test(size=(120, 45)) as pilot:
        await settle(pilot)
        await pilot.press(strategy.value[0])
        await settle(pilot)
        await pilot.press("a")
    decision = app.return_value
    assert decision.draft.collision_strategy is strategy
    executor = execute_decision(decision, collisions, mocker)
    assert executor.manifest.collision_strategy is strategy


@pytest.mark.asyncio
async def test_trust_gate_blocks_until_the_commands_are_confirmed(tmp_path, mocker):
    app = make_review(untrusted_draft(tmp_path / "t.toml"))
    async with app.run_test(size=(120, 50)) as pilot:
        await settle(pilot)
        note = plain(app, "#trust-note")
        assert "\n  git init" in note
        assert "\n  uv run nbdime config-git --enable" in note
        apply_button = app.screen.query_one("#apply", Button)
        assert apply_button.disabled
        await pilot.click("#trust")
        assert not apply_button.disabled
        await pilot.click("#trust")
        assert apply_button.disabled
        await pilot.click("#apply")
        assert app.is_running
        await pilot.click("#trust")
        await pilot.click("#apply")
    decision = app.return_value
    commands = decision.confirmed_commands
    assert commands[0] == ("git", "init")
    assert commands[-1] == REMOTE_TASK
    # The confirmation is what lets the CLI run exactly these commands.
    executor = execute_decision(decision, UserConfig(), mocker)
    assert [tuple(task.command) for task in executor.manifest.tasks.post_install_tasks][
        -1
    ] == REMOTE_TASK


@pytest.mark.asyncio
async def test_review_and_execution_share_one_hook_snapshot(collisions, mocker):
    snapshot = tuple(
        ResolvedHookRevision(hook, "v9.9.9", PinProvenance.REGISTRY)
        for hook in RemoteHook
    )
    take = mocker.patch(
        "protostar.cli.tui.review.screen.resolve_hook_revisions",
        return_value=snapshot,
    )
    fresh = mocker.patch("protostar.executor.resolve_hook_revisions")
    app = make_review(config=collisions)
    async with app.run_test(size=(120, 45)) as pilot:
        await settle(pilot)
        await highlight(pilot, ".pre-commit-config.yaml")
        assert "+  - rev: v9.9.9" in plain(app, "#diff")
        # Re-preparing for another strategy reuses the snapshot.
        await pilot.click("#strategy-overwrite")
        await settle(pilot)
        await pilot.click("#apply")
    take.assert_called_once()
    decision = app.return_value
    assert decision.hook_revisions is snapshot
    executor = execute_decision(decision, collisions, mocker)
    assert executor.hook_revisions is snapshot
    fresh.assert_not_called()


@pytest.mark.asyncio
async def test_back_returns_to_the_editor_with_its_choices():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        app.screen.query_one("#tool-just", Checkbox).value = True
        await settle(pilot)
        await pilot.click("#continue")
        await settle(pilot)
        assert "justfile" in file_nodes(app)
        await pilot.press("escape")
        assert isinstance(app.screen, RecipeScreen)
        assert app.screen.query_one("#tool-just", Checkbox).value
        await apply(pilot)
    assert dict(app.return_value.draft.tool_choices)[Tool.JUST]


@pytest.mark.asyncio
async def test_escape_cancels_a_review_with_no_editor_behind_it(collisions):
    app = make_review(config=collisions)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert labels(app) == {
            "cancel": "Cancel  esc",
            "keep-all": "Keep all mine  K",
            "apply": "Apply  a",
        }
        await pilot.press("escape")
        assert isinstance(app.screen, LeaveScreen)
        await pilot.press("enter")
        assert not app.is_running
    assert app.return_value is None


@pytest.mark.asyncio
async def test_review_keys_scroll_the_diff_from_the_file_tree(collisions):
    app = make_review(config=collisions)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(pilot)
        tree = app.screen.query_one("#files", Tree)
        assert app.focused is tree
        assert legend(app) == {"Move", "Scroll diff", "Next", "Keybindings"}
        await highlight(pilot, ".pre-commit-config.yaml")
        pane = app.screen.query_one("#diff-pane")
        assert pane.max_scroll_y > 0
        await pilot.press("pagedown")
        assert pane.scroll_y > 0
        await pilot.press("pageup")
        assert pane.scroll_y == 0
        assert app.focused is tree
        # A key whose control is hidden does nothing.
        await pilot.press("t")
        assert not app.screen.query_one("#trust", Checkbox).value


@pytest.mark.asyncio
async def test_review_keys_confirm_trust_and_apply(tmp_path):
    app = make_review(untrusted_draft(tmp_path / "t.toml"))
    async with app.run_test(size=(120, 50)) as pilot:
        await settle(pilot)
        await pilot.press("a")
        assert app.is_running
        await pilot.press("t", "a")
    assert app.return_value.confirmed_commands[-1] == REMOTE_TASK


def record_template(workspace):
    """Record a built-in template the drafts under test are not."""
    recorded = TemplateReference(TemplateOrigin.BUILT_IN, "api", "a" * 64)
    (workspace / "protostar.lock").write_text(
        serialize_state(SyncState("0.9.0", recorded))
    )


@pytest.mark.asyncio
async def test_a_review_that_never_prepares_hands_its_error_to_the_cli(
    tmp_path, workspace
):
    """No choice on the review can fix it, so the app leaves with the error."""
    record_template(workspace)
    app = make_review(template_draft(tmp_path / "t.toml", "[files]\n"))
    async with app.run_test() as pilot:
        await settle(pilot)
        assert not app.is_running
    assert app.return_value is None
    assert app.failure is not None
    assert "differs" in str(app.failure)


def test_decide_raises_the_error_a_screen_left_with(mocker):
    from textual.screen import Screen

    app: DecisionApp[None] = DecisionApp(Screen())
    mocker.patch.object(app, "run", return_value=None)
    assert app.decide() is None
    app.failure = ConfigurationError("Unfixable.")
    with pytest.raises(ConfigurationError, match="Unfixable"):
        app.decide()


@pytest.mark.asyncio
async def test_a_review_with_an_editor_behind_it_shows_the_error_and_hint(
    tmp_path, workspace
):
    """Going back to the editor can fix it, so the review stays with the hint."""
    record_template(workspace)
    draft = template_draft(tmp_path / "t.toml", "[files]\n")
    app = DecisionApp(ReviewScreen(draft, UserConfig(), can_go_back=True))
    async with app.run_test(size=(160, 40)) as pilot:
        await settle(pilot)
        assert app.is_running
        subtitle = plain(app, "#subtitle")
        assert "differs" in subtitle
        assert "Select the same template source" in subtitle
        assert app.screen.query_one("#apply", Button).disabled


@pytest.mark.asyncio
async def test_q_asks_before_leaving_a_review_with_an_editor_behind_it():
    app = make_app()
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        await pilot.press("ctrl+s")
        await settle(pilot)
        assert labels(app) == {
            "back": "Back  esc",
            "cancel": "Cancel  q",
            "apply": "Apply  a",
        }
        await pilot.press("q")
        assert isinstance(app.screen, LeaveScreen)
        await pilot.press("escape")
        assert isinstance(app.screen, ReviewScreen)


def test_review_snapshot(snap_compare, monkeypatch, mocker, collisions):
    monkeypatch.delenv("NO_COLOR", raising=False)
    # Fixed pins: fallback revisions move with every registry bump.
    mocker.patch(
        "protostar.cli.tui.review.screen.resolve_hook_revisions",
        return_value=tuple(
            ResolvedHookRevision(hook, "v1.0.0", PinProvenance.REGISTRY)
            for hook in RemoteHook
        ),
    )
    app = make_review(config=UserConfig(just=True, prek=True))
    assert snap_compare(app, terminal_size=(110, 45), run_before=settle)


def test_trust_gate_snapshot(snap_compare, monkeypatch, tmp_path):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = make_review(untrusted_draft(tmp_path / "t.toml"))
    assert snap_compare(app, terminal_size=(110, 45), run_before=settle)


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


def test_benchmark_exits_after_first_frame(mocker, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROTOSTAR_BENCHMARK_WIZARD", "1")
    monkeypatch.setattr(sys, "argv", ["protostar", "init"])
    mocker.patch.object(UserConfig, "load", return_value=UserConfig())
    launch = mocker.patch.object(parser, "edit_recipe", return_value=None)
    execute = mocker.patch.object(ui, "_run_engine")
    with pytest.raises(SystemExit) as exc:
        parser.intercept_interactive_wizards(mocker.Mock())
    assert exc.value.code == 0
    assert launch.call_args.kwargs["exit_after_first_frame"] is True
    execute.assert_not_called()


@pytest.mark.asyncio
async def test_app_exits_after_first_frame():
    from textual.screen import Screen

    app: DecisionApp[None] = DecisionApp(Screen(), exit_after_first_frame=True)
    async with app.run_test() as pilot:
        await pilot.pause()
    assert app.return_value is None


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


def test_the_wizard_hands_the_editor_its_analysis(mocker, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "justfile").write_text("test:\n")
    monkeypatch.setattr(sys, "argv", ["protostar"])
    mocker.patch.object(parser, "is_interactive", return_value=True)
    mocker.patch.object(UserConfig, "load", return_value=UserConfig())
    edit = mocker.patch.object(parser, "edit_recipe", return_value=None)
    with pytest.raises(ExecutionAbortedError):
        parser.intercept_interactive_wizards(mocker.Mock())
    draft = edit.call_args.args[0]
    assert draft.analysis == analyze_project(tmp_path)
    assert draft.analysis.existing


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


def test_review_summary_is_cp1252_safe(mocker):
    from protostar.init_draft import InitDecision

    output = io.BytesIO()
    stream = io.TextIOWrapper(output, encoding="cp1252", errors="strict")
    mocker.patch.object(ui, "console", Console(file=stream, force_terminal=False))
    ui.print_review_summary(
        InitDecision(
            InitDraft(
                collision_strategy=CollisionStrategy.MERGE,
                allowed_secrets=frozenset({"ORG", "BETA"}),
            ),
            (),
            (("git", "init"), ("uv", "run", "setup")),
        )
    )
    ui.print_review_summary(InitDecision(InitDraft(), ()))
    stream.flush()
    heading, *rows = [
        line.rstrip() for line in output.getvalue().decode("cp1252").splitlines()
    ]
    # cp1252 cannot encode box drawing, so the heading's rule falls back to dashes.
    assert heading.startswith("REVIEW -")
    assert rows == [
        "  Existing files  merge",
        "  Commands        2 confirmed from an untrusted template",
        "  Kept values     flagged as credentials: BETA, ORG",
    ]


def test_credential_name_warning_is_cp1252_safe(mocker):
    output = io.BytesIO()
    stream = io.TextIOWrapper(output, encoding="cp1252", errors="strict")
    console = Console(file=stream, force_terminal=False, width=200)
    mocker.patch.object(ui, "console", console)
    mocker.patch.object(ui, "is_json_mode", False)
    ui.warn_credential_names(("[red]api_token[/red]",))
    stream.flush()
    assert (
        output.getvalue()
        .decode("cp1252")
        .startswith(
            "! Template variables named like credentials: [red]api_token[/red]."
        )
    )


def test_line_conflicts_name_the_kept_lines():
    from protostar.cli.tui.review.screen import Change, Entry, describe
    from protostar.merge import ConflictReason, LineSpan, MergeConflict, MergeLocation

    def conflict(lines):
        return MergeConflict(
            MergeLocation("justfile", lines=lines), ConflictReason.DIVERGED
        )

    entry = Entry(
        "justfile",
        Change.CONFLICT,
        conflicts=(conflict(LineSpan(5, 3)), conflict(LineSpan(9, 0))),
    )
    console = Console(file=io.StringIO(), width=80, record=True)
    console.print(describe(entry))

    assert console.export_text().splitlines() == [
        "Lines 5-7: your edit is kept (diverged).",
        "After line 9: your edit is kept (diverged).",
    ]


def test_recipe_import_defers_pygments_until_code_is_rendered(tmp_path):
    probe = """
import sys
from protostar.cli.tui.recipe.screen import RecipeScreen
from protostar.cli.tui.code import CodeSource, source_text
assert not any(name == "pygments" or name.startswith("pygments.") for name in sys.modules)
rendered = source_text(CodeSource('name = "orbit"', 'pyproject.toml'))
assert rendered.plain == 'name = "orbit"'
assert rendered.spans
assert "pygments.lexers" in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


OPTIONS_TEMPLATE = """
[options.compose]
description = "Ship a compose.yaml."
default = false

[options.database]
choices = ["none", "postgres", "sqlite"]
default = "none"

[[optional]]
requires = "compose"
files = ["compose.yaml"]

[[optional]]
requires = "database=postgres"
dependencies = ["psycopg"]

[files]
"compose.yaml" = "services: {}\\n"
"""


@pytest.mark.asyncio
async def test_options_are_chosen_from_the_keyboard(tmp_path):
    draft = template_draft(
        tmp_path / "t.toml",
        OPTIONS_TEMPLATE,
        option_overrides=(("database", "sqlite"),),
    )
    app = make_app(draft)
    async with app.run_test(size=(110, 45)) as pilot:
        await settle(pilot)
        screen = app.screen
        text = "\n".join(
            str(widget.content) for widget in screen.query("OptionFields Static")
        )
        assert "Ship a compose.yaml." in text
        choice = screen.query_one("#option-database", RadioSet)
        # A value the flags chose starts selected.
        assert choice.pressed_button.id == "option-database-2"

        screen.query_one("#option-compose").focus()
        await pilot.press("space")
        await pilot.press("down")
        assert app.focused is choice
        await pilot.press("down", "space")
        await settle(pilot)

        assert dict(screen._current_draft().option_choices or ()) == {
            "compose": True,
            "database": "postgres",
        }
        await apply(pilot)
        await settle(pilot)
    decision = app.return_value
    assert decision is not None
    _modules, request = resolve_init(decision.draft, UserConfig())
    # Only the values away from the template's defaults are recorded.
    assert request.recipe is not None
    assert request.recipe.options == (("compose", True), ("database", "postgres"))


def test_tui_does_not_use_broken_border_titles() -> None:
    """Ensure no widget or style breaks borders with border_title or border_subtitle."""
    tui_root = Path(__file__).parents[1] / "src" / "protostar" / "cli" / "tui"
    for py_path in tui_root.rglob("*.py"):
        text = py_path.read_text()
        assert "border_title" not in text, f"{py_path} sets border_title"
        assert "border_subtitle" not in text, f"{py_path} sets border_subtitle"

    tcss_text = (tui_root / "protostar.tcss").read_text()
    assert "border-title" not in tcss_text, (
        "protostar.tcss contains border-title styles"
    )
    assert "border-subtitle" not in tcss_text, (
        "protostar.tcss contains border-subtitle styles"
    )
