from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, time
from typing import cast

import pytest

from protostar.errors import ConfigurationError
from protostar.merge import (
    DEFAULT_POLICY,
    MISSING,
    ConflictReason,
    ConflictSides,
    LineSpan,
    MergeConflict,
    MergeDecision,
    MergeLocation,
    MergePolicy,
    ResolutionChoice,
    Value,
    describe_location,
    hold,
    overlay_declared,
    prune_unapplied,
    reconcile,
    retract_undeclared,
    semantic_equal,
    without_paths,
)

LOC = MergeLocation("pyproject.toml", ("tool", "example"), "module:example")


@pytest.mark.parametrize(
    ("base", "local", "remote", "value", "baseline", "decision"),
    [
        (1, 2, MISSING, 2, 1, MergeDecision.KEEP_LOCAL),
        (MISSING, MISSING, MISSING, MISSING, MISSING, MergeDecision.KEEP_LOCAL),
        (MISSING, MISSING, 1, 1, 1, MergeDecision.APPLY_REMOTE),
        (MISSING, 1, 1, 1, MISSING, MergeDecision.KEEP_LOCAL),
        (MISSING, 2, 1, 2, MISSING, MergeDecision.CONFLICT),
        (1, 2, 2, 2, 2, MergeDecision.KEEP_LOCAL),
        (1, 1, 1, 1, 1, MergeDecision.KEEP_LOCAL),
        (1, 2, 1, 2, 1, MergeDecision.KEEP_LOCAL),
        (1, MISSING, 1, MISSING, 1, MergeDecision.KEEP_LOCAL),
        (1, 1, 2, 2, 2, MergeDecision.APPLY_REMOTE),
        (1, 2, 3, 2, 1, MergeDecision.CONFLICT),
        (1, MISSING, 2, MISSING, 1, MergeDecision.CONFLICT),
        (None, None, "new", None, None, MergeDecision.CONFLICT),
        (MISSING, MISSING, None, None, None, MergeDecision.APPLY_REMOTE),
        (MISSING, None, None, None, MISSING, MergeDecision.KEEP_LOCAL),
        (True, 1, False, 1, True, MergeDecision.CONFLICT),
        ("old", "old", {"new": 1}, "old", "old", MergeDecision.CONFLICT),
    ],
)
def test_scalar_truth_table(base, local, remote, value, baseline, decision):
    result = reconcile(base, local, remote, LOC)
    assert semantic_equal(result.value, value)
    assert semantic_equal(result.baseline, baseline)
    assert result.decision is decision
    assert bool(result.conflicts) == (decision is MergeDecision.CONFLICT)
    if result.conflicts:
        assert result.conflicts[0].location == LOC


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (True, 1),
        (1, 1.0),
        (None, MISSING),
        (date(2026, 1, 1), datetime(2026, 1, 1)),
        ([True], [1]),
        ({"a": True}, {"a": 1}),
    ],
)
def test_equality_is_type_aware(left, right):
    assert not semantic_equal(left, right)


@pytest.mark.parametrize(
    "value",
    [date(2026, 1, 1), datetime(2026, 1, 1), time(12, 30), float("nan"), float("inf")],
)
def test_native_semantic_values(value):
    result = reconcile(value, value, value, LOC)
    assert semantic_equal(result.baseline, value)
    assert result.decision is MergeDecision.KEEP_LOCAL


def test_partial_conflicts_advance_only_successful_owned_keys():
    base: dict[str, Value] = {"safe": 1, "conflict": 1, "deleted": 1, "omitted": 1}
    local: dict[str, Value] = {
        "safe": 1,
        "conflict": 9,
        "foreign": 7,
        "equal_foreign": 4,
    }
    remote: dict[str, Value] = {
        "safe": 2,
        "conflict": 2,
        "deleted": 2,
        "added": 3,
        "equal_foreign": 4,
    }
    inputs = deepcopy((base, local, remote))
    result = reconcile(base, local, remote, LOC)
    assert result.value == {
        "safe": 2,
        "conflict": 9,
        "foreign": 7,
        "equal_foreign": 4,
        "added": 3,
    }
    assert isinstance(result.value, dict)
    assert list(result.value) == [*local, "added"]
    assert result.baseline == {
        "safe": 2,
        "conflict": 1,
        "deleted": 1,
        "omitted": 1,
        "added": 3,
    }
    assert [c.location.keys[-1] for c in result.conflicts] == ["conflict", "deleted"]
    assert (base, local, remote) == inputs
    result.value["safe"] = 99
    assert base == inputs[0]
    assert remote == inputs[2]


