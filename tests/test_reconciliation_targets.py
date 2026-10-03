"""Contracts of validating declared targets and of writing container artifacts."""

import hashlib
import logging
import sys
import tomllib
from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.documents.locations import Resolution
from protostar.documents.pyproject import declare_contribution
from protostar.errors import ConfigurationError, FileSystemError
from protostar.intent import DependencyGroup, StructuredContribution, StructuredFormat
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.reconciliation import Reconciliation
from protostar.review_workspace import ReviewWorkspace
from protostar.sync_state import FilePolicy, FileState


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return ReviewWorkspace(tmp_path)


def build(workspace, manifest=None):
    return Reconciliation(
        manifest or EnvironmentManifest(),
        UserConfig(),
        workspace,
        workspace,
        workspace,
    )


@pytest.fixture
def reconciliation(workspace):
    return build(workspace)


# ---- validating targets ---- #


@pytest.mark.parametrize("kind", ["injection", "structured", "region", "directory"])
def test_every_kind_of_target_is_validated(reconciliation, kind):
    filesystem = reconciliation.manifest.filesystem
    if kind == "injection":
        filesystem.file_injections["../escape.txt"] = "x"
    elif kind == "structured":
        filesystem.structured["../escape.toml"] = [StructuredContribution("t", "a = 1")]
    elif kind == "region":
        filesystem.regions["../escape.md"] = []
    else:
        filesystem.directories.add("../escape")

    with pytest.raises(ConfigurationError, match="Unsupported contribution target"):
        reconciliation._validate_targets()


def test_a_free_form_pyproject_replacement_is_refused(reconciliation):
    reconciliation.manifest.filesystem.file_injections["pyproject.toml"] = "x"

    with pytest.raises(ConfigurationError) as caught:
        reconciliation._validate_targets()

    assert str(caught.value) == "Free-form pyproject.toml replacement is unsupported."
    assert (
        caught.value.hint
        == "Declare structured contributions; tool.protostar is reserved."
    )


def test_an_injected_renovate_configuration_is_checked_after_rendering(
    reconciliation,
):
    reconciliation.manifest.metadata["project_name"] = "demo"
    reconciliation.manifest.filesystem.file_injections[".github/renovate.json"] = (
        '{"name": "<% PROJECT_NAME %>"}'
    )

    reconciliation._validate_targets()


def test_an_unsupported_yaml_target_is_refused(reconciliation):
    reconciliation.manifest.filesystem.structured["other.yaml"] = [
        StructuredContribution("t", "a: 1\n", format=StructuredFormat.YAML)
    ]

    with pytest.raises(ConfigurationError) as caught:
        reconciliation._validate_targets()

    assert str(caught.value) == "Unsupported YAML contributions."
    assert (
        caught.value.hint == "Declare exactly one producer for a supported YAML target."
    )


def test_two_producers_for_one_yaml_target_are_refused(reconciliation):
    reconciliation.manifest.filesystem.structured[".readthedocs.yaml"] = [
        StructuredContribution("a", "version: 2\n", format=StructuredFormat.YAML),
        StructuredContribution("b", "build: {}\n", format=StructuredFormat.YAML),
    ]

    with pytest.raises(ConfigurationError, match="Unsupported YAML contributions"):
        reconciliation._validate_targets()


def test_a_yaml_target_does_not_stop_the_documents_after_it(reconciliation):
    structured = reconciliation.manifest.filesystem.structured
    structured[".readthedocs.yaml"] = [
        StructuredContribution("t", "version: 2\n", format=StructuredFormat.YAML)
    ]
    structured["zzz.toml"] = [StructuredContribution("t", "not = [valid")]

    with pytest.raises(ConfigurationError):
        reconciliation._validate_targets()


def test_a_held_document_does_not_stop_the_documents_after_it(
    reconciliation, monkeypatch
):
    structured = reconciliation.manifest.filesystem.structured
    structured["a.toml"] = [StructuredContribution("t", "x = 1\n")]
    structured["b.toml"] = [StructuredContribution("t", "y = 1\n")]
    Path("b.toml").write_text("[broken", encoding="utf-8")
    resolve = reconciliation._resolve
    monkeypatch.setattr(
        reconciliation,
        "_resolve",
        lambda target: (
            Resolution(None, None) if target == "a.toml" else resolve(target)
        ),
    )

    with pytest.raises(ConfigurationError, match="Syntax error in existing"):
        reconciliation._validate_targets()


