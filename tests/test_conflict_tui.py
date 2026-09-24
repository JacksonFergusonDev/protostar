"""The sync conflict screen: choosing sides by key, previews, and the CLI hand-off."""

import argparse
import contextlib
import io
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from rich.console import Console
from textual.widgets import RadioButton, Static, Tree
from textual.worker import WorkerCancelled

from protostar.cli import main, ui
from protostar.cli.tui.app import DecisionApp
from protostar.cli.tui.conflicts.screen import ConflictScreen
from protostar.cli.tui.conflicts.sides import side_text
from protostar.cli.tui.keys import KeysScreen, LeaveScreen
from protostar.config import TemplateSource, UserConfig
from protostar.executor import SystemExecutor
from protostar.lifecycle import prepare_project
from protostar.manifest import EnvironmentManifest
from protostar.merge import (
    MISSING,
    ConflictReason,
    ConflictSides,
    MergeConflict,
    MergeLocation,
    ResolutionChoice,
)
from protostar.recipe import RecipeIntent, Tool, establish_recipe

RENOVATE = ".github/renovate.json"
NOTES = "notes.txt"
LOCAL, DESIRED, BOTH = ResolutionChoice


def revision(value):
    return (
        f"[files]\n\"{RENOVATE}\" = '{json.dumps({'value': value})}'\n"
        f'[appends."{NOTES}".managed]\ncontent = "{value}"\n'
    )