def test_converged_mapping_does_not_adopt_foreign_sibling():
    result = reconcile(
        {"owned": 1}, {"owned": 2, "foreign": 3}, {"owned": 2, "foreign": 3}, LOC
    )
    assert result.baseline == {"owned": 2}
    assert result.decision is MergeDecision.KEEP_LOCAL


def test_missing_state_fills_only_absent_keys_recursively():
    result = reconcile(
        MISSING,
        {"nested": {"equal": 1, "custom": 3}},
        {"nested": {"equal": 1, "new": 2}},
        LOC,
    )
    assert result.value == {"nested": {"equal": 1, "custom": 3, "new": 2}}
    assert result.baseline == {"nested": {"new": 2}}


@pytest.mark.parametrize(
    ("local", "reason"),
    [
        (MISSING, ConflictReason.DELETED_ANCESTOR),
        ("user scalar", ConflictReason.TYPE_MISMATCH),
        ([], ConflictReason.TYPE_MISMATCH),
    ],
)
def test_deleted_or_incompatible_owned_table_protects_new_children(local, reason):
    result = reconcile({"old": 1}, local, {"old": 1, "new": 2}, LOC)
    assert semantic_equal(result.value, local)
    assert result.baseline == {"old": 1}
    [conflict] = result.conflicts
    assert conflict.reason is reason


def test_deleted_ancestor_blocks_unowned_descendant():
    result = reconcile(MISSING, MISSING, 2, LOC, MergePolicy(protected_ancestor=True))
    assert result.value is MISSING
    assert result.baseline is MISSING
    assert result.conflicts[0].reason is ConflictReason.DELETED_ANCESTOR


def test_deleted_table_unchanged_remote_does_not_warn():
    result = reconcile({"old": 1}, MISSING, {"old": 1}, LOC)
    assert not result.conflicts
    assert result.value is MISSING


@pytest.mark.parametrize(
    ("base", "local", "remote", "expected"),
    [
        ([1], [1], [2], [2]),
        ([1], [9], [2], [9]),
        ([{"id": "a"}], [{"id": "a"}], [{"id": "b"}], [{"id": "b"}]),
        ([1], [1], [1, 1], [1, 1]),
    ],
)
def test_unknown_sequences_and_arrays_of_tables_are_atomic(
    base, local, remote, expected
):
    assert reconcile(base, local, remote, LOC).value == expected


def test_set_policy_preserves_order_omissions_deletions_and_foreign_members():
    base: list[Value] = ["deleted", "kept", "omitted"]
    local: list[Value] = ["custom", "kept", "omitted", "foreign_equal"]
    remote: list[Value] = ["kept", "deleted", "new_b", "foreign_equal", "new_a"]
    result = reconcile(base, local, remote, LOC, MergePolicy(frozenset({LOC.keys})))
    assert result.value == [*local, "new_b", "new_a"]
    assert result.baseline == [*base, "new_b", "new_a"]
    assert not result.conflicts
    repeated = reconcile(
        result.baseline, result.value, remote, LOC, MergePolicy(frozenset({LOC.keys}))
    )
    assert repeated.value == result.value
    assert repeated.baseline == result.baseline
    assert repeated.decision is MergeDecision.KEEP_LOCAL


def test_set_policy_convergence_does_not_adopt_members():
    result = reconcile(
        ["owned"],
        ["owned", "foreign", "new"],
        ["owned", "foreign", "new"],
        LOC,
        MergePolicy(frozenset({LOC.keys})),
    )
    assert result.baseline == ["owned"]


@pytest.mark.parametrize("sequence", [["duplicate", "duplicate"], [{"id": 1}], [[1]]])
def test_set_policy_rejects_ambiguous_members(sequence):
    with pytest.raises(ConfigurationError) as error:
        reconcile(MISSING, MISSING, sequence, LOC, MergePolicy(frozenset({LOC.keys})))
    assert str(error.value) == "Ambiguous set-like sequence."
    assert error.value.hint == (
        "Use unique scalar members or an atomic/file-specific sequence policy."
    )


def test_unowned_existing_set_records_only_newly_added_members():
    result = reconcile(
        MISSING,
        ["foreign"],
        ["foreign", "new"],
        LOC,
        MergePolicy(frozenset({LOC.keys})),
    )
    assert result.baseline == ["new"]


@pytest.mark.parametrize(
    ("base", "local", "remote"),
    [(MISSING, {}, {}), (MISSING, [], []), (MISSING, {"same": 1}, {"same": 1})],
)
def test_empty_or_equal_unowned_collections_are_not_adopted(base, local, remote):
    result = reconcile(base, local, remote, LOC)
    assert result.baseline is MISSING


def _cyclic() -> list[Value]:
    cyclic: list[Value] = []
    cyclic.append(cyclic)
    return cyclic


