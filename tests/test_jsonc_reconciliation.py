"""Three-way JSONC reconciliation: ownership, conflicts, and comment preservation."""

import pytest

from protostar.errors import ConfigurationError
from protostar.jsonc_ast import decode_jsonc, reconcile_jsonc
from protostar.merge import MISSING, ConflictReason, MergeLocation

LOCATION = MergeLocation(".github/renovate.json")

DESIRED_V1 = """\
{
  // managed by protostar
  "extends": ["config:best-practices"],
  "schedule": ["before 4am on monday"],
  "packageRules": {"automerge": true}
}
"""
DESIRED_V2 = DESIRED_V1.replace("before 4am", "before 6am")


def merge(local, remote, base=MISSING, **kwargs):
    return reconcile_jsonc(local, remote, base, LOCATION, **kwargs)


def owned(text):
    return decode_jsonc(text)


def test_missing_file_writes_desired_bytes_verbatim_and_owns_everything():
    result = merge("", DESIRED_V1, missing_file=True)

    assert result.content == DESIRED_V1
    assert result.baseline == owned(DESIRED_V1)
    assert result.conflicts == ()


def test_existing_equal_content_is_not_adopted():
    result = merge(DESIRED_V1, DESIRED_V1)

    assert result.content == DESIRED_V1
    assert result.baseline is MISSING
    assert result.conflicts == ()


def test_unowned_file_receives_only_missing_keys_and_keeps_local_trivia():
    local = '{\n  // mine\n  "extends": ["local"], // keep\n  "custom": 1\n}\n'

    result = merge(local, DESIRED_V1)

    assert result.content.startswith(
        '{\n  // mine\n  "extends": ["local"], // keep\n  "custom": 1,\n'
    )
    assert decode_jsonc(result.content) == {
        "extends": ["local"],
        "custom": 1,
        "schedule": ["before 4am on monday"],
        "packageRules": {"automerge": True},
    }
    assert result.baseline == {
        "schedule": ["before 4am on monday"],
        "packageRules": {"automerge": True},
    }
    assert [c.location.keys for c in result.conflicts] == [("extends",)]
    assert result.conflicts[0].reason is ConflictReason.UNOWNED


def test_owned_unedited_value_takes_remote_update_in_place():
    result = merge(DESIRED_V1, DESIRED_V2, owned(DESIRED_V1))

    assert result.content == DESIRED_V2
    assert result.baseline == owned(DESIRED_V2)
    assert result.conflicts == ()


def test_clean_update_preserves_user_comments_and_foreign_keys():
    local = (
        "{\n  // managed by protostar\n"
        '  "extends": ["config:best-practices"], // team preset\n'
        '  "schedule": ["before 4am on monday"],\n'
        '  "labels": ["deps"], /* ours */\n'
        '  "packageRules": {"automerge": true}\n}\n'
    )

    result = merge(local, DESIRED_V2, owned(DESIRED_V1))

    assert result.content == local.replace("before 4am", "before 6am")
    assert result.conflicts == ()


def test_locally_edited_owned_value_is_preserved_with_a_conflict():
    local = DESIRED_V1.replace("before 4am", "before 9pm")

    result = merge(local, DESIRED_V2, owned(DESIRED_V1))

    assert result.content == local
    assert result.baseline == owned(DESIRED_V1)
    assert [(c.location.keys, c.reason) for c in result.conflicts] == [
        (("schedule",), ConflictReason.DIVERGED)
    ]


def test_local_edits_are_silent_when_remote_intent_is_unchanged():
    local = DESIRED_V1.replace("before 4am", "before 9pm")

    result = merge(local, DESIRED_V1, owned(DESIRED_V1))

    assert result.content == local
    assert result.conflicts == ()
    assert result.baseline == owned(DESIRED_V1)


def test_locally_deleted_owned_key_stays_deleted():
    local = '{\n  "extends": ["config:best-practices"]\n}\n'

    unchanged = merge(local, DESIRED_V1, owned(DESIRED_V1))
    changed = merge(local, DESIRED_V2, owned(DESIRED_V1))

    assert unchanged.content == local
    assert unchanged.conflicts == ()
    assert changed.content == local
    assert [c.reason for c in changed.conflicts] == [ConflictReason.DELETED_ANCESTOR]


def test_type_mismatch_is_preserved():
    local = '{"packageRules": ["custom"]}\n'
    remote = DESIRED_V1.replace('"automerge": true', '"automerge": false')

    result = merge(local, remote, owned(DESIRED_V1))

    assert "custom" in result.content
    assert ConflictReason.TYPE_MISMATCH in {c.reason for c in result.conflicts}


