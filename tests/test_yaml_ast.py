"""YAML codec safety, trivia, and Codecov semantic acceptance tests."""

import difflib
from dataclasses import replace

import pytest

from protostar import yaml_ast
from protostar.documents.codecov import SPEC as CODECOV_SPEC
from protostar.documents.pre_commit import SPEC as PRE_COMMIT_SPEC
from protostar.errors import ConfigurationError
from protostar.merge import (
    MISSING,
    ConflictReason,
    ConflictSides,
    MergeConflict,
    MergeLocation,
    MergePolicy,
    ResolutionChoice,
)
from protostar.sync_state import (
    FilePolicy,
    FileState,
    SyncState,
    deserialize_state,
    serialize_state,
)
from protostar.yaml_ast import (
    DEFAULT_STYLE,
    YamlDocumentSpec,
    YamlGuard,
    YamlStyle,
    decode_yaml_baseline,
    detect_style,
    encode_yaml_baseline,
    reconcile_yaml,
    validate_yaml_baseline,
)

LOCATION = MergeLocation(".github/codecov.yml")


def merge(local, remote, base=MISSING, **kwargs):
    return reconcile_yaml(CODECOV_SPEC, local, remote, base, LOCATION, **kwargs)


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
    with pytest.raises(ConfigurationError) as error:
        decode_yaml_baseline(content)
    assert str(error.value) == "Invalid or unsupported YAML configuration."
    assert error.value.hint == (
        "Use one YAML 1.2 mapping with unique string keys, standard JSON-like"
        " values, no cyclic aliases, and at most 100 levels/10000 nodes/1 MB."
    )


def _nested(depth: int) -> str:
    """A document whose innermost value sits ``depth`` levels below the root."""
    return "a: " + "{a: " * (depth - 1) + "0" + "}" * (depth - 1) + "\n"


def test_the_depth_limit_is_exactly_one_hundred_levels():
    assert decode_yaml_baseline(_nested(100))

    with pytest.raises(ConfigurationError) as error:
        decode_yaml_baseline(_nested(101))
    # The loader's own limit, before the kernel's would apply.
    assert str(error.value) == "Invalid or unsupported YAML configuration."


def test_the_node_limit_is_exact(monkeypatch):
    # The root, then a key and a value per entry.
    monkeypatch.setattr(yaml_ast, "_MAX_NODES", 5)
    assert decode_yaml_baseline("a: 1\nb: 2\n") == {"a": 1, "b": 2}

    with pytest.raises(ConfigurationError):
        decode_yaml_baseline("a: 1\nb: 2\nc: 3\n")


def test_the_size_limit_is_exact(monkeypatch):
    monkeypatch.setattr(yaml_ast, "_MAX_BYTES", len("a: 12\n"))
    assert decode_yaml_baseline("a: 12\n") == {"a": 12}

    with pytest.raises(ConfigurationError):
        decode_yaml_baseline("a: 123\n")


def test_decoded_floats_and_anchored_booleans_keep_their_types():
    data = decode_yaml_baseline("a: 1.5\nb: &t true\nc: *t\n")

    assert data == {"a": 1.5, "b": True, "c": True}
    assert [type(value) for value in data.values()] == [float, bool, bool]


