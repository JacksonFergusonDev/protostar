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
from protostar.documents.pyproject_layout import BANNER
from protostar.errors import (
    ConfigurationError,
    FileSystemError,
    InvalidUsageError,
    MissingTemplateVariablesError,
    UnsupportedFilesystemNodeError,
)
from protostar.executor import SystemExecutor
from protostar.ide import IDEType
from protostar.intent import TemplateOrigin, TemplateReference, validate_configuration
from protostar.manifest import EnvironmentManifest
from protostar.modules import DockerModule
from protostar.network import GitHost, RemoteSource, RemoteTemplate
from protostar.recipe import (
    RecipeIntent,
    RecipeSource,
    SelectionLayer,
    Tool,
    decode_recipe,
    edit_recipe,
    establish_recipe,
    read_recipe,
    remove_recipe,
    select_tooling,
    validate_tools,
)
from protostar.templates import builtin_template_aliases


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
    changed = edit_recipe(commented, replace(recipe(), ide=IDEType.VSCODE))
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


PYTHON_FORMAT_HINT = "Write the Python version as major.minor, such as '3.13'."
PYTHON_MAJOR_HINT = (
    "Protostar scaffolds Python 3 projects; choose a 3.x version such as '3.13'."
)
USERNAME_HINT = (
    "A GitHub username is at most 39 letters, digits, and hyphens, "
    "starting with a letter or digit."
)


@pytest.mark.parametrize(
    ("invalid", "message", "expected_hint"),
    [
        ("foo", "Invalid", PYTHON_FORMAT_HINT),
        ("3.x", "Invalid", PYTHON_FORMAT_HINT),
        ("", "Invalid", PYTHON_FORMAT_HINT),
        ("3", "Invalid", PYTHON_FORMAT_HINT),
        (" 3.13", "Invalid", PYTHON_FORMAT_HINT),
        (3.13, "Invalid", PYTHON_FORMAT_HINT),
        ("2.7", "Unsupported", PYTHON_MAJOR_HINT),
        ("4.0", "Unsupported", PYTHON_MAJOR_HINT),
        ("03.13", "Unsupported", PYTHON_MAJOR_HINT),
    ],
)
def test_invalid_python_version_recipe_error(invalid, message, expected_hint):
    with pytest.raises(ConfigurationError) as exc_info:
        decode_recipe(recipe().to_dict() | {"python": invalid})
    assert f"{message} Python version: {invalid!r}." in str(exc_info.value)
    assert exc_info.value.hint == expected_hint


@pytest.mark.parametrize("valid", ["3.0", "3.7", "3.10", "3.15", "3.30", "3.13.1"])
def test_any_python_3_version_decodes(valid):
    current = dict(recipe().context) | {"PYTHON_VERSION": valid}
    decoded = decode_recipe(
        recipe().to_dict()
        | {"python": valid, "context": current, "metadata": {"minimum_python": valid}}
    )
    assert decoded.python == valid


@pytest.mark.parametrize(
    ("invalid", "message", "expected_hint"),
    [
        (
            "foo",
            "Invalid",
            "Write the minimum Python version as major.minor, such as '3.13'.",
        ),
        ("2.7", "Unsupported", PYTHON_MAJOR_HINT),
    ],
)
def test_invalid_metadata_minimum_python_error(invalid, message, expected_hint):
    with pytest.raises(ConfigurationError) as exc_info:
        decode_recipe(recipe().to_dict() | {"metadata": {"minimum_python": invalid}})
    assert f"{message} minimum Python version: {invalid!r}." in str(exc_info.value)
    assert exc_info.value.hint == expected_hint


@pytest.mark.parametrize(
    ("invalid", "expected_hint"),
    [
        ("abc", "Container port must be a whole number, such as '8000'."),
        ("+8000", "Container port must be a whole number, such as '8000'."),
        (" 80 ", "Container port must be a whole number, such as '8000'."),
        (0, "Container port must be between 1 and 65535."),
        ("0", "Container port must be between 1 and 65535."),
        (65536, "Container port must be between 1 and 65535."),
        ("70000", "Container port must be between 1 and 65535."),
        (-1, "Container port must be between 1 and 65535."),
    ],
)
def test_invalid_metadata_docker_port_error(invalid, expected_hint):
    with pytest.raises(ConfigurationError) as exc_info:
        decode_recipe(recipe().to_dict() | {"metadata": {"docker_port": invalid}})
    assert f"Invalid container port: {invalid!r}." in str(exc_info.value)
    assert exc_info.value.hint == expected_hint


