"""Transaction journaling and rollback mechanisms."""

import dataclasses
import enum
import stat
from pathlib import Path

from .errors import (
    SecurityViolationError,
    TransactionStateError,
    UnsupportedFilesystemNodeError,
)
from .fs import atomic_write_bytes

__all__ = [
    "MutationJournal",
    "NodeKind",
    "OriginalState",
    "RollbackFailure",
    "RollbackResult",
    "TransactionState",
]


class TransactionState(enum.StrEnum):
    """Lifecycle state for a mutation transaction."""

    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled back"


class NodeKind(enum.StrEnum):
    """Supported original filesystem node kinds."""

    ABSENT = "absent"
    REGULAR_FILE = "regular file"
    DIRECTORY = "directory"


@dataclasses.dataclass(frozen=True)
class OriginalState:
    """Pre-execution state of a filesystem node."""

    kind: NodeKind
    file_content: bytes | None = None
    mode: int | None = None

    @classmethod
    def absent(cls) -> "OriginalState":
        """Absent state."""
        return cls(kind=NodeKind.ABSENT)

    @classmethod
    def directory(cls, mode: int) -> "OriginalState":
        """Directory state."""
        return cls(kind=NodeKind.DIRECTORY, mode=mode)

    @classmethod
    def file(cls, content: bytes, mode: int) -> "OriginalState":
        """File state."""
        return cls(kind=NodeKind.REGULAR_FILE, file_content=content, mode=mode)


@dataclasses.dataclass(frozen=True)
class RollbackFailure:
    """A single path that could not be restored."""

    path: Path
    detail: str


@dataclasses.dataclass(frozen=True)
class RollbackResult:
    """The outcome of an attempted rollback operation."""

    succeeded: bool
    failed_paths: tuple[Path, ...]
    errors: tuple[RollbackFailure, ...] = ()


class MutationJournal:
    """Tracks file mutations to enable rollback."""

    def __init__(self, workspace_root: Path | None = None) -> None:
        self._workspace_root = (workspace_root or Path.cwd()).resolve()
        self._journal: dict[Path, OriginalState] = {}
        self._created_paths: set[Path] = set()
        self._mutated_paths: set[Path] = set()
        self._state = TransactionState.ACTIVE
        self._rollback_result: RollbackResult | None = None

    @property
    def state(self) -> TransactionState:
        """Returns the transaction lifecycle state."""
        return self._state

    @property
    def workspace_root(self) -> Path:
        """Returns the fixed workspace root for this transaction."""
        return self._workspace_root

    def normalize_path(self, path: Path) -> Path:
        """Returns an absolute path without dereferencing its final component."""
        candidate = path if path.is_absolute() else self._workspace_root / path
        normalized = Path(candidate.absolute())
        if not normalized.is_relative_to(self._workspace_root):
            raise SecurityViolationError(
                f"SECURITY VIOLATION: Transaction path escapes the workspace: {path}"
            )
        return normalized

    def _display_path(self, path: Path) -> str:
        try:
            return path.relative_to(self._workspace_root).as_posix()
        except ValueError:
            return path.as_posix()

    @property
    def created_paths(self) -> frozenset[str]:
        """Returns created paths."""
        return frozenset(self._display_path(path) for path in self._created_paths)

    @property
    def mutated_paths(self) -> frozenset[str]:
        """Returns mutated paths."""
        return frozenset(self._display_path(path) for path in self._mutated_paths)

    @property
    def touched_paths(self) -> frozenset[str]:
        """Returns touched paths."""
        return frozenset(self.created_paths | self.mutated_paths)

    def record_mutation(self, path: Path) -> None:
        """Records a path."""
        if self._state is not TransactionState.ACTIVE:
            raise TransactionStateError("record a mutation in", self._state.value)

        path = self.normalize_path(path)
        if path in self._journal:
            return

        try:
            node_stat = path.lstat()
        except FileNotFoundError:
            self._journal[path] = OriginalState.absent()
            self._created_paths.add(path)
            return
        except OSError as e:
            from .errors import FileSystemError

            raise FileSystemError("inspect path before mutation", str(path), e) from e

        mode = stat.S_IMODE(node_stat.st_mode)
        if stat.S_ISLNK(node_stat.st_mode):
            raise UnsupportedFilesystemNodeError(path, "symbolic link")
        if stat.S_ISDIR(node_stat.st_mode):
            self._journal[path] = OriginalState.directory(mode)
        elif stat.S_ISREG(node_stat.st_mode):
            try:
                self._journal[path] = OriginalState.file(path.read_bytes(), mode)
            except OSError as e:
                from .errors import FileSystemError

                raise FileSystemError(
                    "read existing file for journaling", str(path), e
                ) from e
        else:
            raise UnsupportedFilesystemNodeError(path, "special filesystem node")
        self._mutated_paths.add(path)

    def commit(self) -> None:
        """Commits the journal."""
        if self._state is not TransactionState.ACTIVE:
            raise TransactionStateError("commit", self._state.value)
        self._state = TransactionState.COMMITTED
        self._journal.clear()

    def rollback(self) -> RollbackResult:
        """Rolls back the journal."""
        if self._state is TransactionState.COMMITTED:
            raise TransactionStateError("roll back", self._state.value)
        if self._rollback_result is not None:
            return self._rollback_result

        failures: list[RollbackFailure] = []
        for path in reversed(self._journal.keys()):
            state = self._journal[path]
            try:
                if state.kind is NodeKind.ABSENT:
                    if path.exists() or path.is_symlink():
                        if path.is_dir() and not path.is_symlink():
                            path.rmdir()
                        else:
                            path.unlink()
                elif state.kind is NodeKind.DIRECTORY:
                    if not path.is_dir() or path.is_symlink():
                        if path.exists() or path.is_symlink():
                            path.unlink()
                        path.mkdir(parents=True, exist_ok=True)
                    if state.mode is not None:
                        path.chmod(state.mode)
                elif state.file_content is not None and state.mode is not None:
                    if path.exists() and path.is_dir():
                        path.rmdir()
                    atomic_write_bytes(path, state.file_content, mode=state.mode)
            except Exception as e:
                failures.append(RollbackFailure(path=path, detail=str(e)))

        self._state = TransactionState.ROLLED_BACK
        self._journal.clear()
        self._rollback_result = RollbackResult(
            succeeded=not failures,
            failed_paths=tuple(failure.path for failure in failures),
            errors=tuple(failures),
        )
        return self._rollback_result
