"""JSONC codec safety, lossless round trip, and byte-splice editor acceptance tests."""

import json
import random
from typing import Any

import pytest

from protostar.errors import ConfigurationError
from protostar.jsonc_ast import (
    NodeKind,
    decode_jsonc,
    decode_jsonc_baseline,
    dumps_jsonc,
    encode_jsonc_baseline,
    parse_jsonc,
)
from protostar.merge import MISSING, Value

VS_CODE_SETTINGS = """\
{
    // Python
    "python.defaultInterpreterPath": ".venv/bin/python", // local venv
    /* terminal */
    "python.terminal.activateEnvironment": true,
    "editor.rulers": [80, 100,],
    "files.exclude": {
        "**/.git": true, // hidden
    },
}
"""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("{}", {}),
        ("  {\n}\n", {}),
        ('{"a": 1}', {"a": 1}),
        ('{"a": 1,}', {"a": 1}),
        ('{"a": [1, 2, ],}', {"a": [1, 2]}),
        ('{"a": {"b": null}}', {"a": {"b": None}}),
        ('{"a": true, "b": false}', {"a": True, "b": False}),
        ('{"a": 1.5, "b": -0, "c": 1e3, "d": 2E-2, "e": 0.0}', None),
        ('{"a": "\\u00e9\\n\\"\\/"}', {"a": 'é\n"/'}),
        ('{"a": "\\ud83d\\ude00"}', {"a": "\U0001f600"}),
        ('{"é": "日本"}', {"é": "日本"}),
        ('// lead\n{ /* c */ "a" /* k */ : /* v */ 1 // t\n}\n// end', {"a": 1}),
        ("\ufeff{}", {}),
        ('{"a": 1}\r\n', {"a": 1}),
        ('{"a": "http://x/*not-a-comment*/"}', {"a": "http://x/*not-a-comment*/"}),
    ],
)
def test_decode_accepts_jsonc(text, expected):
    doc = parse_jsonc(text)

    assert doc.text == text
    if expected is not None:
        assert decode_jsonc(text) == expected


def test_decode_preserves_number_types():
    value = decode_jsonc(
        '{"i": 1, "f": 1.0, "neg": -0, "e": 1e2, "big": 12345678901234567890}'
    )

    assert type(value["i"]) is int
    assert type(value["f"]) is float
    assert value["neg"] == 0
    assert type(value["neg"]) is int
    assert type(value["e"]) is float
    assert value["big"] == 12345678901234567890


def test_vs_code_settings_round_trip_and_decode():
    doc = parse_jsonc(VS_CODE_SETTINGS)

    assert doc.text == VS_CODE_SETTINGS
    assert doc.indent_unit == "    "
    assert doc.newline == "\n"
    assert doc.value() == {
        "python.defaultInterpreterPath": ".venv/bin/python",
        "python.terminal.activateEnvironment": True,
        "editor.rulers": [80, 100],
        "files.exclude": {"**/.git": True},
    }


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   \n",
        "// only a comment\n",
        "[]",
        "null",
        '"a"',
        "1",
        "{",
        "}",
        '{"a"}',
        '{"a":}',
        '{"a": 1 "b": 2}',
        '{"a": 1,, "b": 2}',
        '{,"a": 1}',
        '{"a": [,]}',
        '{"a": [1 2]}',
        "{a: 1}",
        "{'a': 1}",
        '{"a": 1} {"b": 2}',
        '{"a": 1} x',
        '{"a": 1, "a": 2}',
        '{"a": {"b": 1, "b": 2}}',
        '{"a": 01}',
        '{"a": +1}',
        '{"a": .5}',
        '{"a": 1.}',
        '{"a": 1e}',
        '{"a": 1e+}',
        '{"a": -}',
        '{"a": 0x10}',
        '{"a": NaN}',
        '{"a": Infinity}',
        '{"a": -Infinity}',
        '{"a": 1e999}',
        '{"a": tru}',
        '{"a": "unterminated}',
        '{"a": "bad \\x escape"}',
        '{"a": "bad \\u12 escape"}',
        '{"a": "\\ud800"}',
        '{"a": "raw\ttab"}',
        '{"a": "raw\nnewline"}',
        '{"a": 1} /* unterminated',
        '{"a": 1 /* unterminated }',
        '{"a": 1, /',
        '{"a": ' + "1" * 5000 + "}",
    ],
)
def test_decode_rejects_invalid_documents(text):
    with pytest.raises(ConfigurationError) as error:
        decode_jsonc(text)

    assert error.value.hint


