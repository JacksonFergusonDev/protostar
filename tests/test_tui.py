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
    RadioSet,
    Select,
    SelectionList,
    Static,
    Tree,
)
from textual.worker import WorkerCancelled

from protostar.cli import parser, ui
from protostar.cli.tui.app import DecisionApp
from protostar.cli.tui.keys import KeysScreen, LeaveScreen
from protostar.cli.tui.recipe.screen import RecipeScreen, _TemplateChoice
from protostar.cli.tui.recipe.variables import VariablesScreen
from protostar.cli.tui.review.screen import ReviewScreen
from protostar.config import TemplateAliasConfig, TemplateSource, UserConfig
from protostar.errors import ExecutionAbortedError
from protostar.executor import SystemExecutor
from protostar.init_draft import DraftTemplate, InitDraft, resolve_init
from protostar.manifest import CollisionStrategy
from protostar.orchestrator import Orchestrator
from protostar.recipe import Tool, establish_recipe
from protostar.registry import PinProvenance, RemoteHook, ResolvedHookRevision
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
        await apply(pilot)
    choices = dict(app.return_value.draft.tool_choices)
    assert choices[Tool.PREK]
    assert not choices[Tool.PRE_COMMIT]
    assert not choices[Tool.READTHEDOCS]


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
    """Each button's label, by id."""
    return {button.id: str(button.label) for button in app.screen.query(Button)}


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
        assert legend(app) == {"Open", "Move", "Next", "Keys"}
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
        assert legend(app) == {"Toggle", "Move", "Next", "Keys"}
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

        screen.query_one("#tool-agents").focus()
        await pilot.press("down")
        assert app.focused is choice
        assert highlighted() == ["none-0"]
        assert legend(app) == {"Move", "Choose", "Next", "Keys"}
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
        assert legend(app) == {"Move", "Accept", "Next", "Keys"}
        await pilot.press(*"Orbit", "enter")
        assert app.focused.id == "meta-license"
        await settle(pilot)
        await apply(pilot)
    draft = app.return_value.draft
    assert draft.docker
    assert dict(draft.tool_choices)[Tool.PREK]
    assert dict(draft.metadata)["description"] == "Orbit"


@pytest.mark.asyncio
async def test_buttons_show_their_keys_and_f1_lists_them_all():
    app = make_app()
    async with app.run_test() as pilot:
        await settle(pilot)
        assert labels(app) == {"cancel": "Cancel  esc", "continue": "Continue  ^s"}
        await pilot.press("f1")
        assert isinstance(app.screen, KeysScreen)
        assert ("^s", "Continue") in app.screen.rows
        await pilot.press("escape")
        assert isinstance(app.screen, RecipeScreen)


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
        assert "not found" in plain(app, "#template-status")
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
            "pyproject.toml": "pyproject.toml  existing",
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
        assert "Your version of the file is kept (unowned)." in plain(app, "#diff")
        await highlight(pilot, "pyproject.toml")
        assert "Nothing is written to it before setup" in plain(app, "#diff")
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
        assert labels(app) == {"cancel": "Cancel  esc", "apply": "Apply  a"}
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
        assert legend(app) == {"Move", "Scroll diff", "Next", "Keys"}
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