@pytest.mark.parametrize("valid", [8000, "8000", 1, 65535, "1", "65535"])
def test_valid_metadata_docker_port(valid):
    decoded = decode_recipe(recipe().to_dict() | {"metadata": {"docker_port": valid}})
    assert dict(decoded.metadata)["docker_port"] == valid


@pytest.mark.parametrize("key", ["docker_port", "minimum_python", "github_username"])
def test_empty_metadata_is_unset_not_invalid(key):
    decoded = decode_recipe(recipe().to_dict() | {"metadata": {key: ""}})
    assert dict(decoded.metadata)[key] == ""


@pytest.mark.parametrize(
    ("invalid", "expected_hint"),
    [
        ("@octocat", "Drop the leading '@': use 'octocat'."),
        ("-user", USERNAME_HINT),
        ("_user", USERNAME_HINT),
        ("user.name", USERNAME_HINT),
        ("user name", USERNAME_HINT),
        ("a" * 40, USERNAME_HINT),
    ],
)
def test_invalid_metadata_github_username_error(invalid, expected_hint):
    with pytest.raises(ConfigurationError) as exc_info:
        decode_recipe(recipe().to_dict() | {"metadata": {"github_username": invalid}})
    assert f"Invalid GitHub username: {invalid!r}." in str(exc_info.value)
    assert exc_info.value.hint == expected_hint


# Legacy accounts may end in or repeat a hyphen; Enterprise Managed Users
# carry an underscore suffix.
@pytest.mark.parametrize(
    "valid",
    ["octocat", "user-name-123", "a", "user-", "a--b", "octocat_acme", "a" * 39],
)
def test_valid_metadata_github_username(valid):
    decoded = decode_recipe(
        recipe().to_dict() | {"metadata": {"github_username": valid}}
    )
    assert dict(decoded.metadata)["github_username"] == valid


@pytest.mark.parametrize("invalid", ["my-package", "123pkg", "pkg name", "pkg.name"])
def test_invalid_context_package_name_error(invalid):
    current = dict(recipe().context)
    current["PACKAGE_NAME"] = invalid
    with pytest.raises(ConfigurationError) as exc_info:
        decode_recipe(recipe().to_dict() | {"context": current})
    assert f"Invalid package name: {invalid!r}." in str(exc_info.value)
    assert (
        exc_info.value.hint
        == "Package name must be a valid Python identifier (e.g., 'my_package')."
    )


@pytest.mark.parametrize("invalid", ["foo/bar", "foo\\bar", "foo\0bar", "", ".", ".."])
def test_invalid_context_project_name_error(invalid):
    current = dict(recipe().context)
    current["PROJECT_NAME"] = invalid
    with pytest.raises(ConfigurationError) as exc_info:
        decode_recipe(recipe().to_dict() | {"context": current})
    assert f"Invalid project name: {invalid!r}." in str(exc_info.value)
    assert (
        exc_info.value.hint
        == "Project name cannot contain slashes or null bytes, and cannot be empty, '.', or '..'."
    )


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


def test_the_highest_layer_to_enable_a_hook_manager_picks_the_pair():
    configured = establish_recipe(UserConfig(pre_commit=True, prek=False))

    def hooks(recipe, opinions):
        return {
            s.tool: (s.enabled, s.layer)
            for s in recipe.selections(opinions)
            if s.tool in {Tool.PRE_COMMIT, Tool.PREK}
        }

    # A template's prek displaces the configured pre-commit.
    assert hooks(configured, {"prek": True}) == {
        Tool.PREK: (True, SelectionLayer.TEMPLATE),
        Tool.PRE_COMMIT: (False, SelectionLayer.TEMPLATE),
    }
    # A template that only switches prek off leaves the configured choice.
    assert hooks(configured, {"prek": False})[Tool.PRE_COMMIT] == (
        True,
        SelectionLayer.FALLBACK,
    )
    # The project's recorded choice outranks the template's.
    chosen = replace(configured, tools=((Tool.PRE_COMMIT, True),))
    assert hooks(chosen, {"prek": True}) == {
        Tool.PREK: (False, SelectionLayer.PROJECT),
        Tool.PRE_COMMIT: (True, SelectionLayer.PROJECT),
    }
    # Both enabled in one layer is a real conflict, left for validation.
    both = replace(configured, tools=((Tool.PRE_COMMIT, True), (Tool.PREK, True)))
    assert all(enabled for enabled, _ in hooks(both, {}).values())


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
    original_write = executor.fs.write_bytes

    def fail_after_write(path, content):
        original_write(path, content)
        if path == Path("pyproject.toml" if failure == "recipe" else "protostar.lock"):
            raise OSError("late write failure")

    # Every text write lands in write_bytes.
    mocker.patch.object(executor.fs, "write_bytes", side_effect=fail_after_write)
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
    args = argparse.Namespace(force_merge=True)
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
        "protostar.cli.tui.launch.edit_variables",
        side_effect=AssertionError("no prompts"),
    )

    with pytest.raises(MissingTemplateVariablesError) as caught:
        handle_init(argparse.Namespace(from_path=str(source), variables=["REGION=eu"]))

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
    prompt = mocker.patch("protostar.cli.tui.launch.edit_variables")

    with pytest.raises(MissingTemplateVariablesError):
        handle_init(argparse.Namespace(from_path=str(source)))

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
        "protostar.cli.tui.launch.edit_variables",
        side_effect=lambda draft, config, flagged, **_: replace(
            draft, variables=(*draft.variables, ("TIER", "gold"))
        ),
    )

    handle_init(argparse.Namespace(from_path=str(source), variables=["REGION=eu"]))

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
        "protostar.cli.tui.launch.edit_variables",
        side_effect=AssertionError("nothing is missing"),
    )

    handle_init(argparse.Namespace(variables=["TIER=gold"]))

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
        handle_init(argparse.Namespace(from_path=str(source), variables=variables))


