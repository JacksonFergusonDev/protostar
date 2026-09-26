"""A selected tool's missing executable is reported as data, never a failure."""

import json
from dataclasses import replace

import pytest

from protostar.config import TemplateSource, UserConfig
from protostar.errors import MissingDependencyError
from protostar.executor import SystemExecutor
from protostar.init_draft import InitDraft, resolve_init
from protostar.lifecycle import inspect_project, prepare_project
from protostar.manifest import EnvironmentManifest, MissingTool
from protostar.models import ExecutionResult
from protostar.modules import DirenvModule, JustModule
from protostar.orchestrator import Orchestrator
from protostar.recipe import RecipeIntent, Tool, establish_recipe
from protostar.system_deps import GlobalExecutable

DIRENV = MissingTool(GlobalExecutable.DIRENV, Tool.DIRENV)
JUST = MissingTool(GlobalExecutable.JUST, Tool.JUST)


def plan_init(**tools: bool) -> EnvironmentManifest:
    """Plans an init with the given tools overriding the defaults."""
    draft = InitDraft(
        tool_overrides=tuple((Tool(name), value) for name, value in tools.items()),
        metadata=(),
    )
    modules, request = resolve_init(draft, UserConfig())
    return Orchestrator(modules, UserConfig(), request=request).plan()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_missing_tool_executables_plan_as_data(workspace, missing_executables):
    missing_executables.update({GlobalExecutable.DIRENV, GlobalExecutable.JUST})

    manifest = plan_init(direnv=True, just=True)

    assert manifest.missing_tools == {DIRENV, JUST}
    assert ".envrc" in manifest.filesystem.file_injections
    assert ["direnv", "allow"] not in [
        task.command for task in manifest.tasks.post_install_tasks
    ]
    assert [note.message for note in manifest.diagnostics] == [
        "Skipping `direnv allow`; direnv is not installed. "
        "Run it in the project once direnv is installed."
    ]


def test_installed_tool_executables_run_as_before(workspace):
    manifest = plan_init(direnv=True, just=True)

    assert manifest.missing_tools == frozenset()
    assert ["direnv", "allow"] in [
        task.command for task in manifest.tasks.post_install_tasks
    ]
    assert manifest.diagnostics == []


def test_only_enabled_tools_count(workspace, missing_executables):
    missing_executables.update({GlobalExecutable.DIRENV, GlobalExecutable.JUST})

    manifest = plan_init(direnv=False, just=True)

    assert manifest.missing_tools == {JUST}


@pytest.mark.parametrize("executable", [GlobalExecutable.UV, GlobalExecutable.GIT])
def test_missing_required_executable_fails_init_planning(
    workspace, missing_executables, executable
):
    missing_executables.add(executable)

    with pytest.raises(MissingDependencyError) as caught:
        plan_init()

    assert caught.value.missing == (executable,)


def test_execution_result_carries_missing_tools(workspace, missing_executables, mocker):
    missing_executables.add(GlobalExecutable.DIRENV)
    engine = Orchestrator([DirenvModule(), JustModule()], UserConfig(ide=None))
    manifest = engine.plan()
    run = mocker.patch("protostar.system.ProcessRunner.run")

    result = engine.execute(manifest)

    assert (workspace / ".envrc").is_file()
    run.assert_not_called()
    assert result.missing_tools == {DIRENV}
    assert result.to_dict()["missing_tools"] == [
        {"executable": "direnv", "tool": "direnv"}
    ]
    assert [note.message for note in result.diagnostics if "direnv" in note.message]


def test_missing_tools_serialize_sorted():
    result = ExecutionResult(
        frozenset(), frozenset(), (), missing_tools=frozenset({JUST, DIRENV})
    )
    manifest = EnvironmentManifest(missing_tools=frozenset({JUST, DIRENV}))

    expected = [
        {"executable": "direnv", "tool": "direnv"},
        {"executable": "just", "tool": "just"},
    ]
    assert result.to_dict()["missing_tools"] == expected
    assert manifest.to_dict()["missing_tools"] == expected
    assert json.dumps(result.to_dict()) == json.dumps(result.to_dict())


@pytest.fixture
def project(workspace, mocker):
    """A tracked project whose recipe enables direnv and just."""
    source = workspace / "source.toml"
    source.write_text('[files]\n"notes.txt" = "notes\\n"\n')
    blueprint = TemplateSource.load(str(source)).render({})
    recipe = establish_recipe(UserConfig(), RecipeIntent(reference=blueprint.reference))
    recipe = replace(
        recipe,
        fallback=tuple((tool, tool in (Tool.DIRENV, Tool.JUST)) for tool in Tool),
    )
    manifest = EnvironmentManifest(
        template_reference=blueprint.reference, recipe=recipe
    )
    manifest.filesystem.add_structured(
        "pyproject.toml", '[project]\nname = "demo"\n', producer="seed"
    )
    executor = SystemExecutor(manifest, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    mocker.patch("protostar.lifecycle.resolve_hook_revisions", return_value=())
    mocker.patch("subprocess.run", side_effect=AssertionError("subprocess.run"))


def test_sync_reports_missing_tools(project, missing_executables):
    missing_executables.update({GlobalExecutable.DIRENV, GlobalExecutable.JUST})

    prepared = prepare_project()

    assert prepared.manifest.missing_tools == {DIRENV, JUST}
    assert prepared.review.missing_tools == {DIRENV, JUST}
    assert [
        item["executable"] for item in prepared.review.to_dict()["missing_tools"]
    ] == [
        "direnv",
        "just",
    ]


@pytest.mark.parametrize("executable", [GlobalExecutable.UV, GlobalExecutable.GIT])
def test_missing_required_executable_fails_sync(
    project, missing_executables, executable
):
    missing_executables.add(executable)

    with pytest.raises(MissingDependencyError):
        prepare_project()
    # A read-only review is never applied, so it needs neither.
    inspect_project()
