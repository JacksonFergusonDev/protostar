"""Read-only analysis of an existing project, so its first recipe starts from facts.

``init`` in a repository that has no recipe yet asks this module what is already
there: the tools the project uses, and facts such as its Python version, authors,
and license. Each tooling module declares its own signals, so no file name is
hardcoded here beyond the project files every Python project shares. Nothing is
written, no subprocess runs, and a file that cannot be read is reported as a note
rather than raised, because analysis only pre-fills choices the user still makes.
"""

from __future__ import annotations

import configparser
import os
import re
import tomllib
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from .documents import github_workflows, pyproject
from .metadata import LicenseType, MetadataKey
from .modules import (
    TOOLING_MODULES,
    PathSignal,
    RequirementSignal,
    SectionSignal,
    Signal,
    TableSignal,
)
from .recipe import EXCLUSIVE_TOOL_PAIRS, Tool
from .workflows import DOCKERFILE, TargetOS

_PYTHON_VERSION_FILE = ".python-version"
# Names a license file commonly has; only its header and copyright line are read.
_LICENSE_FILES = ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING")
_GITHUB_URL = re.compile(r"^https?://(?:www\.)?github\.com/([A-Za-z0-9-]+)/", re.I)
_COPYRIGHT = re.compile(r"^\s*copyright\s+(?:\(c\)\s*|©\s*)?(\d{4})\b", re.I)
_OS_INDEPENDENT = "Operating System :: OS Independent"


class NoteKind(StrEnum):
    """Why analysis left something out."""

    UNREADABLE = "unreadable"
    """A file that could not be parsed; nothing was read from it."""
    OTHER_WORKFLOW = "other-workflow"
    """A GitHub Actions workflow Protostar does not generate."""


@dataclass(frozen=True)
class AnalysisNote:
    """Something analysis found but did not turn into a tool or a fact.

    Attributes:
        kind: What the note is about.
        path: Workspace-relative POSIX path it concerns.
    """

    kind: NoteKind
    path: str


@dataclass(frozen=True)
class Fact[T]:
    """A value read from the project, and where it was read.

    Attributes:
        value: The value.
        source: Where it came from, such as ``pyproject.toml [project].authors``.
    """

    value: T
    source: str


@dataclass(frozen=True)
class ToolEvidence:
    """A tool the project already uses.

    Attributes:
        tool: The tool.
        sources: What shows it is in use, in the module's declaration order.
    """

    tool: Tool
    sources: tuple[str, ...]


@dataclass(frozen=True)
class ProjectFacts:
    """Project facts the recipe would otherwise fill with defaults or placeholders.

    Attributes:
        python_version: The Python version to record in the recipe.
        minimum_python: The lowest Python version the project supports.
        description: The project description.
        author_name: The first author's name.
        author_email: The first author's email address.
        github_username: The GitHub account in the project's URLs.
        license: The project's license, when it is one Protostar ships.
        supported_os: Operating systems the project's classifiers name.
        current_year: The year of the license's copyright line.
    """

    python_version: Fact[str] | None = None
    minimum_python: Fact[str] | None = None
    description: Fact[str] | None = None
    author_name: Fact[str] | None = None
    author_email: Fact[str] | None = None
    github_username: Fact[str] | None = None
    license: Fact[LicenseType] | None = None
    supported_os: Fact[tuple[TargetOS, ...]] | None = None
    current_year: Fact[str] | None = None

    def metadata(self) -> dict[str, str | tuple[str, ...]]:
        """Returns the facts that are recipe metadata, keyed by metadata key.

        Returns:
            Only the facts that were found.
        """
        values: dict[str, str | tuple[str, ...]] = {}
        for key, found in (
            (MetadataKey.DESCRIPTION, self.description),
            (MetadataKey.AUTHOR_NAME, self.author_name),
            (MetadataKey.AUTHOR_EMAIL, self.author_email),
            (MetadataKey.GITHUB_USERNAME, self.github_username),
            (MetadataKey.MINIMUM_PYTHON, self.minimum_python),
        ):
            if found is not None:
                values[key.value] = found.value
        if self.license is not None:
            values[MetadataKey.LICENSE.value] = self.license.value.value
        if self.supported_os is not None:
            values[MetadataKey.SUPPORTED_OS.value] = tuple(
                target.value for target in self.supported_os.value
            )
        return values

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Returns the found facts as JSON-ready records, sorted by name."""
        records: dict[str, dict[str, Any]] = {}
        for name in sorted(self.__dataclass_fields__):
            found: Fact[Any] | None = getattr(self, name)
            if found is None:
                continue
            value = found.value
            if isinstance(value, tuple):
                value = [str(item) for item in value]
            elif isinstance(value, StrEnum):
                value = value.value
            records[name] = {"value": value, "source": found.source}
        return records


@dataclass(frozen=True)
class ProjectAnalysis:
    """What an existing project already has, before Protostar changes anything.

    Attributes:
        existing: Whether the directory holds a project: a ``pyproject.toml`` or
            any file a tool signal names.
        tools: Tools found, in tool order.
        docker: What shows the project ships a container image, if anything.
        facts: Facts read from the project.
        notes: What analysis found but left out.
    """

    existing: bool
    tools: tuple[ToolEvidence, ...] = ()
    docker: tuple[str, ...] = ()
    facts: ProjectFacts = field(default_factory=ProjectFacts)
    notes: tuple[AnalysisNote, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Returns deterministic JSON-ready analysis data."""
        return {
            "existing": self.existing,
            "tools": [
                {"tool": evidence.tool.value, "sources": list(evidence.sources)}
                for evidence in sorted(self.tools, key=lambda item: item.tool.value)
            ],
            "docker": list(self.docker),
            "facts": self.facts.to_dict(),
            "notes": [
                {"kind": note.kind.value, "path": note.path}
                for note in sorted(self.notes, key=lambda item: (item.kind, item.path))
            ],
        }


