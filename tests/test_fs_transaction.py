import os
import sys
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protostar.errors import FileSystemError, UnsupportedFilesystemNodeError
from protostar.fs_transaction import TransactionAwareFS
from protostar.journal import MutationJournal


def test_write_text_tracks_nested_parents_and_rolls_back(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)
    fs = TransactionAwareFS(journal)
    target = tmp_path / "a" / "b" / "file.txt"

    fs.write_text(target, "content")

    assert journal.created_paths == frozenset({"a", "a/b", "a/b/file.txt"})
    assert journal.rollback().succeeded
    assert not (tmp_path / "a").exists()


def test_write_text_restores_existing_content_and_mode(tmp_path: Path) -> None:
    target = tmp_path / "script.sh"
    target.write_text("original")
    target.chmod(0o755)
    journal = MutationJournal(tmp_path)
    fs = TransactionAwareFS(journal)

    fs.write_text(target, "changed")
    if sys.platform != "win32":
        assert target.stat().st_mode & 0o777 == 0o755
    assert journal.rollback().succeeded

    assert target.read_text() == "original"
    if sys.platform != "win32":
        assert target.stat().st_mode & 0o777 == 0o755


def test_write_text_rejects_symlink_target(tmp_path: Path) -> None:
    original = tmp_path / "original.txt"
    original.write_text("original")
    link = tmp_path / "link.txt"
    link.symlink_to(original)
    fs = TransactionAwareFS(MutationJournal(tmp_path))

    with pytest.raises(UnsupportedFilesystemNodeError):
        fs.write_text(link, "changed")

    assert link.is_symlink()
    assert original.read_text() == "original"


def test_write_text_rejects_symlink_parent(tmp_path: Path) -> None:
    real_directory = tmp_path / "real"
    real_directory.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(real_directory, target_is_directory=True)
    fs = TransactionAwareFS(MutationJournal(tmp_path))

    with pytest.raises(UnsupportedFilesystemNodeError) as error:
        fs.write_text(link / "file.txt", "changed")

    assert (error.value.path, error.value.node_type) == (link, "symbolic link parent")
    assert list(real_directory.iterdir()) == []


def test_write_text_rejects_non_directory_parent(tmp_path: Path) -> None:
    parent = tmp_path / "notes"
    parent.write_text("a file, not a directory")
    journal = MutationJournal(tmp_path)
    fs = TransactionAwareFS(journal)

    with pytest.raises(UnsupportedFilesystemNodeError) as error:
        fs.write_text(parent / "file.txt", "changed")

    assert (error.value.path, error.value.node_type) == (
        parent,
        "non-directory parent",
    )
    assert journal.touched_paths == frozenset()


def test_write_text_journals_only_the_missing_parents(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    journal = MutationJournal(tmp_path)
    fs = TransactionAwareFS(journal)

    fs.write_text(tmp_path / "a" / "b" / "file.txt", "content")

    assert journal.created_paths == frozenset({"a/b", "a/b/file.txt"})
    assert journal.rollback().succeeded
    assert (tmp_path / "a").is_dir()
    assert not (tmp_path / "a" / "b").exists()


def test_atomic_temp_file_is_removed_on_keyboard_interrupt(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    fs = TransactionAwareFS(MutationJournal(tmp_path))
    mocker.patch("os.replace", side_effect=KeyboardInterrupt)

    with pytest.raises(KeyboardInterrupt):
        fs.write_text(tmp_path / "file.txt", "content")

    assert [path for path in tmp_path.iterdir() if path.name.endswith(".tmp")] == []


def test_write_text_wraps_encoding_error_without_mutation(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)
    fs = TransactionAwareFS(journal)

    with pytest.raises(FileSystemError, match="Failed to encode file") as error:
        fs.write_text(tmp_path / "file.txt", "🚀", encoding="ascii")

    assert error.value.path == str(tmp_path / "file.txt")
    assert isinstance(error.value.original, UnicodeEncodeError)

    assert journal.touched_paths == frozenset()
    assert not (tmp_path / "file.txt").exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO is not supported")
def test_write_text_rejects_special_node(tmp_path: Path) -> None:
    fifo = tmp_path / "events"
    os.mkfifo(fifo)
    fs = TransactionAwareFS(MutationJournal(tmp_path))

    with pytest.raises(UnsupportedFilesystemNodeError) as error:
        fs.write_text(fifo, "changed")

    assert (error.value.path, error.value.node_type) == (
        fifo,
        "special filesystem node",
    )


def test_ensure_directory_leaves_an_existing_directory_untouched(
    tmp_path: Path,
) -> None:
    (tmp_path / "docs").mkdir()
    journal = MutationJournal(tmp_path)

    TransactionAwareFS(journal).ensure_directory(tmp_path / "docs")

    assert journal.touched_paths == frozenset()


def test_ensure_directory_creates_and_rolls_back(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)

    TransactionAwareFS(journal).ensure_directory(tmp_path / "a" / "b")

    assert (tmp_path / "a" / "b").is_dir()
    assert journal.touched_paths == frozenset({"a", "a/b"})
    assert journal.rollback().succeeded
    assert not (tmp_path / "a").exists()


def test_ensure_directory_rejects_a_file(tmp_path: Path) -> None:
    target = tmp_path / "docs"
    target.write_text("a file")
    fs = TransactionAwareFS(MutationJournal(tmp_path))

    with pytest.raises(UnsupportedFilesystemNodeError) as error:
        fs.ensure_directory(target)

    assert (error.value.path, error.value.node_type) == (target, "non-directory")


def test_ensure_directory_rejects_a_symlink(tmp_path: Path) -> None:
    real_directory = tmp_path / "real"
    real_directory.mkdir()
    link = tmp_path / "docs"
    link.symlink_to(real_directory, target_is_directory=True)
    fs = TransactionAwareFS(MutationJournal(tmp_path))

    with pytest.raises(UnsupportedFilesystemNodeError) as error:
        fs.ensure_directory(link)

    assert (error.value.path, error.value.node_type) == (link, "symbolic link")


def test_remove_file_ignores_a_missing_path(tmp_path: Path) -> None:
    journal = MutationJournal(tmp_path)

    TransactionAwareFS(journal).remove_file(tmp_path / "missing.txt")

    assert journal.touched_paths == frozenset()


def test_remove_file_restores_on_rollback(tmp_path: Path) -> None:
    target = tmp_path / "old.txt"
    target.write_text("original")
    journal = MutationJournal(tmp_path)

    TransactionAwareFS(journal).remove_file(target)

    assert not target.exists()
    assert journal.rollback().succeeded
    assert target.read_text() == "original"