def test_syntax_errors_report_line_and_column():
    with pytest.raises(ConfigurationError, match=r"line 3, column 8"):
        decode_jsonc('{\n  "a": 1,\n  "b": ?\n}')


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1, // no\n"b": 2}',
        '{"a": /* no */ 1}',
        '{"a": 1,}',
        '{"a": [1,]}',
    ],
)
def test_strict_mode_rejects_jsonc_features(text):
    with pytest.raises(ConfigurationError):
        parse_jsonc(text, strict=True)
    parse_jsonc(text)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param('{"a": ' + "[" * 99 + "0" + "]" * 99 + "}", id="depth-at-limit"),
    ],
)
def test_decode_accepts_boundary_nesting(text):
    parse_jsonc(text)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param('{"a": ' + "[" * 100 + "0" + "]" * 100 + "}", id="depth"),
        pytest.param(
            '{"a": [' + ",".join("0" for _ in range(10000)) + "]}", id="nodes"
        ),
        pytest.param('{"a": "' + "x" * 1_000_000 + '"}', id="bytes"),
    ],
)
def test_decode_enforces_resource_limits(text):
    with pytest.raises(ConfigurationError, match="limits"):
        parse_jsonc(text)


def test_empty_and_comment_only_documents_need_opt_in():
    doc = parse_jsonc("// note\n", allow_empty=True)

    assert doc.root is None
    assert doc.value() == {}
    assert doc.get(("a",)) is MISSING


def test_get_returns_missing_and_nested_values():
    doc = parse_jsonc('{"a": {"b": [1, {"c": 2}]}}')

    assert doc.get(("a", "b", 1, "c")) == 2
    assert doc.get(("a", "b")) == [1, {"c": 2}]
    assert doc.get(()) == doc.value()
    assert doc.get(("a", "x")) is MISSING
    assert doc.get(("a", "b", 9)) is MISSING
    assert doc.get(("a", 0)) is MISSING
    assert doc.root is not None
    assert doc.root.kind is NodeKind.OBJECT


def test_newline_and_indent_inference():
    crlf = parse_jsonc('{\r\n\t"a": 1\r\n}\r\n')

    assert crlf.newline == "\r\n"
    assert crlf.indent_unit == "\t"
    assert parse_jsonc('{"a": 1}').indent_unit == "  "
    assert parse_jsonc('{"a": 1}', default_indent="    ").indent_unit == "    "


def _random_json(rng: random.Random, depth: int = 0):
    kinds = ["str", "int", "float", "bool", "null"]
    if depth < 4:
        kinds += ["obj", "arr"]
    kind = rng.choice(kinds)
    if kind == "obj":
        return {
            f"k{rng.randrange(50)}é\n": _random_json(rng, depth + 1)
            for _ in range(rng.randrange(4))
        }
    if kind == "arr":
        return [_random_json(rng, depth + 1) for _ in range(rng.randrange(4))]
    if kind == "str":
        return rng.choice(["", "a", 'q"uote', "back\\slash", "\u2028", "日本", "\x01"])
    if kind == "int":
        return rng.choice([0, -1, 7, 10**20, -(10**15)])
    if kind == "float":
        return rng.choice([0.5, -1.25, 1e-7, 1e22, 123.456])
    if kind == "bool":
        return rng.choice([True, False])
    return None


