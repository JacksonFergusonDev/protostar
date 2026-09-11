"""Transaction journaling and rollback mechanisms."""

import dataclasses
import shutil
from pathlib import Path

__all__ = ["MutationJournal", "OriginalState", "RollbackResult"]


@dataclasses.dataclass(frozen=True)
class OriginalState:
    """Pre-execution state of a filesystem node."""

    is_absent: bool = False
    is_directory: bool = False
    file_content: bytes | None = None

    @classmethod
    def absent(cls) -> "OriginalState":
        """Absent state."""
        return cls(is_absent=True)

    @classmethod
    def directory(cls) -> "OriginalState":
        """Directory state."""
        return cls(is_directory=True)

    @classmethod
    def file(cls, content: bytes) -> "OriginalState":
        """File state."""
        return cls(file_content=content)


@dataclasses.dataclass(frozen=True)
class RollbackResult:
    """The outcome of an attempted rollback operation."""

    succeeded: bool
    failed_paths: tuple[Path, ...]


class MutationJournal:
    """Tracks file mutations to enable rollback."""

    def __init__(self) -> None:
        self._journal: dict[Path, OriginalState] = {}
        self._committed: bool = False
        self._rolled_back: bool = False

    @property
    def created_paths(self) -> frozenset[str]:
        """Returns created paths."""
        cwd = Path.cwd().resolve()
        paths = []
        for p, s in self._journal.items():
            if s.is_absent:
                try:
                    paths.append(p.relative_to(cwd).as_posix())
                except ValueError:
                    paths.append(p.as_posix())
        return frozenset(paths)

    @property
    def mutated_paths(self) -> frozenset[str]:
        """Returns mutated paths."""
        cwd = Path.cwd().resolve()
        paths = []
        for p, s in self._journal.items():
            if not s.is_absent:
                try:
                    paths.append(p.relative_to(cwd).as_posix())
                except ValueError:
                    paths.append(p.as_posix())
        return frozenset(paths)

    @property
    def touched_paths(self) -> frozenset[str]:
        """Returns touched paths."""
        return frozenset(self.created_paths | self.mutated_paths)

    def record_mutation(self, path: Path) -> None:
        """Records a path."""
        path = path.resolve()
        if path in self._journal:
            return

        if not path.exists() and not path.is_symlink():
            self._journal[path] = OriginalState.absent()
        elif path.is_dir() and not path.is_symlink():
            self._journal[path] = OriginalState.directory()
        elif path.is_file() and not path.is_symlink():
            try:
                self._journal[path] = OriginalState.file(path.read_bytes())
            except OSError:
                # We can't guarantee safety if we can't read the existing state
                raise ValueError(
                    f"Failed to read existing file for journaling: {path}"
                ) from None
        else:
            raise ValueError(
                f"Unsupported filesystem node for journaling (symlinks/special nodes not supported): {path}"
            )

    def commit(self) -> None:
        """Commits the journal."""
        self._committed = True

    def rollback(self) -> RollbackResult:
        """Rolls back the journal."""
        if self._committed:
            return RollbackResult(succeeded=False, failed_paths=())
        if self._rolled_back:
            return RollbackResult(succeeded=True, failed_paths=())

        failed = []
        for path in reversed(self._journal.keys()):
            state = self._journal[path]
            try:
                if state.is_absent:
                    if path.exists() or path.is_symlink():
                        if path.is_dir() and not path.is_symlink():
                            shutil.rmtree(path)
                        else:
                            path.unlink()
                elif state.is_directory:
                    if not path.is_dir() or path.is_symlink():
                        if path.exists() or path.is_symlink():
                            if path.is_dir() and not path.is_symlink():
                                shutil.rmtree(path)
                            else:
                                path.unlink()
                        path.mkdir(parents=True, exist_ok=True)
                elif state.file_content is not None:
                    if path.exists() and path.is_dir() and not path.is_symlink():
                        shutil.rmtree(path)
                    path.write_bytes(state.file_content)
            except OSError:
                failed.append(path)

        self._rolled_back = True
        return RollbackResult(succeeded=(len(failed) == 0), failed_paths=tuple(failed))