def test_accepted_array_update_keeps_comments_on_unchanged_elements():
    base = {"extends": ["a", "b"]}
    local = '{\n  "extends": [\n    "a", // first\n    "b" // second\n  ]\n}\n'
    remote = '{"extends": ["a", "b", "c"]}'

    result = merge(local, remote, base)

    assert result.content == (
        '{\n  "extends": [\n    "a", // first\n    "b", // second\n    "c"\n  ]\n}\n'
    )
    assert result.baseline == {"extends": ["a", "b", "c"]}


def test_edited_array_is_atomic_and_preserved():
    base = {"extends": ["a", "b"]}
    local = '{"extends": ["a", "mine"]}'

    result = merge(local, '{"extends": ["a", "b", "c"]}', base)

    assert result.content == local
    assert [c.reason for c in result.conflicts] == [ConflictReason.DIVERGED]


def test_nested_mappings_recurse_and_retain_foreign_siblings():
    base = {"vulnerabilityAlerts": {"schedule": ["at any time"]}}
    local = (
        '{\n  "vulnerabilityAlerts": {\n    "schedule": ["at any time"],\n'
        '    "labels": ["security"] // mine\n  }\n}\n'
    )
    remote = '{"vulnerabilityAlerts": {"schedule": ["daily"], "enabled": true}}'

    result = merge(local, remote, base)

    assert decode_jsonc(result.content) == {
        "vulnerabilityAlerts": {
            "schedule": ["daily"],
            "labels": ["security"],
            "enabled": True,
        }
    }
    assert "// mine" in result.content


def test_semantic_noop_returns_original_bytes_exactly():
    local = '{ "extends" :[ "config:best-practices" ] ,\r\n\t/* x */ "schedule":["before 4am on monday"],"packageRules":{"automerge":true}}'

    result = merge(local, DESIRED_V1, owned(DESIRED_V1))

    assert result.content == local
    assert result.conflicts == ()


def test_blank_and_comment_only_files_gain_a_root_and_keep_comments():
    blank = merge("\n", '{"a": 1}')
    commented = merge("// notes\n", '{"a": 1}')

    assert blank.content == '\n{\n  "a": 1\n}\n'
    assert commented.content == '// notes\n{\n  "a": 1\n}\n'
    assert commented.baseline == {"a": 1}


def test_default_indent_applies_when_the_document_has_none_to_infer():
    result = merge("{}", '{"a": {"b": 1}}', default_indent="    ")

    assert result.content == '{\n    "a": {\n        "b": 1\n    }\n}'


def test_deleted_tracked_file_is_not_recreated_without_overwrite():
    silent = merge("", DESIRED_V1, owned(DESIRED_V1), missing_file=True)
    result = merge("", DESIRED_V2, owned(DESIRED_V1), missing_file=True)

    assert silent.content == ""
    assert silent.conflicts == ()
    assert result.content == ""
    assert result.baseline == owned(DESIRED_V1)
    assert [c.reason for c in result.conflicts] == [ConflictReason.DELETED_ANCESTOR]


def test_overwrite_owns_declared_values_and_retains_foreign_siblings():
    local = '{\n  "extends": ["mine"], // mine\n  "custom": 1\n}\n'

    result = merge(local, DESIRED_V1, overwrite=True)

    assert decode_jsonc(result.content) == {
        "extends": ["config:best-practices"],
        "custom": 1,
        "schedule": ["before 4am on monday"],
        "packageRules": {"automerge": True},
    }
    assert "// mine" in result.content
    assert result.baseline == owned(DESIRED_V1)
    assert result.conflicts == ()


def test_overwrite_recreates_a_deleted_file_from_desired_bytes():
    result = merge("", DESIRED_V1, owned(DESIRED_V1), missing_file=True, overwrite=True)

    assert result.content == DESIRED_V1
    assert result.conflicts == ()


def test_repeated_reconciliation_is_idempotent():
    first = merge("", DESIRED_V1, missing_file=True)
    second = merge(first.content, DESIRED_V1, first.baseline)
    third = merge(first.content, DESIRED_V2, first.baseline)
    fourth = merge(third.content, DESIRED_V2, third.baseline)

    assert second.content == first.content
    assert second.baseline == first.baseline
    assert fourth.content == third.content
    assert fourth.baseline == owned(DESIRED_V2)


def test_null_values_are_owned_and_distinct_from_absence():
    result = merge("{}", '{"a": null}')

    assert decode_jsonc(result.content) == {"a": None}
    assert result.baseline == {"a": None}


@pytest.mark.parametrize(
    ("original", "desired"),
    [
        ('{"a": 1, "a": 2}', "{}"),
        ("{", "{}"),
        ("{}", '{"a": 1,, }'),
        ("{}", "[]"),
        ("{}", ""),
    ],
)
def test_invalid_documents_are_domain_errors(original, desired):
    with pytest.raises(ConfigurationError):
        merge(original, desired)