def test_encoding_rejects_a_missing_value():
    with pytest.raises(ConfigurationError) as error:
        encode_yaml_baseline({"a": MISSING})
    assert str(error.value) == "Invalid semantic mapping entry."


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
        pytest.param("a:\n b: 1\n", YamlStyle(1, 3, 1), id="one-space-mapping"),
        pytest.param(
            "a:\nb: 1\nc:\n   d: 1\n", YamlStyle(3, 5, 3), id="sibling-is-not-nesting"
        ),
        pytest.param("- a:\n    b: 1\n", YamlStyle(2, 4, 2), id="key-after-a-dash"),
        pytest.param(
            "a:\n  # note\n    b: 1\n", YamlStyle(4, 6, 4), id="indented-comment"
        ),
        pytest.param(
            "a:\n  - x\nb:\n- y\n", YamlStyle(2, 4, 2), id="first-sequence-wins"
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
    result = reconcile_yaml(
        PRE_COMMIT_SPEC, local, desired, base, MergeLocation(".pre-commit-config.yaml")
    )
    assert not result.conflicts
    assert result.content == desired


# --- versions, specs, and reports ---------------------------------------------------

PLAIN = YamlDocumentSpec("plain")
COMPLETE = YamlDocumentSpec("complete", policy=MergePolicy(complete=True))
HERE = MergeLocation("settings.yml")


def plain(local, remote, base=MISSING, spec=PLAIN, **kwargs):
    return reconcile_yaml(spec, local, remote, base, HERE, **kwargs)


def test_a_yaml_12_directive_is_accepted():
    assert decode_yaml_baseline("%YAML 1.2\n---\na: 1\n") == {"a": 1}


@pytest.mark.parametrize(
    ("value", "message"),
    [
        pytest.param(
            {"repos": "x"}, "Invalid pre-commit record sequence.", id="not-a-list"
        ),
        pytest.param(
            {"repos": [{"hooks": []}]}, "Invalid pre-commit identity.", id="no-identity"
        ),
        pytest.param(
            {"repos": [{"repo": "a", "rev": ""}]},
            "Invalid pre-commit field 'rev'.",
            id="empty-field",
        ),
        pytest.param(
            {"repos": [{"repo": "a", "rev": 1}]},
            "Invalid pre-commit field 'rev'.",
            id="non-string-field",
        ),
        pytest.param(
            {"repos": [{"repo": "a"}, {"repo": "a"}]},
            "Duplicate desired or owned pre-commit identity.",
            id="duplicate",
        ),
    ],
)
def test_keyed_records_are_validated(value, message):
    with pytest.raises(ConfigurationError) as error:
        validate_yaml_baseline(PRE_COMMIT_SPEC, value)
    assert str(error.value) == message


def test_an_owned_record_without_an_identity_is_rejected():
    with pytest.raises(ConfigurationError, match=r"Invalid pre-commit identity\."):
        reconcile_yaml(
            PRE_COMMIT_SPEC,
            "repos: []\n",
            "repos: []\n",
            {"repos": [{"hooks": []}]},
            MergeLocation(".pre-commit-config.yaml"),
        )


def test_a_duplicate_identity_is_held_where_it_is():
    result = reconcile_yaml(
        PRE_COMMIT_SPEC,
        "repos:\n- repo: x\n- repo: x\n",
        "repos:\n- repo: x\n  rev: v1\n",
        MISSING,
        MergeLocation(".pre-commit-config.yaml"),
    )

    assert result.content == "repos:\n- repo: x\n- repo: x\n"
    assert result.conflicts == (
        MergeConflict(
            MergeLocation(".pre-commit-config.yaml", ("repos", "x"), "x"),
            ConflictReason.DUPLICATE_IDENTITY,
        ),
    )


def test_an_unowned_document_takes_changes_without_proposals_by_default():
    result = plain("b: 1\n", "a: 2\n")

    assert result.content == "b: 1\na: 2\n"
    assert not result.proposals


def test_a_new_key_goes_before_its_next_desired_sibling():
    assert plain("b: 1\nc: 1\n", "a: 1\nb: 1\nc: 1\n").content == "a: 1\nb: 1\nc: 1\n"


def test_a_deleted_owned_document_reports_how_its_conflict_was_settled():
    [conflict] = plain("", "a: 2\n", {"a": 1}, missing_file=True).conflicts
    assert (conflict.reason, conflict.location) == (
        ConflictReason.DELETED_ANCESTOR,
        HERE,
    )

    kept = plain(
        "",
        "a: 2\n",
        {"a": 1},
        missing_file=True,
        resolutions={conflict.id: ResolutionChoice.LOCAL},
    )

    assert (kept.content, kept.baseline, kept.conflicts) == ("", {"a": 2}, ())
    assert [settled.resolution for settled in kept.resolved] == [ResolutionChoice.LOCAL]


def test_a_declined_proposal_for_a_missing_document_is_reported():
    [proposal] = plain("", "a: 2\n", missing_file=True, proposing=True).proposals

    declined = plain(
        "",
        "a: 2\n",
        missing_file=True,
        proposing=True,
        resolutions={proposal.id: ResolutionChoice.LOCAL},
    )

    assert declined.content == ""
    assert [settled.resolution for settled in declined.proposals] == [
        ResolutionChoice.LOCAL
    ]


def test_a_kept_edit_is_reported_beside_an_applied_change():
    result = plain("a: 1\nb: 9\n", "a: 2\nb: 1\n", {"a": 1, "b": 1})

    assert result.content == "a: 2\nb: 9\n"
    [preserved] = result.preserved
    assert preserved.location.keys == ("b",)


def test_a_removed_last_key_takes_its_blank_line_with_it():
    assert plain(
        "a: 1\n\nb: 1\n", "a: 1\n", {"a": 1, "b": 1}, spec=COMPLETE
    ).content == ("a: 1\n")


def test_the_last_value_is_kept_exactly():
    assert plain("a: 1\nb: X\n", "a: 2\nb: X\n", {"a": 1, "b": "X"}).content == (
        "a: 2\nb: X\n"
    )


def test_overwrite_retracts_nothing_unless_the_document_is_complete():
    result = plain("a: 1\nold: 1\n", "a: 2\n", {"a": 1, "old": 1}, overwrite=True)

    assert result.content == "a: 2\nold: 1\n"
    assert result.baseline == {"a": 2, "old": 1}


def test_a_document_ending_in_a_blank_line_keeps_it():
    assert plain("a: 1\n\n", "a: 2\n", {"a": 1}).content == "a: 2\n\n"


# --- shared structure ---------------------------------------------------------------


def test_retracting_an_aliased_value_is_a_shared_structure_conflict():
    local = "old: &o {a: 1}\nkeep: *o\n"

    result = plain(local, "{}\n", {"old": {"a": 1}}, spec=COMPLETE)

    assert result.content == local
    assert result.baseline == {"old": {"a": 1}}
    assert result.conflicts == (
        MergeConflict(
            MergeLocation(HERE.file, ("old",)), ConflictReason.SHARED_STRUCTURE
        ),
    )


def test_replacing_a_list_holding_an_aliased_member_is_a_conflict():
    local = "wrap:\n  - &i {a: 1}\nother: *i\n"

    result = plain(local, "wrap: []\n", {"wrap": [{"a": 1}]})

    assert result.content == local
    assert result.baseline == {"wrap": [{"a": 1}]}
    assert result.conflicts == (
        MergeConflict(
            MergeLocation(HERE.file, ("wrap",)), ConflictReason.SHARED_STRUCTURE
        ),
    )


def test_an_edit_beside_an_aliased_sibling_is_safe():
    local = "a:\n  shared: &s {x: 1}\n  plain: 1\nb: *s\n"

    result = plain(local, "a: {plain: 2}\n", {"a": {"plain": 1}})

    assert result.content == local.replace("plain: 1", "plain: 2")
    assert not result.conflicts


def test_a_key_added_beside_a_merge_key_is_a_conflict():
    local = "base: &b {a: 1}\n<<: *b\nc: 1\n"

    result = plain(local, "c: 1\nnew: 2\n", {"c": 1})

    assert result.content == local
    assert result.baseline == {"c": 1}
    assert result.conflicts == (
        MergeConflict(
            MergeLocation(HERE.file, ("new",)), ConflictReason.SHARED_STRUCTURE
        ),
    )


# --- guards ---------------------------------------------------------------------------

TARGET = ("coverage", "target")
OTHER = ("coverage", "x")
GUARDED_LOCAL = "coverage: {target: 90%, x: 1}\n"
GUARDED_DESIRED = "coverage: {target: 85%, x: 2}\n"
GUARDED_BASE = {"coverage": {"target": "80%", "x": 1}}
ON_TARGET = MergeConflict(
    MergeLocation(HERE.file, TARGET),
    ConflictReason.DIVERGED,
    ConflictSides("80%", "90%", "85%"),
)
ON_OTHER = MergeConflict(
    MergeLocation(HERE.file, OTHER), ConflictReason.DIVERGED, ConflictSides(1, 1, 2)
)


def guarded(guard, **kwargs):
    return plain(GUARDED_LOCAL, GUARDED_DESIRED, GUARDED_BASE, guard=guard, **kwargs)


def test_an_open_guard_conflict_holds_its_path():
    result = guarded(YamlGuard((TARGET,), (ON_TARGET,)))

    assert result.content == "coverage: {target: 90%, x: 2}\n"
    assert result.conflicts == (ON_TARGET,)
    assert result.baseline == {"coverage": {"target": "80%", "x": 2}}


@pytest.mark.parametrize(
    ("choice", "content", "preserved"),
    [
        (ResolutionChoice.LOCAL, "coverage: {target: 90%, x: 2}\n", 1),
        (ResolutionChoice.DESIRED, "coverage: {target: 85%, x: 2}\n", 0),
    ],
)
def test_settling_a_guard_conflict_owns_the_update(choice, content, preserved):
    result = guarded(
        YamlGuard((TARGET,), (ON_TARGET,)), resolutions={ON_TARGET.id: choice}
    )

    assert result.content == content
    assert result.baseline == {"coverage": {"target": "85%", "x": 2}}
    assert not result.conflicts
    assert result.resolved == (replace(ON_TARGET, resolution=choice),)
    assert len(result.preserved) == preserved


def test_overwrite_leaves_guard_conflicts_open():
    result = guarded(
        YamlGuard((TARGET,), (ON_TARGET,)),
        resolutions={ON_TARGET.id: ResolutionChoice.DESIRED},
        overwrite=True,
    )

    assert result.content == "coverage: {target: 90%, x: 2}\n"
    assert result.conflicts == (ON_TARGET,)
    assert not result.resolved


@pytest.mark.parametrize(
    "order",
    [(ON_TARGET, ON_OTHER), (ON_OTHER, ON_TARGET)],
    ids=["open-first", "settled-first"],
)
def test_each_guard_conflict_is_settled_on_its_own(order):
    holds = tuple(conflict.location.keys for conflict in order)

    result = guarded(
        YamlGuard(holds, order), resolutions={ON_OTHER.id: ResolutionChoice.DESIRED}
    )

    assert result.content == "coverage: {target: 90%, x: 2}\n"
    assert result.conflicts == (ON_TARGET,)
    assert [settled.location.keys for settled in result.resolved] == [OTHER]


@pytest.mark.parametrize("held", [("b", "c"), ("a", "absent")], ids=["parent", "key"])
def test_a_hold_on_an_undeclared_path_changes_nothing(held):
    result = plain(
        "a: {x: 1}\n", "a: {x: 2}\n", {"a": {"x": 1}}, guard=YamlGuard((held,))
    )

    assert result.content == "a: {x: 2}\n"