class _Workspace:
    """Cached, exact-case reads of one project directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.notes: list[AnalysisNote] = []
        self._listings: dict[PurePosixPath, frozenset[str]] = {}
        self._ini: dict[str, configparser.ConfigParser | None] = {}
        self.pyproject = self._pyproject()

    def names(self, directory: PurePosixPath) -> frozenset[str]:
        """Returns the entry names of a directory, empty when it is absent."""
        if directory not in self._listings:
            try:
                self._listings[directory] = frozenset(os.listdir(self.root / directory))
            except OSError:
                self._listings[directory] = frozenset()
        return self._listings[directory]

    def exists(self, path: str) -> bool:
        """Returns whether a path exists with exactly this spelling.

        A case-insensitive filesystem would otherwise report ``Justfile`` for a
        ``justfile`` and list one file as two sources.
        """
        target = PurePosixPath(path)
        return target.name in self.names(target.parent)

    def read_text(self, path: str) -> str | None:
        """Returns a file's text, or ``None`` when it is absent or unreadable."""
        if not self.exists(path):
            return None
        try:
            return (self.root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            self.notes.append(AnalysisNote(NoteKind.UNREADABLE, path))
            return None

    def _pyproject(self) -> dict[str, Any]:
        text = self.read_text(pyproject.TARGET)
        if text is None:
            return {}
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            self.notes.append(AnalysisNote(NoteKind.UNREADABLE, pyproject.TARGET))
            return {}

    def ini(self, path: str) -> configparser.ConfigParser | None:
        """Returns a parsed INI file, or ``None`` when it is absent or unreadable."""
        if path not in self._ini:
            parser: configparser.ConfigParser | None = None
            text = self.read_text(path)
            if text is not None:
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                try:
                    parser.read_string(text, source=path)
                except configparser.Error:
                    self.notes.append(AnalysisNote(NoteKind.UNREADABLE, path))
                    parser = None
            self._ini[path] = parser
        return self._ini[path]

    def project(self) -> dict[str, Any]:
        """Returns the ``[project]`` table, empty when it is missing or malformed."""
        table = self.pyproject.get("project")
        return table if isinstance(table, dict) else {}

    def requirements(self) -> frozenset[str]:
        """Returns the canonical names of every package the project lists."""
        lists: list[object] = []
        project = self.project()
        lists.append(project.get("dependencies"))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            lists.extend(optional.values())
        groups = self.pyproject.get("dependency-groups")
        if isinstance(groups, dict):
            lists.extend(groups.values())
        tool = self.pyproject.get("tool")
        uv = tool.get("uv") if isinstance(tool, dict) else None
        if isinstance(uv, dict):
            lists.append(uv.get("dev-dependencies"))
        names: set[str] = set()
        for entries in lists:
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, str):
                    continue
                try:
                    names.add(canonicalize_name(Requirement(entry).name))
                except InvalidRequirement:
                    continue
        return frozenset(names)


