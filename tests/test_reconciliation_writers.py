"""Contracts of the writers for injected seeds, justfiles, and directories."""

import hashlib
import logging
import sys
from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.errors import UnsupportedFilesystemNodeError
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
from protostar.review_workspace import LiveWorkspace, ReviewWorkspace
from protostar.sync_state import FilePolicy, FileState


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return ReviewWorkspace(tmp_path)


def build(workspace, *, resolutions=None):
    return Reconciliation(
        EnvironmentManifest(),
        UserConfig(),
        workspace,
        workspace,
        workspace,
        resolutions=resolutions or {},
    )


def digest(content):
    return hashlib.sha256(content.encode()).hexdigest()


def seeded(path, content):
    return FileState(path, FilePolicy.SEED, digest=digest(content))


def inject(reconciliation, path, content):
    reconciliation.manifest.filesystem.add_file_injection(path, content)


def own(reconciliation, *records):
    for record in records:
        reconciliation.candidate_state = reconciliation.candidate_state.with_file(
            record
        )


def deleted_seed(path, content):
    return MergeConflict(
        MergeLocation(path),
        ConflictReason.PRESERVED,
        ConflictSides(MISSING, MISSING, content, line=0),
    )


def test_an_existing_seed_is_skipped_and_the_next_one_is_written(workspace):
    reconciliation = build(workspace)
    Path("a.txt").write_text("mine\n", encoding="utf-8")
    inject(reconciliation, "a.txt", "seed a\n")
    inject(reconciliation, "b.txt", "seed b\n")

    reconciliation._write_injected_files()

    assert reconciliation.diagnostics == [
        DiagnosticEvent(
            DiagnosticPhase.EXECUTOR,
            "Skipping a.txt generation; existing or deleted seed.",
            Severity.SKIP,
        )
    ]
    assert workspace.contents == {"b.txt": b"seed b\n"}
    assert reconciliation.candidate_state.files == (seeded("b.txt", "seed b\n"),)


def test_a_deleted_seed_stays_deleted_and_is_offered_for_restoring(workspace):
    reconciliation = build(workspace)
    own(reconciliation, seeded("a.txt", "seed a\n"))
    inject(reconciliation, "a.txt", "seed a\n")
    inject(reconciliation, "b.txt", "seed b\n")

    reconciliation._write_injected_files()

    assert reconciliation.preserved == [deleted_seed("a.txt", "seed a\n")]
    assert reconciliation.diagnostics == []
    assert workspace.contents == {"b.txt": b"seed b\n"}


@pytest.mark.parametrize(
    ("choice", "kept", "written"),
    [
        (ResolutionChoice.DESIRED, "taking the update", {"a.txt", "b.txt"}),
        (ResolutionChoice.LOCAL, "keeping local content", {"b.txt"}),
    ],
)
def test_a_deleted_seed_is_restored_only_when_the_update_is_chosen(
    workspace, choice, kept, written
):
    conflict = deleted_seed("a.txt", "seed a\n")
    reconciliation = build(workspace, resolutions={conflict.id: choice})
    own(reconciliation, seeded("a.txt", "seed a\n"))
    inject(reconciliation, "a.txt", "seed a\n")
    inject(reconciliation, "b.txt", "seed b\n")

    reconciliation._write_injected_files()

    assert reconciliation.diagnostics == [
        DiagnosticEvent(
            DiagnosticPhase.EXECUTOR,
            f"Resolved local change in a.txt by {kept}.",
            Severity.INFO,
            resolved=conflict.settle({conflict.id: choice}),
        )
    ]
    assert reconciliation.preserved == []
    assert set(workspace.contents) == written


def test_a_seed_held_between_aliases_is_not_written(workspace):
    for held in ("docs/CONTRIBUTING.md", ".github/CONTRIBUTING.md"):
        Path(held).parent.mkdir(exist_ok=True)
        Path(held).write_text("mine\n", encoding="utf-8")
    reconciliation = build(workspace)
    own(reconciliation, seeded("CONTRIBUTING.md", "seed\n"))
    inject(reconciliation, "CONTRIBUTING.md", "seed\n")

    reconciliation._write_injected_files()

    assert workspace.contents == {}
    assert reconciliation.candidate_state.files == (
        seeded("CONTRIBUTING.md", "seed\n"),
    )


