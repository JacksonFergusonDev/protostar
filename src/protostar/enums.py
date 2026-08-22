"""Domain enumerations for Protostar."""

import enum


class PromptType(enum.StrEnum):
    """Enumeration of interactive prompt widget types."""

    TEXT = "text"
    CHECKBOX = "checkbox"
    SELECT = "select"


class MetadataKey(enum.StrEnum):
    """Enumeration of recognized project metadata keys."""

    DESCRIPTION = "description"
    LICENSE = "license"
    AUTHOR_NAME = "author_name"
    AUTHOR_EMAIL = "author_email"
    GITHUB_USERNAME = "github_username"
    MINIMUM_PYTHON = "minimum_python"
    SUPPORTED_OS = "supported_os"
    DOCKER_PORT = "docker_port"


class TargetOS(enum.StrEnum):
    """Enumeration of supported target operating systems."""

    MACOS = "MacOS"
    LINUX = "Linux"
    WINDOWS = "Windows"

    @property
    def runner_name(self) -> str:
        """Returns the default GitHub Actions runner tag for this OS."""
        mapping = {
            TargetOS.MACOS: "macos-latest",
            TargetOS.LINUX: "ubuntu-latest",
            TargetOS.WINDOWS: "windows-latest",
        }
        return mapping[self]

    @property
    def trove_classifier(self) -> str:
        """Returns the PEP 621 PyPI trove classifier for this OS."""
        mapping = {
            TargetOS.MACOS: "Operating System :: MacOS",
            TargetOS.LINUX: "Operating System :: POSIX :: Linux",
            TargetOS.WINDOWS: "Operating System :: Microsoft :: Windows",
        }
        return mapping[self]


class LicenseType(enum.StrEnum):
    """Enumeration of supported open source project licenses."""

    MIT = "MIT"
    APACHE_2_0 = "Apache-2.0"
    BSD_3_CLAUSE = "BSD-3-Clause"
    GPL_3_0 = "GPL-3.0"
    LGPL_3_0 = "LGPL-3.0"
    AGPL_3_0 = "AGPL-3.0"
    NONE = "None"

    @property
    def resource_filename(self) -> str | None:
        """Returns the bundled license template filename, or None if no license."""
        mapping = {
            LicenseType.MIT: "mit.txt",
            LicenseType.APACHE_2_0: "apache_2_0.txt",
            LicenseType.BSD_3_CLAUSE: "bsd_3.txt",
            LicenseType.GPL_3_0: "gpl_3.txt",
            LicenseType.LGPL_3_0: "lgpl_3.txt",
            LicenseType.AGPL_3_0: "agpl_3.txt",
            LicenseType.NONE: None,
        }
        return mapping[self]

    @property
    def trove_classifier(self) -> str | None:
        """Returns the PEP 621 PyPI trove classifier for this license, or None."""
        mapping = {
            LicenseType.MIT: "License :: OSI Approved :: MIT License",
            LicenseType.APACHE_2_0: "License :: OSI Approved :: Apache Software License",
            LicenseType.BSD_3_CLAUSE: "License :: OSI Approved :: BSD License",
            LicenseType.GPL_3_0: "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
            LicenseType.LGPL_3_0: "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
            LicenseType.AGPL_3_0: "License :: OSI Approved :: GNU Affero General Public License v3",
            LicenseType.NONE: None,
        }
        return mapping[self]


class IDEType(enum.StrEnum):
    """Enumeration of supported integrated development environments."""

    VSCODE = "vscode"
    CURSOR = "cursor"
    NONE = "none"

    @property
    def binary_name(self) -> str | None:
        """Returns the CLI executable name for this IDE, or None if disabled."""
        mapping = {
            IDEType.VSCODE: "code",
            IDEType.CURSOR: "cursor",
            IDEType.NONE: None,
        }
        return mapping[self]


class DiagnosticPhase(enum.StrEnum):
    """Enumeration of execution phases for diagnostic telemetry events."""

    CONFIG = "Config"
    DIRENV = "Direnv"
    IDE = "IDE"
    PRE_COMMIT = "Pre-commit"
    JUST = "Just"
    EXECUTOR = "Executor"
    DOCKER = "Docker"


class CIFlag(enum.StrEnum):
    """Enumeration of feature flags for CI workflow and justfile generators."""

    PYTEST = "pytest"
    CODECOV = "codecov"
    ZENSICAL = "zensical"


class DependencyGroup(enum.StrEnum):
    """Enumeration of dependency groups and uv installation targets."""

    MAIN = "main"
    DEV = "dev"
    DOCS = "docs"

    @property
    def cli_args(self) -> list[str]:
        """Returns the CLI arguments for uv add."""
        mapping = {
            DependencyGroup.MAIN: [],
            DependencyGroup.DEV: ["--dev"],
            DependencyGroup.DOCS: ["--group", "docs"],
        }
        return mapping[self]

    @property
    def label(self) -> str:
        """Returns the human-readable description for progress messages."""
        mapping = {
            DependencyGroup.MAIN: "standard",
            DependencyGroup.DEV: "development",
            DependencyGroup.DOCS: "documentation",
        }
        return mapping[self]


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
