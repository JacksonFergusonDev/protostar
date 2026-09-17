import sys
from pathlib import Path

import pytest

from protostar.errors import (
    SecurityViolationError,
    TransactionStateError,
    UnsupportedFilesystemNodeError,
)
from protostar.journal import MutationJournal, TransactionState


def test_journal_create_file(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)
    target = tmp_path / "new_file.txt"

    journal.record_mutation(target)
    target.write_text("hello")

    assert target.exists()
    assert journal.created_paths == frozenset({"new_file.txt"})
    assert journal.touched_paths == frozenset({"new_file.txt"})
    assert journal.mutated_paths == frozenset()

    res = journal.rollback()
    assert res.succeeded
    assert not target.exists()


def test_journal_mutate_file(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)
    target = tmp_path / "existing.txt"
    target.write_text("original")

    journal.record_mutation(target)
    target.write_text("mutated")

    assert target.read_text() == "mutated"
    assert journal.mutated_paths == frozenset({"existing.txt"})

    res = journal.rollback()
    assert res.succeeded
    assert target.read_text() == "original"


def test_journal_create_directory(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)
    target = tmp_path / "new_dir"

    journal.record_mutation(target)
    target.mkdir()

    assert target.is_dir()

    res = journal.rollback()
    assert res.succeeded
    assert not target.exists()


def test_journal_mutate_directory(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)
    target = tmp_path / "existing_dir"
    target.mkdir()

    journal.record_mutation(target)
    # We mutate it by deleting it
    target.rmdir()

    assert not target.exists()

    res = journal.rollback()
    assert res.succeeded
    assert target.is_dir()


def test_journal_create_then_mutate(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)
    target = tmp_path / "file.txt"

    journal.record_mutation(target)
    target.write_text("first")

    # Second mutation shouldn't record the intermediate state
    journal.record_mutation(target)
    target.write_text("second")

    assert target.read_text() == "second"

    res = journal.rollback()
    assert res.succeeded
    assert not target.exists()


def test_journal_idempotent_rollback(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)
    target = tmp_path / "file.txt"
    journal.record_mutation(target)
    target.write_text("hello")

    res1 = journal.rollback()
    assert res1.succeeded
    assert not target.exists()

    # second time does nothing
    res2 = journal.rollback()
    assert res2.succeeded
    assert not target.exists()


def test_journal_cannot_rollback_committed(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)
    target = tmp_path / "file.txt"
    journal.record_mutation(target)
    target.write_text("hello")

    journal.commit()
    with pytest.raises(TransactionStateError):
        journal.rollback()
    assert target.exists()


def test_journal_rejects_mutation_after_rollback(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)
    journal.rollback()

    with pytest.raises(TransactionStateError):
        journal.record_mutation(tmp_path / "later.txt")


def test_journal_rejects_symlink_before_mutation(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("original")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    journal = MutationJournal(tmp_path)

    with pytest.raises(UnsupportedFilesystemNodeError):
        journal.record_mutation(link)

    assert link.is_symlink()
    assert target.read_text() == "original"


def test_journal_rejects_path_outside_workspace(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path / "workspace")

    with pytest.raises(SecurityViolationError):
        journal.record_mutation(tmp_path / "outside.txt")


def test_journal_restores_original_mode(tmp_path: Path) -> None:
    target = tmp_path / "script.sh"
    target.write_text("original")
    target.chmod(0o755)
    journal = MutationJournal(tmp_path)
    journal.record_mutation(target)
    target.write_text("changed")
    target.chmod(0o600)

    result = journal.rollback()

    assert result.succeeded
    assert target.read_text() == "original"
    if sys.platform != "win32":
        assert target.stat().st_mode & 0o777 == 0o755
    assert journal.state is TransactionState.ROLLED_BACK


def test_journal_does_not_delete_untracked_directory_content(tmp_path: Path) -> None:
    created = tmp_path / "created"
    journal = MutationJournal(tmp_path)
    journal.record_mutation(created)
    created.mkdir()
    (created / "external.txt").write_text("untracked")

    first_result = journal.rollback()
    second_result = journal.rollback()

    assert not first_result.succeeded
    assert second_result == first_result
    assert (created / "external.txt").read_text() == "untracked"


def test_journal_continues_after_one_path_fails(tmp_path: Path) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("original")
    blocked_directory = tmp_path / "created"
    journal = MutationJournal(tmp_path)
    journal.record_mutation(existing)
    journal.record_mutation(blocked_directory)
    existing.write_text("changed")
    blocked_directory.mkdir()
    (blocked_directory / "external.txt").write_text("untracked")

    result = journal.rollback()

    assert not result.succeeded
    assert result.failed_paths == (blocked_directory,)
    assert existing.read_text() == "original"


def test_record_tree_creation_absent(tmp_path: Path) -> None:
    """Tests that record_tree_creation uses rmtree for new trees."""
    journal = MutationJournal(workspace_root=tmp_path)
    target = tmp_path / ".git"

    # Record tree creation
    journal.record_tree_creation(target)

    # Simulate git init creating a nested structure
    target.mkdir()
    (target / "hooks").mkdir()
    (target / "hooks" / "pre-commit").write_text("echo test")

    assert target.exists()

    journal.rollback()

    # The entire tree should be removed
    assert not target.exists()


def test_record_tree_creation_existing(tmp_path: Path) -> None:
    """Tests that record_tree_creation falls back to mutation for existing trees."""
    journal = MutationJournal(workspace_root=tmp_path)
    target = tmp_path / ".git"

    # Pre-create the tree
    target.mkdir()
    journal.record_tree_creation(target)

    # Check that it recorded as a directory, not a created tree
    state = journal._journal[target]
    assert state.kind == "directory"
