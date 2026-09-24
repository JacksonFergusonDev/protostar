"""Recipe persistence, recorded template variables, and separation from ownership."""

import random
import string
import sys
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from protostar.config import TemplateBlueprint, UserConfig
from protostar.errors import (
    ConfigurationError,
    FileSystemError,
    InvalidUsageError,
    MissingTemplateVariablesError,
    UnsupportedFilesystemNodeError,
)
from protostar.executor import SystemExecutor
from protostar.intent import TemplateOrigin, validate_configuration
from protostar.manifest import EnvironmentManifest
from protostar.recipe import (
    RecipeIntent,
    RecipeSource,
    SelectionLayer,
    Tool,
    decode_recipe,
    edit_recipe,
    establish_recipe,
    read_recipe,
    select_tooling,
)


def recipe():
    """Returns a complete tooling-only recipe without consulting host defaults."""
    return establish_recipe(
        UserConfig(ruff=True, mypy=False),
        RecipeIntent(metadata={"author_name": "Ada", "supported_os": ["Linux"]}),
    )


def test_round_trip_preserves_foreign_bytes_comments_and_recipe_comments(tmp_path):
    original = (
        '# Header\n[project]\nname = "foreign" # comment\n\n[tool.other]\nvalue=42\n'
    )
    first = edit_recipe(original, recipe())
    assert first.startswith(original)
    path = tmp_path / "pyproject.toml"
    path.write_text(first)
    assert read_recipe(path) == recipe()
    assert edit_recipe(first, recipe()) == first
    commented = first.replace("ruff = true", "ruff = true # my default")
    changed = edit_recipe(commented, replace(recipe(), docker=True))
    assert "# my default" in changed
    assert "[tool.other]\nvalue=42" in changed


@pytest.mark.parametrize(
    "mutation",
    [
        {"version": 2},
        {"version": True},
        {"unknown": True},
        {"docker": "yes"},
        {"python": "../../python"},
        {"ide": "emacs"},
        {"tools": {"imaginary": True}},
        {"tools": {"ruff": 1}},
        {"fallback": {}},
        {"context": {"SECRET": "value"}},
        {"bindings": {"ANSWER": "ENVIRONMENT"}},
        {"variables": {"1st": "value"}},
        {"variables": {"CURRENT_YEAR": "2020"}},
        {"variables": {"REGION": 1}},
        {"variables": ["REGION"]},
        {"metadata": {"secret": "value"}},
        {"mode": "template"},
        {"source": {"origin": "local", "locator": "x"}},
        {"mode": "template", "source": {"origin": "local", "locator": "../outside"}},
        {"mode": "template", "source": {"origin": "built-in", "locator": "unknown"}},
    ],
)
def test_strict_recipe_validation(mutation):
    with pytest.raises(ConfigurationError):
        decode_recipe(recipe().to_dict() | mutation)


def test_recorded_variables_render_and_persist():
    recorded = replace(recipe(), variables=(("REGION", "eu-west-1"),))

    context = recorded.rendering_context()
    assert context["REGION"] == "eu-west-1"
    assert context["PROJECT_NAME"] == dict(recipe().context)["PROJECT_NAME"]
    assert 'REGION = "eu-west-1"' in edit_recipe("", recorded)
    assert decode_recipe(recorded.to_dict()) == recorded
    assert "trust" not in recorded.to_dict()


def _token():
    # Built at test time; a literal would trip this repository's gitleaks hook.
    rng = random.Random(20260922)
    return "ghp_" + "".join(
        rng.choice(string.ascii_letters + string.digits) for _ in range(36)
    )


def test_decoding_accepts_recorded_variable_values_the_guard_would_flag():
    """Values are checked when entered; a recorded one never blocks later runs."""
    data = recipe().to_dict() | {"variables": {"REGION": _token()}}

    assert dict(decode_recipe(data).variables) == {"REGION": _token()}


def test_unknown_template_flags_are_named():
    with pytest.raises(ConfigurationError, match="unknown tooling flags: mypi, rufff"):
        recipe().selections({"rufff": True, "ruff": True, "mypi": False})