def test_var_flags_need_a_template(tmp_path, monkeypatch, mocker):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())

    with pytest.raises(InvalidUsageError, match="needs a template"):
        handle_init(argparse.Namespace(variables=["REGION=eu"]))


def test_dry_run_has_no_recipe_or_lock_write(tmp_path, monkeypatch, mocker):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    mocker.patch(
        "protostar.cli.main.UserConfig.load", return_value=UserConfig(ruff=False)
    )
    mocker.patch("shutil.which", return_value="/mock/command")
    with pytest.raises(SystemExit) as error:
        handle_init(argparse.Namespace(dry_run=True))
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
    second = EnvironmentManifest(recipe=replace(recipe(), ide=IDEType.VSCODE))
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
            and 'ide = "vscode"' in content
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
        "protostar.cli.tui.launch.review_changes",
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

    handle_init(argparse.Namespace(from_path=str(source), DockerModule=flag))

    blueprint = engines[-1].request.template_blueprint
    assert blueprint is not None
    selections = {
        s.tool: s.enabled
        for s in engines[-1].request.recipe.selections(blueprint.opinions(None))
    }
    assert selections[Tool.DOCKER] is expected
    assert any(isinstance(m, DockerModule) for m in engines[-1].modules) is expected


def test_captured_recipe_docker_wins_over_a_later_template_opinion(
    tmp_path, monkeypatch, mocker
):
    """An initialized project keeps its captured intent when the template changes."""
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        edit_recipe(
            '[project]\nname="foreign"\n',
            replace(recipe(), tools=((Tool.DOCKER, False),)),
        )
    )
    source = tmp_path / "blueprint.toml"
    source.write_text('name="custom"\ndocker=true\n')
    engines = _capture_init_engines(mocker)

    handle_init(argparse.Namespace(from_path=str(source)))

    blueprint = engines[-1].request.template_blueprint
    assert blueprint is not None
    selections = {
        s.tool: s.enabled
        for s in engines[-1].request.recipe.selections(blueprint.opinions(None))
    }
    assert selections[Tool.DOCKER] is False
    assert any(isinstance(m, DockerModule) for m in engines[-1].modules) is False


def _cli_template_pyproject(tmp_path, monkeypatch, mocker, **flags):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    engines = _capture_init_engines(mocker)
    handle_init(argparse.Namespace(template_name="cli", **flags))
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
    handle_init(argparse.Namespace(template_name=template, **flags))
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

    second = edit_recipe(first, replace(recipe(), ide=IDEType.VSCODE))

    assert second == first.replace('ide = "none"', 'ide = "vscode"')


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

    updated = tomllib.loads(
        edit_recipe(scattered, replace(recipe(), ide=IDEType.VSCODE))
    )

    assert updated["tool"]["protostar"]["ide"] == "vscode"
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


# ---- what a recorded recipe may say, and exactly how it fails ---- #

INVALID_RECIPE_HINT = (
    "Correct the schema-v1 recipe fields; see docs/usage/project-recipes.md."
)
FORGE = "https://github.com/acme/template"
PLAIN_URL = "https://example.com/acme/protostar.toml"


def template_recipe(**source: Any) -> dict[str, Any]:
    """Returns recipe data whose template source is exactly ``source``."""
    return recipe().to_dict() | {"mode": "template", "source": source}


