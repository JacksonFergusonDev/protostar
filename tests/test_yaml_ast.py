"""YAML codec safety, trivia, and Codecov semantic acceptance tests."""

import difflib

import pytest

from protostar.errors import ConfigurationError
from protostar.merge import MISSING, ConflictReason, MergeLocation
from protostar.sync_state import (
    FilePolicy,
    FileState,
    SyncState,
    deserialize_state,
    serialize_state,
)
from protostar.yaml_ast import (
    DEFAULT_STYLE,
    YamlStyle,
    decode_yaml_baseline,
    detect_style,
    encode_yaml_baseline,
    reconcile_codecov,
    reconcile_pre_commit,
)

LOCATION = MergeLocation(".github/codecov.yml")


def merge(local, remote, base=MISSING, **kwargs):
    return reconcile_codecov(local, remote, base, LOCATION, **kwargs)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "[]",
        "null",
        "a: 1\na: 2\n",
        "---\na: 1\n---\nb: 2\n",
        "%YAML 1.1\n---\nyes: on\n",
        "a: !custom value\n",
        "a: !!python/object:thing {}\n",
        "a: &cycle [*cycle]\n",
        "a: &cycle {a: *cycle}\n",
        "a: [unterminated",
        "1: value\n",
        "a: 2026-09-16\n",
        "a: !!set {x: null}\n",
        "a: !!binary YQ==\n",
        pytest.param("a: " + "[" * 102 + "0" + "]" * 102, id="max-depth-exceeded"),
        pytest.param(
            "a: [" + ",".join("0" for _ in range(10001)) + "]",
            id="max-nodes-exceeded",
        ),
        pytest.param("a: " + "x" * 1_000_000, id="max-bytes-exceeded"),
    ],
)
def test_rejects_unsupported_or_unbounded_input(content):
    with pytest.raises(ConfigurationError):
        decode_yaml_baseline(content)


def test_yaml_12_types_and_canonical_state():
    content = "%YAML 1.2\n---\nx: null\nyes: on\nboolean: true\ninteger: 1\n"
    data = decode_yaml_baseline(content)
    assert data == {"x": None, "yes": "on", "boolean": True, "integer": 1}
    assert type(data["boolean"]) is bool
    assert type(data["integer"]) is int
    state = SyncState(
        "test", files=(FileState(LOCATION.file, FilePolicy.YAML, content),)
    )
    encoded = serialize_state(state)
    assert serialize_state(deserialize_state(encoded)) == encoded
    assert encode_yaml_baseline(data) == encode_yaml_baseline(
        dict(reversed(list(data.items())))
    )
    assert decode_yaml_baseline("a: &bool true\nb: *bool\n") == {"a": True, "b": True}


def test_clean_update_keeps_trivia_and_foreign_values():
    local = '# heading\ncoverage: {target: "80%", threshold: 2} # note\nforeign: |\n  hello\n  world\nignore: ["tests/**", "custom/**"] # ignores\n'
    base = {"coverage": {"target": "80%", "threshold": 2}, "ignore": ["tests/**"]}
    result = merge(
        local,
        'coverage: {target: "85%", threshold: 2}\nignore: [tests/**, docs/**]\n',
        base,
    )
    assert "# heading" in result.content
    assert 'target: "85%"' in result.content
    assert "# note" in result.content
    assert "# ignores" in result.content
    assert "foreign: |\n  hello\n  world\n" in result.content
    assert 'ignore: ["tests/**", "custom/**", docs/**]' in result.content
    assert result.baseline == {
        "coverage": {"target": "85%", "threshold": 2},
        "ignore": ["tests/**", "docs/**"],
    }
    assert not result.conflicts


def test_local_edit_deleted_member_and_partial_baseline():
    base = {"coverage": {"target": "80%"}, "ignore": ["tests/**", "docs/**"]}
    result = merge(
        'coverage: {target: "90%"} # local\nignore: [custom/**, tests/**]\n',
        'coverage: {target: "85%", precision: 2}\nignore: [tests/**, docs/**, scripts/**]\n',
        base,
    )
    assert decode_yaml_baseline(result.content) == {
        "coverage": {"target": "90%", "precision": 2},
        "ignore": ["custom/**", "tests/**", "scripts/**"],
    }
    assert result.conflicts[0].location.keys == ("coverage", "target")
    assert result.conflicts[0].reason is ConflictReason.DIVERGED
    assert result.baseline["coverage"] == {"target": "80%", "precision": 2}
    assert result.baseline["ignore"] == ["tests/**", "docs/**", "scripts/**"]


