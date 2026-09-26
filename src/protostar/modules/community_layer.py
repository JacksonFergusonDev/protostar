from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from protostar.community import (
    CommunitySpec,
    generate_bug_report_form,
    generate_code_of_conduct,
    generate_feature_request_form,
    generate_issue_config,
    generate_security_policy,
)
from protostar.documents import community
from protostar.metadata import MetadataKey
from protostar.workflows import TargetOS

from .base import BootstrapModule, PathSignal, ToolInfo

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")


def _supported_os(values: object) -> tuple[TargetOS, ...]:
    """Returns the recognized operating systems among the recorded metadata."""
    if not isinstance(values, list | tuple):
        return ()
    known = {target.value: target for target in TargetOS}
    return tuple(known[str(value)] for value in values if str(value) in known)


class CommunityModule(BootstrapModule):
    """Configures the community health files GitHub surfaces to contributors."""

    cli_flags = ("--community",)
    info = ToolInfo(
        summary="Add the files GitHub shows people who want to contribute",
        adds=(
            "A contributing guide, code of conduct, security policy, and issue "
            "and pull request templates."
        ),
        workflow=(
            "GitHub links these from the repository and pre-fills new issues "
            "and pull requests with the templates. Nothing changes for your own "
            "work."
        ),
        docs_url="https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions",
    )
    config_key = "community"
    signals = tuple(
        PathSignal(path)
        for locations in (
            community.CONTRIBUTING_LOCATIONS,
            community.CODE_OF_CONDUCT_LOCATIONS,
            community.BUG_REPORT_LOCATIONS,
            community.FEATURE_REQUEST_LOCATIONS,
        )
        for path in locations.editable
    )
    required_metadata = (
        MetadataKey.AUTHOR_EMAIL,
        MetadataKey.GITHUB_USERNAME,
        MetadataKey.SUPPORTED_OS,
    )

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return "Community"

    def build(self, manifest: EnvironmentManifest) -> None:
        """Queues the health files that depend only on the project's metadata.

        The contributing guide and pull request template describe the tooling
        other modules contribute, so they are rendered from the aggregated
        manifest once every module has built.

        Args:
            manifest: The centralized state object.
        """
        logger.debug("Building Community layer.")
        manifest.tooling.wants_community = True

        email = manifest.metadata.get(MetadataKey.AUTHOR_EMAIL.value)
        github = manifest.metadata.get(MetadataKey.GITHUB_USERNAME.value)
        spec = CommunitySpec(
            contact_email=str(email) if email else None,
            repository_url=(
                f"https://github.com/{github}/{Path.cwd().name}" if github else None
            ),
            supported_os=_supported_os(
                manifest.metadata.get(MetadataKey.SUPPORTED_OS.value)
            ),
        )
        files = manifest.filesystem
        files.add_file_injection(
            community.CODE_OF_CONDUCT_TARGET, generate_code_of_conduct(spec)
        )
        files.add_file_injection(
            community.SECURITY_TARGET, generate_security_policy(spec)
        )
        files.add_file_injection(
            community.BUG_REPORT_TARGET, generate_bug_report_form(spec)
        )
        files.add_file_injection(
            community.FEATURE_REQUEST_TARGET, generate_feature_request_form()
        )
        if config := generate_issue_config(spec):
            files.add_file_injection(community.ISSUE_CONFIG_TARGET, config)