def recipe_with_source(source: object) -> dict[str, Any]:
    """Returns recipe data for a template whose source is any value."""
    return recipe().to_dict() | {"mode": "template", "source": source}


def assert_invalid(data: object) -> None:
    with pytest.raises(ConfigurationError) as error:
        decode_recipe(data)
    assert str(error.value) == "Invalid [tool.protostar] project recipe."
    assert error.value.hint == INVALID_RECIPE_HINT


def test_an_invalid_recipe_says_what_to_correct():
    assert_invalid("not a table")


def test_a_tooling_only_recipe_has_no_source():
    assert decode_recipe(recipe().to_dict()).source is None


@pytest.mark.parametrize(
    "source",
    [
        {"origin": "remote", "locator": FORGE, "ref": "v1"},
        {"origin": "remote", "locator": FORGE, "path": "sub", "ref": "v1"},
        {"origin": "remote", "locator": PLAIN_URL},
        {"origin": "local", "locator": "templates/mine"},
        {"origin": "built-in", "locator": next(iter(builtin_template_aliases()))},
    ],
)
def test_every_kind_of_source_decodes_as_recorded(source):
    decoded = decode_recipe(template_recipe(**source)).source

    assert decoded == RecipeSource(
        TemplateOrigin(source["origin"]),
        source["locator"],
        source.get("path", ""),
        source.get("ref"),
    )


BUILT_IN = next(iter(builtin_template_aliases()))


@pytest.mark.parametrize(
    "source",
    [
        "not a table",
        {"origin": "local"},
        {"locator": "x"},
        {"origin": "local", "locator": "x", "extra": 1},
        {"origin": "local", "locator": 5},
        {"origin": "local", "locator": ""},
        {"origin": "nowhere", "locator": "x"},
        {"origin": "remote", "locator": FORGE, "path": 1, "ref": "v1"},
        {"origin": "remote", "locator": FORGE, "ref": 1},
        {"origin": "remote", "locator": FORGE, "ref": ""},
        {"origin": "local", "locator": "x", "path": "sub"},
        {"origin": "local", "locator": "x", "ref": "v1"},
        {"origin": "built-in", "locator": BUILT_IN, "path": "sub"},
        {"origin": "built-in", "locator": BUILT_IN, "ref": "v1"},
        {"origin": "local", "locator": "a/../b"},
        {"origin": "local", "locator": "a\\b"},
        {"origin": "local", "locator": "a\x00b"},
        {"origin": "local", "locator": "C:b"},
        {"origin": "remote", "locator": FORGE + ".git", "ref": "v1"},
        {"origin": "remote", "locator": FORGE},
        {"origin": "remote", "locator": FORGE, "path": "./sub", "ref": "v1"},
        {"origin": "remote", "locator": FORGE + "/tree/v1", "ref": "v1"},
        {"origin": "remote", "locator": FORGE + "/tree/main/sub", "ref": "v1"},
        {"origin": "remote", "locator": FORGE + "/blob/main/protostar.toml"},
        {"origin": "remote", "locator": "http://github.com/acme/template"},
        {"origin": "remote", "locator": PLAIN_URL, "ref": "v1"},
        {"origin": "remote", "locator": PLAIN_URL, "path": "sub"},
    ],
)
def test_a_malformed_source_is_invalid(source):
    assert_invalid(recipe_with_source(source))


def test_a_source_must_be_present_for_a_template_recipe():
    assert_invalid(recipe().to_dict() | {"mode": "template"})


def test_a_forge_source_that_names_its_path_decodes_it():
    source = decode_recipe(
        template_recipe(origin="remote", locator=FORGE, path="sub", ref="v1")
    ).source

    assert source is not None
    assert source.path == "sub"
    assert source.ref == "v1"


@pytest.mark.parametrize(
    "context",
    [
        {"CURRENT_YEAR": "20x6"},
        {"CURRENT_YEAR": "202"},
        {"PYTHON_VERSION": "3.99"},
    ],
)
def test_the_recorded_context_must_be_well_formed(context):
    data = recipe().to_dict()
    data["context"] = data["context"] | context

    assert_invalid(data)


@pytest.mark.parametrize(
    "options",
    [
        ["fast"],
        {"1st": True},
        {"fast": 1},
        {"fast": "Not A Choice!"},
        {"fast": ["x"]},
    ],
)
def test_recorded_options_are_booleans_or_choices(options):
    assert_invalid(recipe().to_dict() | {"options": options})


def test_recorded_options_that_are_booleans_or_choices_decode():
    decoded = decode_recipe(
        recipe().to_dict() | {"options": {"fast": True, "mode": "strict"}}
    )

    assert dict(decoded.options) == {"fast": True, "mode": "strict"}


