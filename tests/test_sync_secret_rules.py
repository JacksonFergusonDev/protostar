import base64
import dataclasses
import json
import re
import string
import tomllib
import warnings
import zlib
from pathlib import Path

import pytest

from protostar import _secret_rules
from protostar._fallbacks import DEFAULT_REVISIONS
from protostar.secret_guard import (
    Allowlist,
    AllowlistCondition,
    AllowlistTarget,
    Rule,
    RuleSet,
    _matches,
    decode_rules,
    load_rules,
)
from scripts import sync_secret_rules
from scripts.sync_secret_rules import (
    POSIX_CLASSES,
    TranslationError,
    compile_strict,
    convert,
    convert_allowlist,
    generate,
    read_payload,
    render,
    translate,
)

# --- translate ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("go", "python"),
    [
        (r"ghp_[0-9a-zA-Z]{36}", r"ghp_[0-9a-zA-Z]{36}"),
        (r"(?i)leading\b", r"(?i)leading\b"),
        (r"end\z", r"end\Z"),
        (r"\\z", r"\\z"),
        (r"[[:alnum:]]{4}", r"[0-9A-Za-z]{4}"),
        (r"[^[:space:]x]", "[^\\t\\n\\v\\f\\r x]"),
        (r"[a[]", r"[a\[]"),
        (r"[]a]", r"[\]a]"),
        (r"(?<name>\w+)", r"(?P<name>\w+)"),
        (r"(?<=a)b(?<!c)", r"(?<=a)b(?<!c)"),
        (r"p8e-(?i)[a-z]{4}", r"p8e-(?i:[a-z]{4})"),
        (r"(A(?i)B|C)", r"(A(?i:B)|(?i:C))"),
        (r"a(?i)b|c", r"a(?i:b)|(?i:c)"),
        (r"a(?i)b(?s)c|d", r"a(?i:b(?s:c))|(?i:(?s:d))"),
        (r"x(?-i)y", r"x(?-i:y)"),
        (r"[(|)](?i)z", r"[(|)](?i:z)"),
        (r"\((?i)z\)", r"\((?i:z\))"),
    ],
)
def test_translate(go, python):
    assert translate(go) == python
    compile_strict(python)


def test_translated_flag_keeps_go_scope():
    """In Go, a mid-pattern flag also covers later branches of its group."""
    pattern = re.compile(translate(r"^(A(?i)B|C)$"))

    assert pattern.match("Ab")
    assert not pattern.match("ab")
    assert pattern.match("c")


@pytest.mark.parametrize(
    ("name", "members"),
    [
        ("alnum", string.ascii_letters + string.digits),
        ("alpha", string.ascii_letters),
        ("digit", string.digits),
        ("lower", string.ascii_lowercase),
        ("upper", string.ascii_uppercase),
        ("word", string.ascii_letters + string.digits + "_"),
        ("xdigit", string.hexdigits),
        ("punct", string.punctuation),
        ("space", " \t\n\v\f\r"),
        ("blank", " \t"),
        ("graph", "".join(chr(c) for c in range(0x21, 0x7F))),
        ("print", "".join(chr(c) for c in range(0x20, 0x7F))),
        ("cntrl", "".join(chr(c) for c in [*range(0x20), 0x7F])),
        ("ascii", "".join(chr(c) for c in range(0x80))),
    ],
)
def test_posix_classes_match_re2_definitions(name, members):
    pattern = re.compile(translate(f"[[:{name}:]]"))
    matched = {chr(c) for c in range(0x80) if pattern.fullmatch(chr(c))}

    assert matched == set(members)
    assert name in POSIX_CLASSES


@pytest.mark.parametrize(
    "go",
    [
        r"\Qa.b\E",
        r"\p{L}",
        r"[\pL]",
        r"(?U)a+",
        r"x(?U)a+",
        r"[[:nope:]]",
        r"[[:^alpha:]]",
        "(a",
        "a)",
        "[a",
    ],
)
def test_translate_rejects_what_python_cannot_express(go):
    with pytest.raises(TranslationError):
        translate(go)


def test_compile_strict_treats_warnings_as_errors():
    # An untranslated POSIX class compiles with only a FutureWarning in Python.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        re.compile("[[:alnum:]]", re.ASCII)
    with pytest.raises(TranslationError):
        compile_strict("[[:alnum:]]")


# --- convert -----------------------------------------------------------------


def test_convert_allowlist_keeps_only_checks_a_value_can_meet():
    assert convert_allowlist(
        {"regexTarget": "match", "regexes": ["a(?i)b"], "paths": ["x"]}
    ) == Allowlist(target=AllowlistTarget.MATCH, regexes=("a(?i:b)",))
    assert convert_allowlist({"stopwords": ["Beta", "alpha", "beta"]}) == Allowlist(
        stopwords=("alpha", "beta")
    )