@pytest.mark.parametrize(
    ("value", "message", "hint"),
    [
        pytest.param(
            _cyclic(),
            "Cyclic semantic configuration.",
            "Remove cyclic aliases before reconciliation.",
            id="cycle",
        ),
        pytest.param(
            {"bad": object()},
            "Unsupported semantic value type.",
            "Pass decoded scalar, mapping, or sequence values to reconciliation.",
            id="unsupported-type",
        ),
        pytest.param(
            {"bad": MISSING},
            "Invalid semantic mapping entry.",
            "Use string keys and omit missing entries.",
            id="missing-entry",
        ),
        pytest.param(
            {1: "non-string key"},
            "Invalid semantic mapping entry.",
            "Use string keys and omit missing entries.",
            id="non-string-key",
        ),
        pytest.param(
            [MISSING],
            "Missing sequence member.",
            "Use absence only for entire values.",
            id="missing-member",
        ),
    ],
)
def test_kernel_rejects_cycles_and_unsupported_values(value, message, hint):
    with pytest.raises(ConfigurationError) as error:
        reconcile(MISSING, MISSING, cast(Value, value), LOC)
    assert str(error.value) == message
    assert error.value.hint == hint


def _nested(depth: int, container: type) -> Value:
    value: Value = "leaf"
    for _ in range(depth):
        value = {"k": value} if container is dict else [value]
    return value


@pytest.mark.parametrize("container", [dict, list])
def test_kernel_accepts_exactly_one_hundred_levels_of_nesting(container):
    value = _nested(100, container)

    assert reconcile(MISSING, MISSING, value, LOC).value == value

    with pytest.raises(ConfigurationError) as error:
        reconcile(MISSING, MISSING, _nested(101, container), LOC)
    assert str(error.value) == "Semantic value is too deeply nested."
    assert error.value.hint == "Limit configuration nesting to 100 levels."


@pytest.mark.parametrize(
    ("base", "local", "remote"),
    [
        (["a", "a"], ["a", "a"], ["a", "a"]),
        (["a"], ["a", "a"], ["a"]),
        (MISSING, ["a", "a"], ["a"]),
    ],
)
def test_set_policy_rejects_duplicates_even_on_unchanged_or_converged_inputs(
    base, local, remote
):
    with pytest.raises(ConfigurationError):
        reconcile(base, local, remote, LOC, MergePolicy(frozenset({LOC.keys})))


@pytest.mark.parametrize("remote", [{}, [], {"empty": {}}, {"list": []}])
def test_new_empty_collections_establish_ownership(remote):
    result = reconcile(MISSING, MISSING, remote, LOC)
    assert result.value == remote
    assert result.baseline == remote
    assert result.decision is MergeDecision.APPLY_REMOTE


def test_atomic_sequence_convergence_advances_owned_baseline():
    result = reconcile([{"id": "old"}], [{"id": "new"}], [{"id": "new"}], LOC)
    assert result.baseline == [{"id": "new"}]
    assert result.decision is MergeDecision.KEEP_LOCAL


def test_omitted_baseline_retains_evidence_of_user_deletion():
    omitted = reconcile({"owned": 1}, {}, {}, LOC)
    assert omitted.baseline == {"owned": 1}
    reintroduced = reconcile(omitted.baseline, omitted.value, {"owned": 2}, LOC)
    assert reintroduced.value == {}
    assert reintroduced.baseline == {"owned": 1}
    assert reintroduced.conflicts


def test_kernel_never_reads_writes_executes_or_prints(mocker, capsys):
    read = mocker.patch("pathlib.Path.read_text", side_effect=AssertionError("read"))
    write = mocker.patch("pathlib.Path.write_text", side_effect=AssertionError("write"))
    run = mocker.patch("subprocess.run", side_effect=AssertionError("subprocess"))
    reconcile({"a": 1}, {"a": 9}, {"a": 2, "new": 3}, LOC)
    read.assert_not_called()
    write.assert_not_called()
    run.assert_not_called()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("base", "local", "remote"),
    [
        ({"select": ["A", "A"]}, {"select": ["A", "A"]}, {"select": ["A", "A"]}),
        ({"select": ["A"]}, {"select": ["A", "A"]}, {"select": ["A"]}),
        ({"select": [{"id": 1}]}, MISSING, {"select": [{"id": 1}]}),
    ],
)
def test_unchanged_ancestor_cannot_bypass_nested_set_validation(base, local, remote):
    with pytest.raises(ConfigurationError):
        reconcile(
            base, local, remote, LOC, MergePolicy(frozenset({(*LOC.keys, "select")}))
        )