def test_template_opinions_evolve_only_under_omitted_overrides():
    captured = replace(recipe(), tools=((Tool.MYPY, True), (Tool.RENOVATE, False)))
    decisions = {
        s.tool: s
        for s in captured.selections({"ruff": False, "mypy": False, "renovate": True})
    }
    assert not decisions[Tool.RUFF].enabled
    assert decisions[Tool.RUFF].layer is SelectionLayer.TEMPLATE
    assert decisions[Tool.MYPY].enabled
    assert decisions[Tool.MYPY].layer is SelectionLayer.PROJECT
    assert not decisions[Tool.RENOVATE].enabled
    assert decisions[Tool.CI].layer is SelectionLayer.FALLBACK
    assert [
        m.config_key for m in select_tooling(captured, {"ruff": True, "renovate": True})
    ] == ["ruff", "mypy"]
    # A new global default is not an input to replay.
    assert decode_recipe(captured.to_dict()).selections({}) == captured.selections({})


@pytest.mark.parametrize(
    "payload",
    ["[tool.protostar]\nversion=1", "tool.protostar = {}", 'tool = "replace ancestor"'],
)
def test_reserved_subtree(payload):
    with pytest.raises(ConfigurationError):
        validate_configuration(payload)
    with pytest.raises(ConfigurationError):
        EnvironmentManifest().filesystem.add_structured(
            "pyproject.toml", payload, producer="foreign"
        )


def test_free_form_replacement_cannot_bypass_reservation():
    with pytest.raises(ConfigurationError):
        TemplateBlueprint._parse('[files]\n"pyproject.toml" = "[tool.protostar]"')
    with pytest.raises(ConfigurationError):
        EnvironmentManifest().filesystem.add_file_injection(
            "pyproject.toml", "[project]"
        )


