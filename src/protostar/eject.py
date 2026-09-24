"""Prepare and apply a transaction that stops tracking a project."""

from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigurationError, FileSystemError, RollbackFailedError
from .fs_transaction import TransactionAwareFS
from .journal import MutationJournal, NodeKind
from .recipe import remove_recipe
from .review_workspace import CapturedInput, capture_node
from .system import shield_sigint


@dataclass(frozen=True)
class PreparedEjection:
    """Captured inputs and the exact pyproject bytes accepted for ejection."""

    root: Path
    pyproject: CapturedInput
    lock: CapturedInput
    pyproject_after: bytes | None

    @property
    def changed_paths(self) -> tuple[str, ...]:
        """Lists paths the prepared operation will change."""
        changed: list[str] = []
        if self.lock.original.kind is NodeKind.REGULAR_FILE:
            changed.append(self.lock.path)
        if self.pyproject_after is not None:
            changed.append(self.pyproject.path)
        return tuple(changed)

    def apply(self) -> None:
        """Applies both edits atomically against the captured workspace revision."""
        self.pyproject.validate(self.root)
        self.lock.validate(self.root)
        journal = MutationJournal(self.root)
        fs = TransactionAwareFS(journal)
        try:
            if self.lock.original.kind is NodeKind.REGULAR_FILE:
                fs.remove_file(self.root / self.lock.path)
            if self.pyproject_after is not None:
                fs.write_bytes(self.root / self.pyproject.path, self.pyproject_after)
            journal.commit()
        except BaseException as error:
            with shield_sigint():
                rollback = journal.rollback()
            if not rollback.succeeded:
                raise RollbackFailedError(rollback, error) from error
            if isinstance(error, OSError):
                raise FileSystemError("eject project", str(self.root), error) from error
            raise


def prepare_ejection(root: Path) -> PreparedEjection:
    """Reads the two project files and computes ejection without writing."""
    root = root.resolve()
    pyproject = CapturedInput("pyproject.toml", capture_node(root / "pyproject.toml"))
    lock = CapturedInput("protostar.lock", capture_node(root / "protostar.lock"))
    if pyproject.original.kind is NodeKind.DIRECTORY:
        raise ConfigurationError("pyproject.toml is a directory.")
    if lock.original.kind is NodeKind.DIRECTORY:
        raise ConfigurationError("protostar.lock is a directory.")
    before = pyproject.original.file_content
    after: bytes | None = None
    if before is not None:
        try:
            text = before.decode("utf-8")
        except UnicodeError as error:
            raise ConfigurationError(
                "Cannot read pyproject.toml as UTF-8.",
                hint="Correct its encoding before ejecting.",
            ) from error
        edited = remove_recipe(text).encode("utf-8")
        if edited != before:
            after = edited
    return PreparedEjection(root, pyproject, lock, after)