def test_overlay_declared_recurses_and_retains_foreign_siblings():
    target: dict[str, Value] = {"a": {"x": 1, "foreign": 2}, "keep": [1]}
    incoming: dict[str, Value] = {"a": {"x": 9}, "b": [1, 2], "keep": {"n": 1}}

    overlay_declared(target, incoming)

    assert target == {"a": {"x": 9, "foreign": 2}, "b": [1, 2], "keep": {"n": 1}}
    cast(list[Value], target["b"]).append(3)
    assert incoming["b"] == [1, 2]


def test_prune_unapplied_drops_only_new_empty_owned_mappings():
    owned: dict[str, Value] = {
        "new_empty": {},
        "old_empty": {},
        "nested": {"inner": {}},
        "applied": {"k": 1},
    }
    previous: dict[str, Value] = {"old_empty": {}}
    current: dict[str, Value] = {
        "new_empty": {},
        "old_empty": {},
        "nested": {"inner": {}},
        "applied": {"k": 1},
    }

    prune_unapplied(owned, previous, current)

    assert owned == {"old_empty": {}, "applied": {"k": 1}}


COMPLETE = MergePolicy(complete=True)


@pytest.mark.parametrize(
    ("local", "value", "baseline", "reasons"),
    [
        pytest.param({"a": 1, "b": 2}, {"a": 1}, {"a": 1}, [], id="unedited-removed"),
        pytest.param(
            {"a": 1, "b": 3},
            {"a": 1, "b": 3},
            {"a": 1, "b": 2},
            [ConflictReason.RETRACTED],
            id="edited-kept-with-conflict",
        ),
        pytest.param({"a": 1}, {"a": 1}, {"a": 1}, [], id="already-deleted"),
    ],
)
def test_complete_policy_retracts_undeclared_owned_keys(
    local, value, baseline, reasons
):
    result = reconcile({"a": 1, "b": 2}, local, {"a": 1}, LOC, COMPLETE)
    assert result.value == value
    assert result.baseline == baseline
    assert [c.reason for c in result.conflicts] == reasons
    if reasons:
        assert result.conflicts[0].location.keys == (*LOC.keys, "b")


def test_complete_policy_retracts_nested_leaves_and_protects_foreign_content():
    base: Value = {"x": {"a": 1, "b": 2}, "y": {"a": 1}}
    result = reconcile(
        base,
        {"x": {"a": 1, "b": 2}, "y": {"a": 1, "mine": 0}, "foreign": 1},
        {"x": {"a": 1}},
        LOC,
        COMPLETE,
    )
    assert result.value == {"x": {"a": 1}, "y": {"a": 1, "mine": 0}, "foreign": 1}
    assert result.baseline == {"x": {"a": 1}, "y": {"a": 1}}
    [conflict] = result.conflicts
    assert conflict.reason is ConflictReason.RETRACTED
    assert conflict.location.keys == (*LOC.keys, "y")


def test_default_policy_never_retracts():
    result = reconcile({"a": 1, "b": 2}, {"a": 1, "b": 2}, {"a": 1}, LOC)
    assert result.value == {"a": 1, "b": 2}
    assert result.baseline == {"a": 1, "b": 2}
    assert not result.conflicts


def test_retract_undeclared_removes_owned_keys_even_when_edited():
    target: dict[str, Value] = {"x": {"a": 9, "b": 2, "mine": 0}, "gone": 5, "own": 1}
    owned: dict[str, Value] = {"x": {"a": 1, "b": 2}, "gone": 1}
    retract_undeclared(target, owned, {"x": {"b": 2}})
    assert target == {"x": {"b": 2, "mine": 0}, "own": 1}
    assert owned == {"x": {"b": 2}}


def test_without_paths_prunes_only_tables_it_empties():
    value: dict[str, Value] = {
        "project": {"name": "demo", "extra": {"generator": False}},
        "theme": {"features": ["a"], "font": {"text": "Inter"}},
        "empty": {},
    }
    result = without_paths(
        value,
        frozenset(
            {
                ("project", "name"),
                ("project", "extra"),
                ("theme", "font"),
                ("empty", "missing"),
                ("absent", "key"),
            }
        ),
    )
    assert result == {"theme": {"features": ["a"]}, "empty": {}}
    assert value["project"] == {"name": "demo", "extra": {"generator": False}}


@pytest.mark.parametrize(
    ("location", "label"),
    [
        (MergeLocation("pyproject.toml", ("tool", "ruff")), "tool.ruff"),
        (MergeLocation("justfile"), ""),
        (MergeLocation("justfile", lines=LineSpan(5, 1)), "line 5"),
        (MergeLocation("justfile", lines=LineSpan(5, 3)), "lines 5-7"),
        (MergeLocation("justfile", lines=LineSpan(5, 0)), "after line 5"),
        (MergeLocation("justfile", lines=LineSpan(0, 0)), "at the start"),
    ],
)
def test_describe_location(location, label):
    assert describe_location(location) == label


