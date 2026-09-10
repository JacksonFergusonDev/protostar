from protostar.docs_registry import DocsPage


def test_docs_page_enum_members():
    """Verify that all core documentation pages are defined in the registry."""
    assert DocsPage.GETTING_STARTED.value == "getting-started/"
    assert DocsPage.CLI_REFERENCE.value == "usage/cli-reference/"
    assert DocsPage.CONFIGURATION.value == "usage/configuration/"
    assert DocsPage.TEMPLATES.value == "usage/templates/"
    assert DocsPage.AUTHORING_TEMPLATES.value == "usage/authoring-templates/"
    assert DocsPage.INIT.value == "usage/init/"


def test_docs_page_troubleshooting_anchors():
    """Verify troubleshooting anchors have valid URI fragment structure."""
    assert "#" in DocsPage.TROUBLESHOOTING_DEPS.value
    assert "#" in DocsPage.TROUBLESHOOTING_COLLISIONS.value
    assert "#" in DocsPage.TROUBLESHOOTING_SECURITY.value


def test_docs_page_values_format():
    """Verify all docs pages conform to path standards (no leading slash, valid suffix)."""
    for page in DocsPage:
        val = page.value
        assert not val.startswith("/"), (
            f"Page {page.name} must not start with leading slash"
        )
        if "#" in val:
            path, anchor = val.split("#", 1)
            assert path.endswith("/"), (
                f"Base path for {page.name} must end with trailing slash"
            )
            assert len(anchor) > 0, f"Anchor for {page.name} must not be empty"
        else:
            assert val.endswith("/"), f"Page {page.name} must end with trailing slash"
