"""The configuration form's save: values applied to the file's text."""

import tomllib

import pytest

from protostar.config import DEFAULT_CONFIG_CONTENT, UserConfig
from protostar.config_edit import EDITABLE_KEYS, config_values, edit_config
from protostar.errors import ConfigurationError

CUSTOM = """\
# My settings.
[env]
ruff = true  # keep this comment
ide = "vscode"
unknown_key = 1
author_name = "Old Name"

[templates]
team = "https://example.com/team.toml"
"""


def test_a_round_trip_keeps_comments_unknown_keys_and_templates():
    edit = edit_config(CUSTOM, {"ruff": False, "ide": "cursor"}, source="c")
    assert edit.after == CUSTOM.replace(
        "ruff = true  # keep", "ruff = false  # keep"
    ).replace('ide = "vscode"', 'ide = "cursor"')
    assert edit.changed == ("ide", "ruff")


def test_only_values_that_change_are_written():
    unchanged = config_values(UserConfig.parse(CUSTOM, "c"))
    assert edit_config(CUSTOM, unchanged, source="c").after == CUSTOM
    # Ruff is on by default, so the default file gains no `ruff = true`.
    edit = edit_config(DEFAULT_CONFIG_CONTENT, {"ruff": True, "mypy": True}, source="c")
    assert edit.changed == ("mypy",)
    added = set(edit.after.splitlines()) - set(DEFAULT_CONFIG_CONTENT.splitlines())
    assert added == {"mypy = true"}


def test_nothing_to_change_leaves_the_text_as_it_is():
    edit = edit_config(CUSTOM, {"ide": "vscode"}, source="c")
    assert edit.changed == ()
    assert edit.after == edit.before == CUSTOM


def test_a_new_key_follows_its_commented_example():
    edit = edit_config(
        DEFAULT_CONFIG_CONTENT, {"author_name": "Ada", "prek": True}, source="c"
    )
    lines = edit.after.splitlines()
    assert (
        lines[lines.index('# author_name = "your-name"') + 1] == 'author_name = "Ada"'
    )
    assert lines[lines.index("prek = true") - 1].startswith("# prek = true")
    assert tomllib.loads(edit.after)["env"]["prek"] is True


def test_a_key_without_an_example_follows_the_last_setting():
    edit = edit_config(CUSTOM, {"mypy": True}, source="c")
    assert 'author_name = "Old Name"\nmypy = true\n\n[templates]' in edit.after


def test_an_empty_file_gains_an_env_table():
    edit = edit_config("", {"ide": "cursor"}, source="c")
    assert edit.after == '[env]\nide = "cursor"\n'


@pytest.mark.parametrize("cleared", ["", None])
def test_clearing_a_value_removes_its_key(cleared):
    edit = edit_config(CUSTOM, {"author_name": cleared}, source="c")
    assert "author_name" not in edit.after
    assert edit.changed == ("author_name",)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"pre_commit": True, "prek": True}, "both 'pre_commit = true'"),
        ({"github_username": "not a user!"}, "GitHub username"),
        ({"python_version": "two"}, "Python"),
    ],
)
def test_an_invalid_result_is_a_configuration_error(values, message):
    with pytest.raises(ConfigurationError, match=message):
        edit_config(DEFAULT_CONFIG_CONTENT, values, source="c")


def test_every_editable_key_is_a_user_config_field():
    values = config_values(UserConfig())
    assert tuple(values) == EDITABLE_KEYS
