"""Identity-aware pre-commit reconciliation and pin acceptance contracts."""

import pytest

from protostar.errors import ConfigurationError
from protostar.merge import MISSING, MergeLocation
from protostar.pre_commit import TARGET, reconcile_hook_config
from protostar.registry import RemoteHook, ResolvedHookRevision
from protostar.sync_state import FilePolicy, FileState, PinProvenance
from protostar.yaml_ast import (
    decode_yaml_baseline,
    encode_yaml_baseline,
    reconcile_pre_commit,
)

LOCATION = MergeLocation(TARGET)
BASE = """# hooks
repos:
  - repo: remote
    rev: v1.0.0 # pin
    hooks:
      - id: managed
        args: [old] # args
  - repo: local
    hooks:
      - id: check
        entry: old
        language: system
"""


def merge(local, desired, base=BASE, **kwargs):
    return reconcile_pre_commit(
        local,
        desired,
        decode_yaml_baseline(base) if base is not MISSING else MISSING,
        LOCATION,
        **kwargs,
    )


def repositories(content):
    records = decode_yaml_baseline(content)["repos"]
    assert isinstance(records, list)
    return records


def repo(content, name="remote"):
    return next(r for r in repositories(content) if r["repo"] == name)


def test_update_pin_add_hook_preserve_comments_and_foreign_fields():
    local = BASE.replace(
        "args: [old]", "args: [custom]\n        stages: [manual]"
    ).replace(
        "  - repo: local",
        "      - id: custom\n        args: [foreign]\n  - repo: local",
    )
    desired = BASE.replace("v1.0.0", "v2.0.0").replace(
        "  - repo: local", "      - id: added\n  - repo: local"
    )
    result = merge(local, desired)
    updated = repo(result.content)
    assert updated["rev"] == "v2.0.0"
    assert [h["id"] for h in updated["hooks"]] == ["managed", "custom", "added"]
    assert updated["hooks"][0]["args"] == ["custom"]
    assert updated["hooks"][0]["stages"] == ["manual"]
    assert "# pin" in result.content
    assert "# args" in result.content
    owned = repo(encode_yaml_baseline(result.baseline))
    assert [h["id"] for h in owned["hooks"]] == ["managed", "added"]
    assert "stages" not in owned["hooks"][0]
    assert not result.conflicts


def test_new_file_noop_and_unowned_equal():
    initial = merge("", BASE, MISSING, missing_file=True)
    repeated = merge(initial.content, BASE, encode_yaml_baseline(initial.baseline))
    assert repeated.content == initial.content
    assert repeated.baseline == initial.baseline
    equal = merge(BASE, BASE, MISSING)
    assert equal.content == BASE
    assert equal.baseline is MISSING


@pytest.mark.parametrize(
    "local",
    [BASE.replace("v1.0.0", "v9.0.0"), BASE.replace("    rev: v1.0.0 # pin\n", "")],
)
def test_pin_edit_and_deletion_survive(local):
    result = merge(local, BASE.replace("v1.0.0", "v2.0.0"))
    assert result.content == local
    assert result.baseline == decode_yaml_baseline(BASE)
    assert result.conflicts


@pytest.mark.parametrize("local", ["repos: []\n", "{}\n", ""])
def test_deleted_repository_parent_or_file_not_resurrected(local):
    result = merge(
        local, BASE.replace("entry: old", "entry: new"), missing_file=not local
    )
    assert result.content == local
    assert result.conflicts


def test_local_hooks_are_managed_by_identity():
    result = merge(BASE, BASE.replace("entry: old", "entry: new"))
    assert repo(result.content, "local")["hooks"][0]["entry"] == "new"
    assert not result.conflicts


def test_foreign_same_repo_is_not_adopted():
    local = "repos:\n  - repo: remote\n    rev: v1.0.0\n    hooks: [{id: custom}]\n"
    result = merge(local, BASE, MISSING)
    owned = repo(encode_yaml_baseline(result.baseline))
    assert "rev" not in owned
    assert owned["hooks"] == [{"id": "managed", "args": ["old"]}]
    assert repo(result.content)["hooks"][0]["id"] == "custom"


@pytest.mark.parametrize("duplicate", ["  - repo: remote\n    hooks: []\n", ""])
def test_duplicate_identities_preserve_repository(duplicate):
    local = (
        BASE + duplicate
        if duplicate
        else BASE.replace(
            "      - id: managed", "      - id: managed\n      - id: managed"
        )
    )
    result = merge(local, BASE.replace("v1.0.0", "v2.0.0"))
    assert result.content == local
    assert result.conflicts
    assert result.baseline == decode_yaml_baseline(BASE)


def test_desired_duplicates_are_fatal():
    with pytest.raises(ConfigurationError):
        merge(BASE, BASE + "  - repo: local\n    hooks: []\n")