@pytest.fixture
def conflicted(tmp_path, monkeypatch, mocker):
    """A synced project whose renovate value and notes line both conflict."""
    project = tmp_path / "orbit"
    project.mkdir()
    monkeypatch.chdir(project)
    source = tmp_path / "source.toml"
    source.write_text(revision("original"))
    blueprint = TemplateSource.load(str(source)).render({})
    recipe = establish_recipe(UserConfig(), RecipeIntent(reference=blueprint.reference))
    recipe = replace(recipe, fallback=tuple((tool, False) for tool in Tool))
    manifest = EnvironmentManifest(
        template_reference=blueprint.reference, recipe=recipe
    )
    manifest.filesystem.add_structured(
        "pyproject.toml", '[project]\nname = "orbit"\n', producer="seed"
    )
    executor = SystemExecutor(manifest, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    mocker.patch("protostar.lifecycle.resolve_hook_revisions", return_value=())
    mocker.patch("subprocess.run", side_effect=AssertionError("subprocess.run"))
    prepare_project().apply()
    Path(RENOVATE).write_text(json.dumps({"value": "mine"}))
    # LF on every platform: the sides are reported in the local newline style.
    Path(NOTES).write_text(
        Path(NOTES).read_text().replace("original", "mine"), newline="\n"
    )
    source.write_text(revision("remote"))
    return project


def make_app():
    return DecisionApp(ConflictScreen(prepare_project()))


async def settle(pilot):
    """Wait for the preview worker, including one a key press starts."""
    await pilot.pause()
    for _ in range(10):
        workers = list(pilot.app.workers)
        if not workers:
            break
        for worker in workers:
            with contextlib.suppress(WorkerCancelled):
                await worker.wait()
        await pilot.pause()
    await pilot.pause()


def plain(app, selector):
    console = Console(file=io.StringIO(), width=200, record=True, color_system=None)
    console.print(app.screen.query_one(selector, Static).content)
    return console.export_text()


def rows(app):
    """Each conflict row's label, in list order."""
    tree = app.screen.query_one("#conflicts", Tree)
    return [
        str(child.label)
        for file in tree.root.children
        for child in (file, *file.children)
    ]


def pressed(app):
    """The ids of the lit choice buttons."""
    return [b.id for b in app.screen.query("#choice RadioButton") if b.value]


async def select(pilot, file, *, conflict=True):
    """Highlight a file's row, or its first conflict."""
    tree = pilot.app.screen.query_one("#conflicts", Tree)
    node = next(n for n in tree.root.children if n.data.path == file)
    tree.move_cursor(node.children[0] if conflict else node)
    await pilot.pause()


@pytest.mark.asyncio
async def test_lists_conflicts_by_file_with_both_sides(conflicted):
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        assert rows(app) == [
            f"{RENOVATE}  1",
            "value  diverged  open",
            f"{NOTES}  1",
            "line 2  diverged  open",
        ]
        assert "2 conflicts · 0 resolved · 2 open" in plain(app, "#subtitle")
        await select(pilot, RENOVATE)
        assert plain(app, "#local").strip() == '{\n  "value": "mine"\n}'
        assert plain(app, "#desired").strip() == '{\n  "value": "remote"\n}'
        assert "The file stays as it is." in plain(app, "#result")
        await select(pilot, NOTES)
        assert plain(app, "#local").strip() == "mine"
        assert plain(app, "#desired").strip() == "remote"


@pytest.mark.asyncio
async def test_keys_choose_sides_and_apply_exits_with_the_choices(conflicted):
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await select(pilot, RENOVATE)
        # Structured values can't keep both, so b does nothing there.
        await pilot.press("b")
        assert "open" in rows(app)[1]
        await pilot.press("u")
        await settle(pilot)
        assert rows(app)[1] == "value  diverged  take update"
        assert '+{"value": "remote"}' in plain(app, "#result")
        await select(pilot, NOTES)
        await pilot.press("b")
        await settle(pilot)
        assert rows(app)[3] == "line 2  diverged  keep both"
        # Exactly one lamp is lit, though RadioSet re-presses one switched off.
        assert pressed(app) == ["choice-both"]
        assert "+remote" in plain(app, "#result")
        assert "2 resolved · 0 open" in plain(app, "#subtitle")
        await pilot.press("a")
    ids = {c.location.file: c.id for c in prepare_project().review.conflicts}
    assert app.return_value == {ids[RENOVATE]: DESIRED, ids[NOTES]: BOTH}


@pytest.mark.asyncio
async def test_a_file_row_settles_every_conflict_in_it_and_x_reopens(conflicted):
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await select(pilot, RENOVATE, conflict=False)
        await pilot.press("k")
        assert rows(app)[1] == "value  diverged  keep mine"
        assert pressed(app) == ["choice-local"]
        await pilot.press("x")
        assert rows(app)[1] == "value  diverged  open"
        assert pressed(app) == ["choice-open"]
        await pilot.press("n")
        cursor = app.screen.query_one("#conflicts", Tree).cursor_node
        assert cursor.data.conflict.location.file == RENOVATE
        await pilot.press("a")
    assert app.return_value == {}


@pytest.mark.asyncio
async def test_a_kept_edit_takes_the_update_only_from_its_own_row(conflicted):
    # Back at the recorded revision, both local edits are kept, not conflicts.
    (conflicted.parent / "source.toml").write_text(revision("original"))
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        assert rows(app) == [
            f"{RENOVATE}  1",
            "value  preserved  keep mine",
            f"{NOTES}  1",
            "whole file  preserved  keep mine",
        ]
        assert "2 kept edits" in plain(app, "#subtitle")
        # A file row never takes the update for a deliberate local edit.
        await select(pilot, RENOVATE, conflict=False)
        await pilot.press("u")
        assert rows(app)[1] == "value  preserved  keep mine"
        await select(pilot, RENOVATE)
        assert pressed(app) == ["choice-local"]
        assert app.screen.query_one("#choice-open", RadioButton).disabled
        assert "update is still Protostar's version" in plain(app, "#meaning")
        await pilot.press("u")
        await settle(pilot)
        assert rows(app)[1] == "value  preserved  take update"
        assert "2 kept edits (1 updated)" in plain(app, "#subtitle")
        assert '+{"value": "original"}' in plain(app, "#result")
        await pilot.press("a")
    kept = {c.location.file: c.id for c in prepare_project().review.preserved}
    assert app.return_value == {kept[RENOVATE]: DESIRED}


def test_the_screen_opens_for_proposals_but_not_for_kept_edits_alone(monkeypatch):
    from protostar.cli import reviews, ui
    from protostar.preparation import PreparedReview

    monkeypatch.setattr(reviews, "is_interactive", lambda: True)
    monkeypatch.setattr(ui, "is_json_mode", False)
    args = argparse.Namespace(dry_run=False, check=False, resolve=[])
    proposal = MergeConflict(
        MergeLocation("pyproject.toml", ("tool",)),
        ConflictReason.PROPOSED,
        ConflictSides(MISSING, MISSING, {"a": 1}),
    )
    kept = MergeConflict(MergeLocation("pyproject.toml"), ConflictReason.PRESERVED)

    def review(**decisions: object) -> PreparedReview:
        fields = {"conflicts": (), "proposals": (), "preserved": (), **decisions}
        return cast(PreparedReview, SimpleNamespace(**fields))

    assert reviews._asks(args, review(proposals=(proposal,)))
    assert not reviews._asks(args, review(preserved=(kept,)))


@pytest.mark.asyncio
async def test_choice_buttons_follow_the_highlighted_conflict(conflicted):
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await select(pilot, RENOVATE)
        both = app.screen.query_one("#choice-both", RadioButton)
        assert both.disabled
        await select(pilot, NOTES)
        assert not both.disabled
        choice = app.screen.query_one("#choice")
        leave = app.screen.query_one("#choice-open", RadioButton)
        assert leave.value
        choice.focus()
        await pilot.press("down")
        # Moving never changes the choice; space does.
        assert leave.value
        assert "open" in rows(app)[3]
        await pilot.press("space")
        await settle(pilot)
        assert not leave.value
        assert "open" not in rows(app)[3]


@pytest.mark.asyncio
async def test_escape_asks_before_leaving_and_f1_lists_the_keys(conflicted):
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("f1")
        assert isinstance(app.screen, KeysScreen)
        await pilot.press("escape", "escape")
        assert isinstance(app.screen, LeaveScreen)
        assert app.screen.question == "Leave without syncing?"
        await pilot.press("enter")
    assert app.return_value is None


@pytest.mark.parametrize(
    ("file", "local", "desired"),
    [
        ("pyproject.toml", "[value]\na = 2", "value = 3"),
        (".github/codecov.yml", "value:\n  a: 2", "value: 3"),
        (
            ".vscode/settings.json",
            '{\n  "value": {\n    "a": 2\n  }\n}',
            '{\n  "value": 3\n}',
        ),
    ],
)
def test_structured_sides_render_in_their_files_format(file, local, desired):
    conflict = MergeConflict(
        MergeLocation(file, ("tool", "value")),
        ConflictReason.TYPE_MISMATCH,
        ConflictSides(1, {"a": 2}, 3),
    )
    assert str(side_text(conflict, "local")) == local
    assert str(side_text(conflict, "desired")) == desired


def test_missing_sides_say_what_happened():
    from protostar.merge import MISSING

    conflict = MergeConflict(
        MergeLocation(".readthedocs.yaml", ("build", "os")),
        ConflictReason.RETRACTED,
        ConflictSides("a", "b", MISSING),
    )
    assert str(side_text(conflict, "desired")) == "No longer generated."
    assert str(side_text(conflict, "local")) == "os: b"


def test_interactive_sync_applies_the_chosen_resolutions(
    conflicted, monkeypatch, mocker, capsys
):
    ids = {c.location.file: c.id for c in prepare_project().review.conflicts}
    launch = mocker.patch(
        "protostar.cli.reviews.resolve_conflicts",
        return_value={ids[RENOVATE]: LOCAL, ids[NOTES]: DESIRED},
    )
    monkeypatch.setattr("protostar.cli.reviews.is_interactive", lambda: True)
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "sync"])

    main()

    launch.assert_called_once()
    assert "2 conflicts resolved; 0 conflicts retained" in " ".join(
        capsys.readouterr().out.split()
    )
    assert json.loads(Path(RENOVATE).read_text()) == {"value": "mine"}
    assert "remote" in Path(NOTES).read_text()
    assert not prepare_project().review.pending