def test_unsupported_recipe_node(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.symlink_to(tmp_path / "missing")
    with pytest.raises(UnsupportedFilesystemNodeError):
        read_recipe(path)


@pytest.mark.parametrize("failure", ["recipe", "state"])
def test_recipe_and_state_rollback_together(tmp_path, monkeypatch, mocker, failure):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "pyproject.toml"
    original = b'# original\n[project]\nname="existing"\n'
    target.write_bytes(original)
    target.chmod(0o640)
    manifest = EnvironmentManifest(recipe=recipe())
    executor = SystemExecutor(manifest, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    mocker.patch.object(
        executor.process_runner,
        "run",
        side_effect=AssertionError("no subprocess expected"),
    )
    original_write = executor.fs.write_text

    def fail_after_write(path, content):
        original_write(path, content)
        if path == Path("pyproject.toml" if failure == "recipe" else "protostar.lock"):
            raise OSError("late write failure")

    mocker.patch.object(executor.fs, "write_text", side_effect=fail_after_write)
    with pytest.raises(FileSystemError):
        executor.execute()
    assert target.read_bytes() == original
    if sys.platform != "win32":
        assert target.stat().st_mode & 0o777 == 0o640
    assert not (tmp_path / "protostar.lock").exists()


def test_repeat_recipe_has_no_writes(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest(recipe=recipe())
    for _ in range(2):
        executor = SystemExecutor(manifest, UserConfig())
        mocker.patch.object(executor, "_check_ide_extensions")
        mocker.patch.object(
            executor.process_runner,
            "run",
            side_effect=AssertionError("unexpected process"),
        )
        executor.execute()
    assert not executor.journal.touched_paths
    state = tomllib.loads((tmp_path / "protostar.lock").read_text())
    assert "protostar" not in str(state.get("files"))


def test_exact_local_source_load(tmp_path):
    path = tmp_path / "blueprint.toml"
    path.write_text('name="source"\nruff=false\n')
    source = RecipeSource(TemplateOrigin.LOCAL, "blueprint.toml")
    blueprint = source.acquire(tmp_path).render({})
    assert blueprint.reference is not None
    assert blueprint.reference.locator == path.resolve().as_posix()
    assert blueprint.tooling_overrides == {"ruff": False}


def test_cli_preserves_diversions_and_frozen_context(tmp_path, monkeypatch, mocker):
    import argparse

    from protostar.cli.main import handle_init
    from protostar.models import ExecutionResult

    monkeypatch.chdir(tmp_path)
    captured = replace(recipe(), tools=((Tool.MYPY, True), (Tool.RENOVATE, False)))
    captured = replace(
        captured,
        context=tuple(
            sorted((dict(captured.context) | {"CURRENT_YEAR": "2001"}).items())
        ),
    )
    (tmp_path / "pyproject.toml").write_text(
        edit_recipe('[project]\nname="foreign"\n', captured)
    )
    mocker.patch(
        "protostar.cli.main.UserConfig.load",
        return_value=UserConfig(
            ruff=False, renovate=True, author_name="Changed", python_version="3.14"
        ),
    )
    mocker.patch("shutil.which", return_value="/mock/command")
    engines = []

    def capture(engine, request, decision):
        engines.append(engine)
        return ExecutionResult(frozenset(), frozenset(), ())

    mocker.patch("protostar.cli.ui._run_engine", side_effect=capture)
    args = argparse.Namespace(docker=None, force_merge=True)
    handle_init(args)
    desired = engines[-1].request.recipe
    assert desired == captured
    manifest = engines[-1].plan()
    assert {m.config_key for m in engines[-1].modules if m.config_key} == {
        "ruff",
        "mypy",
    }
    assert {p.tool for p in manifest.producer_contributions if p.tool} == {
        Tool.RUFF,
        Tool.MYPY,
    }
    args.MypyModule = False
    args.python_version = "3.12"
    handle_init(args)
    desired = engines[-1].request.recipe
    assert dict(desired.tools) == {Tool.MYPY: False, Tool.RENOVATE: False}
    assert dict(desired.context)["CURRENT_YEAR"] == "2001"
    assert dict(desired.context)["PYTHON_VERSION"] == "3.12"


def test_template_variables_persist_and_optout_keeps_independent_contributions(
    tmp_path, monkeypatch, mocker
):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    source = tmp_path / "blueprint.toml"
    source.write_text(
        'name="custom"\nruff=true\n[dev.pyproject]\nforeign="""[tool.ruff]\nline-length=99\n"""\n[files]\n"custom.txt"="<% ANSWER %>"\n'
    )
    engines = _capture_init_engines(mocker)
    args = argparse.Namespace(
        from_path=str(source),
        variables=["ANSWER=template-answer"],
        docker=None,
        RuffModule=False,
    )
    handle_init(args)
    engine = engines[-1]
    assert dict(engine.request.recipe.variables) == {"ANSWER": "template-answer"}
    assert 'ANSWER = "template-answer"' in edit_recipe("", engine.request.recipe)
    assert not any(m.config_key == "ruff" for m in engine.modules)
    manifest = engine.plan()
    assert any(
        "line-length=99" in c.content
        for c in manifest.filesystem.structured["pyproject.toml"]
    )
    assert manifest.filesystem.file_injections["custom.txt"] == "template-answer"
    assert "protostar" not in str(
        [c.content for c in manifest.filesystem.structured["pyproject.toml"]]
    )


def _two_variable_template(tmp_path):
    source = tmp_path / "blueprint.toml"
    source.write_text('[files]\n"custom.txt"="<% REGION %> <% TIER %>"\n')
    return source


def test_missing_variables_fail_without_prompt_or_mutation_off_a_terminal(
    tmp_path, monkeypatch, mocker
):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    source = _two_variable_template(tmp_path)
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())
    mocker.patch("protostar.cli.main.is_interactive", return_value=False)
    prompt = mocker.patch(
        "protostar.cli.main.edit_variables",
        side_effect=AssertionError("no prompts"),
    )

    with pytest.raises(MissingTemplateVariablesError) as caught:
        handle_init(
            argparse.Namespace(
                from_path=str(source), variables=["REGION=eu"], docker=None
            )
        )

    assert caught.value.variables == ("TIER",)
    prompt.assert_not_called()
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "blueprint.toml",
        "config.toml",
    ]


def test_json_mode_never_prompts_for_variables(tmp_path, monkeypatch, mocker):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    source = _two_variable_template(tmp_path)
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())
    mocker.patch("protostar.cli.main.is_interactive", return_value=True)
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    prompt = mocker.patch("protostar.cli.main.edit_variables")

    with pytest.raises(MissingTemplateVariablesError):
        handle_init(argparse.Namespace(from_path=str(source), docker=None))

    prompt.assert_not_called()


