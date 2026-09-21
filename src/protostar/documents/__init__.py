"""Catalog of the structured workspace documents Protostar merges.

Each submodule owns one document: its target path, the spec its format engine
merges it under, and any policy that engine cannot express, such as guards that
hold user-owned content. The format engines (``toml_ast``, ``yaml_ast``,
``jsonc_ast``) know no file by name; callers look a document up here.
"""

from collections.abc import Mapping
from functools import partial
from types import MappingProxyType

from ..toml_ast import DEFAULT_TOML_SPEC, TomlDocumentSpec
from ..yaml_ast import YamlDocumentSpec, YamlGuardPolicy
from . import codecov, github_workflows, pre_commit, pyproject, readthedocs, zensical

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
        github_workflows.CI_TARGET: partial(
            github_workflows.guard_workflow, github_workflows.CI_TARGET
        ),
        github_workflows.RELEASE_TARGET: partial(
            github_workflows.guard_workflow, github_workflows.RELEASE_TARGET
        ),
        readthedocs.TARGET: readthedocs.guard_build,
    }
)
TOML_DOCUMENTS: Mapping[str, TomlDocumentSpec] = MappingProxyType(
    {pyproject.TARGET: pyproject.SPEC, zensical.TARGET: zensical.SPEC}
)


def toml_spec(path: str) -> TomlDocumentSpec:
    """Returns the merge spec for a TOML target, or plain tables for unknown files.

    Args:
        path: Workspace-relative POSIX path of the TOML document.

    Returns:
        The document's spec, or ``DEFAULT_TOML_SPEC``.
    """
    return TOML_DOCUMENTS.get(path, DEFAULT_TOML_SPEC)
