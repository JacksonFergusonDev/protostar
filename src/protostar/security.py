"""Security policies and enforcement boundaries."""

import enum
from pathlib import Path

from .errors import SecurityViolationError

__all__ = [
    "ALLOWED_BINARIES",
    "SafelistBinary",
    "enforce_binary_safelist",
    "enforce_path_jail",
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


ALLOWED_BINARIES: frozenset[SafelistBinary | str] = frozenset(SafelistBinary)


def enforce_path_jail(target_path: Path, workspace_root: Path) -> None:
    """Ensures no file operations escape the workspace root.

    Args:
        target_path: The filesystem path to validate.
        workspace_root: The allowed root boundary directory.

    Raises:
        SecurityViolationError: If the target path resolves outside the workspace root.
    """
    resolved_target = target_path.resolve()
    resolved_root = workspace_root.resolve()

    if not resolved_target.is_relative_to(resolved_root):
        raise SecurityViolationError(
            f"SECURITY VIOLATION: Template attempted to write outside the workspace: {target_path}"
        )


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
