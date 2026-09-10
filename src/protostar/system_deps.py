"""System dependency enumerations."""

import enum
import sys


class GlobalExecutable(enum.StrEnum):
    """Enumeration of system-level executables required by Protostar."""

    UV = "uv"
    GIT = "git"
    DIRENV = "direnv"

    @property
    def package_name(self) -> str:
        """Returns the OS-specific package name for the executable."""
        if sys.platform == "win32":
            if self == GlobalExecutable.UV:
                return "astral-sh.uv"
            if self == GlobalExecutable.GIT:
                return "Git.Git"
        return self.value
