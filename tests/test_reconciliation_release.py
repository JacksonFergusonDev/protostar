"""Contracts of letting go of retired seeds and undeclared generated files."""

import sys
from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.errors import ConfigurationError, FileSystemError
from protostar.manifest import (
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    Severity,
)
from protostar.merge import (
    MISSING,
    ConflictReason,
    ConflictSides,
    MergeConflict,
    MergeLocation,
    ResolutionChoice,
)
from protostar.reconciliation import Reconciliation
from protostar.review_workspace import ReviewWorkspace
from protostar.sync_state import FilePolicy, FileState


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


def seed(path):
    return FileState(path, FilePolicy.SEED, digest="a" * 64, retired=True)


def generated(path, baseline="generated\n"):
    return FileState(path, FilePolicy.TEXT, baseline)


def retracted(path, base, local, *, line=None):
    return MergeConflict(
        MergeLocation(path),
        ConflictReason.RETRACTED,
        ConflictSides(base, local, MISSING, line=line),
    )


def open_warning(conflict):
    return DiagnosticEvent(
        DiagnosticPhase.EXECUTOR,
        f"Kept your version of {conflict.location.file}: it conflicts with the update.",
        Severity.WARNING,
        conflict=conflict,
    )


def settled_note(conflict, choice, kept):
    return DiagnosticEvent(
        DiagnosticPhase.EXECUTOR,
        f"Resolved conflict in {conflict.location.file} by {kept}.",
        Severity.INFO,
        resolved=conflict.settle({conflict.id: choice}),
    )


def paths(reconciliation):
    return [record.path for record in reconciliation.candidate_state.files]


# ---- the ownership policy check ---- #


def test_a_file_record_of_another_policy_is_a_configuration_error(workspace):
    reconciliation = build(workspace, generated("notes.txt"))

    with pytest.raises(ConfigurationError) as caught:
        reconciliation._file_record(Path("notes.txt"), FilePolicy.TOML)

    assert str(caught.value) == "Conflicting file ownership policy."
    assert caught.value.hint == "Keep the tracked file policy unchanged."


def test_a_file_record_is_returned_for_its_own_policy_and_none_without_one(workspace):
    record = generated("notes.txt")
    reconciliation = build(workspace, record)

    assert reconciliation._file_record(Path("notes.txt"), FilePolicy.TEXT) is record
    assert reconciliation._file_record(Path("other.txt"), FilePolicy.TEXT) is None


# ---- retired seeds ---- #


def test_a_retired_seed_the_project_deleted_is_forgotten_and_the_rest_are_settled(
    workspace,
):
    Path("kept.txt").write_text("my edits\n", encoding="utf-8")
    reconciliation = build(workspace, seed("gone.txt"), seed("kept.txt"))

    reconciliation._settle_retired()

    assert paths(reconciliation) == ["kept.txt"]
    assert reconciliation.diagnostics == [
        open_warning(retracted("kept.txt", MISSING, "my edits\n"))
    ]


def test_every_unsettled_retired_seed_is_reported_and_kept(workspace):
    Path("a.txt").write_text("a edits\n", encoding="utf-8")
    Path("b.txt").write_text("b edits\n", encoding="utf-8")
    reconciliation = build(workspace, seed("a.txt"), seed("b.txt"))

    reconciliation._settle_retired()

    assert paths(reconciliation) == ["a.txt", "b.txt"]
    assert reconciliation.diagnostics == [
        open_warning(retracted("a.txt", MISSING, "a edits\n")),
        open_warning(retracted("b.txt", MISSING, "b edits\n")),
    ]
    assert workspace.removed == set()


def test_a_retired_seed_reads_undecodable_bytes_with_replacement_characters(
    workspace,
):
    Path("a.txt").write_bytes(b"caf\xe9\n")
    reconciliation = build(workspace, seed("a.txt"))

    reconciliation._settle_retired()

    assert reconciliation.diagnostics == [
        open_warning(retracted("a.txt", MISSING, "caf�\n"))
    ]


@pytest.mark.parametrize(
    ("choice", "kept", "removed"),
    [
        (ResolutionChoice.LOCAL, "keeping local content", set()),
        (ResolutionChoice.DESIRED, "taking the update", {"a.txt"}),
    ],
)
def test_a_settled_retired_seed_is_released_and_taking_the_update_deletes_it(
    workspace, choice, kept, removed
):
    Path("a.txt").write_text("a edits\n", encoding="utf-8")
    Path("b.txt").write_text("b edits\n", encoding="utf-8")
    conflict = retracted("a.txt", MISSING, "a edits\n")
    reconciliation = build(
        workspace,
        seed("a.txt"),
        seed("b.txt"),
        resolutions={conflict.id: choice},
    )

    reconciliation._settle_retired()

    assert reconciliation.diagnostics == [
        settled_note(conflict, choice, kept),
        open_warning(retracted("b.txt", MISSING, "b edits\n")),
    ]
    assert paths(reconciliation) == ["b.txt"]
    assert workspace.removed == removed


# ---- generated files nothing declares any more ---- #


def test_an_unedited_generated_file_is_deleted_and_the_rest_are_released(workspace):
    Path("a.txt").write_text("generated\n", encoding="utf-8")
    Path("b.txt").write_text("generated\n", encoding="utf-8")
    reconciliation = build(workspace, generated("a.txt"), generated("b.txt"))

    reconciliation._release_undeclared_generated()

    assert workspace.removed == {"a.txt", "b.txt"}
    assert paths(reconciliation) == []
    assert reconciliation.diagnostics == []