def test_terminal_opens_the_variables_step_for_missing_variables(
    tmp_path, monkeypatch, mocker
):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    source = _two_variable_template(tmp_path)
    engines = _capture_init_engines(mocker)
    mocker.patch("protostar.cli.main.is_interactive", return_value=True)
    step = mocker.patch(
        "protostar.cli.main.edit_variables",
        side_effect=lambda draft, config, flagged: replace(
            draft, variables=(*draft.variables, ("TIER", "gold"))
        ),
    )

    handle_init(
        argparse.Namespace(from_path=str(source), variables=["REGION=eu"], docker=None)
    )

    step.assert_called_once()
    draft = step.call_args.args[0]
    assert draft.template.source.variables - dict(draft.variables).keys() == {"TIER"}
    assert dict(engines[-1].request.recipe.variables) == {
        "REGION": "eu",
        "TIER": "gold",
    }


def test_reinit_reuses_recorded_variables_and_flags_override_them(
    tmp_path, monkeypatch, mocker
):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    _two_variable_template(tmp_path)
    recorded = replace(
        recipe(),
        source=RecipeSource(TemplateOrigin.LOCAL, "blueprint.toml"),
        variables=(("REGION", "eu"), ("RETIRED", "old"), ("TIER", "silver")),
    )
    (tmp_path / "pyproject.toml").write_text(edit_recipe("", recorded))
    engines = _capture_init_engines(mocker)
    mocker.patch("protostar.cli.main.is_interactive", return_value=True)
    prompt = mocker.patch(
        "protostar.cli.main.edit_variables",
        side_effect=AssertionError("nothing is missing"),
    )

    handle_init(argparse.Namespace(variables=["TIER=gold"], docker=None))

    prompt.assert_not_called()
    # RETIRED is no longer used by the template, so it is not carried forward.
    assert dict(engines[-1].request.recipe.variables) == {
        "REGION": "eu",
        "TIER": "gold",
    }
    rendered = engines[-1].request.template_blueprint.files["custom.txt"]
    assert rendered == "eu gold"


@pytest.mark.parametrize(
    ("variables", "match"),
    [
        (["NOPE=1"], "no variable named NOPE"),
        (["REGION=a", "REGION=b"], "more than once"),
    ],
)
def test_var_flags_are_validated_against_the_template(
    tmp_path, monkeypatch, mocker, variables, match
):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    source = _two_variable_template(tmp_path)
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())

    with pytest.raises(InvalidUsageError, match=match):
        handle_init(
            argparse.Namespace(from_path=str(source), variables=variables, docker=None)
        )


def test_var_flags_need_a_template(tmp_path, monkeypatch, mocker):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())

    with pytest.raises(InvalidUsageError, match="needs a template"):
        handle_init(argparse.Namespace(variables=["REGION=eu"], docker=None))


def test_dry_run_has_no_recipe_or_lock_write(tmp_path, monkeypatch, mocker):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    mocker.patch(
        "protostar.cli.main.UserConfig.load", return_value=UserConfig(ruff=False)
    )
    mocker.patch("shutil.which", return_value="/mock/command")
    with pytest.raises(SystemExit) as error:
        handle_init(argparse.Namespace(docker=None, dry_run=True))
    assert error.value.code == 0
    assert [p.name for p in tmp_path.iterdir()] == ["config.toml"]