def test_convert_allowlist_drops_allowlists_that_can_never_apply():
    """A value has no path or commit: AND with either never passes."""
    assert (
        convert_allowlist({"condition": "AND", "regexes": ["x"], "paths": ["y"]})
        is None
    )
    assert (
        convert_allowlist({"condition": "&&", "stopwords": ["x"], "commits": ["c"]})
        is None
    )
    assert convert_allowlist({"paths": ["only-a-path"]}) is None
    assert convert_allowlist({"condition": "and", "regexes": ["x"]}) == Allowlist(
        condition=AllowlistCondition.AND, regexes=("x",)
    )


@pytest.mark.parametrize(
    "raw",
    [
        {"condition": "XOR", "regexes": ["x"]},
        {"regexTarget": "file", "regexes": ["x"]},
        {"regex": ["x"]},
    ],
)
def test_convert_allowlist_rejects_unknown_fields_and_values(raw):
    with pytest.raises(TranslationError):
        convert_allowlist(raw)


def _config(*rules, **extra):
    return {"title": "test", "rules": list(rules), **extra}


def test_convert_translates_sorts_and_records_omissions():
    rule_set = convert(
        _config(
            {"id": "zeta", "regex": "z(?i)z", "keywords": ["ZZ"], "entropy": 3},
            {"id": "alpha", "regex": "a+", "keywords": ["a"], "secretGroup": 0},
            {"id": "scoped", "regex": "x", "path": r"\.tf$", "keywords": ["x"]},
            {"id": "file-only", "path": r"\.p12$"},
        )
    )

    assert rule_set.rules == (
        Rule(rule_id="alpha", pattern="a+", keywords=("a",)),
        Rule(rule_id="zeta", pattern="z(?i:z)", keywords=("zz",), entropy=3.0),
    )
    assert rule_set.omitted == (
        ("file-only", "applies only to files matching a path"),
        ("scoped", "applies only to files matching a path"),
    )


def test_convert_attaches_targeted_and_deprecated_allowlists():
    rule_set = convert(
        _config(
            {
                "id": "one",
                "regex": "x",
                "keywords": ["x"],
                "allowlist": {"stopwords": ["s"]},
            },
            allowlist={"regexes": ["^g$"]},
            allowlists=[{"targetRules": ["one"], "regexes": ["^t$"]}],
        )
    )

    assert rule_set.global_allowlists == (Allowlist(regexes=("^g$",)),)
    assert rule_set.rules[0].allowlists == (
        Allowlist(stopwords=("s",)),
        Allowlist(regexes=("^t$",)),
    )


@pytest.mark.parametrize(
    "config",
    [
        _config({"id": "multi", "regex": "x", "required": [{"id": "other"}]}),
        _config({"id": "skip", "regex": "x", "skipReport": True}),
        _config({"id": "one", "regex": "x"}, extend={"useDefault": True}),
        _config(
            {"id": "one", "regex": "x"},
            allowlists=[{"targetRules": ["missing"], "regexes": ["y"]}],
        ),
        _config({"id": "bad", "regex": r"\p{L}"}),
    ],
)
def test_convert_refuses_what_it_cannot_carry_over(config):
    with pytest.raises(TranslationError):
        convert(config)


def test_convert_honors_exclusions(monkeypatch):
    monkeypatch.setitem(sync_secret_rules.EXCLUDE, "bad", "needs \\p classes")

    rule_set = convert(_config({"id": "bad", "regex": r"\p{L}"}))

    assert rule_set.rules == ()
    assert rule_set.omitted == (("bad", "needs \\p classes"),)


# --- generate ----------------------------------------------------------------

_SOURCE = b"""
title = "test"
[[allowlists]]
regexes = ['''(?i)^example$''']
[[rules]]
id = "demo"
regex = '''demo-(?i)[a-z]{8}'''
keywords = ["demo"]
entropy = 2.5
secretGroup = 1
[[rules.allowlists]]
condition = "AND"
regexTarget = "line"
regexes = ['''ignore''']
stopwords = ["Test"]
[[rules]]
id = "scoped"
regex = "x"
path = '''\\.tf$'''
"""
_LICENSE = "MIT License\n\nCopyright (c) Someone"


