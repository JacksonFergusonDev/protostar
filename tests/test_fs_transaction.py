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

    with pytest.raises(UnsupportedFilesystemNodeError):
        fs.write_text(link / "file.txt", "changed")

    assert list(real_directory.iterdir()) == []


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

    with pytest.raises(FileSystemError, match="Failed to encode file"):
        fs.write_text(tmp_path / "file.txt", "🚀", encoding="ascii")

    assert journal.touched_paths == frozenset()
    assert not (tmp_path / "file.txt").exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO is not supported")
def test_write_text_rejects_special_node(tmp_path: Path) -> None:
    fifo = tmp_path / "events"
    os.mkfifo(fifo)
    fs = TransactionAwareFS(MutationJournal(tmp_path))

    with pytest.raises(UnsupportedFilesystemNodeError):
        fs.write_text(fifo, "changed")
