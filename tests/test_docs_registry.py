from protostar.docs_registry import DocsPage


def test_docs_page_enum_members():
    """Verify that all core documentation pages are defined in the registry."""
    assert DocsPage.GETTING_STARTED.path == "getting-started/"
    assert DocsPage.CLI_REFERENCE.path == "usage/cli-reference/"
    assert DocsPage.CLI_REFERENCE.label == "CLI Reference"
    assert DocsPage.CONFIGURATION.path == "usage/configuration/"
    assert DocsPage.TEMPLATES.path == "usage/templates/"
    assert DocsPage.AUTHORING_TEMPLATES.path == "usage/authoring-templates/"
    assert DocsPage.INIT.path == "usage/init/"


def test_docs_page_troubleshooting_anchors():
    """Verify troubleshooting anchors have valid URI fragment structure."""
    assert "#" in DocsPage.TROUBLESHOOTING_DEPS.path
    assert "#" in DocsPage.TROUBLESHOOTING_COLLISIONS.path
    assert "#" in DocsPage.TROUBLESHOOTING_SECURITY.path


def test_docs_page_values_format():
    """Verify all docs pages conform to path standards (no leading slash, valid suffix)."""
    for page in DocsPage:
        val = page.path
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
