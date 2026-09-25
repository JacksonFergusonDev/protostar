"""Filesystem helpers for safe disk mutation operations."""

import enum
import os
import stat
import tempfile
from contextlib import suppress
from pathlib import Path

from .errors import FileSystemError

__all__ = [
    "ArchiveFormat",
    "atomic_write_bytes",
    "atomic_write_text",
]


def atomic_write_bytes(path: Path, content: bytes, *, mode: int | None = None) -> None:
    """Atomically writes bytes to a regular file.

    Args:
        path: Destination file path.
        content: Byte payload to write.
        mode: Optional permission bits to apply before promoting the temporary file.

    Raises:
        FileSystemError: If file creation, writing, syncing, or replacement fails.
    """
    effective_mode = mode
    if effective_mode is None:
        try:
            target_stat = path.lstat()
        except FileNotFoundError:
            target_stat = None
        except OSError as e:
            raise FileSystemError("inspect file mode", str(path), e) from e
        if target_stat is not None:
            effective_mode = stat.S_IMODE(target_stat.st_mode)

    file_descriptor = -1
    temp_path: Path | None = None
    try:
        file_descriptor, temp_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        temp_path = Path(temp_name)
        with os.fdopen(file_descriptor, "wb") as temp_file:
            file_descriptor = -1
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            if effective_mode is not None and hasattr(os, "fchmod"):
                os.fchmod(temp_file.fileno(), effective_mode)
        if (
            effective_mode is not None
            and not hasattr(os, "fchmod")
            and temp_path is not None
        ):
            os.chmod(temp_path, effective_mode)
        os.replace(temp_path, path)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        if isinstance(e, FileSystemError):
            raise
        raise FileSystemError("write file", str(path), e) from e
    finally:
        if file_descriptor >= 0:
            with suppress(OSError):
                os.close(file_descriptor)
        if temp_path is not None and temp_path.exists():
            with suppress(OSError):
                temp_path.unlink()


class ArchiveFormat(enum.StrEnum):
    """Enumeration of supported template archive formats."""

    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    TAR_XZ = "tar.xz"

    @property
    def is_tar(self) -> bool:
        """Returns True if the format is a tarball variation."""
        return self in (
            ArchiveFormat.TAR,
            ArchiveFormat.TAR_GZ,
            ArchiveFormat.TAR_BZ2,
            ArchiveFormat.TAR_XZ,
        )

    @property
    def extensions(self) -> tuple[str, ...]:
        """Returns the recognized file extensions for this archive format."""
        mapping = {
            ArchiveFormat.ZIP: (".zip",),
            ArchiveFormat.TAR: (".tar",),
            ArchiveFormat.TAR_GZ: (".tar.gz", ".tgz"),
            ArchiveFormat.TAR_BZ2: (".tar.bz2", ".tbz2"),
            ArchiveFormat.TAR_XZ: (".tar.xz", ".txz"),
        }
        return mapping[self]

    @classmethod
    def from_path(cls, path: Path | str) -> "ArchiveFormat | None":
        """Detects the archive format from a file path or URL string."""
        lower = str(path).lower()
        for fmt in cls:
            for ext in fmt.extensions:
                if lower.endswith(ext):
                    return fmt
        return None


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically writes text content to a file.

    The write is performed via a temporary file in the same directory and then
    promoted with ``os.replace`` to guarantee an atomic swap on local filesystems.

    Args:
        path: Destination file path.
        content: Text payload to write.
        encoding: Text encoding used to serialize the content.

    Raises:
        FileSystemError: If file creation, encoding, writing, syncing, or renaming fails.
    """
    try:
        payload = content.encode(encoding)
    except UnicodeError as e:
        raise FileSystemError("write file", str(path), e) from e
    atomic_write_bytes(path, payload)