def test_top_level_managed_fields_change_preserving_custom_fields():
    base = "default_install_hook_types: [pre-commit]\n" + BASE
    local = base + "fail_fast: true\n"
    result = merge(
        local, base.replace("[pre-commit]", "[pre-commit, commit-msg]"), base
    )
    assert decode_yaml_baseline(result.content)["default_install_hook_types"] == [
        "pre-commit",
        "commit-msg",
    ]
    assert decode_yaml_baseline(result.content)["fail_fast"] is True
    assert "fail_fast" not in result.baseline


def test_alias_blocks_are_preserved():
    local = BASE.replace("args: [old]", "args: &args [old]") + "foreign: *args\n"
    result = merge(local, BASE.replace("args: [old]", "args: [new]"))
    assert result.content == local
    assert result.conflicts
    assert result.baseline == decode_yaml_baseline(BASE)


def automatic(rev, provenance=PinProvenance.REGISTRY):
    return (ResolvedHookRevision(RemoteHook.GITLEAKS, rev, provenance),)


PINNED = f"repos:\n  - repo: {RemoteHook.GITLEAKS.value}\n    rev: {RemoteHook.GITLEAKS.placeholder}\n    hooks: [{{id: gitleaks}}]\n"


def pin_run(
    local,
    revision,
    record=None,
    pins=(),
    provenance=PinProvenance.REGISTRY,
    desired=PINNED,
):
    return reconcile_hook_config(
        local,
        desired,
        record,
        automatic(revision, provenance),
        pins,
        missing_file=not local,
    )


def pin_record(result):
    return FileState(TARGET, FilePolicy.YAML, encode_yaml_baseline(result.baseline))


@pytest.mark.parametrize(
    ("revision", "provenance"),
    [
        ("v0.5.0", PinProvenance.REGISTRY),
        ("opaque", PinProvenance.REGISTRY),
        ("v3.0.0", PinProvenance.FALLBACK),
        ("v0.5.0", PinProvenance.FALLBACK),
    ],
)
def test_automatic_pin_guard(revision, provenance):
    first, pins = pin_run("", "v1.0.0")
    result, updated = pin_run(
        first.content, revision, pin_record(first), pins, provenance
    )
    assert result.content == first.content
    assert result.baseline == first.baseline
    assert updated == pins
    assert result.conflicts


def test_safe_pin_advances_once_and_explicit_opaque_changes_apply():
    first, pins = pin_run("", "v1.0.0")
    result, pins = pin_run(first.content, "v2.0.0", pin_record(first), pins)
    assert pins[0].revision == "v2.0.0"
    assert pins[0].provenance is PinProvenance.REGISTRY
    explicit, pins = pin_run(
        result.content,
        "v2.0.0",
        pin_record(result),
        pins,
        desired=PINNED.replace(RemoteHook.GITLEAKS.placeholder, "abcdef"),
    )
    assert pins[0].revision == "abcdef"
    assert pins[0].provenance is PinProvenance.TEMPLATE
    assert not explicit.conflicts


def test_ambiguous_repo_does_not_block_independent_update_or_reorder():
    local = BASE + "  - repo: remote\n    hooks: [{id: foreign}]\n"
    result = merge(
        local, BASE.replace("entry: old", "entry: new").replace("v1.0.0", "v2.0.0")
    )
    records = repositories(result.content)
    assert [r["repo"] for r in records] == ["remote", "local", "remote"]
    assert records[0]["rev"] == "v1.0.0"
    assert records[1]["hooks"][0]["entry"] == "new"
    assert result.conflicts[0].location.identity == "remote"


def test_overwrite_targets_managed_fields_preserves_foreign_hooks():
    local = BASE.replace("args: [old]", "args: [user]").replace(
        "  - repo: local", "      - id: custom\n  - repo: local"
    )
    result = merge(local, BASE.replace("args: [old]", "args: [new]"), overwrite=True)
    assert repo(result.content)["hooks"] == [
        {"id": "managed", "args": ["new"]},
        {"id": "custom"},
    ]
    assert not result.conflicts


@pytest.mark.parametrize(
    "desired",
    [
        "repos: null",
        "repos: [1]",
        "repos: [{repo: x, rev: false}]",
        "repos: [{repo: x, hooks: [1]}]",
    ],
)
def test_invalid_pre_commit_shapes_raise_domain_errors(desired):
    with pytest.raises(ConfigurationError):
        reconcile_hook_config(BASE, desired, None, (), ())


def test_owned_duplicate_identities_are_invalid_state():
    with pytest.raises(ConfigurationError):
        FileState(TARGET, FilePolicy.YAML, BASE + "  - repo: local\n    hooks: []\n")
