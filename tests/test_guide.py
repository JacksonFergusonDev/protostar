"""The project guide: commands from the guide spec and recorded project facts."""

import importlib.resources
import io
import json
import re
from dataclasses import replace

import pytest
from rich.console import Console

from protostar.cli import ui
from protostar.cli.guide import render_guide
from protostar.cli.main import main
from protostar.config import TemplateSource, UserConfig
from protostar.executor import SystemExecutor
from protostar.guide import (
    Entrypoint,
    GuideNote,
    Topic,
    build_guide,
    project_guide,
    read_entrypoints,
)
from protostar.init_draft import DraftTemplate, InitDraft, resolve_init
from protostar.manifest import EnvironmentManifest, MissingTool
from protostar.orchestrator import Orchestrator
from protostar.recipe import RecipeIntent, Tool, establish_recipe
from protostar.system_deps import GlobalExecutable, PackageManager
from protostar.templates import builtin_template_aliases
from protostar.workflows import CIFlag, GuideSpec, HookRunner, generate_agents_md

SPEC = GuideSpec(
    python_version="3.12",
    hook_runner=HookRunner.PREK,
    wants_just=True,
    format_commands=["uv run ruff format ."],
    lint_commands=["uv run ruff check ."],
    typecheck_commands=["uv run mypy ."],
    ci_flags={CIFlag.PYTEST, CIFlag.ZENSICAL},
)
ENTRYPOINT = Entrypoint("orbit", "orbit.cli:app", "src/orbit/cli.py")
JUST = MissingTool(GlobalExecutable.JUST, Tool.JUST)


def commands(guide, topic):
    return next(
        (action.commands for action in guide.actions if action.topic is topic), None
    )


def test_guide_with_just_names_its_recipes():
    guide = build_guide(SPEC, (ENTRYPOINT,))

    assert [action.topic for action in guide.actions] == list(Topic)
    assert commands(guide, Topic.RUN) == ("uv run orbit",)
    assert commands(guide, Topic.TEST) == ("just test",)
    assert commands(guide, Topic.CHECK) == (
        "just format",
        "just lint",
        "just typecheck",
        "just ci",
    )
    assert commands(guide, Topic.DOCS) == ("just serve",)
    assert commands(guide, Topic.MORE) == ("just --list",)
    (start,) = [a for a in guide.actions if a.topic is Topic.START]
    assert start.paths == ("src/orbit/cli.py",)
    assert "`orbit` runs `orbit.cli:app`" in start.explanation


def test_guide_without_just_shows_the_commands_themselves():
    guide = build_guide(replace(SPEC, wants_just=False), ())

    assert commands(guide, Topic.TEST) == ("uv run pytest",)
    assert commands(guide, Topic.CHECK) == (
        "uv run ruff format .",
        "uv run ruff check .",
        "uv run mypy .",
    )
    assert commands(guide, Topic.DOCS) == ("uv run zensical serve -o",)
    assert commands(guide, Topic.MORE) is None


def test_guide_with_just_missing_falls_back_and_reports_it():
    guide = build_guide(SPEC, (), frozenset({JUST}))

    assert commands(guide, Topic.TEST) == ("uv run pytest",)
    assert commands(guide, Topic.MORE) is None
    assert guide.missing_tools == {JUST}


def test_guide_shows_only_what_the_spec_supports():
    bare = GuideSpec("3.12", HookRunner.NONE, False, [], [], [], set())

    assert build_guide(bare, ()).actions == ()


def test_guide_explains_checks_in_plain_language():
    guide = build_guide(SPEC, ())
    (check,) = [a for a in guide.actions if a.topic is Topic.CHECK]

    assert check.explanation.startswith(
        "Formatting rewrites code into one consistent style, linting flags likely "
        "bugs, and type checking catches a value used as the wrong type."
    )
    assert "prek runs the project's git hooks on every commit" in check.explanation


def test_guide_serializes_deterministically():
    guide = build_guide(SPEC, (ENTRYPOINT,), frozenset({JUST}))

    payload = guide.to_dict()

    assert json.dumps(payload, sort_keys=True) == json.dumps(
        build_guide(SPEC, (ENTRYPOINT,), frozenset({JUST})).to_dict(), sort_keys=True
    )
    assert payload["missing_tools"] == [{"executable": "just", "tool": "just"}]
    assert payload["actions"][0] == {
        "topic": "run",
        "title": "Run the app",
        "explanation": payload["actions"][0]["explanation"],
        "commands": ["uv run orbit"],
        "paths": [],
    }


def test_entrypoints_name_the_file_their_module_lives_in(tmp_path):
    (tmp_path / "src" / "orbit").mkdir(parents=True)
    (tmp_path / "src" / "orbit" / "cli.py").write_text("")
    (tmp_path / "tool").mkdir()
    (tmp_path / "tool" / "__init__.py").write_text("")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "orbit"\n\n[project.scripts]\n'
        'orbit = "orbit.cli:app"\ntool = "tool:main"\ngone = "missing.mod:run"\n'
    )

    assert read_entrypoints(tmp_path) == (
        Entrypoint("gone", "missing.mod:run", None),
        Entrypoint("orbit", "orbit.cli:app", "src/orbit/cli.py"),
        Entrypoint("tool", "tool:main", "tool/__init__.py"),
    )