# --- resolutions --------------------------------------------------------------

COMPLETE = MergePolicy(complete=True)


def resolve_all(base, local, remote, choice, policy=DEFAULT_POLICY):
    """Merges once to find the conflicts, then again with each one resolved."""
    first = reconcile(base, local, remote, LOC, policy)
    choices = {conflict.id: choice for conflict in first.conflicts}
    return first, reconcile(base, local, remote, LOC, policy, choices)


@pytest.mark.parametrize(
    ("base", "local", "remote", "reason", "kept", "taken"),
    [
        pytest.param(
            {"a": 1},
            {"a": 2},
            {"a": 3},
            ConflictReason.DIVERGED,
            ({"a": 2}, {"a": 3}),
            ({"a": 3}, {"a": 3}),
            id="diverged",
        ),
        pytest.param(
            MISSING,
            {"a": 2},
            {"a": 3},
            ConflictReason.UNOWNED,
            ({"a": 2}, {"a": 3}),
            ({"a": 3}, {"a": 3}),
            id="adopted",
        ),
        pytest.param(
            {"a": 1},
            {"a": "one"},
            {"a": 3},
            ConflictReason.TYPE_MISMATCH,
            ({"a": "one"}, {"a": 3}),
            ({"a": 3}, {"a": 3}),
            id="type-mismatch",
        ),
        pytest.param(
            {"a": {"b": 1}},
            {},
            {"a": {"b": 2}},
            ConflictReason.DELETED_ANCESTOR,
            ({}, {"a": {"b": 2}}),
            ({"a": {"b": 2}}, {"a": {"b": 2}}),
            id="deleted",
        ),
    ],
)
def test_resolution_owns_the_update_whichever_side_it_keeps(
    base, local, remote, reason, kept, taken
):
    for choice, (value, baseline) in (
        (ResolutionChoice.LOCAL, kept),
        (ResolutionChoice.DESIRED, taken),
    ):
        first, resolved = resolve_all(base, local, remote, choice)
        (conflict,) = first.conflicts
        assert conflict.reason is reason
        assert conflict.choices == (ResolutionChoice.LOCAL, ResolutionChoice.DESIRED)
        assert (resolved.value, resolved.baseline) == (value, baseline)
        assert not resolved.conflicts
        assert [c.resolution for c in resolved.resolved] == [choice]
        # Settled for good: the next merge of the same update is quiet.
        again = reconcile(resolved.baseline, resolved.value, remote, LOC)
        assert not again.conflicts
        assert semantic_equal(again.value, resolved.value)


@pytest.mark.parametrize(
    ("choice", "value"),
    [(ResolutionChoice.LOCAL, {"a": 2}), (ResolutionChoice.DESIRED, {})],
)
def test_resolving_a_retraction_drops_ownership(choice, value):
    first, resolved = resolve_all({"a": 1}, {"a": 2}, {}, choice, COMPLETE)

    (conflict,) = first.conflicts
    assert conflict.reason is ConflictReason.RETRACTED
    assert conflict.sides == ConflictSides(1, 2, MISSING)
    assert (resolved.value, resolved.baseline) == (value, {})
    assert not resolved.conflicts


def test_structured_conflicts_cannot_keep_both():
    first, resolved = resolve_all({"a": 1}, {"a": 2}, {"a": 3}, ResolutionChoice.BOTH)

    assert resolved.conflicts == first.conflicts
    assert not resolved.resolved


def test_conflict_identity_follows_content_not_line_numbers():
    (conflict,) = reconcile({"a": 1}, {"a": 2}, {"a": 3}, LOC).conflicts
    (edited,) = reconcile({"a": 1}, {"a": 4}, {"a": 3}, LOC).conflicts

    assert conflict.id != edited.id
    assert len(conflict.id) == 12
    moved = replace(conflict, location=replace(conflict.location, lines=LineSpan(3, 1)))
    assert moved.id == conflict.id
    assert replace(conflict, resolution=ResolutionChoice.LOCAL).id == conflict.id


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (1, True),
        (1, 1.0),
        (1.0, 2.0),
        (1, "1"),
        (None, MISSING),
        (date(2024, 1, 1), "2024-01-01"),
    ],
)
def test_conflict_identity_distinguishes_types(left, right):
    def conflict(value: Value) -> MergeConflict:
        return MergeConflict(LOC, ConflictReason.DIVERGED, ConflictSides(0, value, 2))

    assert conflict(left).id != conflict(right).id


