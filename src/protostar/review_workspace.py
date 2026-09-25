"""Workspace reads and in-memory accepted bytes for reconciliation preparation."""

import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import FileSystemError, StaleReviewError, UnsupportedFilesystemNodeError
from .intent import validate_target
from .journal import NodeKind, OriginalState


class WorkspaceReader(Protocol):
    """Read boundary used by semantic reconciliation."""

    def exists(self, path: Path) -> bool:
        """Returns whether a file exists."""
        ...

    def read_bytes(self, path: Path) -> bytes:
        """Returns current bytes."""
        ...

    def read_text(self, path: Path) -> str:
        """Returns UTF-8 text."""
        ...


class ByteSink(Protocol):
    """Accepted byte and directory declarations."""

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        """Accepts exact text bytes."""
        ...

    def write_bytes(self, path: Path, content: bytes) -> None:
        """Accepts exact bytes."""
        ...

    def remove_file(self, path: Path) -> None:
        """Accepts a file's removal."""
        ...

    def ensure_directory(self, path: Path) -> None:
        """Declares a directory."""
        ...


class PresenceReader(Protocol):
    """Original presence used to distinguish initializer-created content."""

    @property
    def workspace_root(self) -> Path:
        """Returns the explicit workspace root."""
        ...

    def normalize_path(self, path: Path) -> Path:
        """Returns a workspace path."""
        ...

    def was_present(self, path: Path) -> bool:
        """Returns original presence."""
        ...


class LiveWorkspace:
    """Reads the execution workspace without caching resolver output."""

    def exists(self, path: Path) -> bool:
        """Returns current presence."""
        return path.exists()

    def read_bytes(self, path: Path) -> bytes:
        """Returns current bytes."""
        return path.read_bytes()

    def read_text(self, path: Path) -> str:
        """Returns current UTF-8 text."""
        return path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class CapturedInput:
    """Exact pre-review bytes, presence, node kind, and POSIX mode."""

    path: str
    original: OriginalState

    def validate(self, root: Path) -> None:
        """Rejects stale bytes, modes, or presence before mutation."""
        if capture_node(root / self.path) != self.original:
            raise StaleReviewError(self.path)


def capture_node(path: Path) -> OriginalState:
    """Reads a supported node without following symbolic links."""
    try:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise UnsupportedFilesystemNodeError(path, "symbolic link")
        if stat.S_ISDIR(mode):
            return OriginalState.directory(stat.S_IMODE(mode))
        if stat.S_ISREG(mode):
            return OriginalState.file(path.read_bytes(), stat.S_IMODE(mode))
        raise UnsupportedFilesystemNodeError(path, "special filesystem node")
    except FileNotFoundError:
        return OriginalState.absent()
    except OSError as error:
        raise FileSystemError("capture review input", str(path), error) from error


class ReviewWorkspace:
    """Captures read inputs and accumulates accepted edits entirely in memory."""

    def __init__(self, root: Path, presence: PresenceReader | None = None) -> None:
        """Starts an in-memory review at an explicit root with optional transaction origin."""
        self.workspace_root = root
        self.presence = presence
        self.inputs: dict[str, CapturedInput] = {}
        self.contents: dict[str, bytes] = {}
        self.removed: set[str] = set()
        self.directories: set[str] = set()

    def normalize_path(self, path: Path) -> Path:
        """Normalizes a validated relative target inside the explicit root."""
        relative = path.relative_to(self.workspace_root) if path.is_absolute() else path
        if relative.as_posix() not in {"protostar.lock", "uv.lock"}:
            validate_target(relative.as_posix())
        return self.workspace_root / relative

    def capture(self, path: Path, *, directory: bool = False) -> CapturedInput:
        """Captures the path and every relevant ancestor before reading."""
        absolute = self.normalize_path(path)
        relative = absolute.relative_to(self.workspace_root).as_posix()
        for parent in reversed(absolute.parents):
            if parent == self.workspace_root or not parent.is_relative_to(
                self.workspace_root
            ):
                continue
            key = parent.relative_to(self.workspace_root).as_posix()
            if key not in self.inputs:
                self.inputs[key] = CapturedInput(key, capture_node(parent))
            if self.inputs[key].original.kind not in (
                NodeKind.ABSENT,
                NodeKind.DIRECTORY,
            ):
                raise UnsupportedFilesystemNodeError(parent, "non-directory parent")
        if relative not in self.inputs:
            self.inputs[relative] = CapturedInput(relative, capture_node(absolute))
        item = self.inputs[relative]
        expected = NodeKind.DIRECTORY if directory else NodeKind.REGULAR_FILE
        if item.original.kind not in (NodeKind.ABSENT, expected):
            raise UnsupportedFilesystemNodeError(absolute, "unsupported review target")
        return item

    def exists(self, path: Path) -> bool:
        """Returns captured or accepted file presence."""
        item = self.capture(path)
        if item.path in self.removed:
            return False
        return item.path in self.contents or item.original.kind is not NodeKind.ABSENT

    def read_bytes(self, path: Path) -> bytes:
        """Returns accepted bytes or the immutable captured input."""
        item = self.capture(path)
        return self.contents.get(item.path, item.original.file_content or b"")

    def read_text(self, path: Path) -> str:
        """Returns captured UTF-8 text."""
        return self.read_bytes(path).decode("utf-8")

    def was_present(self, path: Path) -> bool:
        """Uses transaction origin for eligible initializer-created content."""
        if self.presence is not None:
            return self.presence.was_present(path)
        return self.capture(path).original.kind is not NodeKind.ABSENT

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        """Records accepted bytes without touching disk."""
        self.write_bytes(path, content.encode(encoding))

    def write_bytes(self, path: Path, content: bytes) -> None:
        """Records accepted bytes without touching disk."""
        item = self.capture(path)
        self.removed.discard(item.path)
        self.contents[item.path] = content

    def remove_file(self, path: Path) -> None:
        """Records a file's removal without touching disk."""
        item = self.capture(path)
        self.contents.pop(item.path, None)
        if item.original.kind is not NodeKind.ABSENT:
            self.removed.add(item.path)

    def ensure_directory(self, path: Path) -> None:
        """Records a directory declaration without touching disk."""
        item = self.capture(path, directory=True)
        if item.original.kind is NodeKind.ABSENT:
            self.directories.add(item.path)
