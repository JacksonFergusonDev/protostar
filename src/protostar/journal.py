"""The record of what a run changed, and how to put it back.

Every path execution mutates is journaled before its first mutation, through
``TransactionAwareFS`` or a task's declared outputs. Three rules make rollback
restore the workspace exactly:

- **First record wins.** A path is captured once, so later writes in the same
  run never overwrite the state it had before the run.
- **Rollback runs in reverse.** Missing parent directories are journaled
  before the files inside them, so undoing in reverse removes children before
  their parents.
- **Only what the run created is deleted.** A directory the run created is
  removed only if it is empty again. One that still holds files no journaled
  path accounts for fails its restore instead, and the rollback reports it,
  rather than deleting files Protostar cannot vouch for. A tree a command
  declared it creates (``record_tree_creation``) is removed whole.

Symbolic links and special nodes are refused before they are mutated, since
their original state could not be restored byte for byte.
"""

import dataclasses
import enum
import shutil
import stat
from pathlib import Path

from .errors import (
    TransactionStateError,
    UnsupportedFilesystemNodeError,
)
from .fs import atomic_write_bytes
from .security import enforce_path_jail

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
    created_as_tree: bool = False

    @classmethod
    def absent(cls, created_as_tree: bool = False) -> "OriginalState":
        """Absent state."""
        return cls(kind=NodeKind.ABSENT, created_as_tree=created_as_tree)

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


def _remove_tree(path: Path) -> str | None:
    """Removes as much of a created tree as it can.

    Args:
        path: The root of the tree.

    Returns:
        What could not be removed, or None when the whole tree is gone.
    """
    problems: list[BaseException] = []
    shutil.rmtree(path, onexc=lambda _function, _path, error: problems.append(error))
    if not problems:
        return None
    more = f" (and {len(problems) - 1} more)" if len(problems) > 1 else ""
    return f"{problems[0]}{more}"


class MutationJournal:
    """Captures each path's state before its first mutation, to roll a run back.

    A journal is single-use: it is active until it commits, which discards the
    captures, or rolls back, which restores them.
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        self._workspace_root = (workspace_root or Path.cwd()).resolve()
        self._journal: dict[Path, OriginalState] = {}
        self._created_paths: set[Path] = set()
        self._mutated_paths: set[Path] = set()
        self._touched_display_paths: set[str] = set()
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
        return enforce_path_jail(
            path,
            self._workspace_root,
            # None would read as False too.
            dereference_leaf=False,  # pragma: no mutate
        )

    def _format_display_path(self, path: Path, is_dir: bool = False) -> str:
        # Every journaled path went through normalize_path, so it is inside the root.
        display = path.relative_to(self._workspace_root).as_posix()
        return f"{display}/" if is_dir else display

    @property
    def created_paths(self) -> frozenset[str]:
        """Returns created paths."""
        return frozenset(
            self._format_display_path(path) for path in self._created_paths
        )

    @property
    def mutated_paths(self) -> frozenset[str]:
        """Returns mutated paths."""
        return frozenset(
            self._format_display_path(path) for path in self._mutated_paths
        )

    @property
    def touched_paths(self) -> frozenset[str]:
        """Returns formatted touched paths with trailing slashes for directories."""
        return frozenset(self._touched_display_paths)

    def was_present(self, path: Path) -> bool:
        """Returns whether a path existed before its first managed mutation."""
        original = self._journal.get(self.normalize_path(path))
        return original.kind != NodeKind.ABSENT if original else path.exists()

    def record_tree_creation(self, path: Path) -> None:
        """Records a path as a newly created tree to be eradicated on rollback."""
        if self._state is not TransactionState.ACTIVE:
            raise TransactionStateError("record a tree creation in", self._state.value)

        path = self.normalize_path(path)
        if path in self._journal:
            return

        if path.exists():
            self.record_mutation(path)
            return

        self._journal[path] = OriginalState.absent(created_as_tree=True)
        self._created_paths.add(path)
        self._touched_display_paths.add(self._format_display_path(path, is_dir=True))

    def record_mutation(self, path: Path) -> None:
        """Captures a path's current state before its first mutation.

        A path already journaled keeps its first capture. An absent path is
        recorded as created; a file keeps its bytes and mode, a directory its
        mode.

        Args:
            path: The path about to be mutated, inside the workspace.

        Raises:
            TransactionStateError: If the journal has committed or rolled back.
            UnsupportedFilesystemNodeError: If the path is a symbolic link or a
                special node.
            FileSystemError: If the path cannot be inspected or read.
        """
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
            self._touched_display_paths.add(self._format_display_path(path))
            return
        except OSError as e:
            from .errors import FileSystemError

            raise FileSystemError("inspect path before mutation", str(path), e) from e

        mode = stat.S_IMODE(node_stat.st_mode)
        is_dir = stat.S_ISDIR(node_stat.st_mode)
        if stat.S_ISLNK(node_stat.st_mode):
            raise UnsupportedFilesystemNodeError(path, "symbolic link")
        if is_dir:
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
        self._touched_display_paths.add(self._format_display_path(path, is_dir=is_dir))

    @staticmethod
    def _restore(path: Path, state: OriginalState) -> str | None:
        """Puts one path back in its captured state.

        Args:
            path: The journaled path.
            state: What it was before its first mutation.

        Returns:
            What a created tree left behind, or None when the path is restored.
        """
        if state.kind is NodeKind.ABSENT:
            if path.exists() or path.is_symlink():
                if state.created_as_tree:
                    return _remove_tree(path)
                if path.is_dir() and not path.is_symlink():
                    path.rmdir()
                else:
                    path.unlink()
        elif state.kind is NodeKind.DIRECTORY:
            if not path.is_dir() or path.is_symlink():
                if path.exists() or path.is_symlink():
                    path.unlink()
                path.mkdir(parents=True)
            if state.mode is not None:
                path.chmod(state.mode)
        elif state.file_content is not None:
            if path.exists() and path.is_dir():
                path.rmdir()
            atomic_write_bytes(path, state.file_content, mode=state.mode)
        return None

    def commit(self) -> None:
        """Accepts every mutation and discards the captures.

        Raises:
            TransactionStateError: If the journal is no longer active.
        """
        if self._state is not TransactionState.ACTIVE:
            raise TransactionStateError("commit", self._state.value)
        self._state = TransactionState.COMMITTED
        self._journal.clear()

    def rollback(self) -> RollbackResult:
        """Restores every journaled path, newest first.

        Each path is attempted even when another fails, so one stuck path does
        not leave the rest changed. Rolling back twice returns the first result.

        Returns:
            Whether every path was restored, and why any was not.

        Raises:
            TransactionStateError: If the journal has already committed.
        """
        if self._state is TransactionState.COMMITTED:
            raise TransactionStateError("roll back", self._state.value)
        if self._rollback_result is not None:
            return self._rollback_result

        failures: list[RollbackFailure] = []
        for path in reversed(self._journal.keys()):
            try:
                leftover = self._restore(path, self._journal[path])
            except Exception as e:
                failures.append(RollbackFailure(path=path, detail=str(e)))
            else:
                if leftover is not None:
                    failures.append(RollbackFailure(path, leftover))

        self._state = TransactionState.ROLLED_BACK
        self._journal.clear()
        self._rollback_result = RollbackResult(
            succeeded=not failures,
            failed_paths=tuple(failure.path for failure in failures),
            errors=tuple(failures),
        )
        return self._rollback_result
