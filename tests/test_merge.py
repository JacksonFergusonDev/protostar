from copy import deepcopy
from datetime import date, datetime, time
from typing import cast

import pytest

from protostar.errors import ConfigurationError
from protostar.merge import (
    MISSING,
    ConflictReason,
    MergeDecision,
    MergeLocation,
    MergePolicy,
    Value,
    overlay_declared,
    prune_unapplied,
    reconcile,
    semantic_equal,
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


@pytest.mark.parametrize("local", [MISSING, "user scalar", []])
def test_deleted_or_incompatible_owned_table_protects_new_children(local):
    result = reconcile({"old": 1}, local, {"old": 1, "new": 2}, LOC)
    assert semantic_equal(result.value, local)
    assert result.baseline == {"old": 1}
    assert len(result.conflicts) == 1


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
    with pytest.raises(ConfigurationError):
        reconcile(MISSING, MISSING, sequence, LOC, MergePolicy(frozenset({LOC.keys})))


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


def test_kernel_rejects_cycles_and_unsupported_values():
    cyclic: list[Value] = []
    cyclic.append(cyclic)
    for value in (cyclic, {"bad": object()}, {"bad": MISSING}, [MISSING]):
        with pytest.raises(ConfigurationError):
            reconcile(MISSING, MISSING, cast(Value, value), LOC)


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
