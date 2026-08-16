"""Filesystem helpers for safe disk mutation operations."""

import os
import tempfile
from contextlib import suppress
from pathlib import Path

from .errors import FileSystemError


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
        with suppress(OSError):
            temp_path.unlink()
        if isinstance(e, FileSystemError):
            raise
        raise FileSystemError("write file", str(path), e) from e


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