def _match(workspace: _Workspace, signal: Signal, packages: frozenset[str]) -> str:
    """Returns how a signal shows in the project, or ``""`` when it does not."""
    if isinstance(signal, PathSignal):
        return signal.path if workspace.exists(signal.path) else ""
    if isinstance(signal, TableSignal):
        node: object = workspace.pyproject
        for key in signal.keys:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, dict):
            return f"{pyproject.TARGET} [{'.'.join(signal.keys)}]"
        return ""
    if isinstance(signal, SectionSignal):
        parser = workspace.ini(signal.path)
        if parser is not None and parser.has_section(signal.section):
            return f"{signal.path} [{signal.section}]"
        return ""
    if isinstance(signal, RequirementSignal):
        if signal.name in packages:
            return f"{signal.name} in {pyproject.TARGET} dependencies"
        return ""
    return ""


def _tools(workspace: _Workspace) -> tuple[ToolEvidence, ...]:
    packages = workspace.requirements()
    found: dict[Tool, tuple[str, ...]] = {}
    for module in TOOLING_MODULES:
        sources = tuple(
            source
            for signal in module.signals
            if (source := _match(workspace, signal, packages))
        )
        if sources:
            found[Tool(module.config_key)] = tuple(dict.fromkeys(sources))
    # Tools that read the same files can both match. Keep the one with more
    # evidence; a tie keeps the pair's first member by name, which for the hook
    # runners is pre-commit, whose configuration format both read.
    for pair in EXCLUSIVE_TOOL_PAIRS:
        matched = sorted(tool for tool in pair if tool in found)
        if len(matched) > 1:
            keep = max(
                matched, key=lambda tool: (len(found[tool]), -matched.index(tool))
            )
            for tool in matched:
                if tool is not keep:
                    del found[tool]
    return tuple(ToolEvidence(tool, found[tool]) for tool in Tool if tool in found)


def _version(value: str) -> str | None:
    match = re.search(r"(\d+)\.(\d+)", value)
    return f"{int(match.group(1))}.{int(match.group(2))}" if match else None


def _lower_bound(requires: str) -> str | None:
    try:
        specifiers = SpecifierSet(requires)
    except InvalidSpecifier:
        return None
    bounds: list[Version] = []
    for specifier in specifiers:
        if specifier.operator not in (">=", "~=", "=="):
            continue
        try:
            bounds.append(Version(specifier.version.removesuffix(".*")))
        except InvalidVersion:
            continue
    if not bounds:
        return None
    lowest = min(bounds)
    return f"{lowest.major}.{lowest.minor}"


_SPDX: dict[str, LicenseType] = {
    identifier.casefold(): license_type
    for license_type in LicenseType
    if license_type is not LicenseType.NONE
    for identifier in (
        license_type.value,
        f"{license_type.value}-only",
        f"{license_type.value}-or-later",
    )
}
# The BSD classifier covers every BSD variant, so it cannot name BSD-3-Clause.
_CLASSIFIERS: dict[str, LicenseType] = {
    classifier: license_type
    for license_type in LicenseType
    if license_type is not LicenseType.BSD_3_CLAUSE
    and (classifier := license_type.trove_classifier) is not None
}


def _license_header(text: str) -> LicenseType | None:
    lines = [line.strip().upper() for line in text.splitlines() if line.strip()][:3]
    head = " ".join(lines)
    if lines and lines[0] == "MIT LICENSE":
        return LicenseType.MIT
    if lines and lines[0] == "BSD 3-CLAUSE LICENSE":
        return LicenseType.BSD_3_CLAUSE
    if head.startswith("APACHE LICENSE VERSION 2.0"):
        return LicenseType.APACHE_2_0
    for title, license_type in (
        ("GNU AFFERO GENERAL PUBLIC LICENSE", LicenseType.AGPL_3_0),
        ("GNU LESSER GENERAL PUBLIC LICENSE", LicenseType.LGPL_3_0),
        ("GNU GENERAL PUBLIC LICENSE", LicenseType.GPL_3_0),
    ):
        if head.startswith(f"{title} VERSION 3"):
            return license_type
    return None


def _license_file(workspace: _Workspace) -> tuple[str, str] | None:
    for name in _LICENSE_FILES:
        text = workspace.read_text(name)
        if text is not None:
            return name, text
    return None