def test_conflicts_without_sides_are_settled_by_hand():
    conflict = MergeConflict(LOC, ConflictReason.SHARED_STRUCTURE)

    assert conflict.choices == ()
    assert conflict.settle({conflict.id: ResolutionChoice.LOCAL}) is None


def test_conflicts_with_container_sides_are_hashable():
    (conflict,) = reconcile({"a": [1]}, {"a": [2]}, {"a": [3]}, LOC).conflicts

    assert {conflict, replace(conflict)} == {conflict}
    assert hash(conflict) != hash(replace(conflict, resolution=ResolutionChoice.LOCAL))


def test_a_namespace_retracts_each_owned_key_and_keeps_foreign_ones():
    policy = MergePolicy(complete=True, namespace_paths=frozenset({("tool",)}))
    base: Value = {"tool": {"example": {"a": 1}, "edited": {"a": 1}}}
    local: Value = {
        "tool": {"example": {"a": 1}, "edited": {"a": 2}, "protostar": {"v": 1}}
    }
    result = reconcile(base, local, {}, MergeLocation("pyproject.toml"), policy)

    assert result.value == {"tool": {"edited": {"a": 2}, "protostar": {"v": 1}}}
    assert result.baseline == {"tool": {"edited": {"a": 1}}}
    [conflict] = result.conflicts
    assert conflict.reason is ConflictReason.RETRACTED
    assert conflict.location.keys == ("tool", "edited")


def test_a_retained_path_is_never_retracted():
    policy = MergePolicy(
        complete=True,
        retained_paths=frozenset({("dependency-groups",), ("project", "name")}),
    )
    base: Value = {"dependency-groups": {"dev": []}, "project": {"name": "x"}}
    result = reconcile(
        base, deepcopy(base), {}, MergeLocation("pyproject.toml"), policy
    )

    assert result.value == base
    assert result.baseline == base
    assert not result.conflicts


# --- what each decision carries -------------------------------------------------

SET_LIKE = MergePolicy(frozenset({LOC.keys}))
PROPOSING_SET = MergePolicy(frozenset({LOC.keys}), proposing=True)
NESTED = MergeLocation(LOC.file, (*LOC.keys, "a", "b"), LOC.identity)


@pytest.mark.parametrize(
    ("base", "local", "remote", "reason"),
    [
        (1, 2, 3, ConflictReason.DIVERGED),
        (MISSING, 2, 1, ConflictReason.UNOWNED),
        (1, MISSING, 2, ConflictReason.DELETED_ANCESTOR),
        (True, 1, False, ConflictReason.TYPE_MISMATCH),
        ("old", "old", {"new": 1}, ConflictReason.TYPE_MISMATCH),
        ("old", {"x": 1}, {"new": 1}, ConflictReason.TYPE_MISMATCH),
    ],
)
def test_a_conflict_carries_every_side(base, local, remote, reason):
    [conflict] = reconcile(base, local, remote, LOC).conflicts

    assert conflict == MergeConflict(LOC, reason, ConflictSides(base, local, remote))


def test_a_nested_conflict_keeps_its_location_and_marks_the_whole_merge():
    result = reconcile({"a": {"b": 1}}, {"a": {"b": 2}}, {"a": {"b": 3}}, LOC)

    assert result.decision is MergeDecision.CONFLICT
    assert result.conflicts == (
        MergeConflict(NESTED, ConflictReason.DIVERGED, ConflictSides(1, 2, 3)),
    )


def test_a_kept_edit_under_an_unchanged_update_is_preserved_where_it_is():
    base: Value = {"a": {"b": 1, "c": 1}}
    local: Value = {"a": {"b": 2, "c": 1}}

    result = reconcile(base, local, deepcopy(base), LOC)

    assert (result.value, result.baseline) == (local, base)
    assert result.decision is MergeDecision.KEEP_LOCAL
    assert not result.conflicts
    assert result.preserved == (
        MergeConflict(NESTED, ConflictReason.PRESERVED, ConflictSides(1, 2, 1)),
    )


@pytest.mark.parametrize(
    ("choice", "value", "decision"),
    [
        (ResolutionChoice.LOCAL, {"a": {"b": 2}}, MergeDecision.KEEP_LOCAL),
        (ResolutionChoice.DESIRED, {"a": {"b": 1}}, MergeDecision.APPLY_REMOTE),
    ],
)
def test_settling_a_preserved_edit(choice, value, decision):
    base: Value = {"a": {"b": 1}}
    [preserved] = reconcile(base, {"a": {"b": 2}}, base, LOC).preserved

    result = reconcile(
        base, {"a": {"b": 2}}, base, LOC, resolutions={preserved.id: choice}
    )

    assert (result.value, result.baseline) == (value, base)
    assert result.decision is decision
    assert not result.preserved
    assert result.resolved == (replace(preserved, resolution=choice),)


