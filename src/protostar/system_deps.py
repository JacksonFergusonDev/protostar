"""System dependency enumerations."""

import enum


class GlobalExecutable(enum.StrEnum):
    """Enumeration of system-level executables required by Protostar."""

    UV = "uv"
    GIT = "git"
    DIRENV = "direnv"

    @property
    def brew_package_name(self) -> str:
        """Returns the corresponding Homebrew package name for the executable."""
        return self.value