@pytest.mark.parametrize("seed", range(40))
def test_decode_agrees_with_stdlib_json(seed):
    rng = random.Random(seed)
    document = {f"root{i}": _random_json(rng) for i in range(rng.randrange(1, 6))}
    for indent in (None, 2, "\t"):
        for ensure_ascii in (True, False):
            text = json.dumps(document, indent=indent, ensure_ascii=ensure_ascii)

            doc = parse_jsonc(text)

            assert doc.text == text
            assert doc.value() == json.loads(text)
            assert decode_jsonc_baseline(text) == document


def test_baseline_codec_is_deterministic_strict_and_null_preserving():
    value: dict[str, Value] = {
        "b": [{"z": 1, "a": None}],
        "a": {"y": 1.5, "x": False},
    }

    encoded = encode_jsonc_baseline(value)

    assert encoded == (
        '{\n  "a": {\n    "x": false,\n    "y": 1.5\n  },\n'
        '  "b": [\n    {\n      "a": null,\n      "z": 1\n    }\n  ]\n}\n'
    )
    assert decode_jsonc_baseline(encoded) == value
    assert encode_jsonc_baseline({}) == "{}\n"
    with pytest.raises(ConfigurationError):
        decode_jsonc_baseline('{"a": 1, // comment\n}')


@pytest.mark.parametrize(
    "value",
    [{"a": float("nan")}, {"a": float("inf")}, {"a": "\ud800"}, {"a": {1, 2}}],
)
def test_unsupported_values_are_rejected(value):
    with pytest.raises(ConfigurationError):
        dumps_jsonc(value)
    with pytest.raises(ConfigurationError):
        parse_jsonc("{}").set(("a",), value["a"])


def test_dumps_uses_requested_indent():
    assert dumps_jsonc({"a": [1]}, "\t") == '{\n\t"a": [\n\t\t1\n\t]\n}\n'


# --- editor ------------------------------------------------------------------


def edit(text: str, **kwargs):
    return parse_jsonc(text, **kwargs)


def test_replace_scalar_touches_only_the_value_span():
    doc = edit(VS_CODE_SETTINGS).set(("python.terminal.activateEnvironment",), False)

    assert doc.text == VS_CODE_SETTINGS.replace(
        '"python.terminal.activateEnvironment": true',
        '"python.terminal.activateEnvironment": false',
    )


def test_replace_string_escapes_and_unicode():
    doc = edit('{"a": "old" /* keep */}').set(("a",), 'new "é"\n')

    assert doc.text == '{"a": "new \\"é\\"\\n" /* keep */}'
    assert doc.value() == {"a": 'new "é"\n'}


@pytest.mark.parametrize(
    ("text", "path", "value", "expected"),
    [
        # multi-line, no trailing comma: comma added before trailing comment
        (
            '{\n  "a": 1 // one\n}\n',
            ("b",),
            2,
            '{\n  "a": 1, // one\n  "b": 2\n}\n',
        ),
        # multi-line, trailing comma style retained
        (
            '{\n  "a": 1,\n}\n',
            ("b",),
            2,
            '{\n  "a": 1,\n  "b": 2,\n}\n',
        ),
        # trailing comment after comma stays on its line
        (
            '{\n  "a": 1, // one\n  // dangling\n}\n',
            ("b",),
            2,
            '{\n  "a": 1, // one\n  "b": 2,\n  // dangling\n}\n',
        ),
        # single-line container stays compact
        ('{"a": 1}', ("b",), 2, '{"a": 1, "b": 2}'),
        ('{"a": 1,}', ("b",), 2, '{"a": 1, "b": 2,}'),
        # separator style copied from the last member
        ('{\n  "a":1\n}\n', ("b",), 2, '{\n  "a":1,\n  "b":2\n}\n'),
        # tabs and CRLF
        (
            '{\r\n\t"a": 1\r\n}\r\n',
            ("b",),
            {"x": [1]},
            '{\r\n\t"a": 1,\r\n\t"b": {\r\n\t\t"x": [\r\n\t\t\t1\r\n\t\t]\r\n\t}\r\n}\r\n',
        ),
        # empty containers
        ("{}", ("a",), 1, '{\n  "a": 1\n}'),
        ("{ }", ("a",), {"b": 1}, '{\n  "a": {\n    "b": 1\n  }\n}'),
        ("{\n}\n", ("a",), 1, '{\n  "a": 1\n}\n'),
        ("{\n  // note\n}\n", ("a",), 1, '{\n  // note\n  "a": 1\n}\n'),
        ("{ /* note */ }", ("a",), 1, '{ /* note */ \n  "a": 1\n}'),
        # nested creation
        (
            '{\n  "a": {\n    "x": 1\n  }\n}\n',
            ("a", "y"),
            2,
            '{\n  "a": {\n    "x": 1,\n    "y": 2\n  }\n}\n',
        ),
        (
            '{\n  "a": 1\n}\n',
            ("p", "q", "r"),
            True,
            '{\n  "a": 1,\n  "p": {\n    "q": {\n      "r": true\n    }\n  }\n}\n',
        ),
        # comment-only and blank documents get a new root
        ("// note\n", ("a",), 1, '// note\n{\n  "a": 1\n}\n'),
        ("", ("a",), 1, '{\n  "a": 1\n}\n'),
        ("// note", ("a", "b"), 1, '// note\n{\n  "a": {\n    "b": 1\n  }\n}\n'),
    ],
)
def test_set_inserts_members(text, path, value, expected):
    doc = edit(text, allow_empty=True).set(path, value)

    assert doc.text == expected
    assert doc.get(path) == value