def test_cancelling_the_conflict_screen_writes_nothing(conflicted, monkeypatch, mocker):
    mocker.patch("protostar.cli.reviews.resolve_conflicts", return_value=None)
    monkeypatch.setattr("protostar.cli.reviews.is_interactive", lambda: True)
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "sync"])
    before = {p: p.read_bytes() for p in Path.cwd().rglob("*") if p.is_file()}

    with pytest.raises(SystemExit) as caught:
        main()

    assert caught.value.code != 0
    assert {p: p.read_bytes() for p in Path.cwd().rglob("*") if p.is_file()} == before


@pytest.mark.parametrize(
    "flags", [["--dry-run"], ["--check"], ["--json"], ["--resolve", f"{NOTES}=local"]]
)
def test_the_conflict_screen_never_opens_for_previews_scripts_or_flags(
    conflicted, monkeypatch, mocker, flags
):
    launch = mocker.patch("protostar.cli.reviews.resolve_conflicts")
    monkeypatch.setattr("protostar.cli.reviews.is_interactive", lambda: True)
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "sync", *flags])

    with contextlib.suppress(SystemExit):
        main()

    launch.assert_not_called()


def test_conflict_screen_snapshot(snap_compare, monkeypatch, conflicted):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert snap_compare(make_app(), terminal_size=(120, 36), run_before=settle)


def test_conflict_screen_narrow_snapshot(snap_compare, monkeypatch, conflicted):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert snap_compare(make_app(), terminal_size=(80, 36), run_before=settle)