def _license(
    workspace: _Workspace,
    project: dict[str, Any],
    license_file: tuple[str, str] | None,
) -> Fact[LicenseType] | None:
    declared = project.get("license")
    if isinstance(declared, dict):
        declared = declared.get("text")
    if (
        isinstance(declared, str)
        and (found := _SPDX.get(declared.strip().casefold())) is not None
    ):
        return Fact(found, f"{pyproject.TARGET} [project].license")
    classifiers = project.get("classifiers")
    if isinstance(classifiers, list):
        for classifier in classifiers:
            if isinstance(classifier, str) and classifier in _CLASSIFIERS:
                return Fact(
                    _CLASSIFIERS[classifier],
                    f"{pyproject.TARGET} [project].classifiers",
                )
    if license_file is not None:
        name, text = license_file
        if (found := _license_header(text)) is not None:
            return Fact(found, name)
    return None


def _supported_os(project: dict[str, Any]) -> Fact[tuple[TargetOS, ...]] | None:
    classifiers = project.get("classifiers")
    if not isinstance(classifiers, list):
        return None
    names = [item for item in classifiers if isinstance(item, str)]
    if _OS_INDEPENDENT in names:
        targets = tuple(TargetOS)
    else:
        targets = tuple(
            target
            for target in TargetOS
            if any(name.startswith(target.trove_classifier) for name in names)
        )
    if not targets:
        return None
    return Fact(targets, f"{pyproject.TARGET} [project].classifiers")


def _author(project: dict[str, Any], key: str) -> Fact[str] | None:
    authors = project.get("authors")
    if not isinstance(authors, list):
        return None
    for author in authors:
        value = author.get(key) if isinstance(author, dict) else None
        if isinstance(value, str) and value.strip():
            return Fact(value.strip(), f"{pyproject.TARGET} [project].authors")
    return None


def _facts(workspace: _Workspace) -> ProjectFacts:
    project = workspace.project()
    requires = project.get("requires-python")
    minimum = (
        Fact(bound, f"{pyproject.TARGET} [project].requires-python")
        if isinstance(requires, str) and (bound := _lower_bound(requires))
        else None
    )
    pinned_text = workspace.read_text(_PYTHON_VERSION_FILE)
    pinned = (
        Fact(version, _PYTHON_VERSION_FILE)
        if pinned_text is not None and (version := _version(pinned_text))
        else None
    )
    description = project.get("description")
    github: Fact[str] | None = None
    urls = project.get("urls")
    if isinstance(urls, dict):
        for url in urls.values():
            if isinstance(url, str) and (match := _GITHUB_URL.match(url.strip())):
                github = Fact(match.group(1), f"{pyproject.TARGET} [project.urls]")
                break
    license_file = _license_file(workspace)
    year: Fact[str] | None = None
    if license_file is not None:
        name, text = license_file
        for line in text.splitlines():
            # GPL texts open with the Free Software Foundation's own copyright.
            if "free software foundation" in line.casefold():
                continue
            if match := _COPYRIGHT.match(line):
                year = Fact(match.group(1), name)
                break
    return ProjectFacts(
        # The recipe's Python is the lowest supported version, as the editor
        # records it, so requires-python outranks a local interpreter pin.
        python_version=minimum or pinned,
        minimum_python=minimum,
        description=Fact(
            description.strip(), f"{pyproject.TARGET} [project].description"
        )
        if isinstance(description, str) and description.strip()
        else None,
        author_name=_author(project, "name"),
        author_email=_author(project, "email"),
        github_username=github,
        license=_license(workspace, project, license_file),
        supported_os=_supported_os(project),
        current_year=year,
    )


def analyze_project(root: Path) -> ProjectAnalysis:
    """Reads what an existing project already has, without changing anything.

    Args:
        root: The project directory.

    Returns:
        The tools found with their evidence, the facts read, and notes about
        anything left out.
    """
    workspace = _Workspace(root)
    tools = _tools(workspace)
    docker = (DOCKERFILE,) if workspace.exists(DOCKERFILE) else ()
    facts = _facts(workspace)
    workflows = PurePosixPath(github_workflows.CI_TARGET).parent
    generated = {
        *github_workflows.CI_LOCATIONS.paths,
        *github_workflows.RELEASE_LOCATIONS.paths,
    }
    for name in sorted(workspace.names(workflows)):
        path = (workflows / name).as_posix()
        if name.endswith((".yml", ".yaml")) and path not in generated:
            workspace.notes.append(AnalysisNote(NoteKind.OTHER_WORKFLOW, path))
    return ProjectAnalysis(
        existing=workspace.exists(pyproject.TARGET) or bool(tools or docker),
        tools=tools,
        docker=docker,
        facts=facts,
        notes=tuple(dict.fromkeys(workspace.notes)),
    )