@pytest.mark.parametrize(
    ("text", "value", "expected"),
    [
        ('{"a": []}', 5, '{"a": [5]}'),
        ('{"a": [1]}', 2, '{"a": [1, 2]}'),
        ('{"a": [1,]}', 2, '{"a": [1, 2,]}'),
        ('{"a": [\n    1\n  ]}', 2, '{"a": [\n    1,\n    2\n  ]}'),
        ('{"a": [1]}', {"k": 1}, '{"a": [1, {"k": 1}]}'),
        ('{"a": [ ]}', {"k": 1}, '{"a": [\n  {\n    "k": 1\n  }\n]}'),
    ],
)
def test_append_extends_arrays(text, value, expected):
    doc = edit(text).append(("a",), value)

    assert doc.text == expected


def test_append_requires_an_existing_array():
    with pytest.raises(ConfigurationError):
        edit('{"a": 1}').append(("a",), 2)
    with pytest.raises(ConfigurationError):
        edit('{"a": 1}').append(("missing",), 2)
    with pytest.raises(ConfigurationError):
        edit("{}").append((), 2)


def test_array_replacement_edits_by_position_and_keeps_comments():
    text = '{\n  "a": [\n    1, // one\n    2, // two\n    3 // three\n  ]\n}\n'

    grown = edit(text).set(("a",), [1, 2, 3, 4])
    assert grown.text == (
        '{\n  "a": [\n    1, // one\n    2, // two\n    3, // three\n    4\n  ]\n}\n'
    )
    shrunk = edit(text).set(("a",), [1])
    assert shrunk.text == '{\n  "a": [\n    1 // one\n  ]\n}\n'
    changed = edit(text).set(("a",), [1, 9, 3])
    assert changed.text == text.replace("2,", "9,")
    assert edit(text).set(("a",), []).value() == {"a": []}
    assert edit('{"a": []}').set(("a",), [[1], {"b": 2}]).value() == {
        "a": [[1], {"b": 2}]
    }


def test_replacing_container_and_scalar_kinds():
    doc = edit('{\n  "a": 1,\n  "b": {"x": 1},\n  "c": [1]\n}\n')

    doc = doc.set(("a",), {"n": [1]}).set(("b",), 7).set(("c",), {"m": 1})

    assert doc.value() == {"a": {"n": [1]}, "b": 7, "c": {"m": 1}}
    assert doc.text.startswith('{\n  "a": {\n    "n": [\n      1\n    ]\n  },\n')
    assert '"b": 7,' in doc.text


