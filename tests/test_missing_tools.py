"""A selected tool's missing executable is reported as data, never a failure."""

import json
from dataclasses import replace

import jsonschema  # type: ignore[import-untyped]
import pytest
from rich.console import Console

from protostar.cli import schema, ui
from protostar.cli.main import main
from protostar.config import TemplateSource, UserConfig
from protostar.errors import ExitCode, MissingDependencyError
from protostar.executor import SystemExecutor
from protostar.init_draft import InitDraft, resolve_init
from protostar.lifecycle import inspect_project, prepare_project
from protostar.manifest import EnvironmentManifest, MissingTool
from protostar.models import ExecutionResult
from protostar.modules import DirenvModule, JustModule
from protostar.orchestrator import Orchestrator
from protostar.recipe import RecipeIntent, Tool, establish_recipe
from protostar.system_deps import GlobalExecutable, PackageManager, Platform

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


# --- CLI reporting ---------------------------------------------------------


@pytest.fixture
def brew(mocker):
    """Homebrew is the one package manager found, on any platform."""
    mocker.patch(
        "protostar.cli.ui.available_package_managers",
        return_value=frozenset({PackageManager.BREW}),
    )
    mocker.patch(
        "protostar.system_deps.available_package_managers",
        return_value=frozenset({PackageManager.BREW}),
    )


def test_missing_uv_fails_before_the_editor_opens(
    workspace, missing_executables, mocker, monkeypatch, brew
):
    missing_executables.add(GlobalExecutable.UV)
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "init"])
    mocker.patch("protostar.cli.parser.is_interactive", return_value=True)
    editor = mocker.patch("protostar.cli.parser.edit_recipe")

    with pytest.raises(SystemExit) as caught:
        main()

    assert caught.value.code == ExitCode.UNAVAILABLE
    editor.assert_not_called()


def test_missing_git_json_error_names_it_and_its_install_command(
    workspace, missing_executables, monkeypatch, capsys, brew
):
    missing_executables.add(GlobalExecutable.GIT)
    monkeypatch.setattr(ui, "is_json_mode", True)
    monkeypatch.setattr(
        "sys.argv", ["protostar", "init", "--template", "cli", "--json"]
    )

    with pytest.raises(SystemExit) as caught:
        main()

    assert caught.value.code == ExitCode.UNAVAILABLE
    error = json.loads(capsys.readouterr().out)["error"]
    assert error["type"] == "MissingDependencyError"
    assert error["missing_executables"] == ["git"]
    assert error["install_commands"] == ["brew install git"]


def test_init_json_success_lists_missing_tools_and_install_commands(
    workspace, monkeypatch, mocker, capsys, brew
):
    result = ExecutionResult(
        frozenset(), frozenset(), (), missing_tools=frozenset({DIRENV, JUST})
    )
    mocker.patch("protostar.cli.ui._run_engine", return_value=result)
    monkeypatch.setattr(ui, "is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "init", "--json"])

    main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"]["missing_tools"] == [
        {"executable": "direnv", "tool": "direnv"},
        {"executable": "just", "tool": "just"},
    ]
    assert payload["install_commands"] == ["brew install direnv just"]


def test_success_payload_has_no_install_commands_without_a_manager(mocker):
    mocker.patch(
        "protostar.cli.ui.available_package_managers", return_value=frozenset()
    )
    mocker.patch.object(Platform, "current", return_value=Platform.MACOS)

    assert ui.missing_tools_payload(frozenset({DIRENV})) == {}
    assert ui.missing_tools_payload(frozenset()) == {}


def test_sync_reports_missing_tools_after_applying(
    project, missing_executables, monkeypatch, capsys, brew
):
    missing_executables.update({GlobalExecutable.DIRENV, GlobalExecutable.JUST})
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", ["protostar", "sync", "--json"])

    main()

    payload = json.loads(capsys.readouterr().out)
    assert [item["tool"] for item in payload["result"]["missing_tools"]] == [
        "direnv",
        "just",
    ]
    assert payload["install_commands"] == ["brew install direnv just"]
    jsonschema.validate(payload, schema.application_schema())
    assert [item["tool"] for item in payload["review"]["missing_tools"]] == [
        "direnv",
        "just",
    ]


def test_human_sync_ends_with_the_install_command(
    project, missing_executables, monkeypatch, mocker, capsys, brew
):
    missing_executables.add(GlobalExecutable.JUST)
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr(ui, "console", Console(width=100, color_system=None))
    mocker.patch("protostar.cli.reviews.is_interactive", return_value=False)
    monkeypatch.setattr("sys.argv", ["protostar", "sync"])

    main()

    output = capsys.readouterr().out
    assert "just is not installed; its files are ready for when it is." in output
    assert output.rstrip().endswith("brew install just")
