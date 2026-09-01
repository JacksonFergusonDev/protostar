from enum import StrEnum


class DocsPage(StrEnum):
    """Registry of known documentation paths and anchors.

    Using a centralized registry prevents broken links if the documentation
    directory structure changes and provides type safety for exception
    classes that need to link to specific remediation steps.
    """

    GETTING_STARTED = "getting-started/"
    CLI_REFERENCE = "usage/cli-reference/"
    CONFIGURATION = "usage/configuration/"
    TEMPLATES = "usage/templates/"
    AUTHORING_TEMPLATES = "usage/authoring-templates/"

    # Troubleshooting Anchors
    TROUBLESHOOTING_DEPS = (
        "usage/troubleshooting/#missing-dependencies-environment-checks"
    )
    TROUBLESHOOTING_COLLISIONS = "usage/troubleshooting/#workspace-collisions"
    TROUBLESHOOTING_SECURITY = "usage/troubleshooting/#remote-template-security-alerts"

    INIT = "usage/init/"