@pytest.mark.parametrize(
    ("text", "path", "expected"),
    [
        (
            '{\n  "a": 1,\n  "b": 2,\n  "c": 3\n}\n',
            ("b",),
            '{\n  "a": 1,\n  "c": 3\n}\n',
        ),
        (
            '{\n  "a": 1,\n  "b": 2 // last\n}\n',
            ("b",),
            '{\n  "a": 1\n}\n',
        ),
        (
            '{\n  "a": 1,\n  "b": 2,\n}\n',
            ("b",),
            '{\n  "a": 1,\n}\n',
        ),
        (
            '{\r\n  "a": 1,\r\n  "b": 2\r\n}\r\n',
            ("a",),
            '{\r\n  "b": 2\r\n}\r\n',
        ),
        (
            '{\n  // about a\n  "a": 1,\n  "b": 2\n}\n',
            ("a",),
            '{\n  // about a\n  "b": 2\n}\n',
        ),
        ('{"a": 1, "b": 2}', ("a",), '{"b": 2}'),
        ('{"a": 1, "b": 2}', ("b",), '{"a": 1}'),
        ('{"a": 1,}', ("a",), "{}"),
        ('{"a": 1}', ("a",), "{}"),
        ('{"a": [1, 2, 3]}', ("a", 1), '{"a": [1, 3]}'),
        ('{"a": [1, 2, 3]}', ("a", 2), '{"a": [1, 2]}'),
        ('{"a": {"x": 1, "y": 2}}', ("a", "x"), '{"a": {"y": 2}}'),
    ],
)
def test_delete_members_and_elements(text, path, expected):
    doc = edit(text).delete(path)

    assert doc.text == expected
    assert doc.value() == decode_jsonc(expected)


def test_delete_requires_an_existing_path():
    with pytest.raises(ConfigurationError):
        edit('{"a": 1}').delete(("b",))
    with pytest.raises(ConfigurationError):
        edit('{"a": 1}').delete(())


def test_set_cannot_create_through_scalars_arrays_or_indexes():
    doc = edit('{"a": 1, "b": [1]}')

    for path in [("a", "x"), ("b", "x"), ("b", 5), (5,), ()]:
        with pytest.raises(ConfigurationError):
            doc.set(path, 1)


def test_edits_are_immutable():
    doc = edit('{"a": 1}')

    changed = doc.set(("a",), 2)

    assert doc.text == '{"a": 1}'
    assert changed.text == '{"a": 2}'


def test_bom_is_preserved_through_edits():
    doc = edit('\ufeff{\n  "a": 1\n}\n').set(("b",), 2)

    assert doc.text == '\ufeff{\n  "a": 1,\n  "b": 2\n}\n'


@pytest.mark.parametrize("seed", range(40))
def test_random_edit_sequences_match_a_model_and_keep_comments(seed):
    rng = random.Random(seed)
    markers = [f"/* m{i} */" for i in range(6)]
    text = (
        "{\n"
        + "".join(f'  {marker} "k{i}": {i},\n' for i, marker in enumerate(markers))
        + '  "nested": {"x": 1, // tail\n    "y": [1, 2, 3]},\n'
        + "}\n"
    )
    doc = parse_jsonc(text)
    model: dict[str, Any] = doc.value()
    for step in range(25):
        choice = rng.randrange(5)
        key = f"n{rng.randrange(8)}"
        if choice == 0:
            value = _random_json(rng, 3)
            doc, model[key] = doc.set((key,), value), value
        elif choice == 1:
            value = _random_json(rng, 3)
            doc = doc.set(("nested", key), value)
            model["nested"][key] = value
        elif choice == 2 and key in model:
            doc = doc.delete((key,))
            del model[key]
        elif choice == 3:
            value = rng.randrange(100)
            doc = doc.set(("nested", "y"), model["nested"]["y"] + [value])
            model["nested"]["y"] = model["nested"]["y"] + [value]
        else:
            model["k0"] = step
            doc = doc.set(("k0",), step)

        assert doc.value() == model
        assert decode_jsonc(doc.text) == model
    for marker in markers:
        assert marker in doc.text
    assert "// tail" in doc.text