def test_writing_a_seed_and_scaffolding_a_directory_are_logged(workspace, caplog):
    reconciliation = build(workspace)
    inject(reconciliation, "a.txt", "seed a\n")
    reconciliation.manifest.filesystem.add_directory("scratch")
    caplog.set_level(logging.DEBUG, logger="protostar")

    reconciliation._write_injected_files()
    reconciliation._create_directories()

    assert "Injected configuration file: a.txt" in caplog.messages
    assert "Scaffolded directory: scratch" in caplog.messages


def test_the_justfile_carries_every_declared_command_group(workspace):
    reconciliation = build(workspace)
    tooling = reconciliation.manifest.tooling
    tooling.wants_just = True
    tooling.just_format_commands = ["format-it"]
    tooling.just_lint_commands = ["lint-it"]
    tooling.just_typecheck_commands = ["typecheck-it"]

    reconciliation._write_justfile()

    text = workspace.contents["justfile"].decode()
    assert "format-it" in text
    assert "lint-it" in text
    assert "typecheck-it" in text


@pytest.mark.skipif(sys.platform == "win32", reason="Requires unprivileged symlinks")
@pytest.mark.parametrize("writer", ["injected", "justfile", "directory"])
def test_writers_check_the_explicit_root_not_the_callers_directory(
    tmp_path, monkeypatch, writer
):
    name = {"injected": "a.txt", "justfile": "justfile", "directory": "scratch"}[writer]
    root = tmp_path / "project"
    root.mkdir()
    if writer == "directory":
        (root / name).mkdir()
    else:
        (root / name).write_text("mine\n", encoding="utf-8")
    caller = tmp_path / "caller"
    caller.mkdir()
    # An unrelated symlink in the caller's directory must not affect this project.
    (caller / name).symlink_to(root / name)
    monkeypatch.chdir(caller)
    workspace = ReviewWorkspace(root)
    reconciliation = build(workspace)
    if writer == "injected":
        inject(reconciliation, name, "seed\n")
        reconciliation._write_injected_files()
    elif writer == "justfile":
        reconciliation.manifest.tooling.wants_just = True
        reconciliation._write_justfile()
    else:
        reconciliation.manifest.filesystem.add_directory(name)
        reconciliation._create_directories()

    assert (root / name).exists()


# ---- node validation on the live disk ---- #


@pytest.fixture
def live(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    boundary = ReviewWorkspace(tmp_path)
    return Reconciliation(
        EnvironmentManifest(), UserConfig(), LiveWorkspace(), boundary, boundary
    )


@pytest.mark.skipif(sys.platform == "win32", reason="Requires unprivileged symlinks")
@pytest.mark.parametrize("case", ["leaf", "ancestor", "directory-expected-file"])
def test_a_node_that_cannot_be_transacted_names_itself(live, tmp_path, case):
    (tmp_path / "real").mkdir()
    (tmp_path / "real/file.txt").write_text("x", encoding="utf-8")
    if case == "leaf":
        (tmp_path / "link").symlink_to(tmp_path / "real/file.txt")
        target, bad, directory = Path("link"), tmp_path / "link", False
    elif case == "ancestor":
        # The leaf does not exist yet; the directory above it is a link.
        (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
        target, bad, directory = Path("link/new.txt"), tmp_path / "link", False
    else:
        target, bad, directory = Path("real"), tmp_path / "real", False

    with pytest.raises(UnsupportedFilesystemNodeError) as caught:
        live._validate_node(target, directory=directory)

    assert caught.value.path == bad
    assert caught.value.node_type == "unsupported transaction target"


def test_a_regular_file_and_a_directory_are_valid_nodes(live, tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "real/file.txt").write_text("x", encoding="utf-8")

    live._validate_node(Path("real/file.txt"))
    live._validate_node(Path("real"), directory=True)
    live._validate_node(Path("real/missing.txt"))


def test_a_file_where_a_directory_is_expected_is_refused(live, tmp_path):
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")

    with pytest.raises(UnsupportedFilesystemNodeError) as caught:
        live._validate_node(Path("file.txt"), directory=True)

    assert caught.value.path == tmp_path / "file.txt"
