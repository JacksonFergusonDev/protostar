"""Transaction-aware filesystem operations."""

import stat
from pathlib import Path

from .errors import FileSystemError, UnsupportedFilesystemNodeError
from .fs import atomic_write_bytes
from .journal import MutationJournal

__all__ = ["TransactionAwareFS"]


class TransactionAwareFS:
    """Transaction-aware file system operations."""

    def __init__(self, journal: MutationJournal) -> None:
        self.journal = journal

    def _track_implicit_parents(self, path: Path) -> None:
        """Records any missing parent directories before they are created."""
        path = self.journal.normalize_path(path)
        to_create: list[Path] = []
        current = path.parent
        while current != self.journal.workspace_root:
            try:
                node_stat = current.lstat()
            except FileNotFoundError:
                to_create.append(current)
                current = current.parent
                continue
            if stat.S_ISLNK(node_stat.st_mode):
                raise UnsupportedFilesystemNodeError(current, "symbolic link parent")
            if not stat.S_ISDIR(node_stat.st_mode):
                raise UnsupportedFilesystemNodeError(current, "non-directory parent")
            break
        for p in reversed(to_create):
            self.journal.record_mutation(p)

    def ensure_directory(self, path: Path) -> None:
        """Ensures a directory exists."""
        path = self.journal.normalize_path(path)
        try:
            node_stat = path.lstat()
        except FileNotFoundError:
            node_stat = None
        if node_stat is not None:
            if stat.S_ISDIR(node_stat.st_mode):
                return
            node_type = (
                "symbolic link" if stat.S_ISLNK(node_stat.st_mode) else "non-directory"
            )
            raise UnsupportedFilesystemNodeError(path, node_type)
        self._track_implicit_parents(path)
        self.journal.record_mutation(path)
        path.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, path: Path, content: bytes) -> None:
        """Writes bytes to a file."""
        path = self.journal.normalize_path(path)
        self._track_implicit_parents(path)
        self.journal.record_mutation(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, content)

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        """Writes text to a file."""
        try:
            payload = content.encode(encoding)
        except UnicodeError as e:
            raise FileSystemError("encode file", str(path), e) from e
        self.write_bytes(path, payload)

    def remove_file(self, path: Path) -> None:
        """Removes a file."""
        path = self.journal.normalize_path(path)
        if not path.exists() and not path.is_symlink():
            return
        self.journal.record_mutation(path)
        path.unlink()
