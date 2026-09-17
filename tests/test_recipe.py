"""Recipe persistence and its separation from ownership and secret answers."""

import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from protostar.config import TemplateBlueprint, UserConfig
from protostar.errors import (
    ConfigurationError,
    FileSystemError,
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
        {"bindings": {"TOKEN": "not-an-env-name"}},
        {"bindings": {"CURRENT_YEAR": "YEAR"}},
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


def test_binding_values_exist_only_in_memory(monkeypatch):
    bound = replace(recipe(), bindings=(("TOKEN", "PROJECT_TOKEN"),))
    with pytest.raises(ConfigurationError) as error:
        bound.rendering_context()
    assert error.value.hint is not None
    assert "PROJECT_TOKEN" in error.value.hint
    monkeypatch.setenv("PROJECT_TOKEN", "extremely-private-value")
    assert bound.rendering_context()["TOKEN"] == "extremely-private-value"
    assert "extremely-private-value" not in edit_recipe("", bound)
    assert "trust" not in bound.to_dict()


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
        if path == Path(
            "pyproject.toml" if failure == "recipe" else ".protostar.lock.toml"
        ):
            raise OSError("late write failure")

    mocker.patch.object(executor.fs, "write_text", side_effect=fail_after_write)
    with pytest.raises(FileSystemError):
        executor.execute()
    assert target.read_bytes() == original
    assert target.stat().st_mode & 0o777 == 0o640
    assert not (tmp_path / ".protostar.lock.toml").exists()


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
    state = tomllib.loads((tmp_path / ".protostar.lock.toml").read_text())
    assert "protostar" not in str(state.get("files"))


def test_exact_local_source_load(tmp_path):
    path = tmp_path / "blueprint.toml"
    path.write_text('name="source"\nruff=false\n')
    source = RecipeSource(TemplateOrigin.LOCAL, "blueprint.toml")
    blueprint = source.load(tmp_path, {})
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

    def capture(engine, request):
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


def test_bound_template_and_optout_keep_independent_contributions(
    tmp_path, monkeypatch, mocker
):
    import argparse

    from protostar.cli.main import handle_init
    from protostar.models import ExecutionResult

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJECT_TOKEN", "private-template-answer")
    source = tmp_path / "blueprint.toml"
    source.write_text(
        'name="custom"\nruff=true\n[dev.pyproject]\nforeign="""[tool.ruff]\nline-length=99\n"""\n[files]\n"custom.txt"="<% TOKEN %>"\n'
    )
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())
    mocker.patch("shutil.which", return_value="/mock/command")
    engines = []

    def capture(engine, request):
        engines.append(engine)
        return ExecutionResult(frozenset(), frozenset(), ())

    mocker.patch("protostar.cli.ui._run_engine", side_effect=capture)
    args = argparse.Namespace(
        from_path=str(source),
        template_context={},
        bind=["TOKEN=PROJECT_TOKEN"],
        docker=None,
        RuffModule=False,
    )
    handle_init(args)
    engine = engines[-1]
    assert "private-template-answer" not in edit_recipe("", engine.request.recipe)
    assert not any(m.config_key == "ruff" for m in engine.modules)
    manifest = engine.plan()
    assert any(
        "line-length=99" in c.content
        for c in manifest.filesystem.structured["pyproject.toml"]
    )
    assert (
        manifest.filesystem.file_injections["custom.txt"] == "private-template-answer"
    )
    assert "protostar" not in str(
        [c.content for c in manifest.filesystem.structured["pyproject.toml"]]
    )


def test_unbound_custom_template_fails_without_prompt_or_mutation(
    tmp_path, monkeypatch, mocker
):
    import argparse

    from protostar.cli.main import handle_init

    monkeypatch.chdir(tmp_path)
    source = tmp_path / "blueprint.toml"
    source.write_text('[files]\n"custom.txt"="<% TOKEN %>"\n')
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())
    prompt = mocker.patch(
        "protostar.cli.main.resolve_missing_variables",
        side_effect=AssertionError("no prompts"),
    )
    with pytest.raises(ConfigurationError, match="bindings"):
        handle_init(argparse.Namespace(from_path=str(source), docker=None))
    prompt.assert_not_called()
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "blueprint.toml",
        "config.toml",
    ]


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
        [First(), Second()], UserConfig(), InitRequest(recipe=recipe())
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
    lock = tmp_path / ".protostar.lock.toml"
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
        if path == Path(".protostar.lock.toml") or (
            failure == "recipe"
            and "[tool.protostar]" in content
            and "docker = true" in content
        ):
            raise OSError("late failure")

    mocker.patch.object(executor.fs, "write_text", side_effect=fail_after_write)
    with pytest.raises(FileSystemError):
        executor.execute()
    assert (target.read_bytes(), lock.read_bytes()) == before
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
