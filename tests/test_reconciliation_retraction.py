"""Contracts of retracting structured documents that nothing declares any more."""

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from protostar import reconciliation as reconciliation_module
from protostar.config import UserConfig
from protostar.errors import FileSystemError
from protostar.jsonc_ast import encode_jsonc_baseline
from protostar.manifest import EnvironmentManifest
from protostar.merge import ConflictReason, ResolutionChoice
from protostar.reconciliation import Reconciliation
from protostar.review_workspace import ReviewWorkspace
from protostar.sync_state import FilePolicy, FileState, encode_toml_baseline
from protostar.toml_ast import DEFAULT_TOML_SPEC
from protostar.yaml_ast import YamlDocumentSpec, encode_yaml_baseline

OWNED = {"owned": {"answer": 42}}
TOML_FILE = "[owned]\nanswer = 42\n[mine]\nx = 1\n"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return ReviewWorkspace(tmp_path)


def build(workspace, *records, resolutions=None):
    reconciliation = Reconciliation(
        EnvironmentManifest(),
        UserConfig(),
        workspace,
        workspace,
        workspace,
        resolutions=resolutions or {},
    )
    for record in records:
        reconciliation.candidate_state = reconciliation.candidate_state.with_file(
            record
        )
    return reconciliation


def toml_record(path="custom.toml", owned=OWNED):
    return FileState(path, FilePolicy.TOML, encode_toml_baseline(owned))


def yaml_record(path="custom.yaml", owned=None):
    return FileState(path, FilePolicy.YAML, encode_yaml_baseline(owned or {"a": 1}))


def jsonc_record(path="custom.json", owned=None):
    return FileState(path, FilePolicy.JSONC, encode_jsonc_baseline(owned or {"a": 1}))


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


def paths(reconciliation):
    return [record.path for record in reconciliation.candidate_state.files]


def text(workspace, path):
    return workspace.contents[path].decode()


def test_an_unedited_owned_unit_is_removed_and_foreign_content_stays(workspace):
    write("custom.toml", TOML_FILE)
    reconciliation = build(workspace, toml_record())

    reconciliation._release_undeclared_documents()

    assert text(workspace, "custom.toml") == "[mine]\nx = 1\n"
    assert paths(reconciliation) == []
    assert reconciliation.diagnostics == []


def test_a_file_left_with_nothing_is_deleted_and_released(workspace):
    write("zensical.toml", '[project]\nsite_name = "docs"\n')
    reconciliation = build(
        workspace,
        toml_record("zensical.toml", {"project": {"site_name": "docs"}}),
    )

    reconciliation._release_undeclared_documents()

    # A seed is retracted too, though the user owns it once written.
    assert workspace.removed == {"zensical.toml"}
    assert paths(reconciliation) == []


def test_a_retained_path_is_retracted_when_the_document_goes(workspace, monkeypatch):
    spec = replace(
        DEFAULT_TOML_SPEC,
        policy=replace(DEFAULT_TOML_SPEC.policy, retained_paths=frozenset({("keep",)})),
    )
    monkeypatch.setattr(reconciliation_module, "toml_spec", lambda path: spec)
    write("custom.toml", "[keep]\nx = 1\n[other]\ny = 2\n")
    reconciliation = build(workspace, toml_record(owned={"keep": {"x": 1}}))

    reconciliation._release_undeclared_documents()

    assert text(workspace, "custom.toml") == "[other]\ny = 2\n"


def test_a_yaml_document_without_a_spec_is_retracted_under_a_generic_one(workspace):
    write("custom.yaml", "a: 1\nb: 2\n")
    reconciliation = build(workspace, yaml_record())

    reconciliation._release_undeclared_documents()

    assert text(workspace, "custom.yaml") == "b: 2\n"
    assert paths(reconciliation) == []


def test_a_retained_yaml_path_is_retracted_when_the_document_goes(
    workspace, monkeypatch
):
    base = YamlDocumentSpec("custom.yaml")
    spec = replace(
        base,
        policy=replace(base.policy, retained_paths=frozenset({("keep",)})),
    )
    monkeypatch.setattr(reconciliation_module, "yaml_spec", lambda path: spec)
    write("custom.yaml", "keep: 1\nother: 2\n")
    reconciliation = build(workspace, yaml_record(owned={"keep": 1}))

    reconciliation._release_undeclared_documents()

    assert text(workspace, "custom.yaml") == "other: 2\n"


