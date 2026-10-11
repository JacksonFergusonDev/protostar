"""Docs fixtures come from the commands and plans a reader would run."""

from pathlib import Path

import pytest

from protostar.cli import ui
from protostar.modules import TOOLING_MODULES
from scripts.generate_docs_assets import common, diffs
from scripts.generate_docs_assets.tables import _scaffolded_files


def module(name: str):
    return next(mod for mod in TOOLING_MODULES if mod.config_key == name)


def test_a_fixture_command_prints_the_payload_and_leaves_json_mode_off():
    with common.demo_project(), common.stable_host():
        payload = common.cli_json("init", "--template", "lib", "--dry-run")
    assert payload["status"] == "planned"
    assert not ui.is_json_mode


def test_a_failing_fixture_command_stops_generation_unless_its_error_is_the_point():
    with common.demo_project(), common.stable_host():
        Path("pyproject.toml").write_text('[project]\nname = "demo"\n')
        with pytest.raises(SystemExit, match="WorkspaceCollisionError"):
            common.cli_json("init", "--template", "cli")
        error = common.cli_json("init", "--template", "cli", allow_error=True)
    assert error["error"]["paths"] == ["pyproject.toml"]


@pytest.mark.parametrize(
    ("tool", "files"),
    [
        ("docker", [".dockerignore", "Dockerfile"]),
        # Read the Docs needs Zensical; only its own file is listed.
        ("readthedocs", [".readthedocs.yaml"]),
        ("ruff", []),
    ],
)
def test_a_tool_lists_the_files_enabling_it_adds(tool, files):
    assert _scaffolded_files(module(tool)) == files


def test_a_diff_that_vanishes_removes_its_fixture(tmp_path, monkeypatch):
    snapshots, generated = tmp_path / "snapshots", tmp_path / "generated"
    for scenario in ("ml", "ml_merged"):
        for name in ("pyproject.toml", ".gitignore"):
            target = snapshots / scenario / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("same\n")
    (snapshots / "ml_merged" / ".gitignore").write_text("same\nnew\n")
    generated.mkdir()
    stale = generated / "diff_ml_ml_merged_pyproject_toml.diff"
    stale.write_text("an old change\n")
    monkeypatch.setattr(diffs, "SNAPSHOTS_DIR", snapshots)
    monkeypatch.setattr(diffs, "DOCS_GENERATED_DIR", generated)
    monkeypatch.setattr(common, "DOCS_GENERATED_DIR", generated)

    diffs.generate_diff_fixtures()

    assert not stale.exists()
    assert (generated / "diff_ml_ml_merged__gitignore.diff").read_text() == (
        "--- a/.gitignore\n+++ b/.gitignore\n@@ -1 +1,2 @@\n same\n+new\n"
    )