@pytest.mark.parametrize("alias", sorted(builtin_template_aliases()))
def test_guide_commands_match_agents_md_for_every_builtin(alias, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("protostar.metadata.get_git_config", lambda key: None)
    target = importlib.resources.files("protostar.templates").joinpath(f"{alias}.toml")
    source = TemplateSource.load(str(target), built_in=alias)
    modules, request = resolve_init(
        InitDraft(template=DraftTemplate(source), metadata=()), UserConfig()
    )
    spec = Orchestrator(modules, UserConfig(), request=request).plan().guide_spec()
    agents = generate_agents_md(spec)

    guide = build_guide(spec, ())

    stated = set(re.findall(r"`([^`]+)`", agents)) | set(agents.splitlines())
    for action in guide.actions:
        if action.topic in (Topic.TEST, Topic.CHECK):
            assert set(action.commands) <= stated, alias


# --- Discovery ------------------------------------------------------------------


@pytest.fixture
def project(tmp_path, monkeypatch, mocker):
    """A tracked project whose recipe enables just and pytest, with a script."""
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source.toml"
    source.write_text('[files]\n"src/orbit/cli.py" = "def app():\\n    pass\\n"\n')
    blueprint = TemplateSource.load(str(source)).render({})
    recipe = establish_recipe(UserConfig(), RecipeIntent(reference=blueprint.reference))
    recipe = replace(
        recipe,
        fallback=tuple((tool, tool in (Tool.JUST, Tool.PYTEST)) for tool in Tool),
    )
    manifest = EnvironmentManifest(
        template_reference=blueprint.reference, recipe=recipe
    )
    manifest.filesystem.add_structured(
        "pyproject.toml",
        '[project]\nname = "orbit"\n\n[project.scripts]\norbit = "orbit.cli:app"\n',
        producer="seed",
    )
    executor = SystemExecutor(manifest, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    # Discovery runs nothing and fetches nothing.
    mocker.patch("subprocess.run", side_effect=AssertionError("subprocess.run"))
    mocker.patch("subprocess.Popen", side_effect=AssertionError("subprocess.Popen"))
    mocker.patch(
        "protostar.system.ProcessRunner.run", side_effect=AssertionError("process")
    )
    mocker.patch(
        "protostar.registry.resolve_hook_revisions",
        side_effect=AssertionError("registry"),
    )
    (tmp_path / "src" / "orbit").mkdir(parents=True)
    (tmp_path / "src" / "orbit" / "cli.py").write_text("def app():\n    pass\n")
    return tmp_path


def test_project_guide_plans_the_recorded_recipe(project):
    guide = project_guide()

    assert commands(guide, Topic.RUN) == ("uv run orbit",)
    assert commands(guide, Topic.TEST) == ("just test",)
    assert commands(guide, Topic.MORE) == ("just --list",)
    assert guide.notes == ()


def test_project_guide_with_just_missing(project, missing_executables):
    missing_executables.add(GlobalExecutable.JUST)

    guide = project_guide()

    assert commands(guide, Topic.TEST) == ("uv run pytest",)
    assert guide.missing_tools == {JUST}


def test_removed_entrypoint_drops_its_actions(project):
    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace(
            '[project.scripts]\norbit = "orbit.cli:app"\n', ""
        )
    )

    guide = project_guide()

    assert commands(guide, Topic.RUN) is None
    assert Topic.START not in {action.topic for action in guide.actions}


def test_directory_without_a_recipe_invents_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    guide = project_guide()

    assert guide.actions == ()
    assert guide.notes == (GuideNote.NO_RECIPE,)


def test_unreachable_template_leaves_the_recorded_facts(project, mocker):
    from protostar.errors import NetworkFetchError

    mocker.patch(
        "protostar.lifecycle.locate_project",
        side_effect=NetworkFetchError("https://example.invalid/t.zip"),
    )

    guide = project_guide()

    assert commands(guide, Topic.RUN) == ("uv run orbit",)
    assert commands(guide, Topic.TEST) is None
    assert guide.notes == (GuideNote.TEMPLATE_UNAVAILABLE,)


def test_guide_command_json(project, missing_executables, monkeypatch, mocker, capsys):
    missing_executables.add(GlobalExecutable.JUST)
    mocker.patch(
        "protostar.cli.ui.available_package_managers",
        return_value=frozenset({PackageManager.BREW}),
    )
    monkeypatch.setattr(ui, "is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "guide", "--json"])

    main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "success"
    assert payload["guide"]["actions"][0]["commands"] == ["uv run orbit"]
    assert payload["install_commands"] == ["brew install just"]


def test_guide_text_renders_on_cp1252(project):
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    console = Console(file=stream, width=100, force_terminal=False, _environ={})

    console.print(render_guide(project_guide()))

    stream.flush()
    text = stream.buffer.getvalue().decode("cp1252")
    assert "    uv run orbit" in text
    assert "    src/orbit/cli.py" in text
