"""Community health files and the locations GitHub reads each one from.

GitHub reads a contributing guide, code of conduct, security policy, and pull
request template from `.github/`, the repository root, or `docs/`, and uses the
first it finds. Protostar creates each at its most visible path and adopts an
existing one wherever GitHub would read it. Issue forms live only under
`.github/ISSUE_TEMPLATE/`; a Markdown template of the same name competes with a
form, so Protostar never adds a form beside one.
"""

from .locations import DocumentLocations

CONTRIBUTING_TARGET = "CONTRIBUTING.md"
CODE_OF_CONDUCT_TARGET = "CODE_OF_CONDUCT.md"
SECURITY_TARGET = "SECURITY.md"
PULL_REQUEST_TARGET = ".github/pull_request_template.md"
BUG_REPORT_TARGET = ".github/ISSUE_TEMPLATE/bug_report.yml"
FEATURE_REQUEST_TARGET = ".github/ISSUE_TEMPLATE/feature_request.yml"
ISSUE_CONFIG_TARGET = ".github/ISSUE_TEMPLATE/config.yml"

_FOLDERS = (".github/", "", "docs/")


def _health_file(name: str) -> DocumentLocations:
    """Returns the locations of a health file GitHub reads under any folder.

    Args:
        name: The file's stem, such as ``CONTRIBUTING``.

    Returns:
        The Markdown file at the root as the target, the Markdown files in the
        other folders as aliases, and the other formats GitHub renders as
        competitors.
    """
    target = f"{name}.md"
    return DocumentLocations(
        target,
        aliases=tuple(f"{folder}{target}" for folder in _FOLDERS if folder),
        competitors=tuple(
            f"{folder}{name}{suffix}"
            for folder in _FOLDERS
            for suffix in (".rst", ".txt", "")
        ),
    )


def _issue_form(stem: str) -> DocumentLocations:
    """Returns the locations of an issue form and the template it competes with.

    Args:
        stem: The form's file stem, such as ``bug_report``.

    Returns:
        The ``.yml`` form as the target, its ``.yaml`` spelling as an alias, and
        a Markdown issue template of the same name as a competitor.
    """
    folder = ".github/ISSUE_TEMPLATE/"
    return DocumentLocations(
        f"{folder}{stem}.yml",
        aliases=(f"{folder}{stem}.yaml",),
        competitors=(f"{folder}{stem}.md",),
    )


CONTRIBUTING_LOCATIONS = _health_file("CONTRIBUTING")
CODE_OF_CONDUCT_LOCATIONS = _health_file("CODE_OF_CONDUCT")
SECURITY_LOCATIONS = _health_file("SECURITY")
# GitHub matches this name in any case, but case-insensitive filesystems do
# too: listing `PULL_REQUEST_TEMPLATE.md` beside it would make the file Protostar
# wrote look like its own duplicate on macOS and Windows.
PULL_REQUEST_LOCATIONS = DocumentLocations(
    PULL_REQUEST_TARGET,
    aliases=tuple(
        f"{folder}pull_request_template.md"
        for folder in _FOLDERS
        if f"{folder}pull_request_template.md" != PULL_REQUEST_TARGET
    ),
)
BUG_REPORT_LOCATIONS = _issue_form("bug_report")
FEATURE_REQUEST_LOCATIONS = _issue_form("feature_request")

LOCATIONS = (
    CONTRIBUTING_LOCATIONS,
    CODE_OF_CONDUCT_LOCATIONS,
    SECURITY_LOCATIONS,
    PULL_REQUEST_LOCATIONS,
    BUG_REPORT_LOCATIONS,
    FEATURE_REQUEST_LOCATIONS,
)
"""Every community document read from more than one path."""
