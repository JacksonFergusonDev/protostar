"""One-time scaffolding omits Protostar lifecycle state without losing uv state."""

import tomllib
from pathlib import Path

import pytest

from protostar.cli.parser import build_parser
from protostar.config import UserConfig
from protostar.errors import ConfigurationError
from protostar.executor import SystemExecutor
from protostar.init_draft import InitDraft, resolve_init
from protostar.manifest import EnvironmentManifest, SystemTask
from protostar.models import InitRequest
from protostar.orchestrator import Orchestrator
from protostar.preparation import ExecutionPolicy, prepare_review
from protostar.recipe import edit_recipe, establish_recipe
from protostar.sync_state import SyncState, serialize_state
from protostar.workflows import GuideSpec, HookRunner, generate_agents_md


def test_one_shot_resolves_dependencies_without_recording_protostar_state(
    tmp_path, monkeypatch, mocker
):
    """Resolver output survives while recipe and ownership state are omitted."""
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest(one_shot=True)
    manifest.filesystem.add_structured(
        "pyproject.toml", '[project]\nname = "demo"\n', producer="test"
    )
    manifest.dependencies.add("requests")
    manifest.tasks.system_tasks.append(
        SystemTask(["uv", "init"], owned_files=["pyproject.toml"])
    )
    executor = SystemExecutor(manifest, UserConfig())

    def resolve(command, **_kwargs):
        if command[:2] == ["uv", "init"]:
            Path("pyproject.toml").write_text('[project]\nname = "demo"\n')
        elif command[:2] == ["uv", "add"]:
            Path("uv.lock").write_text("resolved\n")

    process = mocker.patch.object(executor.process_runner, "run", side_effect=resolve)
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()

    assert [call.args[0][:2] for call in process.call_args_list] == [
        ["uv", "init"],
        ["uv", "add"],
    ]
    assert Path("uv.lock").read_text() == "resolved\n"
    assert "protostar" not in tomllib.loads(Path("pyproject.toml").read_text()).get(
        "tool", {}
    )
    assert not Path("protostar.lock").exists()
    assert {"pyproject.toml", "uv.lock"} <= executor.journal.touched_paths


def test_one_shot_review_has_no_state_write(tmp_path, monkeypatch):
    """Review reports the scaffold's file edits without pending state output."""
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest(one_shot=True)
    manifest.filesystem.add_file_injection("README.md", "Hello\n")
    review = prepare_review(
        manifest, UserConfig(), policy=ExecutionPolicy.INITIALIZATION
    )
    assert [edit.path for edit in review.edits] == ["README.md"]
    assert not review.state_changed


@pytest.mark.parametrize("record", ["recipe", "state"])
def test_one_shot_rejects_tracked_project_during_plan(tmp_path, monkeypatch, record):
    """A tracked project cannot silently lose its lifecycle records."""
    monkeypatch.chdir(tmp_path)
    if record == "recipe":
        Path("pyproject.toml").write_text(
            edit_recipe("", establish_recipe(UserConfig()))
        )
    else:
        Path("protostar.lock").write_text(serialize_state(SyncState("test")))
    engine = Orchestrator([], UserConfig(), InitRequest(one_shot=True))
    with pytest.raises(ConfigurationError, match="untracked project"):
        engine.plan()


def test_one_shot_rechecks_workspace_before_mutation(tmp_path, monkeypatch, mocker):
    """State created after planning blocks execution before any file is touched."""
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest(one_shot=True)
    manifest.filesystem.add_file_injection("README.md", "new\n")
    Path("protostar.lock").write_text(serialize_state(SyncState("test")))
    executor = SystemExecutor(manifest, UserConfig())
    process = mocker.patch.object(executor.process_runner, "run")

    with pytest.raises(ConfigurationError, match="untracked project"):
        executor.execute()

    assert not Path("README.md").exists()
    process.assert_not_called()


def test_one_shot_cli_and_agent_guidance():
    """The public option and generated guidance agree on lifecycle behavior."""
    args = build_parser().parse_args(["init", "--one-shot"])
    assert args.one_shot
    _, request = resolve_init(InitDraft(one_shot=args.one_shot), UserConfig())
    assert request.one_shot
    guide = generate_agents_md(
        GuideSpec("3.13", HookRunner.PREK, False, [], [], [], set(), one_shot=True)
    )
    assert "protostar sync" not in guide
    assert "[tool.protostar]" not in guide