@pytest.mark.parametrize(
    "metadata",
    [
        {"description": ["a"]},
        {"description": 5},
        {"license": 5},
        {"docker_port": ["8000"]},
        {"docker_port": True},
        {"docker_port": 3.5},
        {"supported_os": [1]},
        {"supported_os": ["Linux", 1]},
        {"supported_os": {"os": "Linux"}},
        {"supported_os": 5},
        {"supported_os": "Linux"},
        {"unknown": "x"},
        "description",
    ],
)
def test_recorded_metadata_has_the_shape_of_its_key(metadata):
    data = recipe().to_dict()
    data["metadata"] = metadata

    assert_invalid(data)


def test_recorded_metadata_decodes_with_each_shape():
    data = recipe().to_dict()
    data["metadata"] = {
        "description": "A thing",
        "docker_port": 8080,
        "supported_os": ["Linux", "macOS"],
    }

    decoded = decode_recipe(data)

    assert dict(decoded.metadata) == {
        "description": "A thing",
        "docker_port": 8080,
        "supported_os": ("Linux", "macOS"),
    }


def test_a_recorded_tier_needs_a_template():
    assert_invalid(recipe().to_dict() | {"tier": "strict"})


def test_incompatible_tools_say_how_to_choose():
    with pytest.raises(ConfigurationError) as error:
        validate_tools({Tool.PRE_COMMIT, Tool.PREK})

    assert str(error.value) == (
        "Cannot use both '--pre-commit' and '--prek' simultaneously. "
        "Please choose one git hook manager."
    )
    assert error.value.hint == (
        "Remove either --pre-commit or --prek from your selection."
    )


def test_a_tool_whose_requirement_is_missing_says_what_to_enable():
    with pytest.raises(ConfigurationError) as error:
        validate_tools({Tool.READTHEDOCS})

    assert str(error.value) == (
        "Read the Docs scaffolding requires the Zensical module to be enabled."
    )
    assert error.value.hint == (
        "Enable the Zensical documentation module (--zensical or [tooling] "
        "zensical = true) or remove the Read the Docs module."
    )


def test_a_tool_with_its_requirement_is_accepted():
    validate_tools({Tool.READTHEDOCS, Tool.ZENSICAL})
    validate_tools({Tool.PRE_COMMIT})
    validate_tools(set())


def test_unknown_template_flags_name_every_valid_tool():
    with pytest.raises(ConfigurationError) as error:
        recipe().selections({"imaginary": True})

    assert error.value.hint == (
        "Use recognized tool names with boolean selections: "
        + ", ".join(sorted(tool.value for tool in Tool))
        + "."
    )


def test_a_recipe_reports_only_a_source_path_it_has():
    plain = {"origin": "remote", "locator": FORGE, "ref": "v1"}
    nested = plain | {"path": "sub"}

    assert decode_recipe(template_recipe(**plain)).to_dict()["source"] == plain
    assert decode_recipe(template_recipe(**nested)).to_dict()["source"] == nested


# ---- establishing a recipe ---- #