@pytest.mark.parametrize(
    ("record", "file", "edited"),
    [
        (toml_record(), "custom.toml", "[owned]\nanswer = 99\n"),
        (yaml_record(), "custom.yaml", "a: 99\n"),
        (jsonc_record(), "custom.json", '{"a": 99}\n'),
    ],
)
def test_an_edited_owned_unit_is_kept_with_a_retracted_conflict(
    workspace, record, file, edited
):
    write(file, edited)
    reconciliation = build(workspace, record)

    reconciliation._release_undeclared_documents()

    assert [e.conflict.reason for e in reconciliation.diagnostics] == [
        ConflictReason.RETRACTED
    ]
    assert paths(reconciliation) == [file]
    assert workspace.contents == {}


@pytest.mark.parametrize(
    ("choice", "removed"),
    [(ResolutionChoice.DESIRED, True), (ResolutionChoice.LOCAL, False)],
)
@pytest.mark.parametrize(
    ("record", "file", "edited"),
    [
        (toml_record(), "custom.toml", "[owned]\nanswer = 99\n"),
        (yaml_record(), "custom.yaml", "a: 99\n"),
        (jsonc_record(), "custom.json", '{"a": 99}\n'),
    ],
)
def test_a_settled_retraction_releases_the_document_either_way(
    workspace, record, file, edited, choice, removed
):
    write(file, edited)
    first = build(workspace, record)
    first._release_undeclared_documents()
    [event] = first.diagnostics

    second = build(workspace, record, resolutions={event.conflict.id: choice})
    second._release_undeclared_documents()

    assert paths(second) == []
    assert (workspace.removed == {file}) is removed
    assert [e.resolved.resolution for e in second.diagnostics] == [choice]


def test_a_document_the_user_deleted_is_forgotten_and_the_rest_continue(workspace):
    write("second.toml", TOML_FILE)
    reconciliation = build(
        workspace, toml_record("first.toml"), toml_record("second.toml")
    )

    reconciliation._release_undeclared_documents()

    assert text(workspace, "second.toml") == "[mine]\nx = 1\n"
    assert paths(reconciliation) == []


def test_a_document_with_nothing_to_retract_does_not_stop_the_rest(workspace):
    write("first.toml", "[mine]\nx = 1\n")
    write("second.toml", TOML_FILE)
    reconciliation = build(
        workspace, toml_record("first.toml", {}), toml_record("second.toml")
    )

    reconciliation._release_undeclared_documents()

    assert "first.toml" not in workspace.contents
    assert text(workspace, "second.toml") == "[mine]\nx = 1\n"
    assert paths(reconciliation) == []


def test_a_failed_retraction_write_names_the_operation_path_and_cause(
    workspace, monkeypatch
):
    write("custom.toml", TOML_FILE)
    reconciliation = build(workspace, toml_record())
    error = OSError("disk full")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(workspace, "write_text", fail)

    with pytest.raises(FileSystemError) as caught:
        reconciliation._release_undeclared_documents()

    assert caught.value.operation == "retract configuration"
    assert caught.value.path == "custom.toml"
    assert caught.value.original is error
    assert caught.value.__cause__ is error


@pytest.mark.skipif(sys.platform == "win32", reason="Requires unprivileged symlinks")
def test_a_document_is_checked_against_the_explicit_root_not_the_callers_directory(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "custom.toml").write_text(TOML_FILE, encoding="utf-8")
    caller = tmp_path / "caller"
    caller.mkdir()
    # An unrelated symlink in the caller's directory must not affect this project.
    (caller / "custom.toml").symlink_to(root / "custom.toml")
    monkeypatch.chdir(caller)
    workspace = ReviewWorkspace(root)
    reconciliation = build(workspace, toml_record())

    reconciliation._release_undeclared_documents()

    assert text(workspace, "custom.toml") == "[mine]\nx = 1\n"


def test_an_edited_seed_is_a_retraction_conflict_not_a_kept_edit(workspace):
    write("zensical.toml", '[project]\nsite_name = "mine"\n')
    reconciliation = build(
        workspace,
        toml_record("zensical.toml", {"project": {"site_name": "docs"}}),
    )

    reconciliation._release_undeclared_documents()

    assert [e.conflict.reason for e in reconciliation.diagnostics] == [
        ConflictReason.RETRACTED
    ]
    assert reconciliation.preserved == []
    assert paths(reconciliation) == ["zensical.toml"]


def test_a_document_is_retracted_under_its_own_specs_spelling_of_names(workspace):
    # Zensical reads the quoted "pymdownx.details" and the nested table as one.
    write("zensical.toml", '[project.markdown_extensions."pymdownx.details"]\n')
    reconciliation = build(
        workspace,
        toml_record(
            "zensical.toml",
            {"project": {"markdown_extensions": {"pymdownx": {"details": {}}}}},
        ),
    )

    reconciliation._release_undeclared_documents()

    assert workspace.removed == {"zensical.toml"}
    assert reconciliation.diagnostics == []
