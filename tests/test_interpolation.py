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


def test_render_template_preserves_unmatched_placeholders():
    """Test that placeholders absent from context are left intact."""
    template = 'name = "<% project_name %>"\nauthor = "<% unknown_var %>"\n'
    context = {"project_name": "my_app"}

    result = render_template(template, context)
    assert 'name = "my_app"' in result
    assert 'author = "<% unknown_var %>"' in result


def test_render_template_without_toml_escape():
    """Test rendering template with escape_toml=False."""
    template = 'raw = "<% value %>"'
    context = {"value": 'unescaped "quotes"\nand newlines'}

    result = render_template(template, context, escape_toml=False)
    assert result == 'raw = "unescaped "quotes"\nand newlines"'


def test_render_template_multiple_placeholders_and_whitespaces():
    """Test various spacing styles and multiple variables in single string."""
    template = "<% a %><%b%><%   c   %>-<%a%>"
    context = {"a": "1", "b": "2", "c": "3"}

    result = render_template(template, context)
    assert result == "123-1"
