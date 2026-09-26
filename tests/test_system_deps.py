"""Install commands for missing executables, and the required-executable check."""

import pytest

from protostar import system_deps
from protostar.errors import MissingDependencyError
from protostar.system_deps import (
    UV_INSTALLER,
    GlobalExecutable,
    InstallCommand,
    PackageManager,
    Platform,
    install_command,
)

UV = GlobalExecutable.UV
GIT = GlobalExecutable.GIT
DIRENV = GlobalExecutable.DIRENV
JUST = GlobalExecutable.JUST


@pytest.mark.parametrize(
    ("platform", "available", "expected"),
    [
        (
            Platform.MACOS,
            {PackageManager.BREW},
            InstallCommand(("brew install direnv git just uv",), False),
        ),
        # Homebrew wins wherever it is found, even over a Linux manager.
        (
            Platform.LINUX,
            {PackageManager.BREW, PackageManager.APT},
            InstallCommand(("brew install direnv git just uv",), False),
        ),
        (
            Platform.WINDOWS,
            {PackageManager.WINGET},
            InstallCommand(
                (
                    "winget install --exact --id direnv.direnv",
                    "winget install --exact --id Git.Git",
                    "winget install --exact --id Casey.Just",
                    "winget install --exact --id astral-sh.uv",
                ),
                True,
            ),
        ),
        (
            Platform.LINUX,
            {PackageManager.APT},
            InstallCommand((UV_INSTALLER, "sudo apt install direnv git just"), True),
        ),
        (
            Platform.LINUX,
            {PackageManager.DNF},
            InstallCommand((UV_INSTALLER, "sudo dnf install direnv git just"), True),
        ),
        (
            Platform.LINUX,
            {PackageManager.PACMAN},
            InstallCommand((UV_INSTALLER, "sudo pacman -S direnv git just"), True),
        ),
        (Platform.MACOS, set(), None),
        (Platform.WINDOWS, set(), None),
        (Platform.LINUX, set(), None),
        (Platform.OTHER, {PackageManager.APT}, None),
    ],
)
def test_install_command_for_each_platform_and_manager(platform, available, expected):
    assert install_command({UV, GIT, DIRENV, JUST}, platform, available) == expected


def test_linux_without_uv_needs_no_installer_or_reload():
    command = install_command({DIRENV}, Platform.LINUX, {PackageManager.APT})

    assert command == InstallCommand(("sudo apt install direnv",), False)


def test_linux_installer_alone_covers_uv_with_no_manager():
    assert install_command({UV}, Platform.LINUX, set()) == InstallCommand(
        (UV_INSTALLER,), True
    )


def test_apt_is_preferred_over_later_linux_managers():
    command = install_command(
        {JUST}, Platform.LINUX, {PackageManager.PACMAN, PackageManager.APT}
    )

    assert command == InstallCommand(("sudo apt install just",), False)


def test_nothing_missing_needs_no_command():
    assert install_command(set(), Platform.MACOS, {PackageManager.BREW}) is None


def test_every_executable_has_a_package_for_brew_and_winget():
    for manager in (PackageManager.BREW, PackageManager.WINGET):
        assert all(executable.package(manager) for executable in GlobalExecutable)


def test_available_package_managers_reads_path_only(mocker):
    which = mocker.patch(
        "protostar.system_deps.shutil.which",
        side_effect=lambda name: "/bin/apt" if name == "apt" else None,
    )

    assert system_deps.available_package_managers() == {PackageManager.APT}
    assert {call.args[0] for call in which.call_args_list} == {
        manager.value for manager in PackageManager
    }


def test_required_executables_pass_when_installed():
    system_deps.check_required_executables()


def test_missing_required_executables_raise_with_the_install_command(
    missing_executables, mocker
):
    missing_executables.update({UV, GIT, DIRENV})
    mocker.patch.object(Platform, "current", return_value=Platform.MACOS)
    mocker.patch(
        "protostar.system_deps.available_package_managers",
        return_value=frozenset({PackageManager.BREW}),
    )

    with pytest.raises(MissingDependencyError) as caught:
        system_deps.check_required_executables()

    # A tool's executable never blocks, even beside a required one.
    assert caught.value.missing == (GIT, UV)
    assert caught.value.install == InstallCommand(("brew install git uv",), False)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("darwin", Platform.MACOS),
        ("win32", Platform.WINDOWS),
        ("linux", Platform.LINUX),
        ("freebsd14", Platform.OTHER),
    ],
)
def test_current_platform(mocker, value, expected):
    mocker.patch("protostar.system_deps.sys.platform", value)

    assert Platform.current() is expected