def test_an_edited_atomic_list_under_an_unchanged_update_is_preserved():
    result = reconcile([1], [1, 2], [1], LOC)

    assert result.value == [1, 2]
    assert not result.conflicts
    [preserved] = result.preserved
    assert preserved == MergeConflict(
        LOC, ConflictReason.PRESERVED, ConflictSides([1], [1, 2], [1])
    )

    restored = reconcile(
        [1], [1, 2], [1], LOC, resolutions={preserved.id: ResolutionChoice.DESIRED}
    )
    assert (restored.value, restored.baseline) == ([1], [1])
    assert restored.decision is MergeDecision.APPLY_REMOTE


@pytest.mark.parametrize(
    ("choice", "value", "decision"),
    [
        (ResolutionChoice.LOCAL, 2, MergeDecision.KEEP_LOCAL),
        (ResolutionChoice.DESIRED, 3, MergeDecision.APPLY_REMOTE),
    ],
)
def test_settling_a_conflict_at_the_root(choice, value, decision):
    [conflict] = reconcile(1, 2, 3, LOC).conflicts

    result = reconcile(1, 2, 3, LOC, resolutions={conflict.id: choice})

    assert (result.value, result.baseline, result.decision) == (value, 3, decision)


def test_a_removed_owned_set_member_is_preserved_and_can_be_restored():
    first = reconcile(["a", "b"], ["a"], ["a", "b"], LOC, SET_LIKE)

    assert first.value == ["a"]
    [preserved] = first.preserved
    assert preserved.sides == ConflictSides(["a", "b"], ["a"], ["a", "b"])

    restored = reconcile(
        ["a", "b"],
        ["a"],
        ["a", "b"],
        LOC,
        SET_LIKE,
        {preserved.id: ResolutionChoice.DESIRED},
    )
    assert restored.value == ["a", "b"]


def test_a_changed_set_keeps_a_removed_member_out_until_restored():
    first = reconcile(["a", "b"], ["a"], ["a", "b", "c"], LOC, SET_LIKE)

    assert first.value == ["a", "c"]
    assert first.baseline == ["a", "b", "c"]
    assert first.decision is MergeDecision.APPLY_REMOTE
    [preserved] = first.preserved

    restored = reconcile(
        ["a", "b"],
        ["a"],
        ["a", "b", "c"],
        LOC,
        SET_LIKE,
        {preserved.id: ResolutionChoice.DESIRED},
    )
    assert restored.value == ["a", "c", "b"]


def test_a_set_with_nothing_removed_preserves_nothing():
    result = reconcile(["a"], ["a"], ["a", "c"], LOC, SET_LIKE)

    assert result.value == ["a", "c"]
    assert result.decision is MergeDecision.APPLY_REMOTE
    assert not result.preserved


@pytest.mark.parametrize(
    ("base", "local"), [(["a"], "a"), ("a", ["a"])], ids=["local", "baseline"]
)
def test_a_set_that_is_not_a_list_is_a_type_mismatch(base, local):
    [conflict] = reconcile(base, local, ["a", "b"], LOC, SET_LIKE).conflicts

    assert conflict.reason is ConflictReason.TYPE_MISMATCH


def test_an_empty_set_establishes_ownership():
    assert reconcile(MISSING, MISSING, [], LOC, SET_LIKE).baseline == []


@pytest.mark.parametrize("base", [MISSING, ["a"]], ids=["unowned", "owned"])
def test_only_a_proposing_policy_proposes_set_members(base):
    result = reconcile(base, ["a"], ["a", "b"], LOC, SET_LIKE)

    assert result.value == ["a", "b"]
    assert not result.proposals


def test_a_proposed_set_member_can_be_declined():
    proposed = reconcile(MISSING, ["a"], ["a", "b"], LOC, PROPOSING_SET)
    assert (proposed.value, proposed.decision) == (
        ["a", "b"],
        MergeDecision.APPLY_REMOTE,
    )
    [proposal] = proposed.proposals
    assert proposal == MergeConflict(
        LOC, ConflictReason.PROPOSED, ConflictSides(MISSING, ["a"], ["a", "b"])
    )

    declined = reconcile(
        MISSING,
        ["a"],
        ["a", "b"],
        LOC,
        PROPOSING_SET,
        {proposal.id: ResolutionChoice.LOCAL},
    )

    assert (declined.value, declined.baseline) == (["a"], ["b"])
    assert declined.decision is MergeDecision.KEEP_LOCAL


