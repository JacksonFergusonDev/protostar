"""Filesystem helpers for safe disk mutation operations."""

import enum
import os
import tempfile
from contextlib import suppress
from pathlib import Path

from .errors import FileSystemError

__all__ = [
    "ArchiveFormat",
    "atomic_write_text",
    "safe_extract_archive",
    "safe_extract_tar",
    "safe_extract_zip",
]


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
    file_descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)

    try:
        with os.fdopen(file_descriptor, "w", encoding=encoding) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    except Exception as e:
        if isinstance(e, FileSystemError):
            raise
        raise FileSystemError("write file", str(path), e) from e
    finally:
        if temp_path.exists():
            with suppress(OSError):
                temp_path.unlink()


def safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
    """Safely extracts a zip archive, preventing path traversal vulnerabilities (Zip Slip).

    Ensures that every member in the archive resolves to a path strictly within
    the target directory before extraction.

    Args:
        zip_path: Path to the .zip archive.
        target_dir: The directory where the archive should be extracted.

    Raises:
        SecurityViolationError: If any archive member attempts path traversal.
    """
    import zipfile

    from .errors import SecurityViolationError

    resolved_target_dir = target_dir.resolve()

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.namelist():
            # Create a path object for the extracted destination
            member_path = (target_dir / member).resolve()

            # Ensure the resolved path is strictly within the target directory
            if not member_path.is_relative_to(resolved_target_dir):
                raise SecurityViolationError(
                    f"SECURITY VIOLATION: Zip archive member attempted path traversal outside target directory: {member}"
                )

        # If all members are safe, extract all
        archive.extractall(path=target_dir)


def safe_extract_tar(tar_path: Path, target_dir: Path) -> None:
    """Safely extracts a tar archive, preventing path traversal vulnerabilities (Tar Slip).

    Args:
        tar_path: Path to the .tar, .tar.gz, .tar.bz2, or .tar.xz archive.
        target_dir: The directory where the archive should be extracted.

    Raises:
        SecurityViolationError: If any archive member attempts path traversal.
    """
    import tarfile

    from .errors import SecurityViolationError

    resolved_target_dir = target_dir.resolve()

    with tarfile.open(tar_path, "r:*") as archive:
        for member in archive.getmembers():
            member_path = (target_dir / member.name).resolve()
            if not member_path.is_relative_to(resolved_target_dir):
                raise SecurityViolationError(
                    f"SECURITY VIOLATION: Tar archive member attempted path traversal outside target directory: {member.name}"
                )
        archive.extractall(path=target_dir, filter="data")


def safe_extract_archive(
    archive_path: Path,
    target_dir: Path,
    archive_format: ArchiveFormat | None = None,
) -> None:
    """Safely extracts an archive file based on format detection or explicit specification.

    Args:
        archive_path: Path to the archive on disk.
        target_dir: The directory where the archive should be extracted.
        archive_format: Optional explicit ArchiveFormat.

    Raises:
        SecurityViolationError: If any member attempts path traversal.
        TemplateResolutionError: If format cannot be determined or is unsupported.
    """
    from .errors import TemplateResolutionError

    fmt = archive_format or ArchiveFormat.from_path(archive_path)
    if fmt == ArchiveFormat.ZIP:
        safe_extract_zip(archive_path, target_dir)
    elif fmt is not None and fmt.is_tar:
        safe_extract_tar(archive_path, target_dir)
    else:
        raise TemplateResolutionError(
            str(archive_path),
            f"Unsupported or unrecognized archive format for '{archive_path.name}'.",
        )