def test_a_generated_file_the_project_deleted_is_forgotten_and_the_rest_continue(
    workspace,
):
    Path("b.txt").write_text("generated\n", encoding="utf-8")
    reconciliation = build(workspace, generated("a.txt"), generated("b.txt"))

    reconciliation._release_undeclared_generated()

    assert workspace.removed == {"b.txt"}
    assert paths(reconciliation) == []


def test_a_declared_generated_file_is_left_alone(workspace):
    Path("justfile").write_text("edited\n", encoding="utf-8")
    reconciliation = build(workspace, generated("justfile"), generated("a.txt"))
    reconciliation.manifest.tooling.wants_just = True
    Path("a.txt").write_text("generated\n", encoding="utf-8")

    reconciliation._release_undeclared_generated()

    assert paths(reconciliation) == ["justfile"]
    assert workspace.removed == {"a.txt"}


def test_a_file_that_receives_a_region_is_declared_at_its_rendered_path(workspace):
    Path("docs").mkdir()
    Path("docs/demo.md").write_text("edited\n", encoding="utf-8")
    reconciliation = build(workspace, generated("docs/demo.md"))
    reconciliation.manifest.metadata["project_name"] = "demo"
    reconciliation.manifest.filesystem.regions["docs/<% PROJECT_NAME %>.md"] = {
        "template:notes": "region\n"
    }

    reconciliation._release_undeclared_generated()

    assert paths(reconciliation) == ["docs/demo.md"]
    assert workspace.removed == set()


@pytest.mark.parametrize(
    ("baseline", "local", "base"),
    [
        ("generated\n", "my edits\n", "generated\n"),
        # A file that was generated empty has no baseline text to show.
        ("", "my edits\n", MISSING),
    ],
)
def test_an_edited_generated_file_is_a_whole_file_retraction_until_settled(
    workspace, baseline, local, base
):
    Path("a.txt").write_text(local, encoding="utf-8")
    Path("b.txt").write_text("b edits\n", encoding="utf-8")
    reconciliation = build(workspace, generated("a.txt", baseline), generated("b.txt"))

    reconciliation._release_undeclared_generated()

    assert reconciliation.diagnostics == [
        open_warning(retracted("a.txt", base, local, line=0)),
        open_warning(retracted("b.txt", "generated\n", "b edits\n", line=0)),
    ]
    assert paths(reconciliation) == ["a.txt", "b.txt"]
    assert workspace.removed == set()


def test_an_empty_generated_file_without_baseline_text_is_unedited(workspace):
    Path("a.txt").write_bytes(b"")
    reconciliation = build(workspace, generated("a.txt", ""))

    reconciliation._release_undeclared_generated()

    assert workspace.removed == {"a.txt"}
    assert reconciliation.diagnostics == []


def test_an_edited_generated_file_reads_undecodable_bytes_with_replacement(
    workspace,
):
    Path("a.txt").write_bytes(b"caf\xe9\n")
    reconciliation = build(workspace, generated("a.txt"))

    reconciliation._release_undeclared_generated()

    assert reconciliation.diagnostics == [
        open_warning(retracted("a.txt", "generated\n", "caf�\n", line=0))
    ]


@pytest.mark.parametrize(
    ("choice", "kept", "removed"),
    [
        (ResolutionChoice.LOCAL, "keeping local content", set()),
        (ResolutionChoice.DESIRED, "taking the update", {"a.txt"}),
    ],
)
def test_a_settled_generated_file_is_released_and_taking_the_update_deletes_it(
    workspace, choice, kept, removed
):
    Path("a.txt").write_text("my edits\n", encoding="utf-8")
    Path("b.txt").write_text("b edits\n", encoding="utf-8")
    conflict = retracted("a.txt", "generated\n", "my edits\n", line=0)
    reconciliation = build(
        workspace,
        generated("a.txt"),
        generated("b.txt"),
        resolutions={conflict.id: choice},
    )

    reconciliation._release_undeclared_generated()

    assert reconciliation.diagnostics == [
        settled_note(conflict, choice, kept),
        open_warning(retracted("b.txt", "generated\n", "b edits\n", line=0)),
    ]
    assert paths(reconciliation) == ["b.txt"]
    assert workspace.removed == removed


def test_a_failed_removal_names_the_operation_path_and_cause(workspace, monkeypatch):
    Path("a.txt").write_text("generated\n", encoding="utf-8")
    reconciliation = build(workspace, generated("a.txt"))
    error = OSError("denied")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(workspace, "remove_file", fail)

    with pytest.raises(FileSystemError) as caught:
        reconciliation._release_undeclared_generated()

    assert caught.value.operation == "remove generated file"
    assert caught.value.path == "a.txt"
    assert caught.value.original is error
    assert caught.value.__cause__ is error


@pytest.mark.skipif(sys.platform == "win32", reason="Requires unprivileged symlinks")
def test_a_generated_file_is_checked_against_the_explicit_root_not_the_callers_directory(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "a.txt").write_text("generated\n", encoding="utf-8")
    caller = tmp_path / "caller"
    caller.mkdir()
    # An unrelated symlink in the caller's directory must not affect this project.
    (caller / "a.txt").symlink_to(root / "a.txt")
    monkeypatch.chdir(caller)
    workspace = ReviewWorkspace(root)
    reconciliation = build(workspace, generated("a.txt"))

    reconciliation._release_undeclared_generated()

    assert workspace.removed == {"a.txt"}
