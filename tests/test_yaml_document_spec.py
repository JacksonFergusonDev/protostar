"""Spec-driven keyed sequences: identity, placement, holds, and ambiguity."""

from typing import Any

import pytest

from protostar.documents import YAML_DOCUMENTS, codecov, github_workflows, pre_commit
from protostar.errors import ConfigurationError
from protostar.merge import MISSING, ConflictReason, MergeLocation
from protostar.yaml_ast import (
    WILDCARD,
    KeyedSequence,
    YamlDocumentSpec,
    YamlGuard,
    decode_yaml_baseline,
    encode_yaml_baseline,
    reconcile_yaml,
    validate_yaml_baseline,
)

# A document shaped like a CI workflow proves the engine is not pre-commit specific.
JOBS = YamlDocumentSpec(
    "jobs", keyed=(KeyedSequence(("jobs", WILDCARD, "steps"), "name"),)
)
LOCATION = MergeLocation("jobs.yml")
DESIRED = """jobs:
  test:
    steps:
      - name: checkout
        uses: checkout@v1
      - name: install
        run: sync
      - name: test
        run: pytest
"""


def merge(local, desired, base=DESIRED, spec=JOBS, **kwargs):
    return reconcile_yaml(
        spec,
        local,
        desired,
        decode_yaml_baseline(base) if base is not MISSING else MISSING,
        LOCATION,
        **kwargs,
    )


def load(content: str) -> Any:
    return decode_yaml_baseline(content)


def steps(content, job="test"):
    return load(content)["jobs"][job]["steps"]


def names(content, job="test"):
    return [step.get("name") for step in steps(content, job)]


def test_wildcard_matches_one_segment_of_the_same_depth():
    sequence = KeyedSequence(("jobs", WILDCARD, "steps"), "name")
    assert sequence.matches(("jobs", "test", "steps"))
    assert not sequence.matches(("jobs", "steps"))
    assert not sequence.matches(("jobs", "test", "steps", "x"))
    assert not sequence.matches(("other", "test", "steps"))
    assert JOBS.sequence_at(("jobs", "lint", "steps")) == sequence
    assert JOBS.sequence_at(("jobs",)) is None


def test_registry_maps_each_supported_document_to_its_spec():
    assert YAML_DOCUMENTS == {
        codecov.TARGET: codecov.SPEC,
        pre_commit.TARGET: pre_commit.SPEC,
        github_workflows.CI_TARGET: github_workflows.SPEC,
        github_workflows.RELEASE_TARGET: github_workflows.SPEC,
    }
    assert pre_commit.SPEC.sequence_at(("repos", "any-repo", "hooks")) is not None


def test_new_record_goes_after_its_nearest_earlier_sibling():
    local = DESIRED.replace(
        "      - name: test\n",
        "      - name: mine\n        run: echo\n      - name: test\n",
    )
    desired = DESIRED.replace(
        "      - name: test\n",
        "      - name: lint\n        run: ruff\n      - name: test\n",
    )
    result = merge(local, desired)
    assert names(result.content) == ["checkout", "install", "lint", "mine", "test"]
    assert not result.conflicts


def test_new_leading_record_goes_before_its_next_sibling():
    local = DESIRED.replace("    steps:\n", "    steps:\n      - name: mine\n")
    desired = DESIRED.replace("    steps:\n", "    steps:\n      - name: first\n")
    result = merge(local, desired)
    assert names(result.content) == ["mine", "first", "checkout", "install", "test"]


def test_consecutive_new_records_keep_desired_order():
    desired = DESIRED.replace(
        "      - name: test\n",
        "      - name: a\n      - name: b\n      - name: test\n",
    )
    result = merge(DESIRED, desired)
    assert names(result.content) == ["checkout", "install", "a", "b", "test"]


def test_records_without_identity_are_foreign_and_stay_in_place():
    local = DESIRED.replace(
        "      - name: install\n",
        "      - run: echo anonymous\n      - name: install\n",
    )
    result = merge(local, DESIRED.replace("checkout@v1", "checkout@v2"))
    assert steps(result.content)[1] == {"run": "echo anonymous"}
    assert steps(result.content)[0]["uses"] == "checkout@v2"
    assert result.baseline == decode_yaml_baseline(
        DESIRED.replace("checkout@v1", "checkout@v2")
    )
    assert not result.conflicts


def test_desired_or_owned_records_need_an_identity():
    with pytest.raises(ConfigurationError):
        merge(DESIRED, DESIRED + "  lint:\n    steps:\n      - run: echo\n")
    with pytest.raises(ConfigurationError):
        validate_yaml_baseline(
            JOBS, decode_yaml_baseline(DESIRED + "  x:\n    steps: [1]\n")
        )


def test_duplicate_nested_identity_holds_the_containing_entry():
    local = (
        DESIRED.replace(
            "      - name: test\n",
            "      - name: test\n        run: a\n      - name: test\n",
        )
        + "  lint:\n    steps:\n      - name: ruff\n"
    )
    base = DESIRED + "  lint:\n    steps:\n      - name: ruff\n"
    desired = base.replace("checkout@v1", "checkout@v2").replace(
        "- name: ruff\n", "- name: ruff\n        run: ruff\n"
    )
    result = merge(local, desired, base)
    assert steps(result.content)[0]["uses"] == "checkout@v1"
    assert steps(result.content, "lint")[0]["run"] == "ruff"
    [conflict] = result.conflicts
    assert conflict.reason is ConflictReason.DUPLICATE_IDENTITY
    assert conflict.location.keys == ("jobs", "test")
    assert conflict.location.identity is None


def test_hold_keeps_local_value_and_previous_ownership_silently():
    local = DESIRED.replace("run: pytest", "run: pytest -x")
    desired = DESIRED.replace("run: pytest", "run: pytest -q").replace(
        "checkout@v1", "checkout@v2"
    )
    held = ("jobs", "test", "steps", "test", "run")
    result = merge(local, desired, guard=YamlGuard((held,)))
    assert steps(result.content)[2]["run"] == "pytest -x"
    assert steps(result.content)[0]["uses"] == "checkout@v2"
    assert steps(encode_yaml_baseline(result.baseline))[2]["run"] == "pytest"
    assert not result.conflicts


def test_hold_on_unowned_path_adds_nothing_and_survives_overwrite():
    desired = DESIRED + "  lint:\n    steps:\n      - name: ruff\n"
    result = merge(DESIRED, desired, guard=YamlGuard((("jobs", "lint"),)))
    assert "lint" not in load(result.content)["jobs"]
    local = DESIRED.replace("run: pytest", "run: pytest -x")
    overwritten = merge(
        local,
        DESIRED.replace("run: pytest", "run: pytest -q"),
        guard=YamlGuard((("jobs", "test", "steps", "test", "run"),)),
        overwrite=True,
    )
    assert steps(overwritten.content)[2]["run"] == "pytest -x"
