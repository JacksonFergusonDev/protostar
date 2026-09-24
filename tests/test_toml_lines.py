"""Source lines of TOML keys."""

import importlib.resources
import tomllib

import pytest

from protostar.interpolation import VARIABLE_PATTERN
from protostar.toml_lines import TomlLineIndex

TEXT = """\
# A template
name = "x"  # trailing comment
description = "has [brackets] and = signs"
deps = [
  "a",   # comment inside an array
  "pytest-cov",
]
table = { a = 1, b = [2, 3] }

[variables.REGION]
description = "r"

[dev]
dev_dependencies = ["pytest-cov"]

[dev.pyproject]
build = \"\"\"
[build-system]
requires = ["hatchling"]
\"\"\"
inline = '''[tool.x]
flag = true'''

[dev.pyproject.lint]
requires = "ruff"
content = '''
[tool.ruff.lint]
extend-select = ["I"]
select = ["E"]
'''

[files]
"src/<% PACKAGE_NAME %>/a.py" = "x"
'single' = "y"

[appends.".envrc".env]
content = "z"
a.b.c = 1

[[jobs]]
id = "first"

[[jobs]]
id = "second"
"""

INDEX = TomlLineIndex(TEXT)


def test_keys_and_headers():
    assert INDEX.line_of(("name",)) == 2
    assert INDEX.line_of(("description",)) == 3
    assert INDEX.line_of(("deps",)) == 4
    assert INDEX.line_of(("table",)) == 8
    assert INDEX.line_of(("variables", "REGION")) == 10
    assert INDEX.line_of(("variables", "REGION", "description")) == 11
    assert INDEX.line_of(("dev", "dev_dependencies")) == 14


def test_brackets_and_equals_inside_values_are_not_keys():
    assert INDEX.line_of(("brackets",)) is None
    assert INDEX.line_of(("a",)) is None


def test_quoted_and_dotted_keys():
    assert INDEX.line_of(("files", "src/<% PACKAGE_NAME %>/a.py")) == 33
    assert INDEX.line_of(("files", "single")) == 34
    assert INDEX.line_of(("appends", ".envrc", "env")) == 36
    assert INDEX.line_of(("appends", ".envrc", "env", "a", "b", "c")) == 38
    assert INDEX.line_of(("appends", ".envrc", "env", "a")) == 38


def test_an_array_of_tables_is_at_its_first_element():
    assert INDEX.line_of(("jobs",)) == 40
    assert INDEX.line_of(("jobs", "id")) == 41


def test_an_implicit_table_is_at_its_first_child():
    assert INDEX.line_of(("variables",)) == 10
    assert INDEX.line_of(("appends",)) == 36


def test_an_absent_key_has_no_line():
    assert INDEX.line_of(("nope",)) is None
    assert INDEX.line_in_value(("nope",), "x") is None
    assert INDEX.line_in_string(("nope",), ("x",)) is None


def test_multi_line_strings_hide_their_content_from_the_document():
    assert INDEX.line_of(("build-system",)) is None
    assert INDEX.line_of(("tool",)) is None
    assert INDEX.line_of(("dev", "pyproject", "lint", "content")) == 26


def test_a_needle_in_a_multi_line_value():
    assert INDEX.line_in_value(("deps",), "pytest-cov") == 6
    assert INDEX.line_in_value(("dev", "dev_dependencies"), "pytest-cov") == 14
    assert INDEX.line_in_value(("deps",), "missing") == 4


def test_keys_inside_a_string_map_to_file_lines():
    lint = ("dev", "pyproject", "lint", "content")
    assert INDEX.line_in_string(lint, ("tool", "ruff", "lint", "select")) == 29
    assert INDEX.line_in_string(lint, ("tool", "ruff")) == 27
    build = ("dev", "pyproject", "build")
    assert INDEX.line_in_string(build, ("build-system", "requires")) == 19
    inline = ("dev", "pyproject", "inline")
    assert INDEX.line_in_string(inline, ("tool", "x")) == 21
    assert INDEX.line_in_string(inline, ("tool", "x", "flag")) == 22


def test_a_key_missing_from_a_string_falls_back_to_its_value():
    build = ("dev", "pyproject", "build")
    assert INDEX.line_in_string(build, ("nope",)) == 17
    assert INDEX.line_in_string(("name",), ("nope",)) == 2


def test_escaped_quotes_do_not_close_a_basic_string():
    index = TomlLineIndex('a = """\nx = \\"""\n"""\nb = 1\n')
    assert index.line_of(("x",)) is None
    assert index.line_of(("b",)) == 4


def test_crlf_line_endings():
    index = TomlLineIndex('a = 1\r\n[t]\r\nb = """\r\nc = 1\r\n"""\r\n')
    assert index.line_of(("t", "b")) == 3
    assert index.line_in_string(("t", "b"), ("c",)) == 4


def test_malformed_toml_locates_what_it_can():
    index = TomlLineIndex("a = 1\n= broken\n[unclosed\nb = \"open\nc = 'open\nd = 2\n")
    assert index.line_of(("a",)) == 1
    assert index.line_of(("b",)) == 4
    assert index.line_of(("d",)) == 6


def _paths(node, prefix=()):
    for key, value in node.items():
        yield (*prefix, key)
        if isinstance(value, dict):
            yield from _paths(value, (*prefix, key))


@pytest.mark.parametrize(
    "template",
    sorted(
        (
            t
            for t in importlib.resources.files("protostar.templates").iterdir()
            if t.name.endswith(".toml")
        ),
        key=str,
    ),
    ids=lambda t: t.name,
)
def test_every_key_of_every_built_in_is_located(template):
    # Indexed as the template check indexes it, placeholders substituted.
    text = VARIABLE_PATTERN.sub("placeholder", template.read_text(encoding="utf-8"))
    lines = text.splitlines()
    index = TomlLineIndex(text)
    data = tomllib.loads(text)
    for path in _paths(data):
        line = index.line_of(path)
        assert line is not None, path
        assert path[-1] in lines[line - 1], (path, lines[line - 1])
    for identity, payload in data.get("dev", {}).get("pyproject", {}).items():
        is_table = isinstance(payload, dict)
        content = payload["content"] if is_table else payload
        where = ("dev", "pyproject", identity, *(("content",) if is_table else ()))
        body = tomllib.loads(content)
        for path in _paths(body):
            line = index.line_in_string(where, path)
            assert line is not None
            assert path[-1] in lines[line - 1], (path, lines[line - 1])
