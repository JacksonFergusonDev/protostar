"""Sync, status, and diff show pending work as init's labelled tree."""

import io
import json
from dataclasses import replace
from pathlib import Path

import pytest
from rich.console import Console

from protostar.cli import main, ui
from protostar.cli.reviews import render_review
from protostar.config import TemplateSource, UserConfig
from protostar.executor import SystemExecutor
from protostar.lifecycle import inspect_project, prepare_project
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.migrations import MigrationOutcome, MigrationStep
from protostar.preparation import ExecutionPolicy, prepare_review
from protostar.recipe import RecipeIntent, Tool, establish_recipe

RENOVATE = ".github/renovate.json"


def source_text(value: str, *, extra: bool = False) -> str:
    """A template writing one managed JSON document, and a new file if ``extra``."""
    text = f"[files]\n\"{RENOVATE}\" = '{json.dumps({'value': value})}'\n"
    return text + ('"docs/new.md" = "# New\\n"\n' if extra else "")


@pytest.fixture
def project(tmp_path, monkeypatch, mocker):
    """A project initialized from ``source.toml``, which the test may change."""
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source.toml"
    source.write_text(source_text("original"))
    blueprint = TemplateSource.load(str(source)).render({})
    recipe = establish_recipe(UserConfig(), RecipeIntent(reference=blueprint.reference))
    recipe = replace(recipe, fallback=tuple((tool, False) for tool in Tool))
    manifest = EnvironmentManifest(
        template_reference=blueprint.reference, recipe=recipe
    )
    manifest.filesystem.add_file_injection(RENOVATE, json.dumps({"value": "original"}))
    manifest.filesystem.add_structured(
        "pyproject.toml", '[project]\nname = "demo"\n', producer="seed"
    )
    executor = SystemExecutor(manifest, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    mocker.patch.object(
        executor.process_runner, "run", side_effect=AssertionError("process")
    )
    executor.execute()
    mocker.patch("protostar.lifecycle.resolve_hook_revisions", return_value=())
    mocker.patch("subprocess.run", side_effect=AssertionError("subprocess.run"))
    mocker.patch("subprocess.Popen", side_effect=AssertionError("subprocess.Popen"))
    # Settle what init leaves to sync, so each test starts with nothing pending.
    prepare_project(check_executables=False).apply()
    assert not inspect_project().pending
    return source


@pytest.fixture
def output(monkeypatch):
    """Points the CLI console at a plain buffer; returns what it printed."""
    buffer = io.StringIO()
    monkeypatch.setattr(ui, "console", Console(file=buffer, width=100))
    monkeypatch.setattr(ui, "is_json_mode", False)
    return buffer.getvalue


def render(**flags):
    """Renders the current project's review as status or diff would."""
    project = prepare_project(check_executables=False)
    render_review(project.manifest, project.review, **flags)


def tree_lines(text: str) -> list[str]:
    """Returns the tree's rows: its root, folders, and labelled paths."""
    return [
        line.rstrip()
        for line in text.splitlines()
        if line.strip() and line.lstrip()[0] in "│├└."
    ]


def test_no_pending_work_has_no_tree(project, output):
    render()

    text = output()
    assert tree_lines(text) == []
    assert text.splitlines()[-1] == "No pending work."


def test_an_update_shows_in_the_tree_and_diff_follows_it(project, output):
    project.write_text(source_text("updated", extra=True))

    render(show_diffs=True)

    text = output()
    assert text.splitlines()[0] == "1 new · 1 modified"
    assert tree_lines(text) == [
        ". (Workspace Root)",
        "├── .github/",
        "│   └── renovate.json  modified",
        "└── docs/",
        "    └── new.md  new",
    ]
    # Unchanged managed files, such as pyproject.toml, stay out of the tree.
    assert "pyproject.toml" not in text
    assert "Accepted:" not in text
    assert text.index("new.md  new") < text.index("--- a/.github/renovate.json")
    assert '+{"value": "updated"}' in text
    assert "+++ b/docs/new.md" in text


def test_a_conflict_is_labelled_and_listed_with_its_id(project, output):
    Path(RENOVATE).write_text(json.dumps({"value": "local"}))
    project.write_text(source_text("remote"))

    render()

    (conflict,) = inspect_project().conflicts
    text = output()
    assert text.splitlines()[0] == "1 conflict"
    assert "renovate.json  conflict" in text
    assert (
        f"Conflict {conflict.id}: {RENOVATE} value: diverged; "
        "resolve with local, desired."
    ) in text


def test_a_preserved_edit_is_marked_on_its_file(project, output):
    Path(RENOVATE).write_text(json.dumps({"value": "local"}))

    render()

    (item,) = inspect_project().preserved
    text = output()
    assert text.splitlines()[0] == "1 kept edit"
    assert tree_lines(text) == [
        ". (Workspace Root)",
        "└── .github/",
        "    └── renovate.json  existing · 1 kept edit",
    ]
    assert f"Preserved local edit {item.id}: {RENOVATE} value" in text
    assert text.rstrip().endswith("No pending work.")


def test_a_proposal_is_counted_and_listed(tmp_path, monkeypatch, output):
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "demo"\n')
    manifest = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    manifest.filesystem.add_structured(
        "pyproject.toml", "[tool.ruff]\nline-length = 88\n", producer="module:test"
    )
    review = prepare_review(
        manifest, UserConfig(), policy=ExecutionPolicy.INITIALIZATION
    )

    render_review(manifest, review)

    (proposal,) = review.proposals
    text = output()
    assert text.splitlines()[0] == "1 modified · 1 change to your files"
    assert "pyproject.toml  modified" in text
    assert (
        f"Proposed {proposal.id}: pyproject.toml tool: applies; decline with local."
    ) in text


def test_a_migration_is_listed_below_the_tree(project, output):
    project.write_text(source_text("updated"))
    prepared = prepare_project(check_executables=False)
    step = MigrationStep("2.0", "old.md", "docs/old.md", MigrationOutcome.MOVED)

    render_review(prepared.manifest, replace(prepared.review, migrations=(step,)))

    text = output()
    assert "renovate.json  modified" in text
    assert "Migration 2.0: old.md moves to docs/old.md." in text
    assert text.index("renovate.json") < text.index("Migration 2.0")


def test_applied_sync_reads_as_done(project, output, monkeypatch):
    project.write_text(source_text("updated"))
    monkeypatch.setattr("sys.argv", ["protostar", "sync"])

    main()

    text = output()
    assert "renovate.json  modified" in text
    assert "Ownership/provenance state advanced." in text
    assert "Applied changes to" in text
    assert json.loads(Path(RENOVATE).read_text()) == {"value": "updated"}
