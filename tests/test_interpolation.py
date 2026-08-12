from protostar.interpolation import extract_variables, render_template, toml_escape


def test_extract_variables():
    """Test that placeholders are correctly identified and deduplicated."""
    content = 'name = "<%project_name%>"\ndesc = "<% description %>"\nrepo = "<%project_name%>"'
    variables = extract_variables(content)
    assert variables == ["project_name", "description"]


def test_toml_escape():
    """Test that potentially dangerous characters are escaped for TOML strings."""
    unsafe = 'Line 1\nLine 2 with "quotes" and \\backslashes\\'
    safe = toml_escape(unsafe)
    assert safe == 'Line 1\\nLine 2 with \\"quotes\\" and \\\\backslashes\\\\'


def test_render_template():
    """Test that placeholders are successfully replaced with escaped context values."""
    template = 'name = "<% project_name %>"\ndir = "src/<%project_name%>"\n'
    context = {"project_name": "my_app"}

    result = render_template(template, context)
    assert 'name = "my_app"' in result
    assert 'dir = "src/my_app"' in result