def test_an_established_recipe_records_the_metadata_it_was_given(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    metadata = {
        "description": "A thing",
        "author_name": "Ada",
        "author_email": "ada@example.com",
    }

    established = establish_recipe(UserConfig(), RecipeIntent(metadata=metadata))

    assert dict(established.metadata) == metadata


def test_an_established_recipe_follows_the_configured_python(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    established = establish_recipe(UserConfig(python_version="3.11"))

    assert established.python == "3.11"
    assert dict(established.context)["PYTHON_VERSION"] == "3.11"


def test_an_unnamed_author_is_a_placeholder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    established = establish_recipe(UserConfig())

    assert dict(established.context)["AUTHOR_NAME"] == "your-name"


def test_a_directory_name_is_normalized_only_in_a_new_unnamed_project(
    tmp_path, monkeypatch
):
    project = tmp_path / "My_Project"
    project.mkdir()
    monkeypatch.chdir(project)

    def name(metadata=None):
        intent = RecipeIntent(metadata=metadata)
        return dict(establish_recipe(UserConfig(), intent).context)["PROJECT_NAME"]

    assert name() == "my-project"
    assert name({"project_name": "My_Project"}) == "My_Project"
    assert name({"name": "My_Project"}) == "My_Project"
    (project / "pyproject.toml").write_text('[project]\nname = "My_Project"\n')
    assert name() == "My_Project"


def test_an_established_recipe_records_the_source_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reference = TemplateReference(
        TemplateOrigin.REMOTE, FORGE, "digest", path="sub", ref="v1"
    )

    established = establish_recipe(UserConfig(), RecipeIntent(reference=reference))

    assert established.source == RecipeSource(TemplateOrigin.REMOTE, FORGE, "sub", "v1")


# ---- reading, editing, and removing the recorded recipe ---- #


def test_an_unsupported_recipe_target_is_named(tmp_path):
    target = tmp_path / "real.toml"
    target.write_text("")
    link = tmp_path / "pyproject.toml"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable")

    with pytest.raises(UnsupportedFilesystemNodeError) as error:
        read_recipe(link)

    assert error.value.path == link
    assert error.value.node_type == "unsupported recipe target"


def test_a_file_without_a_recipe_reads_as_none(tmp_path):
    path = tmp_path / "pyproject.toml"

    assert read_recipe(path) is None
    path.write_text('[project]\nname = "x"\n')
    assert read_recipe(path) is None
    path.write_text("[tool.other]\nx = 1\n")
    assert read_recipe(path) is None


def test_a_tool_entry_that_is_not_a_table_is_not_a_recipe(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text("tool = 5\n")

    with pytest.raises(ConfigurationError, match="Invalid"):
        read_recipe(path)


def test_a_recipe_can_be_written_into_a_file_with_no_tool_tables():
    written = edit_recipe('[project]\nname = "x"\n', recipe())

    assert written.startswith('[project]\nname = "x"\n\n[tool.protostar]\n')
    assert read_recipe_text(written) == recipe()


def read_recipe_text(text: str):
    return decode_recipe(tomllib.loads(text)["tool"]["protostar"])


@pytest.mark.parametrize("content", ["tool = 5\n", "[tool.protostar]\nversion = 2\n"])
def test_editing_refuses_a_recorded_recipe_it_cannot_read(content):
    with pytest.raises(ConfigurationError, match="Invalid"):
        edit_recipe(content, recipe())


def test_editing_a_recipe_leaves_its_tables_in_the_users_order():
    written = edit_recipe("", recipe())
    head, *tables = written.split("\n[tool.protostar.")
    reordered = "\n[tool.protostar.".join([head, *reversed(tables)])
    assert reordered != written

    edited = edit_recipe(reordered, replace(recipe(), ide=IDEType.VSCODE))

    assert edited == reordered.replace('ide = "none"', 'ide = "vscode"')


def test_a_recipe_is_added_beside_a_tool_table_that_holds_its_own_keys():
    written = edit_recipe("[tool]\nfoo = 1\n", recipe())

    assert written.startswith("[tool]\nfoo = 1\n\n[tool.protostar]\n")


def test_removing_a_recipe_from_a_file_without_one_changes_nothing():
    for content in ("", '[project]\nname = "x"\n', "[tool.other]\nx = 1\n"):
        assert remove_recipe(content) == content


@pytest.mark.parametrize("content", ["tool = 5\n", "[tool\n"])
def test_removing_a_recipe_from_unreadable_toml_is_invalid(content):
    with pytest.raises(ConfigurationError, match="Invalid"):
        remove_recipe(content)


def test_removing_the_only_tool_removes_the_banner_with_it():
    banner = "\n".join(BANNER)
    content = (
        f'[project]\nname = "x"\n\n{banner}\n\n# ---- Protostar ---- #\n\n'
        "[tool.hatch.build]\nx = 1\n"
    )

    removed = remove_recipe(edit_recipe(content, recipe()))

    assert removed == '[project]\nname = "x"\n[tool.hatch.build]\nx = 1\n\n'


def test_removing_a_recipe_keeps_the_banner_while_another_tool_remains():
    banner = "\n".join(BANNER)
    content = (
        f'[project]\nname = "x"\n\n{banner}\n\n# ---- Protostar ---- #\n\n'
        "[tool.ruff]\nline-length = 88\n"
    )

    removed = remove_recipe(edit_recipe(content, recipe()))

    assert removed == (
        f'[project]\nname = "x"\n\n{banner}\n\n\n[tool.ruff]\nline-length = 88\n\n'
    )


def test_removing_a_recipe_finds_its_marker_after_sections_without_one():
    content = (
        '[project]\nname = "x"\n\n[tool.ruff]\nx = 1\n\n'
        "# ---- Protostar ---- #\n[tool.protostar]\nversion = 1\n"
    )

    assert remove_recipe(content) == '[project]\nname = "x"\n\n[tool.ruff]\nx = 1\n'


def test_removing_a_recipe_keeps_the_line_breaks_between_other_tables():
    content = (
        '[project]\nname = "x"\n\n[tool.ruff]\nx = 1\n\n'
        "# ---- Protostar ---- #\n\n[tool.protostar]\nversion = 1\n\n"
        "[tool.zzz]\ny = 2\n"
    )

    assert remove_recipe(content) == (
        '[project]\nname = "x"\n\n[tool.ruff]\nx = 1\n[tool.zzz]\ny = 2\n'
    )


# ---- acquiring a recorded source ---- #


@pytest.fixture
def remote_calls(mocker):
    """Fakes the network and the template loader, recording how they are called."""
    listing = mocker.Mock()
    listing.resolve.return_value.revision = "resolved-sha"
    return mocker.Mock(
        list_refs=mocker.patch("protostar.network.list_refs", return_value=listing),
        acquire_remote=mocker.patch(
            "protostar.network.acquire_remote", return_value="bytes"
        ),
        from_remote=mocker.patch(
            "protostar.config.TemplateSource.from_remote", return_value="loaded"
        ),
        listing=listing,
    )


FORGE_SOURCE = RecipeSource(TemplateOrigin.REMOTE, FORGE, "sub", "v1")
FORGE_REMOTE = RemoteSource(FORGE, GitHost.GITHUB, "sub")


def test_a_ref_is_resolved_through_the_repositorys_refs(remote_calls, tmp_path):
    assert FORGE_SOURCE.acquire(tmp_path) == "loaded"

    remote_calls.list_refs.assert_called_once_with(FORGE_REMOTE)
    remote_calls.listing.resolve.assert_called_once_with("v1", FORGE)
    remote_calls.acquire_remote.assert_called_once_with(FORGE_REMOTE, "resolved-sha")
    remote_calls.from_remote.assert_called_once_with(
        RemoteTemplate(FORGE_REMOTE, "bytes", "v1", "resolved-sha")
    )


def test_a_listing_the_caller_has_is_used_instead_of_fetching(remote_calls, tmp_path):
    FORGE_SOURCE.acquire(tmp_path, listing=remote_calls.listing)

    remote_calls.list_refs.assert_not_called()
    remote_calls.listing.resolve.assert_called_once_with("v1", FORGE)


def test_the_recorded_commit_is_used_while_the_recipe_names_the_same_ref(
    remote_calls, tmp_path
):
    recorded = TemplateReference(
        TemplateOrigin.REMOTE, FORGE, "digest", ref="v1", revision="recorded-sha"
    )

    FORGE_SOURCE.acquire(tmp_path, recorded)

    remote_calls.list_refs.assert_not_called()
    remote_calls.acquire_remote.assert_called_once_with(FORGE_REMOTE, "recorded-sha")


@pytest.mark.parametrize(
    "recorded",
    [
        TemplateReference(
            TemplateOrigin.REMOTE, FORGE, "digest", ref="v0", revision="old-sha"
        ),
        TemplateReference(TemplateOrigin.REMOTE, FORGE, "digest", ref="v1"),
        TemplateReference(TemplateOrigin.REMOTE, FORGE, "digest", revision="old-sha"),
    ],
)
def test_a_moved_ref_or_missing_commit_is_resolved_again(
    remote_calls, tmp_path, recorded
):
    FORGE_SOURCE.acquire(tmp_path, recorded)

    remote_calls.list_refs.assert_called_once_with(FORGE_REMOTE)
    remote_calls.acquire_remote.assert_called_once_with(FORGE_REMOTE, "resolved-sha")


def test_a_source_with_no_ref_is_fetched_without_a_revision(remote_calls, tmp_path):
    source = RecipeSource(TemplateOrigin.REMOTE, PLAIN_URL)

    source.acquire(tmp_path)

    remote_calls.list_refs.assert_not_called()
    remote_calls.acquire_remote.assert_called_once_with(source.remote, None)
    remote_calls.from_remote.assert_called_once_with(
        RemoteTemplate(source.remote, "bytes", None, None)
    )


def test_a_local_source_is_loaded_from_under_the_project_root(mocker, tmp_path):
    load = mocker.patch("protostar.config.TemplateSource.load", return_value="loaded")

    result = RecipeSource(TemplateOrigin.LOCAL, "t/protostar.toml").acquire(tmp_path)

    assert result == "loaded"
    load.assert_called_once_with(str(tmp_path / "t/protostar.toml"), built_in=None)


def test_a_built_in_source_is_loaded_from_the_packaged_templates(mocker, tmp_path):
    load = mocker.patch("protostar.config.TemplateSource.load", return_value="loaded")

    RecipeSource(TemplateOrigin.BUILT_IN, BUILT_IN).acquire(tmp_path)

    (target,), options = load.call_args
    assert Path(target).name == f"{BUILT_IN}.toml"
    assert Path(target).parent.name == "templates"
    assert options == {"built_in": BUILT_IN}


# ---- inspecting a source before acquiring it ---- #


@pytest.fixture
def inspected(mocker):
    """Records what ``inspect`` examines and what it then acquires."""
    return mocker.Mock(
        capture=mocker.patch("protostar.review_workspace.capture_node"),
        acquire=mocker.patch.object(RecipeSource, "acquire", return_value="acquired"),
    )


def captured(inspected) -> list[Path]:
    return [call.args[0] for call in inspected.capture.call_args_list]


def test_inspecting_a_template_directory_examines_every_file_it_ships(
    inspected, tmp_path
):
    directory = tmp_path / "tpl"
    (directory / "template" / "pkg").mkdir(parents=True)
    (directory / "protostar.toml").write_text("")
    (directory / "template" / "a.txt").write_text("")
    (directory / "template" / "pkg" / "b.txt").write_text("")
    source = RecipeSource(TemplateOrigin.LOCAL, "tpl")
    recorded = TemplateReference(TemplateOrigin.LOCAL, "tpl", "digest")

    result = source.inspect(tmp_path, recorded, "listing")

    assert result == "acquired"
    seen = captured(inspected)
    assert seen[:3] == [directory, directory / "protostar.toml", directory / "template"]
    assert sorted(seen[3:]) == sorted(
        [
            directory / "template" / "a.txt",
            directory / "template" / "pkg",
            directory / "template" / "pkg" / "b.txt",
        ]
    )
    inspected.acquire.assert_called_once_with(tmp_path, recorded, "listing")


def test_inspecting_a_template_file_examines_the_template_beside_it(
    inspected, tmp_path
):
    (tmp_path / "template").mkdir()
    (tmp_path / "template" / "a.txt").write_text("")
    (tmp_path / "mine.toml").write_text("")

    RecipeSource(TemplateOrigin.LOCAL, "mine.toml").inspect(tmp_path)

    assert captured(inspected) == [
        tmp_path / "mine.toml",
        tmp_path / "template",
        tmp_path / "template" / "a.txt",
    ]
    inspected.acquire.assert_called_once_with(tmp_path, None, None)


def test_inspecting_a_built_in_examines_its_packaged_files(inspected, tmp_path):
    RecipeSource(TemplateOrigin.BUILT_IN, BUILT_IN).inspect(tmp_path)

    first = captured(inspected)[0]
    assert first.name == f"{BUILT_IN}.toml"
    assert first.parent.name == "templates"
    assert tmp_path not in first.parents


def test_inspecting_a_remote_source_examines_nothing_on_disk(inspected, tmp_path):
    assert FORGE_SOURCE.inspect(tmp_path, None, "listing") == "acquired"

    inspected.capture.assert_not_called()
    inspected.acquire.assert_called_once_with(tmp_path, None, "listing")


def test_removing_a_recipe_keeps_the_header_of_another_tool():
    content = (
        '[project]\nname = "x"\n\n# ---- Ruff ---- #\n[tool.ruff]\nx = 1\n\n'
        "# ---- Protostar ---- #\n[tool.protostar]\nversion = 1\n"
    )

    assert remove_recipe(content) == (
        '[project]\nname = "x"\n\n# ---- Ruff ---- #\n[tool.ruff]\nx = 1\n'
    )


def test_an_inline_tool_table_counts_as_another_tool_when_a_recipe_goes():
    banner = "\n".join(BANNER)
    content = (
        f"tool = {{protostar = {{version = 1}}, x = 1}}\n\n{banner}\n\n"
        '[project]\nname = "x"\n'
    )

    removed = remove_recipe(content)

    assert banner in removed
    assert tomllib.loads(removed)["tool"] == {"x": 1}


def test_a_recipe_cannot_be_written_inside_an_inline_tool_table():
    with pytest.raises(ConfigurationError) as error:
        edit_recipe("tool = { x = 1 }\n", recipe())

    assert str(error.value) == (
        "Cannot record a [tool.protostar] recipe inside an inline `tool` table."
    )
    assert error.value.hint == (
        "Write `tool = { ... }` as [tool.<name>] tables, then run Protostar again."
    )


def test_a_recorded_tier_that_names_no_tier_keeps_the_reason():
    data = template_recipe(origin="local", locator="x") | {"tier": "bogus"}

    with pytest.raises(ConfigurationError) as error:
        decode_recipe(data)

    assert str(error.value.__cause__) == "The recorded tier names no tier: 'bogus'."
