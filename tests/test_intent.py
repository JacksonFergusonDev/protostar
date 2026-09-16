"""Contracts for PR A's pure declarations and schema boundaries."""

import hashlib
import json
import tomllib
from pathlib import Path

import pytest

from protostar.appends import append_marker_blocks
from protostar.config import TemplateBlueprint, UserConfig
from protostar.errors import ConfigurationError
from protostar.executor import SystemExecutor
from protostar.intent import (
    AppendContribution,
    ContributionPolicy,
    DependencyGroup,
    TemplateOrigin,
)
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.models import InitRequest
from protostar.orchestrator import Orchestrator


def test_reference_hashes_raw_selected_bytes_before_interpolation(tmp_path):
    source = tmp_path / "template.toml"
    raw = b'name = "<% ANSWER %>"\r\nversion = "2.0"\r\n'
    source.write_bytes(raw)
    first = TemplateBlueprint.load(str(source), {"ANSWER": "one"}, display_name="alias")
    second = TemplateBlueprint.load(str(source), {"ANSWER": "two"})
    assert first.reference is not None
    assert second.reference is not None
    assert first.reference.origin == TemplateOrigin.LOCAL
    assert first.reference.locator == source.resolve().as_posix()
    assert (
        first.reference.digest
        == second.reference.digest
        == hashlib.sha256(raw).hexdigest()
    )
    assert first.reference.version == "2.0"
    assert "ANSWER" not in json.dumps(first.reference.to_dict())
    assert "one" not in json.dumps(first.reference.to_dict())


def test_builtin_reference_never_uses_installation_path(tmp_path):
    source = tmp_path / "api.toml"
    source.write_text('name = "API"')
    blueprint = TemplateBlueprint.load(str(source), built_in="api")
    assert blueprint.reference is not None
    assert blueprint.reference.origin == TemplateOrigin.BUILT_IN
    assert blueprint.reference.locator == "api"


def test_remote_reference_never_uses_extraction_path(tmp_path, mocker):
    source = tmp_path / "download.toml"
    source.write_bytes(b'name = "remote"')
    mocker.patch("protostar.config.resolve_remote_template", return_value=source)
    url = "https://example.test/template.toml"
    blueprint = TemplateBlueprint.load(url)
    assert blueprint.reference is not None
    assert blueprint.reference.origin == TemplateOrigin.REMOTE
    assert blueprint.reference.locator == url
    assert blueprint.reference.digest == hashlib.sha256(source.read_bytes()).hexdigest()


