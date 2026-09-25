import urllib.parse
from enum import Enum

DOCS_BASE_URL = "https://protostar.jacksonferguson.me/"


class DocsPage(Enum):
    """Registry of known documentation paths and anchors.

    Using a centralized registry prevents broken links if the documentation
    directory structure changes and provides type safety for exception
    classes that need to link to specific remediation steps.
    """

    GETTING_STARTED = ("getting-started/", "Getting Started")
    CLI_REFERENCE = ("usage/cli-reference/", "CLI Reference")
    CONFIGURATION = ("usage/configuration/", "Configuration")
    TEMPLATES = ("usage/templates/", "Templates")
    AUTHORING_TEMPLATES = ("usage/authoring-templates/", "Authoring Templates")
    TEMPLATE_VARIABLES = (
        "usage/authoring-templates/#variables-are-not-secrets",
        "Template Variables",
    )
    RECIPE_VARIABLES = (
        "development/project-recipe/#template-variables",
        "Recipe Template Variables",
    )

    # Troubleshooting Anchors
    TROUBLESHOOTING_DEPS = (
        "usage/troubleshooting/#missing-dependencies-environment-checks",
        "Troubleshooting Dependencies",
    )
    TROUBLESHOOTING_COLLISIONS = (
        "usage/troubleshooting/#workspace-collisions",
        "Workspace Collisions",
    )
    TROUBLESHOOTING_SECURITY = (
        "usage/troubleshooting/#remote-template-security-alerts",
        "Remote Template Security",
    )
    ROLLBACK = ("usage/rollback/", "Rollback")
    RESOLVE_CONFLICTS = ("usage/lifecycle/#resolve-conflicts", "Resolve Conflicts")
    VERSION_SKEW = (
        "usage/lifecycle/#keep-protostar-versions-in-step",
        "Keep Protostar Versions in Step",
    )

    INIT = ("usage/init/", "Init")

    @property
    def path(self) -> str:
        """The relative path segment (including anchor if present)."""
        return self.value[0]

    @property
    def label(self) -> str:
        """The human-readable label for this page/section."""
        return self.value[1]

    def build_url(self, anchor: str | None = None) -> str:
        """Builds the full documentation URL for this documentation page."""
        base = DOCS_BASE_URL if DOCS_BASE_URL.endswith("/") else f"{DOCS_BASE_URL}/"
        url = urllib.parse.urljoin(base, self.path.lstrip("/"))
        if anchor:
            url = f"{url}#{anchor.lstrip('#')}"
        return url
