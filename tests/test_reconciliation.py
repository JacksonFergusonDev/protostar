"""Contracts exposed by survivors of the reconciliation mutation run."""

import hashlib
import sys
import tomllib
from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.documents import pyproject_layout
from protostar.errors import FileSystemError
from protostar.manifest import (
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    Severity,
)
from protostar.merge import (
    ConflictReason,
    ConflictSides,
    LineSpan,
    MergeConflict,
    MergeLocation,
    ResolutionChoice,
)
from protostar.migrations import MigrationOutcome, MigrationStep
from protostar.recipe import decode_recipe, establish_recipe
from protostar.reconciliation import Reconciliation
from protostar.review_workspace import LiveWorkspace, ReviewWorkspace
from protostar.sync_state import FilePolicy, FileState


@pytest.fixture
def reconciliation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    workspace = ReviewWorkspace(tmp_path)
    return Reconciliation(
        EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
    )


@pytest.mark.parametrize(
    "record",
    [
        FileState("old.txt", FilePolicy.TEXT, "original"),
        FileState("old.txt", FilePolicy.SEED, retired=True),
    ],
)
def test_seed_migration_cannot_rename_other_policies_or_retired_seeds(
    reconciliation, record
):
    Path("old.txt").write_bytes(b"original")
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(record)

    reconciliation._rename_seed("1.1.0", "old.txt", "new.txt")

    assert reconciliation.candidate_state.files == (record,)
    assert reconciliation.migration_steps == [
        MigrationStep("1.1.0", "old.txt", "new.txt", MigrationOutcome.NOT_OWNED)
    ]
    assert reconciliation.fs.contents == {}
    assert reconciliation.fs.removed == set()
    assert Path("old.txt").read_bytes() == b"original"
    assert not Path("new.txt").exists()


def test_layout_warning_preserves_phase_severity_and_reason(reconciliation):
    reconciliation._layout_warning(Path("config.toml"), "foreign table layout")

    assert reconciliation.diagnostics == [
        DiagnosticEvent(
            DiagnosticPhase.EXECUTOR,
            "Left config.toml unformatted: foreign table layout.",
            Severity.WARNING,
        )
    ]


def test_blocked_seed_rename_keeps_both_files_and_reports_target(reconciliation):
    Path("old.txt").write_bytes(b"local edit")
    Path("new.txt").write_bytes(b"foreign target")
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(
        FileState("old.txt", FilePolicy.SEED)
    )

    reconciliation._rename_seed("1.1.0", "old.txt", "new.txt")

    assert reconciliation.candidate_state.files == ()
    assert reconciliation.migration_steps == [
        MigrationStep("1.1.0", "old.txt", "new.txt", MigrationOutcome.TARGET_EXISTS)
    ]
    assert reconciliation.fs.contents == {}
    assert reconciliation.fs.removed == set()
    assert Path("old.txt").read_bytes() == b"local edit"
    assert Path("new.txt").read_bytes() == b"foreign target"


@pytest.mark.skipif(sys.platform == "win32", reason="Requires unprivileged symlinks")
@pytest.mark.parametrize("operation", ["rename", "remove"])
def test_seed_migration_validates_its_explicit_root_not_the_callers_directory(
    tmp_path, monkeypatch, operation
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "old.txt").write_bytes(b"original")
    caller = tmp_path / "caller"
    caller.mkdir()
    # An unrelated symlink in the caller's directory must not affect this project.
    (caller / "old.txt").symlink_to(root / "old.txt")
    monkeypatch.chdir(caller)
    workspace = ReviewWorkspace(root)
    reconciliation = Reconciliation(
        EnvironmentManifest(), UserConfig(), workspace, workspace, workspace
    )
    record = FileState(
        "old.txt", FilePolicy.SEED, digest=hashlib.sha256(b"original").hexdigest()
    )
    reconciliation.candidate_state = reconciliation.candidate_state.with_file(record)

    if operation == "rename":
        reconciliation._rename_seed("1.1.0", "old.txt", "new.txt")
        assert workspace.contents == {"new.txt": b"original"}
        assert reconciliation.candidate_state.files[0].path == "new.txt"
    else:
        reconciliation._remove_seed("1.1.0", "old.txt")
        assert reconciliation.candidate_state.files == ()
    assert workspace.removed == {"old.txt"}
    assert (root / "old.txt").read_bytes() == b"original"


def recipe(reconciliation):
    reconciliation.manifest.recipe = establish_recipe(reconciliation.config)
    return reconciliation.manifest.recipe


def test_recipe_can_create_a_missing_pyproject_without_reading_it(reconciliation):
    expected = recipe(reconciliation)
    reconciliation.workspace = LiveWorkspace()

    reconciliation._write_recipe()

    content = reconciliation.fs.contents["pyproject.toml"].decode()
    assert decode_recipe(tomllib.loads(content)["tool"]["protostar"]) == expected
    assert not Path("pyproject.toml").exists()


def test_recipe_write_error_identifies_operation_path_and_cause(
    reconciliation, monkeypatch
):
    recipe(reconciliation)
    error = OSError("disk full")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(reconciliation.fs, "write_text", fail)
    with pytest.raises(FileSystemError) as caught:
        reconciliation._write_recipe()

    assert caught.value.operation == "write project recipe"
    assert caught.value.path == "pyproject.toml"
    assert caught.value.original is error
    assert caught.value.__cause__ is error