def test_lock_cannot_own_recipe():
    from protostar.sync_state import FilePolicy, FileState

    with pytest.raises(ConfigurationError):
        FileState(
            "pyproject.toml", FilePolicy.TOML, baseline="[tool.protostar]\nversion=1\n"
        )


def test_duplicate_dependency_declarations_retain_both_producers(tmp_path, monkeypatch):
    from protostar.models import InitRequest
    from protostar.modules import BootstrapModule
    from protostar.orchestrator import Orchestrator

    monkeypatch.chdir(tmp_path)

    class First(BootstrapModule):
        config_key = "ruff"

        @property
        def name(self):
            return "First"

        def build(self, manifest):
            manifest.dependencies.add_dev("shared")

    class Second(First):
        config_key = "mypy"

    manifest = Orchestrator(
        [First(), Second()],
        UserConfig(),
        InitRequest(recipe=replace(recipe(), tools=((Tool.MYPY, True),))),
    ).plan()
    declarations = [
        p
        for p in manifest.producer_contributions
        if p.path == ("dependencies", "dev_dependencies", "shared")
    ]
    assert {p.tool for p in declarations} == {Tool.RUFF, Tool.MYPY}
    assert manifest.dependencies.dev_dependencies == ["shared"]


def test_initial_project_name_matches_initializer_normalization(tmp_path, monkeypatch):
    root = tmp_path / "Demo_Project"
    root.mkdir()
    monkeypatch.chdir(root)
    captured = recipe()
    assert dict(captured.context)["PROJECT_NAME"] == "demo-project"
    assert dict(captured.context)["PACKAGE_NAME"] == "demo_project"


@pytest.mark.parametrize(
    "source",
    [
        {
            "origin": "remote",
            "locator": "https://user:password@example.com/template.toml",
        },
        {
            "origin": "remote",
            "locator": "https://example.com/template.toml?token=secret",
        },
        {"origin": "remote", "locator": "https://[bad/template.toml"},
        {"origin": "local", "locator": "C:outside.toml"},
    ],
)
def test_unsafe_source_is_domain_error(source):
    with pytest.raises(ConfigurationError):
        decode_recipe(recipe().to_dict() | {"mode": "template", "source": source})