@pytest.mark.parametrize(
    "local", ["# comment\ncoverage: {target: 90%}\n", "# comment\n{}\n"]
)
def test_unchanged_remote_preserves_edits_and_deletions_bytewise(local):
    base = {"coverage": {"target": "80%"}}
    result = merge(local, "coverage: {target: 80%}\n", base)
    assert result.content == local
    assert result.baseline == base
    assert not result.conflicts


def test_missing_file_and_deleted_ancestor_are_not_resurrected():
    base = {"coverage": {"target": "80%"}}
    for local, missing in [("", True), ("{}\n", False)]:
        result = merge(
            local, "coverage: {target: 85%, new: true}\n", base, missing_file=missing
        )
        assert result.content == local
        assert result.baseline == base
        assert result.conflicts[0].reason is ConflictReason.DELETED_ANCESTOR


def test_no_adoption_convergence_and_atomic_unknown_sequence():
    result = merge("target: 80%\nforeign: 1\n", "target: 80%\nnew: null\n")
    assert result.baseline == {"new": None}
    converged = merge("target: 85% # my style\n", "target: 85%\n", {"target": "80%"})
    assert converged.content == "target: 85% # my style\n"
    assert converged.baseline == {"target": "85%"}
    conflict = merge("custom: [a, local]\n", "custom: [a, remote]\n", {"custom": ["a"]})
    assert conflict.content == "custom: [a, local]\n"
    assert conflict.conflicts


@pytest.mark.parametrize(
    "local",
    [
        "coverage: &shared {target: 80%}\nforeign: *shared\n",
        "foreign: &shared {target: 80%}\ncoverage: *shared\n",
        "foreign: &shared {target: 80%}\ncoverage: {<<: *shared}\n",
        "coverage: {target: &shared 80%}\nforeign: *shared\n",
    ],
)
def test_shared_alias_or_merge_edit_preserves_foreign_structure(local):
    base = {"coverage": {"target": "80%"}}
    result = merge(local, "coverage: {target: 85%}\nnew: true\n", base)
    coverage = decode_yaml_baseline(result.content)["coverage"]
    assert isinstance(coverage, dict)
    assert coverage["target"] == "80%"
    assert "&shared" in result.content
    assert "*shared" in result.content
    assert result.baseline == {**base, "new": True}
    assert result.conflicts[0].reason is ConflictReason.SHARED_STRUCTURE
    assert merge(local, "coverage: {target: 80%}\n", base).content == local


def test_unshared_anchor_and_unrelated_alias_survive_safe_edit():
    local = (
        "coverage: &settings {target: 80%}\nforeign: &foreign [a, b]\ncopy: *foreign\n"
    )
    result = merge(local, "coverage: {target: 85%}\n", {"coverage": {"target": "80%"}})
    coverage = decode_yaml_baseline(result.content)["coverage"]
    assert isinstance(coverage, dict)
    assert coverage["target"] == "85%"
    assert "&settings" in result.content
    assert "&foreign" in result.content
    assert "*foreign" in result.content
    assert not result.conflicts


def test_overwrite_preserves_foreign_siblings_and_alias_safety():
    result = merge(
        "coverage: {target: 90%, foreign: yes}\n",
        "coverage: {target: 85%}\n",
        overwrite=True,
    )
    assert decode_yaml_baseline(result.content) == {
        "coverage": {"target": "85%", "foreign": "yes"}
    }
    assert result.baseline == {"coverage": {"target": "85%"}}
    local = "coverage: &shared {target: 80%}\nforeign: *shared\n"
    result = merge(
        local,
        "coverage: {target: 85%}\n",
        {"coverage": {"target": "80%"}},
        overwrite=True,
    )
    assert result.content == local
    assert result.conflicts


@pytest.mark.parametrize("content", ["ignore: [a, a]\n", "ignore: [{x: 1}]\n"])
def test_ignore_policy_rejects_ambiguous_members_even_on_noop(content):
    with pytest.raises(ConfigurationError):
        merge(content, content, decode_yaml_baseline(content))


def test_boolean_integer_comparison_is_type_aware():
    result = merge("target: true\n", "target: 2\n", {"target": 1})
    assert result.content == "target: true\n"
    assert result.conflicts[0].reason is ConflictReason.TYPE_MISMATCH