def test_generate_stores_rules_encoded_with_readable_metadata():
    module = generate("v0.0.1", _SOURCE, _LICENSE)
    namespace: dict[str, object] = {}
    exec(compile(module, "<generated>", "exec"), namespace)

    assert namespace["GITLEAKS_VERSION"] == "v0.0.1"
    assert namespace["OMITTED"] == (
        ("scoped", "applies only to files matching a path"),
    )
    payload = namespace["PAYLOAD"]
    assert isinstance(payload, bytes)
    assert read_payload(module) == payload
    assert decode_rules(payload) == RuleSet(
        rules=(
            Rule(
                rule_id="demo",
                pattern="demo-(?i:[a-z]{8})",
                keywords=("demo",),
                entropy=2.5,
                secret_group=1,
                allowlists=(
                    Allowlist(
                        condition=AllowlistCondition.AND,
                        target=AllowlistTarget.LINE,
                        regexes=("ignore",),
                        stopwords=("test",),
                    ),
                ),
            ),
        ),
        global_allowlists=(Allowlist(regexes=("(?i)^example$",)),),
    )
    # Patterns live only in the payload, never as text a scanner could read.
    assert "demo-" not in module
    assert "Copyright (c) Someone" in module
    assert module == generate("v0.0.1", _SOURCE, _LICENSE)


def test_generate_keeps_a_committed_payload_that_decodes_to_the_same_rules():
    """zlib builds can compress differently; equal rules must not churn the file."""
    fresh = generate("v0.0.1", _SOURCE, _LICENSE)
    payload = read_payload(fresh)
    assert payload is not None
    rule_set = decode_rules(payload)
    document = json.dumps(
        dataclasses.asdict(rule_set), sort_keys=True, separators=(",", ":")
    )
    other = base64.b64encode(zlib.compress(document.encode(), 1))
    assert other != payload
    translation = convert(tomllib.loads(_SOURCE.decode()))
    committed = render("v0.0.1", _SOURCE, _LICENSE, translation, other)

    assert generate("v0.0.1", _SOURCE, _LICENSE, committed) == committed


def test_generate_replaces_a_stale_or_unreadable_payload():
    fresh = generate("v0.0.1", _SOURCE, _LICENSE)
    stale = fresh.replace("v0.0.1", "v0.0.0")

    assert generate("v0.0.1", _SOURCE, _LICENSE, stale) == fresh
    assert generate("v0.0.1", _SOURCE, _LICENSE, "PAYLOAD = b'bm90IHpsaWI='") == fresh
    assert generate("v0.0.1", _SOURCE, _LICENSE, "not python (") == fresh


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("PAYLOAD = (b'ab' b'cd')", b"abcd"),
        ("OTHER = b'x'", None),
        ("PAYLOAD = 'text'", None),
        ("def (", None),
    ],
)
def test_read_payload(text, expected):
    assert read_payload(text) == expected


def test_dump_prints_the_committed_rules(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["sync_secret_rules.py", "--dump"])

    sync_secret_rules.main()

    document = json.loads(capsys.readouterr().out)
    assert len(document["rules"]) == len(load_rules().rules)


# --- the committed module ----------------------------------------------------


def test_committed_rules_follow_the_pinned_gitleaks_hook():
    """The guard and the scaffolded pre-commit hook use one gitleaks tag."""
    tag = DEFAULT_REVISIONS[sync_secret_rules.GITLEAKS_REPO]

    assert tag == _secret_rules.GITLEAKS_VERSION, (
        "Run `just sync-secret-rules` after bumping the gitleaks hook revision."
    )


def test_committed_patterns_compile_cleanly_on_this_python():
    """CI runs this on every supported Python version."""
    rule_set = load_rules()
    patterns = [rule.pattern for rule in rule_set.rules]
    patterns += [
        regex
        for allowlists in (
            rule_set.global_allowlists,
            *(rule.allowlists for rule in rule_set.rules),
        )
        for allowlist in allowlists
        for regex in allowlist.regexes
    ]

    assert len(rule_set.rules) > 150
    for pattern in patterns:
        compile_strict(pattern)


def test_committed_rules_are_sorted_with_lowercase_keywords():
    rules = load_rules().rules
    ids = [rule.rule_id for rule in rules]

    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)
    for rule in rules:
        assert rule.keywords, rule.rule_id
        assert all(keyword == keyword.lower() for keyword in rule.keywords)


def test_committed_module_contains_nothing_the_rules_flag():
    """Secret scanners read the module as text; none of its lines may look like a leak."""
    rule_set = load_rules()
    text = Path(_secret_rules.__file__).read_text(encoding="utf-8")

    for line in text.splitlines():
        lowered = line.lower()
        for rule in rule_set.rules:
            if rule.keywords and not any(k in lowered for k in rule.keywords):
                continue
            assert not _matches(rule, line, rule_set.global_allowlists), (
                f"{rule.rule_id} flags: {line[:60]}"
            )
