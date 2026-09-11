"""Transaction-aware filesystem operations."""

import tempfile
from pathlib import Path

from .journal import MutationJournal

__all__ = ["TransactionAwareFS"]


class TransactionAwareFS:
    """Transaction-aware file system operations."""
    def __init__(self, journal: MutationJournal) -> None:
        self.journal = journal

    def _track_implicit_parents(self, path: Path) -> None:
        """Records any missing parent directories before they are created."""
        path = path.resolve()
        to_create = []
        current = path.parent
        while not current.exists():
            to_create.append(current)
            current = current.parent
        for p in reversed(to_create):
            self.journal.record_mutation(p)

    def ensure_directory(self, path: Path) -> None:
        """Ensures a directory exists."""
        if path.exists() and path.is_dir():
            return
        self._track_implicit_parents(path)
        self.journal.record_mutation(path)
        path.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, path: Path, content: bytes) -> None:
        """Writes bytes to a file."""
        self._track_implicit_parents(path)
        self.journal.record_mutation(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write
        temp = tempfile.NamedTemporaryFile(
            delete=False, dir=path.parent, prefix=".tmp-protostar-"
        )
        try:
            temp.write(content)
            temp.close()
            Path(temp.name).replace(path)
        except BaseException:
            Path(temp.name).unlink(missing_ok=True)
            raise

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        """Writes text to a file."""
        self.write_bytes(path, content.encode(encoding))

    def remove_file(self, path: Path) -> None:
        """Removes a file."""
        if not path.exists():
            return
        self.journal.record_mutation(path)
        path.unlink()