def test_planning_preserves_reference_and_region_identity_without_side_effects(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "template.toml"
    source.write_text(
        'name = "test"\n[appends.".envrc".environment]\ncontent = "export A=1"'
    )
    blueprint = TemplateBlueprint.load(str(source))
    request = InitRequest(template_blueprint=blueprint)
    write = mocker.patch.object(Path, "write_text")
    process = mocker.patch("subprocess.run")
    engine = Orchestrator([], UserConfig(), request)
    first = engine.plan()
    assert first.to_dict() == engine.plan().to_dict()
    blueprint.appends[".envrc"]["environment"] = AppendContribution(
        "environment", "export A=2"
    )
    second = engine.plan()
    assert (
        first.filesystem.regions[".envrc"][0].id
        == second.filesystem.regions[".envrc"][0].id
    )
    assert first.template_reference == blueprint.reference
    assert (
        first.to_dict()["template_reference"] == request.to_dict()["template_reference"]
    )
    assert Orchestrator([], UserConfig()).plan().to_dict()["template_reference"] is None
    write.assert_not_called()
    process.assert_not_called()


@pytest.mark.parametrize(
    "path",
    [
        ".protostar.lock.toml",
        "./.protostar.lock.toml",
        "../outside",
        "/absolute",
        "uv.lock",
        "uv.lock/child",
        ".protostar.lock.toml/child",
        "nested/uv.lock",
    ],
)
def test_reserved_and_escaping_targets_rejected(path):
    filesystem = EnvironmentManifest().filesystem
    for operation in (
        lambda: filesystem.add_file_injection(path, "seed"),
        lambda: filesystem.add_region(path, "region", identity="module:test"),
        lambda: filesystem.add_structured(path, "[tool.test]", producer="module:test"),
        lambda: filesystem.add_directory(path),
    ):
        with pytest.raises(ConfigurationError) as error:
            operation()
        assert error.value.hint


@pytest.mark.parametrize(
    "payload",
    [
        '[project]\ndependencies = ["requests"]',
        '[project.optional-dependencies]\nweb = ["requests"]',
        "[dependency-groups]\ndev = []",
        '[tool.uv.sources]\nrequests = {path = "../requests"}',
        "[tool.test]\n__replace__ = false",
        "[[tool.test.records]]\n__remove__ = true",
    ],
)
def test_unsafe_generic_payloads_rejected_in_schema_and_manifest(payload):
    with pytest.raises(ConfigurationError) as error:
        TemplateBlueprint._parse("[dev.pyproject]\nconfig = '''" + payload + "'''")
    assert error.value.hint
    with pytest.raises(ConfigurationError):
        EnvironmentManifest().filesystem.add_structured(
            "pyproject.toml", payload, producer="module:test"
        )


@pytest.mark.parametrize(
    "content",
    [
        '[appends]\n".envrc" = "anonymous"',
        '[appends]\n".envrc" = ["anonymous"]',
        '[appends.".envrc".named]\ncontent = 1',
        '[appends.".envrc".named]\ncontent = "a"\nextra = "b"',
        '[appends."pyproject.toml".named]\ncontent = "[tool.test]"',
        '[files]\n".envrc" = "seed"\n[appends.".envrc".named]\ncontent = "append"',
    ],
)
def test_anonymous_invalid_and_ambiguous_regions_rejected(content):
    with pytest.raises(ConfigurationError) as error:
        TemplateBlueprint._parse(content)
    assert error.value.hint


def test_personal_metadata_is_seed_only_and_tooling_retains_variables():
    manifest = EnvironmentManifest()
    manifest.filesystem.add_structured(
        "pyproject.toml",
        '[project]\ndescription = "personal"\n[project.scripts]\n<% PROJECT_NAME %> = "<% PACKAGE_NAME %>.main:app"\n[tool.ruff]\nline-length = 100',
        producer="template:test",
    )
    seed, managed = manifest.filesystem.structured["pyproject.toml"]
    assert seed.policy == ContributionPolicy.SEED_ONLY
    assert "description" in seed.content
    assert managed.policy == ContributionPolicy.MANAGED
    assert "description" not in managed.content
    assert "<% PROJECT_NAME %>" in managed.content
    assert "<% PACKAGE_NAME %>" in managed.content


def test_existing_personal_metadata_is_preserved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "pyproject.toml"
    original = '[project]\nname = "user"\ndescription = "user description"\n'
    source.write_text(original)
    manifest = EnvironmentManifest()
    manifest.filesystem.add_structured(
        "pyproject.toml",
        '[project]\ndescription = "default"',
        producer="module:PythonCore",
    )
    executor = SystemExecutor(manifest, UserConfig())
    executor._append_files()
    assert source.read_text() == original
    assert not executor.journal.touched_paths


def test_initializer_output_receives_seed_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "pyproject.toml"
    manifest = EnvironmentManifest()
    manifest.filesystem.add_structured(
        "pyproject.toml",
        '[project]\ndescription = "seed"',
        producer="module:PythonCore",
    )
    executor = SystemExecutor(manifest, UserConfig())
    executor.journal.record_mutation(source)
    source.write_text('[project]\nname = "initialized"\ndescription = "uv default"')
    executor._append_files()
    assert tomllib.loads(source.read_text())["project"]["description"] == "seed"


def test_typed_include_applied_before_resolver_and_rolls_back(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    lock = tmp_path / "uv.lock"
    original = '[project]\nname = "demo"\n[dependency-groups]\ndev = ["pytest"]\ndocs = ["zensical"]\n'
    pyproject.write_text(original)
    lock.write_bytes(b"original lock")
    blueprint = TemplateBlueprint._parse(
        'dependency_includes = [{group = "dev", include = "docs"}]\ndocs_dependencies = ["zensical"]'
    )
    manifest = Orchestrator(
        [], UserConfig(), InitRequest(template_blueprint=blueprint, force_merge=True)
    ).plan()
    executor = SystemExecutor(manifest, UserConfig())

    def run(command, timeout=None):
        assert command == ["uv", "lock"]
        assert {"include-group": "docs"} in tomllib.loads(pyproject.read_text())[
            "dependency-groups"
        ]["dev"]
        assert {"pyproject.toml", "uv.lock"} <= executor.journal.touched_paths
        lock.write_bytes(b"resolver lock")

    process = mocker.patch.object(executor.process_runner, "run", side_effect=run)
    executor._apply_dependency_includes()
    executor._install_dependencies()
    assert process.call_count == 1
    assert executor.journal.rollback().succeeded
    assert pyproject.read_text() == original
    assert lock.read_bytes() == b"original lock"


def test_include_only_locks_once_and_identical_repeat_is_noop(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    manifest.dependencies.add_include(DependencyGroup.DEV, DependencyGroup.DOCS)
    executor = SystemExecutor(manifest, UserConfig())
    process = mocker.patch.object(executor.process_runner, "run")
    executor._apply_dependency_includes()
    executor._apply_dependency_includes()
    process.assert_called_once_with(["uv", "lock"], timeout=600)
    assert manifest.dependencies.to_dict()["resolver_footprint"] == {
        "paths": ["pyproject.toml", "uv.lock"]
    }


def test_duplicate_region_and_cycle_rejected():
    manifest = EnvironmentManifest()
    manifest.filesystem.add_region(".envrc", "a", identity="module:environment")
    with pytest.raises(ConfigurationError, match="Duplicate append identity"):
        manifest.filesystem.add_region(".envrc", "b", identity="module:environment")
    manifest.dependencies.add_include(DependencyGroup.DEV, DependencyGroup.DOCS)
    with pytest.raises(ConfigurationError, match="Cyclic"):
        manifest.dependencies.add_include(DependencyGroup.DOCS, DependencyGroup.DEV)


def test_named_region_update_preserves_surrounding_bytes_and_merge_preserves_local():
    first = append_marker_blocks(
        "prefix\n", [AppendContribution("module:environment", "A=1")], Path(".envrc")
    )
    assert first is not None
    first += "suffix\n"
    changed = [AppendContribution("module:environment", "A=2")]
    assert append_marker_blocks(first, changed, Path(".envrc")) is None
    result = append_marker_blocks(first, changed, Path(".envrc"), overwrite=True)
    assert result is not None
    assert result.startswith("prefix\n")
    assert result.endswith("suffix\n")
    assert result.count("Protostar Region: module:environment") == 2
    assert "A=2" in result
    assert "A=1" not in result


@pytest.mark.parametrize(
    "content",
    [
        "# --- Protostar Injection: deadbeef ---\na\n# --- End Protostar Injection ---",
        "# --- Protostar Region: one ---",
        "# --- End Protostar Region: one ---",
        "# --- Protostar Region: one ---\n# --- Protostar Region: two ---",
        "# --- Protostar Region: one ---\n# --- End Protostar Region: two ---",
    ],
)
def test_legacy_and_malformed_region_boundaries_fail(content):
    with pytest.raises(ConfigurationError):
        append_marker_blocks(content, [AppendContribution("one", "a")], Path(".envrc"))


@pytest.mark.parametrize(
    "payload", ['project = "broken"', 'tool = "broken"', '[tool]\nuv = "broken"']
)
def test_generic_configuration_cannot_replace_dependency_ancestors(payload):
    with pytest.raises(ConfigurationError, match="ancestors"):
        EnvironmentManifest().filesystem.add_structured(
            "pyproject.toml", payload, producer="module:test"
        )


def test_equivalent_path_spellings_share_policy_and_collision_checks():
    manifest = EnvironmentManifest()
    manifest.filesystem.add_structured(
        "./pyproject.toml", '[project]\ndescription = "seed"', producer="module:test"
    )
    assert "./pyproject.toml" not in manifest.filesystem.structured
    assert (
        manifest.filesystem.structured["pyproject.toml"][0].policy
        == ContributionPolicy.SEED_ONLY
    )
    with pytest.raises(ConfigurationError, match="Ambiguous"):
        manifest.filesystem.add_file_injection("pyproject.toml", "free-form")
    with pytest.raises(ConfigurationError, match="Ambiguous"):
        TemplateBlueprint._parse(
            '[files]\n"./.envrc" = "seed"\n[appends.".envrc".named]\ncontent = "region"'
        )


def test_remote_equivalent_locators_and_immutable_revision(tmp_path, mocker):
    source = tmp_path / "remote.toml"
    source.write_text('name = "remote"')
    mocker.patch("protostar.config.resolve_remote_template", return_value=source)
    commit = "a" * 40
    blob = TemplateBlueprint.load(
        f"https://github.com/user/repo/blob/{commit}/template.toml"
    )
    raw = TemplateBlueprint.load(
        f"https://raw.githubusercontent.com/user/repo/{commit}/template.toml"
    )
    assert blob.reference is not None
    assert raw.reference is not None
    assert blob.reference == raw.reference
    assert blob.reference.source_revision == commit
    assert blob.reference.identity == raw.reference.identity


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@example.test/template.toml",
        "https://example.test/template.toml?token=secret",
    ],
)
def test_remote_credentials_never_enter_provenance(url, mocker):
    fetch = mocker.patch("protostar.config.resolve_remote_template")
    with pytest.raises(ConfigurationError, match="credentials"):
        TemplateBlueprint.load(url)
    fetch.assert_not_called()


def test_ancestor_workspace_rejected_before_mutation_or_resolution(
    tmp_path, monkeypatch, mocker
):
    ancestor = tmp_path / "pyproject.toml"
    ancestor.write_text(
        '[project]\nname = "owner"\n[tool.uv.workspace]\nmembers = ["packages/*"]'
    )
    root = tmp_path / "packages" / "member"
    root.mkdir(parents=True)
    monkeypatch.chdir(root)
    manifest = EnvironmentManifest()
    manifest.dependencies.add_include(DependencyGroup.DEV, DependencyGroup.DOCS)
    executor = SystemExecutor(manifest, UserConfig())
    run = mocker.patch.object(executor.process_runner, "run")
    with pytest.raises(ConfigurationError, match="transaction boundary"):
        executor.execute()
    run.assert_not_called()
    assert not (root / "pyproject.toml").exists()
    assert not executor.journal.touched_paths


def test_excluded_ancestor_workspace_is_allowed(tmp_path):
    from protostar.workspace import validate_resolver_workspace

    (tmp_path / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\nexclude = ["packages/member"]'
    )
    root = tmp_path / "packages" / "member"
    root.mkdir(parents=True)
    validate_resolver_workspace(root)


def test_requires_python_declares_and_executes_conditional_lock(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "pyproject.toml"
    source.write_text('[project]\nrequires-python = ">=3.12"')
    manifest = EnvironmentManifest()
    manifest.collision_strategy = CollisionStrategy.OVERWRITE
    manifest.filesystem.add_structured(
        "pyproject.toml",
        '[project]\nrequires-python = ">=3.13"',
        producer="template:test",
    )
    contribution = manifest.filesystem.structured["pyproject.toml"][0]
    assert contribution.to_dict()["resolver_footprint"] == {
        "paths": ["pyproject.toml", "uv.lock"]
    }
    executor = SystemExecutor(manifest, UserConfig())
    process = mocker.patch.object(executor.process_runner, "run")
    executor._append_files()
    executor._append_files()
    process.assert_called_once_with(["uv", "lock"], timeout=600)


def test_export_schema_describes_named_records_and_excludes_runtime_provenance(
    monkeypatch, capsys
):
    import argparse

    from protostar.cli import schema, ui

    monkeypatch.setattr(ui, "is_json_mode", True)
    with pytest.raises(SystemExit):
        schema.handle_export_schema(argparse.Namespace())
    properties = json.loads(capsys.readouterr().out)["properties"]
    assert "reference" not in properties
    record = properties["appends"]["additionalProperties"]["additionalProperties"]
    assert record["required"] == ["content"]
    assert record["additionalProperties"] is False
    assert properties["dependency_includes"]["items"]["required"] == [
        "group",
        "include",
    ]


def test_wizard_resolution_retains_builtin_reference(mocker, monkeypatch):
    from protostar.wizard import run_init_wizard

    monkeypatch.delenv("PROTOSTAR_BENCHMARK_WIZARD", raising=False)
    mocker.patch("protostar.wizard._should_run_wizard", return_value=True)
    mocker.patch("protostar.wizard.UserConfig.load", return_value=UserConfig())
    mocker.patch("protostar.wizard.select", return_value="api")
    mocker.patch("protostar.wizard.checkbox", return_value=[])
    mocker.patch("protostar.wizard.prompt_metadata", return_value={})
    selections = run_init_wizard()
    assert selections is not None
    assert selections.blueprint is not None
    reference = selections.blueprint.reference
    assert reference is not None
    assert reference.origin == TemplateOrigin.BUILT_IN
    assert reference.locator == "api"
    assert (
        InitRequest(template_blueprint=selections.blueprint).to_dict()[
            "template_reference"
        ]
        == reference.to_dict()
    )


def test_cli_resolution_passes_builtin_reference_to_request(mocker):
    import argparse

    from protostar.cli.main import handle_init

    engine = mocker.patch("protostar.cli.main.Orchestrator")
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())
    mocker.patch("protostar.cli.main.ui._run_engine")
    mocker.patch("protostar.cli.main.resolve_auto_metadata", return_value={})
    handle_init(
        argparse.Namespace(
            template_name="api",
            from_path=None,
            template_context={},
            python_version=None,
            docker=False,
        )
    )
    request = engine.call_args.kwargs["request"]
    assert request.template_reference is not None
    assert request.template_reference.origin == TemplateOrigin.BUILT_IN
    assert request.template_reference.locator == "api"


def test_generated_schema_example_parses_without_legacy_declarations():
    fixture = Path(__file__).parents[1] / "docs" / "fixtures" / "template_schema.toml"
    blueprint = TemplateBlueprint._parse(fixture.read_text())
    assert (
        blueprint.appends[".envrc"]["project_environment"].id == "project_environment"
    )
    assert blueprint.dependency_includes[0].group == DependencyGroup.DEV


def test_late_bound_reserved_target_rejected_before_writes(
    tmp_path, monkeypatch, mocker
):
    root = tmp_path / "uv"
    root.mkdir()
    monkeypatch.chdir(root)
    manifest = EnvironmentManifest()
    manifest.filesystem.add_file_injection("<% PROJECT_NAME %>.lock", "unsafe")
    executor = SystemExecutor(manifest, UserConfig())
    write = mocker.patch.object(executor.fs, "write_text")
    with pytest.raises(ConfigurationError, match="Unsupported contribution target"):
        executor.execute()
    write.assert_not_called()


@pytest.mark.parametrize("name", ["api", "astro", "cli", "dsp", "embedded", "ml"])
def test_all_builtins_use_supported_typed_declarations(name):
    import importlib.resources

    target = importlib.resources.files("protostar.templates").joinpath(f"{name}.toml")
    blueprint = TemplateBlueprint.load(str(target), built_in=name)
    assert blueprint.reference is not None
    assert blueprint.reference.locator == name
    if name == "embedded":
        assert (
            blueprint.appends["justfile"]["microcontroller_recipes"].id
            == "microcontroller_recipes"
        )
