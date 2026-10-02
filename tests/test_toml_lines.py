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


@pytest.fixture
def index():
    # Built in each test, not at import: mutmut forks every mutant from a
    # process that already imported this module, so an index built once
    # would never run the mutated scanner.
    return TomlLineIndex(TEXT)


def test_keys_and_headers(index):
    assert index.line_of(("name",)) == 2
    assert index.line_of(("description",)) == 3
    assert index.line_of(("deps",)) == 4
    assert index.line_of(("table",)) == 8
    assert index.line_of(("variables", "REGION")) == 10
    assert index.line_of(("variables", "REGION", "description")) == 11
    assert index.line_of(("dev", "dev_dependencies")) == 14


def test_brackets_and_equals_inside_values_are_not_keys(index):
    assert index.line_of(("brackets",)) is None
    assert index.line_of(("a",)) is None


def test_quoted_and_dotted_keys(index):
    assert index.line_of(("files", "src/<% PACKAGE_NAME %>/a.py")) == 33
    assert index.line_of(("files", "single")) == 34
    assert index.line_of(("appends", ".envrc", "env")) == 36
    assert index.line_of(("appends", ".envrc", "env", "a", "b", "c")) == 38
    assert index.line_of(("appends", ".envrc", "env", "a")) == 38


def test_an_array_of_tables_is_at_its_first_element(index):
    assert index.line_of(("jobs",)) == 40
    assert index.line_of(("jobs", "id")) == 41


def test_an_implicit_table_is_at_its_first_child(index):
    assert index.line_of(("variables",)) == 10
    assert index.line_of(("appends",)) == 36


def test_an_absent_key_has_no_line(index):
    assert index.line_of(("nope",)) is None
    assert index.line_in_value(("nope",), "x") is None
    assert index.line_in_string(("nope",), ("x",)) is None


def test_multi_line_strings_hide_their_content_from_the_document(index):
    assert index.line_of(("build-system",)) is None
    assert index.line_of(("tool",)) is None
    assert index.line_of(("dev", "pyproject", "lint", "content")) == 26


def test_a_needle_in_a_multi_line_value(index):
    assert index.line_in_value(("deps",), "pytest-cov") == 6
    assert index.line_in_value(("dev", "dev_dependencies"), "pytest-cov") == 14
    assert index.line_in_value(("deps",), "missing") == 4


def test_keys_inside_a_string_map_to_file_lines(index):
    lint = ("dev", "pyproject", "lint", "content")
    assert index.line_in_string(lint, ("tool", "ruff", "lint", "select")) == 29
    assert index.line_in_string(lint, ("tool", "ruff")) == 27
    build = ("dev", "pyproject", "build")
    assert index.line_in_string(build, ("build-system", "requires")) == 19
    inline = ("dev", "pyproject", "inline")
    assert index.line_in_string(inline, ("tool", "x")) == 21
    assert index.line_in_string(inline, ("tool", "x", "flag")) == 22


def test_a_key_missing_from_a_string_falls_back_to_its_value(index):
    build = ("dev", "pyproject", "build")
    assert index.line_in_string(build, ("nope",)) == 17
    assert index.line_in_string(("name",), ("nope",)) == 2


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


def test_a_needle_is_found_only_inside_its_value(index):
    # "pytest-cov" is on line 6 and "ruff" on line 24, outside these values.
    assert index.line_in_value(("dev", "dev_dependencies"), "pytest-cov") == 14
    assert index.line_in_value(("name",), "pytest-cov") == 2
    assert index.line_in_value(("dev",), "ruff") == 13
    assert index.line_in_value(("dev",), "name") == 13


def test_a_needle_found_twice_is_at_its_first_line():
    index = TomlLineIndex('a = [\n  "x",\n  "x",\n]\n')
    assert index.line_in_value(("a",), "x") == 2


def test_a_dotted_key_indexes_its_value_and_each_parent():
    index = TomlLineIndex('x.y.z = [\n  "needle",\n]\n')
    assert index.line_in_value(("x", "y", "z"), "needle") == 2
    assert index.line_in_value(("x",), "needle") == 1
    assert index.line_in_value(("x", "y"), "needle") == 1


def test_brackets_inside_a_value_keep_it_open():
    text = 'a = [\n  { X = 1 },\n  "needle",\n]\nt = { X = 1 }\nb = 2\n'
    index = TomlLineIndex(text)
    assert index.line_in_value(("a",), "needle") == 3
    assert index.line_of(("b",)) == 6


def test_a_bracket_in_a_comment_does_not_open_the_value():
    index = TomlLineIndex("a = 1  # see [docs\nb = 2\n")
    assert index.line_of(("b",)) == 2


def test_a_multi_line_string_may_end_in_extra_quotes():
    index = TomlLineIndex('a = """x""""\nb = 1\nc = \'\'\'y\'\'\'')
    assert index.line_of(("b",)) == 2
    assert index.line_of(("c",)) == 3


def test_an_empty_multi_line_string_closes():
    index = TomlLineIndex('a = """"""\nb = 1\n')
    assert index.line_of(("b",)) == 2


def test_a_compact_multi_line_string_maps_its_keys():
    index = TomlLineIndex('a="""\n[t]\nk = 1\n"""\n')
    assert index.line_in_string(("a",), ("t", "k")) == 3


def test_escapes_in_multi_line_strings():
    # An escaped quote leaves a basic string open; an escaped backslash
    # doesn't, and neither does any backslash in a literal string.
    index = TomlLineIndex(
        'a = """x\\"""\ny = 1\n"""\n'
        'b = """x\\\\"""\nc = 1\n'
        'd = """x\\""""\ne = 1\n'
        "f = '''x\\'''\ng = 1\n"
    )
    assert index.line_of(("y",)) is None
    assert index.line_of(("c",)) == 5
    assert index.line_of(("e",)) == 7
    assert index.line_of(("g",)) == 9


def test_quoted_keys_and_their_escapes():
    index = TomlLineIndex(
        '"a\\"b" = 1\n'
        '"a\\"" = 2\n'
        "'a\\' = 3\n"
        '"a\\tb" = 4\n'
        '"a\\q" = 5\n'
        '"q".r = 6\n'
        "'' = 7\n"
        "Xy = 8\n"
    )
    assert index.line_of(('a"b',)) == 1
    assert index.line_of(('a"',)) == 2
    assert index.line_of(("a\\",)) == 3
    assert index.line_of(("a\tb",)) == 4
    # An escape JSON doesn't share stays as written.
    assert index.line_of(("a\\q",)) == 5
    assert index.line_of(("q", "r")) == 6
    assert index.line_of(("",)) == 7
    assert index.line_of(("Xy",)) == 8


def test_an_unterminated_string_ends_with_its_line():
    index = TomlLineIndex('a = "open\nb = "x"\n')
    assert index.line_of(("b",)) == 2


@pytest.mark.parametrize(
    "text",
    ["a = 1  # note", "a = 1\n# note", 'a = "open', "a =", "a = 1\n[t."],
    ids=["value-comment", "comment", "string", "no-value", "header"],
)
def test_text_ending_without_a_newline_is_indexed(text):
    assert TomlLineIndex(text).line_of(("a",)) == 1
