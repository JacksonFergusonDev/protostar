"""Pure generators for the community health files that depend only on metadata.

The contributing guide and pull request template describe the project's tooling,
so they render from a ``GuideSpec`` in ``workflows``. The files here need only
who maintains the project and where it lives.
"""

import importlib.resources
from dataclasses import dataclass

from ..workflows import TargetOS

__all__ = [
    "CommunitySpec",
    "generate_bug_report_form",
    "generate_code_of_conduct",
    "generate_feature_request_form",
    "generate_issue_config",
    "generate_security_policy",
]

_CONTACT_PLACEHOLDER = "[INSERT CONTACT METHOD]"


@dataclass(frozen=True)
class CommunitySpec:
    """Who maintains the project, and where it is hosted.

    Attributes:
        contact_email: The maintainer's email address, if known.
        repository_url: The project's GitHub URL, if the owner is known.
        supported_os: The operating systems a bug report may name.
    """

    contact_email: str | None
    repository_url: str | None
    supported_os: tuple[TargetOS, ...]

    @property
    def advisory_url(self) -> str | None:
        """Returns the page that opens a private vulnerability report, if hosted."""
        if self.repository_url is None:
            return None
        return f"{self.repository_url}/security/advisories/new"


def generate_code_of_conduct(spec: CommunitySpec) -> str:
    """Returns the Contributor Covenant 2.1, naming the maintainer as the contact.

    Without an email address the covenant keeps its own placeholder, so the gap
    is visible rather than filled with a contact that reaches nobody.

    Args:
        spec: The project's maintainer and host.

    Returns:
        The Markdown code of conduct.
    """
    covenant = (
        importlib.resources.files(__name__)
        .joinpath("code_of_conduct.md")
        .read_text(encoding="utf-8")
    )
    if spec.contact_email:
        covenant = covenant.replace(_CONTACT_PLACEHOLDER, f"<{spec.contact_email}>")
    return covenant


def generate_security_policy(spec: CommunitySpec) -> str:
    """Returns a security policy that routes reports away from public issues.

    Args:
        spec: The project's maintainer and host.

    Returns:
        The Markdown security policy.
    """
    channels = []
    if spec.advisory_url:
        channels.append(
            f"through GitHub's [private vulnerability reporting]({spec.advisory_url})"
        )
    if spec.contact_email:
        channels.append(f"by email to <{spec.contact_email}>")
    route = " or ".join(channels) if channels else "to the maintainers privately"
    lines = [
        "# Security Policy",
        "",
        "## Supported Versions",
        "",
        "Security fixes are made in the latest release only.",
        "",
        "## Reporting a Vulnerability",
        "",
        "Please do not report security vulnerabilities in public issues, "
        "discussions, or pull requests.",
        "",
        f"Report them {route}. Include a description of the vulnerability, the "
        "steps to reproduce it, and the impact you expect it to have.",
    ]
    if spec.advisory_url:
        lines.extend(
            [
                "",
                "<!-- The reporting link works once private vulnerability reporting "
                "is enabled in the repository's security settings. -->",
            ]
        )
    return "\n".join(lines) + "\n"


def generate_bug_report_form(spec: CommunitySpec) -> str:
    """Returns a GitHub issue form that asks for what reproduces a bug.

    Args:
        spec: The project's maintainer and host.

    Returns:
        The issue form's YAML.
    """
    if spec.supported_os:
        options = "\n".join(
            f"        - {name}" for name in (*spec.supported_os, "Other")
        )
        platform = f"""  - type: dropdown
    id: os
    attributes:
      label: Operating system
      options:
{options}
    validations:
      required: true
"""
    else:
        platform = """  - type: input
    id: os
    attributes:
      label: Operating system
      placeholder: "e.g., Ubuntu 24.04"
    validations:
      required: true
"""
    return f"""name: Bug Report
description: Report something that does not work as expected.
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: Thank you for reporting a bug. Please search the existing issues first.
  - type: textarea
    id: description
    attributes:
      label: What happened?
      description: Describe the bug and paste any error output.
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: Steps to reproduce
      description: The smallest set of steps or code that shows the bug.
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
      description: What did you expect to happen instead?
    validations:
      required: true
  - type: input
    id: version
    attributes:
      label: "<% PROJECT_NAME %> version"
      placeholder: "e.g., 0.1.0"
    validations:
      required: true
  - type: input
    id: python-version
    attributes:
      label: Python version
      placeholder: "e.g., 3.13.1"
    validations:
      required: true
{platform}"""


def generate_feature_request_form() -> str:
    """Returns a GitHub issue form that asks for the problem before the solution.

    Returns:
        The issue form's YAML.
    """
    return """name: Feature Request
description: Suggest an improvement or a new feature.
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem
      description: What are you trying to do, and what gets in the way?
    validations:
      required: true
  - type: textarea
    id: solution
    attributes:
      label: Proposed solution
      description: How would you like it to work?
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
      description: Other approaches or workarounds you have tried.
"""


def generate_issue_config(spec: CommunitySpec) -> str | None:
    """Returns the issue chooser's configuration, linking private security reports.

    Args:
        spec: The project's maintainer and host.

    Returns:
        The configuration's YAML, or ``None`` when the project's host is unknown,
        since the chooser's defaults need no file.
    """
    if spec.advisory_url is None:
        return None
    return f"""blank_issues_enabled: true
contact_links:
  - name: Report a security vulnerability
    url: {spec.advisory_url}
    about: Report vulnerabilities privately, never in a public issue.
"""