def test_a_set_that_already_holds_every_member_proposes_nothing():
    result = reconcile(MISSING, ["a", "b"], ["a", "b"], LOC, PROPOSING_SET)

    assert not result.proposals


def test_an_unchanged_update_under_a_deleted_ancestor_is_quiet():
    result = reconcile(1, MISSING, 1, LOC, MergePolicy(protected_ancestor=True))

    assert result.value is MISSING
    assert not result.conflicts


def test_a_retraction_conflict_keeps_its_location():
    [conflict] = reconcile(
        {"a": 1, "b": 2}, {"a": 1, "b": 3}, {"a": 1}, LOC, COMPLETE
    ).conflicts

    assert conflict.location == MergeLocation(LOC.file, (*LOC.keys, "b"), LOC.identity)


def test_a_namespace_retraction_keeps_its_location():
    policy = MergePolicy(complete=True, namespace_paths=frozenset({(*LOC.keys, "ns")}))
    base: Value = {"ns": {"x": {"a": 1}, "y": {"a": 1}}}

    [conflict] = reconcile(
        base, {"ns": {"x": {"a": 1}, "y": {"a": 2}}}, {}, LOC, policy
    ).conflicts

    assert conflict.location == MergeLocation(
        LOC.file, (*LOC.keys, "ns", "y"), LOC.identity
    )


def test_a_fully_retracted_namespace_is_removed():
    policy = MergePolicy(complete=True, namespace_paths=frozenset({("tool",)}))
    base: Value = {"tool": {"example": {"a": 1}, "deleted": {"a": 1}}, "kept": 1}
    # The user already removed one owned key; the rest is unedited.
    local: Value = {"tool": {"example": {"a": 1}}, "kept": 1}

    result = reconcile(
        base, local, {"kept": 1}, MergeLocation("pyproject.toml"), policy
    )

    assert result.value == {"kept": 1}
    assert result.baseline == {"kept": 1}
    assert not result.conflicts


# --- helpers ---------------------------------------------------------------------


def test_hold_restores_the_baseline_at_a_deep_path():
    remote: dict[str, Value] = {"a": {"b": {"c": 2, "d": 2}}}

    hold(remote, {"a": {"b": {"c": 1}}}, ("a", "b", "c"))

    assert remote == {"a": {"b": {"c": 1, "d": 2}}}


def test_hold_drops_a_value_that_was_never_owned():
    remote: dict[str, Value] = {"a": {"b": {"c": 2}}, "x": {}}

    hold(remote, MISSING, ("a", "b", "c"))
    hold(remote, MISSING, ("x", "absent"))

    assert remote == {"a": {"b": {}}, "x": {}}


def test_without_paths_prunes_every_table_it_empties():
    assert without_paths({"a": {"b": {"c": 1}}}, frozenset({("a", "b", "c")})) == {}


def test_retract_undeclared_tolerates_a_key_the_user_removed():
    target: dict[str, Value] = {}
    owned: dict[str, Value] = {"gone": 1}

    retract_undeclared(target, owned, {})

    assert (target, owned) == ({}, {})


def test_retract_undeclared_leaves_a_table_turned_into_a_value():
    target: dict[str, Value] = {"a": {"x": 1}}
    owned: dict[str, Value] = {"a": {"x": 1}}

    retract_undeclared(target, owned, {"a": 1})

    assert (target, owned) == ({"a": {"x": 1}}, {"a": {"x": 1}})


def test_prune_unapplied_ignores_a_previous_value_that_was_not_a_table():
    owned: dict[str, Value] = {"a": {"b": {}}}

    prune_unapplied(owned, {"a": 1}, {"a": {"b": {}}})

    assert owned == {"a": {}}


def test_conflict_ids_do_not_change_between_releases():
    """A ``--resolve`` printed by one run must still settle the next one."""
    conflict = MergeConflict(
        LOC,
        ConflictReason.DIVERGED,
        ConflictSides(
            MISSING,
            {"b": [1, 2.5], "a": True},
            [date(2024, 1, 2), time(3, 4), "s", None],
        ),
    )

    assert conflict.id == "f18f9a5ff35a"


@pytest.mark.parametrize(("base", "local"), [(1, None), (None, 2)])
def test_an_edit_to_or_from_null_under_an_unchanged_update_is_preserved(base, local):
    result = reconcile(base, local, base, LOC)

    assert (result.value, result.baseline) == (local, base)
    assert result.preserved == (
        MergeConflict(LOC, ConflictReason.PRESERVED, ConflictSides(base, local, base)),
    )


@pytest.mark.parametrize("value", [{"a": {}}, {"a": {"c": {}}}])
def test_without_paths_keeps_what_a_path_below_it_never_reached(value):
    assert without_paths(value, frozenset({("a", "c", "d")})) == value
