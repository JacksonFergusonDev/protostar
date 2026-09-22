"""Catalog of the structured workspace documents Protostar merges.

Each submodule owns one document: its target path, the locations its tool reads
it from, the spec its format engine merges it under, and any policy that engine
cannot express, such as guards that hold user-owned content. The format engines
(``toml_ast``, ``yaml_ast``, ``jsonc_ast``) know no file by name; callers look a
document up here.
"""

from collections.abc import Mapping
from types import MappingProxyType

from ..toml_ast import DEFAULT_TOML_SPEC, TomlDocumentSpec
from ..workflows import HookRunner
from ..yaml_ast import YamlDocumentSpec, YamlGuardPolicy
from . import (
    codecov,
    github_workflows,
    pre_commit,
    pyproject,
    readthedocs,
    renovate,
    zensical,
)
from .locations import DocumentLocations

YAML_DOCUMENTS: Mapping[str, YamlDocumentSpec] = MappingProxyType(
    {
        codecov.TARGET: codecov.SPEC,
        pre_commit.TARGET: pre_commit.SPEC,
        github_workflows.CI_TARGET: github_workflows.SPEC,
        github_workflows.RELEASE_TARGET: github_workflows.SPEC,
        readthedocs.TARGET: readthedocs.SPEC,
    }
)
# YAML documents a module may declare as one managed contribution. The others are
# generated whole by Protostar and are never assembled from contributions.
YAML_CONTRIBUTION_TARGETS = frozenset({codecov.TARGET, readthedocs.TARGET})
# Guards that depend only on the decoded documents. Pre-commit's pin guard is
# planned per run from registry responses, so its caller passes it directly.
YAML_GUARDS: Mapping[str, YamlGuardPolicy] = MappingProxyType(
    {
        github_workflows.CI_TARGET: github_workflows.guard_workflow,
        github_workflows.RELEASE_TARGET: github_workflows.guard_workflow,
        readthedocs.TARGET: readthedocs.guard_build,
    }
)
TOML_DOCUMENTS: Mapping[str, TomlDocumentSpec] = MappingProxyType(
    {pyproject.TARGET: pyproject.SPEC, zensical.TARGET: zensical.SPEC}
)
# Documents whose tool reads more than one path. Pre-commit's depend on the hook
# runner and live in `pre_commit.LOCATIONS`.
LOCATIONS: Mapping[str, DocumentLocations] = MappingProxyType(
    {
        codecov.TARGET: codecov.LOCATIONS,
        github_workflows.CI_TARGET: github_workflows.CI_LOCATIONS,
        github_workflows.RELEASE_TARGET: github_workflows.RELEASE_LOCATIONS,
        readthedocs.TARGET: readthedocs.LOCATIONS,
        renovate.TARGET: renovate.LOCATIONS,
        zensical.TARGET: zensical.LOCATIONS,
    }
)
# Every path a YAML document may be edited at, under any hook runner.
_YAML_SPECS_BY_PATH: Mapping[str, YamlDocumentSpec] = MappingProxyType(
    {
        path: YAML_DOCUMENTS[locations.target]
        for locations in (*LOCATIONS.values(), *pre_commit.LOCATIONS.values())
        if locations.target in YAML_DOCUMENTS
        for path in locations.editable
    }
)


def toml_spec(path: str) -> TomlDocumentSpec:
    """Returns the merge spec for a TOML target, or plain tables for unknown files.

    Args:
        path: Workspace-relative POSIX path of the TOML document.

    Returns:
        The document's spec, or ``DEFAULT_TOML_SPEC``.
    """
    return TOML_DOCUMENTS.get(path, DEFAULT_TOML_SPEC)


def yaml_spec(path: str) -> YamlDocumentSpec | None:
    """Returns the spec of the YAML document a path holds, under any of its names.

    Args:
        path: Workspace-relative POSIX path, such as an ownership record's.

    Returns:
        The document's spec, or ``None`` for a path no YAML document uses.
    """
    return _YAML_SPECS_BY_PATH.get(path)


def document_locations(target: str, hook_runner: HookRunner) -> DocumentLocations:
    """Returns the paths a document's tool reads it from.

    Args:
        target: The document's canonical workspace path.
        hook_runner: The project's hook runner, which decides pre-commit's paths.

    Returns:
        The document's locations; a document read from one path has only its
        target.
    """
    if target == pre_commit.TARGET and hook_runner in pre_commit.LOCATIONS:
        return pre_commit.LOCATIONS[hook_runner]
    return LOCATIONS.get(target, DocumentLocations(target))