def test_a_malformed_existing_document_is_reported_with_the_parser_detail(
    reconciliation,
):
    Path("conf").mkdir()
    Path("conf/demo.toml").write_text("[broken", encoding="utf-8")
    reconciliation.manifest.metadata["project_name"] = "demo"
    reconciliation.manifest.filesystem.structured["conf/<% PROJECT_NAME %>.toml"] = [
        StructuredContribution("t", "x = 1\n")
    ]
    with pytest.raises(tomllib.TOMLDecodeError) as parser:
        tomllib.loads("[broken")

    with pytest.raises(ConfigurationError) as caught:
        reconciliation._validate_targets()

    assert str(caught.value) == (
        "Syntax error in existing workspace file: conf/<% PROJECT_NAME %>.toml\n"
        f"Details: {parser.value}\n"
        "Protostar cannot safely merge configurations into a malformed file. "
        "Please fix the syntax error and re-run the command."
    )


@pytest.mark.parametrize(
    "declare",
    [
        lambda d: d.add("requests>=2"),
        lambda d: d.add_dev("pytest>=8"),
        lambda d: d.add_docs("zensical>=1"),
        lambda d: d.add_include(DependencyGroup.DEV, DependencyGroup.DOCS),
    ],
)
def test_any_dependency_declaration_checks_for_an_ancestor_workspace(
    tmp_path, monkeypatch, declare
):
    (tmp_path / "pyproject.toml").write_text("[broken", encoding="utf-8")
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.chdir(root)
    reconciliation = build(ReviewWorkspace(root))
    declare(reconciliation.manifest.dependencies)

    with pytest.raises(ConfigurationError, match="Malformed ancestor project"):
        reconciliation._validate_targets()


def test_a_contribution_that_moves_the_resolver_checks_for_an_ancestor_workspace(
    tmp_path, monkeypatch
):
    (tmp_path / "pyproject.toml").write_text("[broken", encoding="utf-8")
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.chdir(root)
    reconciliation = build(ReviewWorkspace(root))
    reconciliation.manifest.filesystem.structured["pyproject.toml"] = [
        declare_contribution(
            "pyproject.toml", '[project]\nrequires-python = ">=3.12"\n', "t"
        )
    ]

    with pytest.raises(ConfigurationError, match="Malformed ancestor project"):
        reconciliation._validate_targets()


