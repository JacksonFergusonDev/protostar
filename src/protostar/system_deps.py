"""The executables Protostar and its tools run, and how to install the missing ones.

Only ``REQUIRED`` executables may block a run: nothing useful happens without
them, and they don't depend on the recipe. Every other executable belongs to a
tool the recipe selects. Planning reports a missing one as data, and execution
skips only the steps that need it.

Finding an executable searches ``PATH`` with ``shutil.which``, which starts no
process, so planning may do it and stay read-only.
"""

import enum
import shutil
import sys
from collections.abc import Collection, Sequence
from dataclasses import dataclass

UV_INSTALLER = "curl -LsSf https://astral.sh/uv/install.sh | sh"
"""uv's official installer, for Unix systems whose package manager lacks uv."""


class PackageManager(enum.StrEnum):
    """A system package manager an install command can use."""

    BREW = "brew"
    WINGET = "winget"
    APT = "apt"
    DNF = "dnf"
    PACMAN = "pacman"

    @property
    def install_prefix(self) -> str:
        """Returns the command that installs the packages appended to it."""
        return _INSTALL_PREFIXES[self]


_INSTALL_PREFIXES = {
    PackageManager.BREW: "brew install",
    PackageManager.WINGET: "winget install --exact --id",
    PackageManager.APT: "sudo apt install",
    PackageManager.DNF: "sudo dnf install",
    PackageManager.PACMAN: "sudo pacman -S",
}

_LINUX_MANAGERS = (PackageManager.APT, PackageManager.DNF, PackageManager.PACMAN)
"""Managers of other Linux systems, in the order they are preferred."""


class GlobalExecutable(enum.StrEnum):
    """A system executable that Protostar or a selected tool runs."""

    UV = "uv"
    GIT = "git"
    DIRENV = "direnv"
    JUST = "just"

    def package(self, manager: PackageManager) -> str | None:
        """Returns the executable's package id for a manager, or None if it has none.

        Args:
            manager: The package manager to install with.
        """
        return _PACKAGES[manager].get(self)


_PACKAGES: dict[PackageManager, dict[GlobalExecutable, str]] = {
    PackageManager.BREW: {
        executable: executable.value for executable in GlobalExecutable
    },
    PackageManager.WINGET: {
        GlobalExecutable.UV: "astral-sh.uv",
        GlobalExecutable.GIT: "Git.Git",
        GlobalExecutable.DIRENV: "direnv.direnv",
        GlobalExecutable.JUST: "Casey.Just",
    },
    # uv is packaged by none of these; its own installer covers it.
    **{
        manager: {
            GlobalExecutable.GIT: "git",
            GlobalExecutable.DIRENV: "direnv",
            GlobalExecutable.JUST: "just",
        }
        for manager in _LINUX_MANAGERS
    },
}

REQUIRED = frozenset({GlobalExecutable.UV, GlobalExecutable.GIT})
"""Executables Protostar itself needs, whatever the recipe selects."""


class Platform(enum.StrEnum):
    """The operating system family an install command is built for."""

    MACOS = "darwin"
    WINDOWS = "win32"
    LINUX = "linux"
    OTHER = "other"

    @classmethod
    def current(cls) -> "Platform":
        """Returns the platform this process runs on."""
        return next(
            (platform for platform in cls if sys.platform.startswith(platform.value)),
            cls.OTHER,
        )


@dataclass(frozen=True)
class InstallCommand:
    """Shell commands that install a set of missing executables.

    Attributes:
        lines: Commands to run in order, one per line.
        reload_shell: Whether a new terminal is needed before the installed
            executables are found on ``PATH``.
    """

    lines: tuple[str, ...]
    reload_shell: bool


def installed(executable: GlobalExecutable) -> bool:
    """Returns whether an executable is on ``PATH``, without starting a process.

    Args:
        executable: The executable to find.
    """
    return shutil.which(executable.value) is not None


def available_package_managers() -> frozenset[PackageManager]:
    """Returns the package managers found on ``PATH``, without starting a process."""
    return frozenset(
        manager for manager in PackageManager if shutil.which(manager.value)
    )


def install_command(
    missing: Collection[GlobalExecutable],
    platform: Platform,
    available: Collection[PackageManager],
) -> InstallCommand | None:
    """Builds the commands that install every missing executable.

    Homebrew is used wherever it is found. Otherwise Windows uses winget, one
    command per package, and other Linux systems use uv's installer for uv and
    the first package manager found for the rest.

    Args:
        missing: The executables to install.
        platform: The platform the commands run on.
        available: The package managers found on ``PATH``.

    Returns:
        The commands, or None when nothing found can install all of them.
    """
    wanted = sorted(missing)
    if not wanted:
        return None
    if PackageManager.BREW in available:
        return _single(PackageManager.BREW, wanted, reload_shell=False)
    if platform is Platform.WINDOWS and PackageManager.WINGET in available:
        # One id per command: winget's multi-package install is not relied on.
        return InstallCommand(
            tuple(
                f"{PackageManager.WINGET.install_prefix} "
                f"{executable.package(PackageManager.WINGET)}"
                for executable in wanted
            ),
            reload_shell=True,
        )
    if platform is not Platform.LINUX:
        return None
    lines: list[str] = []
    if GlobalExecutable.UV in wanted:
        lines.append(UV_INSTALLER)
    rest = [
        executable for executable in wanted if executable is not GlobalExecutable.UV
    ]
    if rest:
        manager = next((m for m in _LINUX_MANAGERS if m in available), None)
        if manager is None:
            return None
        lines.extend(_single(manager, rest, reload_shell=False).lines)
    return InstallCommand(tuple(lines), reload_shell=GlobalExecutable.UV in wanted)


def _single(
    manager: PackageManager, wanted: Sequence[GlobalExecutable], *, reload_shell: bool
) -> InstallCommand:
    packages = " ".join(str(executable.package(manager)) for executable in wanted)
    return InstallCommand((f"{manager.install_prefix} {packages}",), reload_shell)


def check_required_executables() -> None:
    """Raises when an executable Protostar itself needs is not on ``PATH``.

    Raises:
        MissingDependencyError: If any of ``REQUIRED`` is missing, with the
            commands that install them.
    """
    missing = tuple(sorted(e for e in REQUIRED if not installed(e)))
    if not missing:
        return
    from .errors import MissingDependencyError

    raise MissingDependencyError(
        missing,
        install_command(missing, Platform.current(), available_package_managers()),
    )
