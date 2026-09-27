"""Security policies and enforcement boundaries."""

import enum
import os
from pathlib import Path, PurePosixPath, PureWindowsPath

from .errors import SecurityViolationError

__all__ = [
    "ALLOWED_BINARIES",
    "SafelistBinary",
    "enforce_binary_safelist",
    "enforce_path_jail",
    "is_safe_relative_path",
    "names_git_directory",
]


class SafelistBinary(enum.StrEnum):
    """Enumeration of authorized binaries allowed to execute in sandboxed environments."""

    UV = "uv"
    GIT = "git"
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    PRE_COMMIT = "pre-commit"
    PREK = "prek"
    DIRENV = "direnv"
    JUST = "just"


ALLOWED_BINARIES: frozenset[SafelistBinary | str] = frozenset(SafelistBinary)


def is_safe_relative_path(path: str | Path) -> bool:
    """Checks whether a path is a safe relative workspace path.

    Rejects absolute paths (POSIX and Windows), drive letters, root prefixes,
    empty paths, and paths containing '..' traversal segments.

    Args:
        path: Path string or Path object to validate.

    Returns:
        True if the path is safely relative to a workspace root; False otherwise.
    """
    target = Path(path)
    posix = PurePosixPath(path)
    win = PureWindowsPath(path)
    return not (
        target.is_absolute()
        or posix.is_absolute()
        or bool(win.drive)
        or bool(win.root)
        or ".." in target.parts
        or not target.parts
    )


def names_git_directory(part: str) -> bool:
    """Returns whether a path segment names the git metadata directory.

    Case-insensitive filesystems (macOS, Windows) map ``.GIT`` onto it, Windows
    drops trailing dots and spaces, and ``GIT~1`` is its 8.3 short name.

    Args:
        part: The path segment to check.

    Returns:
        True if the segment names a git metadata directory; False otherwise.
    """
    name = part.rstrip(". ").lower()
    return name == ".git" or name == "git~1"


def enforce_path_jail(
    target_path: Path,
    workspace_root: Path,
    *,
    dereference_leaf: bool = True,
) -> Path:
    """Ensures no file operations escape the workspace root.

    Args:
        target_path: The filesystem path to validate.
        workspace_root: The allowed root boundary directory.
        dereference_leaf: Whether to dereference the final path component if it is a symlink.
            When False, normalizes '..' components and verifies ancestor directories, but
            preserves the non-dereferenced path without following leaf symlinks, allowing callers
            to inspect or reject symlink nodes.

    Returns:
        The validated and normalized absolute path within the workspace root.

    Raises:
        SecurityViolationError: If the target path resolves outside the workspace root.
    """
    if not isinstance(workspace_root, Path):
        workspace_root = Path.cwd()

    candidate = (
        target_path if target_path.is_absolute() else workspace_root / target_path
    )
    resolved_root = workspace_root.resolve()

    lexical = Path(os.path.normpath(candidate))
    if not lexical.is_relative_to(workspace_root) and not lexical.is_relative_to(
        resolved_root
    ):
        raise SecurityViolationError(
            f"SECURITY VIOLATION: Path escapes the workspace: {target_path}"
        )

    if dereference_leaf:
        resolved = candidate.resolve()
        if not resolved.is_relative_to(resolved_root):
            raise SecurityViolationError(
                f"SECURITY VIOLATION: Path escapes the workspace: {target_path}"
            )
        return resolved

    if lexical in (workspace_root, resolved_root):
        return resolved_root

    current = lexical.parent
    while current not in (workspace_root, resolved_root) and current != current.parent:
        if current.exists() and not current.resolve().is_relative_to(resolved_root):
            raise SecurityViolationError(
                f"SECURITY VIOLATION: Path escapes the workspace: {target_path}"
            )
        current = current.parent

    return lexical


def enforce_binary_safelist(command: list[str]) -> None:
    """Prevents templates from invoking arbitrary shells or interpreters.

    Args:
        command: The command argument list to validate.

    Raises:
        SecurityViolationError: If the command's binary is not in the allowed safelist.
    """
    if not command:
        return

    binary = Path(command[0]).name.lower()

    if binary not in ALLOWED_BINARIES:
        raise SecurityViolationError(
            f"SECURITY VIOLATION: Templates cannot directly invoke arbitrary binaries ({command[0]}). Allowed: {', '.join(sorted(ALLOWED_BINARIES))}"
        )