def test_nothing_declared_checks_nothing_above_the_project(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[broken", encoding="utf-8")
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.chdir(root)
    reconciliation = build(ReviewWorkspace(root))

    reconciliation._validate_targets()


# ---- container artifacts ---- #


def docker(workspace, port=None):
    manifest = EnvironmentManifest()
    manifest.tooling.wants_docker = True
    if port:
        manifest.metadata["docker_port"] = port
    return build(workspace, manifest)


def dockerfile(workspace):
    return workspace.contents["Dockerfile"].decode()


def test_a_project_without_a_runtime_entry_runs_its_package(workspace):
    reconciliation = docker(workspace)

    reconciliation._write_docker_artifacts()

    assert 'CMD ["python", "-m", ' in dockerfile(workspace)


@pytest.mark.parametrize(
    "declare",
    [
        lambda m: m.dependencies.add("typer"),
        lambda m: m.filesystem.add_structured(
            "pyproject.toml", '[project.scripts]\ndemo = "demo:main"\n', producer="t"
        ),
    ],
)
def test_a_command_line_project_starts_through_its_entry_point(workspace, declare):
    reconciliation = docker(workspace)
    reconciliation.manifest.metadata["project_name"] = "demo"
    declare(reconciliation.manifest)

    reconciliation._write_docker_artifacts()

    assert 'ENTRYPOINT ["demo"]' in dockerfile(workspace)


def test_a_project_with_other_scripts_does_not_start_through_an_entry_point(
    workspace,
):
    reconciliation = docker(workspace)
    reconciliation.manifest.filesystem.add_structured(
        "pyproject.toml", '[tool.x]\nscripts = "none"\n', producer="t"
    )

    reconciliation._write_docker_artifacts()

    assert "ENTRYPOINT" not in dockerfile(workspace)


@pytest.mark.parametrize(("port", "exposed"), [(None, "8000"), (9000, "9000")])
def test_a_web_project_exposes_its_declared_port_or_the_default(
    workspace, port, exposed
):
    reconciliation = docker(workspace, port)
    reconciliation.manifest.dependencies.add("fastapi")

    reconciliation._write_docker_artifacts()

    assert f"EXPOSE {exposed}\n" in dockerfile(workspace)


def test_writing_the_container_artifacts_is_logged(workspace, caplog):
    reconciliation = docker(workspace)
    caplog.set_level(logging.DEBUG, logger="protostar")

    reconciliation._write_docker_artifacts()

    assert (
        "Scaffolded container runtime ignore configurations (.dockerignore)"
        in caplog.messages
    )
    assert "Scaffolded Dockerfile" in caplog.messages


@pytest.mark.parametrize("failing", ["read", "write"])
def test_a_failed_dockerignore_names_the_operation_path_and_cause(
    workspace, monkeypatch, failing
):
    Path(".dockerignore").write_text("mine\n", encoding="utf-8")
    reconciliation = docker(workspace)
    error = OSError("denied")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(
        workspace, "read_text" if failing == "read" else "write_text", fail
    )

    with pytest.raises(FileSystemError) as caught:
        reconciliation._write_docker_artifacts()

    assert caught.value.operation == "scaffold container runtime ignore configurations"
    assert caught.value.path == ".dockerignore"
    assert caught.value.original is error
    assert caught.value.__cause__ is error


def test_a_failed_dockerfile_names_the_operation_path_and_cause(workspace, monkeypatch):
    reconciliation = docker(workspace)
    error = OSError("denied")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(reconciliation, "_write_generated", fail)

    with pytest.raises(FileSystemError) as caught:
        reconciliation._write_docker_artifacts()

    assert caught.value.operation == (
        "scaffold container runtime configurations (Dockerfile)"
    )
    assert caught.value.path == "Dockerfile"
    assert caught.value.original is error
    assert caught.value.__cause__ is error


def test_overwrite_ignores_the_dockerignore_the_project_has(workspace):
    Path(".dockerignore").write_text("mine\n", encoding="utf-8")
    reconciliation = docker(workspace)
    reconciliation.manifest.collision_strategy = CollisionStrategy.OVERWRITE

    reconciliation._write_docker_artifacts()

    assert "mine" not in workspace.contents[".dockerignore"].decode()


# ---- IDE settings, initial state, and seeds ---- #


def test_ide_settings_are_indented_by_four_spaces_in_an_empty_object(workspace):
    Path(".vscode").mkdir()
    Path(".vscode/settings.json").write_text("{}\n", encoding="utf-8")
    reconciliation = build(workspace)
    reconciliation.manifest.ide_settings = {"a": {"b": 1}}

    reconciliation._write_ide_settings()

    assert workspace.contents[".vscode/settings.json"] == (
        b'{\n    "a": {\n        "b": 1\n    }\n}\n'
    )


def test_a_new_reconciliation_has_read_no_state(reconciliation):
    assert reconciliation._committed is None
    assert reconciliation._state_bytes is None


@pytest.mark.skipif(sys.platform == "win32", reason="Requires unprivileged symlinks")
def test_a_released_seed_is_checked_against_the_explicit_root_not_the_callers_directory(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "a.txt").write_text("seed\n", encoding="utf-8")
    caller = tmp_path / "caller"
    caller.mkdir()
    # An unrelated symlink in the caller's directory must not affect this project.
    (caller / "a.txt").symlink_to(root / "a.txt")
    monkeypatch.chdir(caller)
    workspace = ReviewWorkspace(root)
    reconciliation = build(workspace)
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(
        FileState(
            "a.txt", FilePolicy.SEED, digest=hashlib.sha256(b"seed\n").hexdigest()
        )
    )

    reconciliation._release_undeclared_seeds()

    assert workspace.removed == {"a.txt"}