def test_blocked_unowned_alias_does_not_create_empty_ownership():
    local = "coverage: &shared {target: 80%}\nforeign: *shared\n"
    result = merge(local, "coverage: {new: true}\n")
    assert result.content == local
    assert result.baseline is MISSING
    assert result.conflicts[0].reason is ConflictReason.SHARED_STRUCTURE


def test_changed_scalar_keeps_local_quote_style_and_unshared_anchor():
    result = merge(
        "target: &choice '80%' # target\n", 'target: "85%"\n', {"target": "80%"}
    )
    assert "target: &choice '85%' # target" in result.content


def changed_lines(before: str, after: str) -> list[str]:
    return [
        line
        for line in difflib.unified_diff(
            before.splitlines(), after.splitlines(), lineterm="", n=0
        )
        if line[:1] in "+-" and line[:3] not in ("+++", "---")
    ]


@pytest.mark.parametrize(
    ("content", "style"),
    [
        pytest.param("", DEFAULT_STYLE, id="empty"),
        pytest.param("a: 1\n", DEFAULT_STYLE, id="flat"),
        pytest.param("a:\n  - x\n", YamlStyle(2, 4, 2), id="indented-sequence"),
        pytest.param("a:\n- x\n", YamlStyle(2, 2, 0), id="indentless-sequence"),
        pytest.param("a:\n    b: 1\n", YamlStyle(4, 6, 4), id="four-space-mapping"),
        pytest.param(
            "a:\n    b:\n    -   x\n", YamlStyle(4, 4, 0), id="wide-sequence-gap"
        ),
        pytest.param(
            "# lead\n\na: # trailing\n  # between\n\n  b: 1\nc:\n- x\n",
            YamlStyle(2, 2, 0),
            id="comments-and-blank-lines",
        ),
        pytest.param(
            "repos:\n  - repo: local\n    hooks:\n      - id: x\n",
            YamlStyle(2, 4, 2),
            id="key-inside-sequence-item",
        ),
        pytest.param(
            "a:\n  - - x\n", YamlStyle(2, 4, 2), id="nested-sequence-dash-key"
        ),
    ],
)
def test_detect_style(content, style):
    assert detect_style(content) == style


def test_long_lines_are_not_rewrapped_on_merge():
    command = "uv run pytest --cov --cov-report=xml --junitxml=junit.xml -o junit_family=legacy ${{ matrix.python-version }}"
    local = f"coverage: {{target: 80%}}\nforeign:\n  run: {command}\n"
    result = merge(local, "coverage: {target: 85%}\n", {"coverage": {"target": "80%"}})
    assert f"  run: {command}\n" in result.content
    assert changed_lines(local, result.content) == [
        "-coverage: {target: 80%}",
        "+coverage: {target: 85%}",
    ]
    assert not any(line != line.rstrip() for line in result.content.splitlines())


@pytest.mark.parametrize(
    "local",
    [
        pytest.param("coverage:\n  target: 80%\nforeign:\n- a\n- b\n", id="indentless"),
        pytest.param(
            "coverage:\n    target: 80%\nforeign:\n    - a\n    - b\n",
            id="four-space",
        ),
    ],
)
def test_merge_keeps_the_local_indentation_style(local):
    result = merge(local, "coverage: {target: 85%}\n", {"coverage": {"target": "80%"}})
    assert result.content == local.replace("80%", "85%")


def test_missing_file_receives_desired_text_verbatim():
    desired = "# Managed by Protostar\ncoverage:\n  target: 85% # floor\nignore:\n  - tests/**\n"
    result = merge("", desired, missing_file=True)
    assert result.content == desired
    assert result.baseline == {"coverage": {"target": "85%"}, "ignore": ["tests/**"]}
    overwritten = merge("", desired, missing_file=True, overwrite=True)
    assert overwritten.content == desired


def test_pre_commit_hook_edit_changes_one_line():
    hooks = "".join(
        f"      - id: hook-{index}\n        entry: uv run tool-{index} --flag --another-flag --output-format=github --config pyproject.toml\n"
        for index in range(3)
    )
    local = f"default_install_hook_types:\n  - pre-commit\nrepos:\n  - repo: local\n    hooks:\n{hooks}"
    base = decode_yaml_baseline(local)
    desired = local.replace("tool-1 ", "tool-one ")
    result = reconcile_pre_commit(
        local, desired, base, MergeLocation(".pre-commit-config.yaml")
    )
    assert not result.conflicts
    assert result.content == desired
