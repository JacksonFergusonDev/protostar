import json
import tomllib

import pytest
from ruamel.yaml import YAML

from protostar.interpolation import (
    escape,
    escaped,
    extract_variables,
    quoted,
    render_template,
)

AWKWARD = 'Line 1\nLine 2 with "quotes", \\backslashes\\, a\ttab, \x01, and \x7f'


def test_extract_variables():
    """Test that placeholders are correctly identified and deduplicated."""
    content = 'name = "<%project_name%>"\ndesc = "<% description %>"\nrepo = "<%project_name%>"'
    variables = extract_variables(content)
    assert variables == ["project_name", "description"]


def test_escape_keeps_a_value_inside_its_string():
    assert escape('say "hi" \\ bye\n') == 'say \\"hi\\" \\\\ bye\\n'


def test_escape_leaves_unicode_as_written():
    assert escape("café ✓") == "café ✓"


@pytest.mark.parametrize(
    "load",
    [
        lambda literal: tomllib.loads(f"value = {literal}")["value"],
        lambda literal: json.loads(literal),
        lambda literal: YAML(typ="safe").load(f"value: {literal}")["value"],
    ],
    ids=["toml", "json", "yaml"],
)
def test_quoted_round_trips_through_every_structured_format(load):
    assert load(quoted(AWKWARD)) == AWKWARD


def test_escaped_escapes_every_value():
    assert escaped({"a": '"', "b": "plain"}) == {"a": '\\"', "b": "plain"}


def test_render_template():
    """Test that placeholders are successfully replaced with context values."""
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


def test_render_template_substitutes_values_as_given():
    template = "# Welcome to <% value %>"
    context = {"value": 'say "hi" \\ bye'}

    assert render_template(template, context) == '# Welcome to say "hi" \\ bye'


def test_render_template_multiple_placeholders_and_whitespaces():
    """Test various spacing styles and multiple variables in single string."""
    template = "<% a %><%b%><%   c   %>-<%a%>"
    context = {"a": "1", "b": "2", "c": "3"}

    result = render_template(template, context)
    assert result == "123-1"