@pytest.mark.parametrize("failure", ["recipe", "state"])
def test_existing_recipe_and_lock_restore_exact_bytes(
    tmp_path, monkeypatch, mocker, failure
):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "pyproject.toml"
    target.write_text('# original\n[project]\nname="existing"\n')
    first = EnvironmentManifest(recipe=recipe())
    first.filesystem.add_structured(
        "pyproject.toml", "[tool.ruff]\nline-length=88", producer="module:test"
    )
    executor = SystemExecutor(first, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    lock = tmp_path / "protostar.lock"
    target.chmod(0o640)
    lock.chmod(0o600)
    before = (target.read_bytes(), lock.read_bytes())
    second = EnvironmentManifest(recipe=replace(recipe(), docker=True))
    second.filesystem.add_structured(
        "pyproject.toml", "[tool.ruff]\nline-length=99", producer="module:test"
    )
    executor = SystemExecutor(second, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    original_write = executor.fs.write_text

    def fail_after_write(path, content):
        original_write(path, content)
        if path == Path("protostar.lock") or (
            failure == "recipe"
            and "[tool.protostar]" in content
            and "docker = true" in content
        ):
            raise OSError("late failure")

    mocker.patch.object(executor.fs, "write_text", side_effect=fail_after_write)
    with pytest.raises(FileSystemError):
        executor.execute()
    assert (target.read_bytes(), lock.read_bytes()) == before
    if sys.platform != "win32":
        assert target.stat().st_mode & 0o777 == 0o640
        assert lock.stat().st_mode & 0o777 == 0o600


def test_invalid_desired_recipe_fails_before_mutation(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    invalid = replace(recipe(), python="not-python")
    manifest = EnvironmentManifest(recipe=invalid)
    manifest.filesystem.add_directory("would-create")
    executor = SystemExecutor(manifest, UserConfig())
    write = mocker.spy(executor.fs, "ensure_directory")
    with pytest.raises(ConfigurationError):
        executor.execute()
    write.assert_not_called()
    assert not (tmp_path / "would-create").exists()


def _capture_init_engines(mocker):
    from protostar.init_draft import InitDecision
    from protostar.models import ExecutionResult

    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())
    mocker.patch("shutil.which", return_value="/mock/command")
    # A local template is untrusted, so an interactive run reviews it first.
    mocker.patch(
        "protostar.cli.main.review_changes",
        side_effect=lambda draft, config: InitDecision(draft, ()),
    )
    engines = []

    def capture(engine, request, decision):
        engines.append(engine)
        return ExecutionResult(frozenset(), frozenset(), ())

    mocker.patch("protostar.cli.ui._run_engine", side_effect=capture)
    return engines


@pytest.mark.parametrize(
    ("template_docker", "flag", "expected"),
    [
        (True, None, True),  # template opinion applies when nothing overrides it
        (True, False, False),  # --no-docker beats the template
        (False, True, True),  # --docker beats the template
        (False, None, False),
        (None, None, False),  # silent template: container scaffolding stays opt-in
    ],
)
def test_template_docker_opinion_follows_flag_precedence(
    tmp_path, monkeypatch, mocker, template_docker, flag, expected
):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    opinion = (
        "" if template_docker is None else f"docker={str(template_docker).lower()}\n"
    )
    source = tmp_path / "blueprint.toml"
    source.write_text(f'name="custom"\n{opinion}')
    engines = _capture_init_engines(mocker)

    handle_init(argparse.Namespace(from_path=str(source), docker=flag))

    assert engines[-1].request.docker is expected
    assert engines[-1].request.recipe.docker is expected


def test_captured_recipe_docker_wins_over_a_later_template_opinion(
    tmp_path, monkeypatch, mocker
):
    """An initialized project keeps its captured intent when the template changes."""
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        edit_recipe('[project]\nname="foreign"\n', replace(recipe(), docker=False))
    )
    source = tmp_path / "blueprint.toml"
    source.write_text('name="custom"\ndocker=true\n')
    engines = _capture_init_engines(mocker)

    handle_init(argparse.Namespace(from_path=str(source), docker=None))

    assert engines[-1].request.docker is False


def _cli_template_pyproject(tmp_path, monkeypatch, mocker, **flags):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    engines = _capture_init_engines(mocker)
    handle_init(argparse.Namespace(template_name="cli", docker=None, **flags))
    manifest = engines[-1].plan()
    return "\n".join(
        c.content for c in manifest.filesystem.structured["pyproject.toml"]
    )


def test_cli_template_keeps_tool_config_for_enabled_tools(
    tmp_path, monkeypatch, mocker
):
    pyproject = _cli_template_pyproject(tmp_path, monkeypatch, mocker)

    assert "strict = true" in pyproject
    assert "[tool.coverage.report]" in pyproject
    assert 'extend-select = [\n    "D",' in pyproject


def test_cli_template_drops_tool_config_for_disabled_tools(
    tmp_path, monkeypatch, mocker
):
    """`--no-mypy --no-pytest` must not leave [tool.mypy] or [tool.coverage] behind."""
    pyproject = _cli_template_pyproject(
        tmp_path, monkeypatch, mocker, MypyModule=False, PytestModule=False
    )

    assert "strict = true" not in pyproject
    assert "[tool.mypy" not in pyproject
    assert "[tool.coverage" not in pyproject
    # Ruff stayed on, and so did the tool-agnostic build system and entrypoint.
    assert "extend-select" in pyproject
    assert "hatchling" in pyproject
    assert "[project.scripts]" in pyproject


def _template_dev_dependencies(tmp_path, monkeypatch, mocker, template, **flags):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    engines = _capture_init_engines(mocker)
    handle_init(argparse.Namespace(template_name=template, docker=None, **flags))
    return engines[-1].plan().dependencies.dev_dependencies


@pytest.mark.parametrize(
    ("template", "packages"),
    [("cli", {"pytest-cov"}), ("api", {"httpx", "pytest-asyncio"})],
)
def test_builtin_test_packages_follow_the_pytest_flag(
    tmp_path, monkeypatch, mocker, template, packages
):
    with_pytest = _template_dev_dependencies(tmp_path, monkeypatch, mocker, template)
    without = _template_dev_dependencies(
        tmp_path, monkeypatch, mocker, template, PytestModule=False
    )

    assert packages <= set(with_pytest)
    assert not packages & set(without)


UV_LAYOUT = """[project]
name = "app"
version = "0.1.0"

[tool.ruff]
line-length = 88

[dependency-groups]
dev = ["ruff"]
"""


def _order(content: str, *markers: str) -> list[str]:
    return sorted(markers, key=content.index)


def test_recipe_write_settles_the_layout_of_a_pyproject_protostar_created(
    tmp_path, monkeypatch
):
    """uv appends [dependency-groups] after the managed merge; the final pass fixes it."""
    monkeypatch.chdir(tmp_path)
    executor = SystemExecutor(EnvironmentManifest(recipe=recipe()), UserConfig())
    executor.fs.write_text(Path("pyproject.toml"), UV_LAYOUT)  # created in this run

    executor._write_recipe()

    content = (tmp_path / "pyproject.toml").read_text()
    assert _order(
        content,
        "[dependency-groups]",
        "# Tool Configuration",
        "# ---- Protostar ---- #",
    ) == ["[dependency-groups]", "# Tool Configuration", "# ---- Protostar ---- #"]


def test_recipe_write_leaves_a_project_the_user_already_had_in_their_order(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(UV_LAYOUT)  # exists before the run
    executor = SystemExecutor(EnvironmentManifest(recipe=recipe()), UserConfig())

    executor._write_recipe()

    content = (tmp_path / "pyproject.toml").read_text()
    assert "# Tool Configuration" not in content
    assert content.startswith(UV_LAYOUT.split("[dependency-groups]")[0])
    assert content.index("[tool.protostar]") < content.index("[dependency-groups]")


def _recipe_table(content: str) -> dict[str, Any]:
    return tomllib.loads(content)["tool"]["protostar"]


def test_edit_recipe_omits_empty_tables_and_keeps_populated_ones():
    """The sample recipe has metadata but no diversions or variables."""
    table = _recipe_table(edit_recipe("", recipe()))

    assert {"fallback", "context", "metadata"} <= set(table)
    assert "tools" not in table
    assert "variables" not in table


def test_edit_recipe_writes_populated_optional_tables():
    populated = replace(
        recipe(),
        tools=((Tool.MYPY, True),),
        variables=(("REGION", "eu-west-1"),),
    )
    table = _recipe_table(edit_recipe("", populated))

    assert table["tools"] == {"mypy": True}
    assert table["variables"] == {"REGION": "eu-west-1"}


def test_absent_optional_tables_decode_as_empty():
    data = recipe().to_dict()
    for name in ("tools", "metadata", "variables"):
        data.pop(name)

    decoded = decode_recipe(data)

    assert decoded.tools == ()
    assert decoded.metadata == ()
    assert decoded.variables == ()


@pytest.mark.parametrize("name", ["fallback", "context"])
def test_always_populated_recipe_tables_stay_required(name):
    data = recipe().to_dict()
    data.pop(name)

    with pytest.raises(ConfigurationError):
        decode_recipe(data)


def test_a_recipe_written_with_empty_tables_still_decodes_and_is_tidied():
    """Projects created before empty tables were dropped keep working."""
    legacy = replace(recipe(), metadata=())
    text = edit_recipe("", legacy)
    text += "\n[tool.protostar.tools]\n\n[tool.protostar.variables]\n"

    assert decode_recipe(_recipe_table(text)) == legacy
    tidied = _recipe_table(edit_recipe(text, legacy))
    assert "tools" not in tidied
    assert "variables" not in tidied


def test_edit_recipe_is_idempotent():
    once = edit_recipe("[tool.ruff]\nline-length = 88\n", recipe())

    assert edit_recipe(once, recipe()) == once


def test_a_table_added_to_an_existing_recipe_lands_in_its_canonical_place():
    """tomlkit appends it, which would steal the next tool's header comment."""
    base = edit_recipe("", recipe())
    existing = base + "\n# ---- Mypy ---- #\n\n[tool.mypy]\nstrict = true\n"

    updated = edit_recipe(existing, replace(recipe(), tools=((Tool.MYPY, True),)))

    assert updated.index("[tool.protostar]") < updated.index("[tool.protostar.tools]")
    assert updated.index("[tool.protostar.tools]") < updated.index(
        "[tool.protostar.fallback]"
    )
    assert "# ---- Mypy ---- #\n\n[tool.mypy]\nstrict = true" in updated
    assert _recipe_table(updated)["tools"] == {"mypy": True}
    assert tomllib.loads(updated)["tool"]["mypy"] == {"strict": True}


def test_every_recipe_table_header_has_a_blank_line_before_it():
    base = edit_recipe("", recipe())
    updated = edit_recipe(
        base + "\n[tool.mypy]\nstrict = true\n",
        replace(recipe(), tools=((Tool.MYPY, True),)),
    )
    lines = updated.split("\n")

    for index, line in enumerate(lines[1:], start=1):
        if line.startswith("[tool.protostar"):
            assert lines[index - 1] == "", f"no blank line before {line!r}"


FOREIGN_PYPROJECT = '# mine\n[project]\nname="x"\n\n\n[tool.black]\nx = 1\n'


def test_editing_a_recipe_leaf_changes_no_other_byte():
    first = edit_recipe(FOREIGN_PYPROJECT, recipe())

    second = edit_recipe(first, replace(recipe(), docker=True))

    assert second == first.replace("docker = false", "docker = true")


def test_a_new_recipe_keeps_the_users_file_and_follows_their_last_tool():
    updated = edit_recipe(FOREIGN_PYPROJECT, recipe())

    assert updated.startswith(FOREIGN_PYPROJECT + "\n[tool.protostar]")
    assert decode_recipe(_recipe_table(updated)) == recipe()


def test_a_new_recipe_follows_the_files_own_newline_style():
    original = '[project]\r\nname = "x"\r\n'

    updated = edit_recipe(original, recipe())

    assert updated.startswith(original + "\r\n[tool.protostar]")
    assert "\n" not in updated.replace("\r\n", "")


def test_out_of_order_recipe_tables_are_edited_where_they_stand():
    first = edit_recipe("", recipe())
    scattered = first.replace(
        "[tool.protostar.context]", "[tool.other]\nz = 1\n\n[tool.protostar.context]"
    )

    updated = tomllib.loads(edit_recipe(scattered, replace(recipe(), docker=True)))

    assert updated["tool"]["protostar"]["docker"] is True
    assert updated["tool"]["other"] == {"z": 1}


def test_an_unformattable_new_pyproject_is_reported_as_a_diagnostic(
    tmp_path, monkeypatch, mocker
):
    """A layout problem must leave the file valid and say so, never stay silent."""
    monkeypatch.chdir(tmp_path)
    mocker.patch(
        "protostar.documents.pyproject_layout.format_sections",
        return_value='[project]\nname = "no"\n',
    )
    executor = SystemExecutor(EnvironmentManifest(recipe=recipe()), UserConfig())
    executor.fs.write_text(Path("pyproject.toml"), UV_LAYOUT)

    executor._write_recipe()

    written = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert written["project"]["name"] == "app"
    assert "protostar" in written["tool"]
    messages = [event.message for event in executor.diagnostics]
    assert any("Left pyproject.toml unformatted" in m for m in messages), messages
