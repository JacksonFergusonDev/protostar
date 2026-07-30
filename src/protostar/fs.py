"""Filesystem helpers for safe disk mutation operations."""

import os
import tempfile
from contextlib import suppress
from pathlib import Path


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically writes text content to a file.

    The write is performed via a temporary file in the same directory and then
    promoted with ``os.replace`` to guarantee an atomic swap on local filesystems.

    Args:
        path: Destination file path.
        content: Text payload to write.
        encoding: Text encoding used to serialize the content.
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
    except Exception:
        with suppress(OSError):
            temp_path.unlink()
        raise