def test_recipe_layout_fallback_reports_why_and_preserves_the_recipe(
    reconciliation, monkeypatch
):
    expected = recipe(reconciliation)
    monkeypatch.setattr(
        pyproject_layout, "format_sections", lambda _: "[foreign]\nanswer = 42\n"
    )

    reconciliation._write_recipe()

    content = reconciliation.fs.contents["pyproject.toml"].decode()
    assert decode_recipe(tomllib.loads(content)["tool"]["protostar"]) == expected
    assert reconciliation.diagnostics == [
        DiagnosticEvent(
            DiagnosticPhase.EXECUTOR,
            "Left pyproject.toml unformatted: AST Parity mismatch during pyproject.toml formatting.",
            Severity.WARNING,
        )
    ]


@pytest.mark.parametrize("located", [False, True])
def test_open_conflict_diagnostic_preserves_the_conflict(reconciliation, located):
    conflict = MergeConflict(
        MergeLocation("config.toml", keys=("tool", "ruff") if located else ()),
        ConflictReason.DIVERGED,
        ConflictSides(88, 120, 100),
    )

    reconciliation._report((conflict,), ())

    location = " at tool.ruff" if located else ""
    assert reconciliation.diagnostics == [
        DiagnosticEvent(
            DiagnosticPhase.EXECUTOR,
            f"Kept your version of config.toml{location}: it conflicts with the update.",
            Severity.WARNING,
            conflict=conflict,
        )
    ]


@pytest.mark.parametrize(
    ("choice", "action"),
    [
        (ResolutionChoice.LOCAL, "keeping local content"),
        (ResolutionChoice.DESIRED, "taking the update"),
        (ResolutionChoice.BOTH, "keeping both"),
    ],
)
@pytest.mark.parametrize("located", [False, True])
def test_settled_text_conflict_diagnostic_says_what_was_kept(
    reconciliation, choice, action, located
):
    conflict = MergeConflict(
        MergeLocation("config.txt", lines=LineSpan(2, 1) if located else None),
        ConflictReason.DIVERGED,
        ConflictSides("base\n", "local\n", "update\n", line=1),
        choice,
    )

    reconciliation._report((), (conflict,))

    location = " at line 2" if located else ""
    assert reconciliation.diagnostics == [
        DiagnosticEvent(
            DiagnosticPhase.EXECUTOR,
            f"Resolved conflict in config.txt{location} by {action}.",
            Severity.INFO,
            resolved=conflict,
        )
    ]


def test_proposals_and_preserved_edits_are_reported_without_warning(reconciliation):
    proposal = MergeConflict(MergeLocation("config.txt"), ConflictReason.PROPOSED)
    preserved = MergeConflict(MergeLocation("local.txt"), ConflictReason.PRESERVED)
    settled = MergeConflict(
        MergeLocation("local.txt"),
        ConflictReason.PRESERVED,
        resolution=ResolutionChoice.LOCAL,
    )

    reconciliation._report((), (settled,), (proposal,), (preserved,))

    assert reconciliation.proposals == [proposal]
    assert reconciliation.preserved == [preserved]
    assert reconciliation.diagnostics == [
        DiagnosticEvent(
            DiagnosticPhase.EXECUTOR,
            "Resolved local change in local.txt by keeping local content.",
            Severity.INFO,
            resolved=settled,
        )
    ]


def test_missing_gitignore_contains_only_requested_entries(reconciliation):
    reconciliation.workspace = LiveWorkspace()
    reconciliation.manifest.filesystem.vcs_ignores = {".cache/", "build/"}

    reconciliation._write_ignores()

    assert reconciliation.fs.contents == {".gitignore": b".cache/\nbuild/\n"}


@pytest.mark.parametrize(
    ("method", "operation", "path"),
    [
        (
            "_write_ignores",
            "update workspace ignore manifest (.gitignore)",
            ".gitignore",
        ),
        ("_write_injected_files", "inject boilerplate file", "generated/config.txt"),
        ("_create_directories", "create scaffolding directory", "generated/cache"),
        ("_write_generated", "write generated file", "generated/notes.txt"),
    ],
)
def test_filesystem_failures_preserve_operation_path_and_cause(
    reconciliation, monkeypatch, method, operation, path
):
    error = OSError("disk full")

    def fail(*args, **kwargs):
        raise error

    if method == "_write_ignores":
        reconciliation.manifest.filesystem.vcs_ignores = {".cache/"}
    elif method == "_write_injected_files":
        reconciliation.manifest.filesystem.add_file_injection(path, "desired")
    elif method == "_create_directories":
        reconciliation.manifest.filesystem.add_directory(path)
    boundary = "ensure_directory" if method == "_create_directories" else "write_text"
    monkeypatch.setattr(reconciliation.fs, boundary, fail)

    def run():
        if method == "_write_generated":
            reconciliation._write_generated(Path(path), "desired\n")
        else:
            getattr(reconciliation, method)()

    with pytest.raises(FileSystemError) as caught:
        run()

    assert caught.value.operation == operation
    assert caught.value.path == str(Path(path))
    assert caught.value.original is error
    assert caught.value.__cause__ is error
