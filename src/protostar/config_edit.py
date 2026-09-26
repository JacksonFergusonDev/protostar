"""The configuration editor's save: form values applied to the file's text.

Pure and headless: the form hands in values, and this returns the new text
without writing it. The CLI writes it once the user has seen the change.
"""

from collections.abc import Mapping
from dataclasses import dataclass

import tomlkit
from tomlkit.container import Container
from tomlkit.items import Comment, Table

from protostar.config import UserConfig
from protostar.modules import TOOLING_MODULES

type EnvValue = str | bool | None
"""A value under ``[env]``; ``None`` leaves the key unset."""

IDENTITY_KEYS = ("author_name", "author_email", "github_username")
"""The identity a new project's metadata starts from."""

ENVIRONMENT_KEYS = ("ide", "python_version")
"""The editor to set up and the Python version to scaffold."""

TOOL_KEYS = tuple(module.config_key for module in TOOLING_MODULES)
"""One default per tool; a template's own choice wins over it."""

EDITABLE_KEYS = (*IDENTITY_KEYS, *ENVIRONMENT_KEYS, *TOOL_KEYS)
"""Every ``[env]`` key the form edits, in the file's order."""


@dataclass(frozen=True)
class ConfigEdit:
    """The configuration file before and after the form's values.

    Attributes:
        before: The text the values were applied to.
        after: The text with the values applied.
        changed: The keys whose effective value changed, in form order.
    """

    before: str
    after: str
    changed: tuple[str, ...]


def config_values(config: UserConfig) -> dict[str, EnvValue]:
    """Returns the effective value of every key the form edits.

    Args:
        config: The configuration, with its defaults filled in.

    Returns:
        Each editable key's value; ``None`` where it is unset.
    """
    values: dict[str, EnvValue] = {}
    for key in EDITABLE_KEYS:
        value = getattr(config, key)
        values[key] = value if value is None or isinstance(value, bool) else str(value)
    return values


def edit_config(
    content: str, values: Mapping[str, EnvValue], *, source: str
) -> ConfigEdit:
    """Applies the form's values to the configuration file's text.

    Only a key whose value differs from what the file already yields is
    written, so comments, unrelated keys, and ``[templates]`` stay as they
    are. An empty string or ``None`` removes the key, restoring its default.
    A new key goes right after its commented example when the file has one.

    Args:
        content: The configuration file's current text.
        values: The form's values, by ``[env]`` key.
        source: Where the text came from, for error messages.

    Returns:
        The file's text before and after, and the keys that changed.

    Raises:
        ConfigurationError: If the current text or the result is invalid,
            such as both hook managers enabled.
    """
    current = config_values(UserConfig.parse(content, source))
    document = tomlkit.parse(content)
    env = document.get("env")
    if not isinstance(env, Table):
        env = tomlkit.table()
        document.add("env", env)
    for key in EDITABLE_KEYS:
        if key not in values:
            continue
        value = values[key]
        if value == "":
            value = None
        if value == current[key]:
            continue
        if value is None:
            if key in env:
                del env[key]
        elif key in env:
            env[key] = value
        else:
            _insert(env.value, key, value)
    after = tomlkit.dumps(document)
    result = config_values(UserConfig.parse(after, source))
    changed = tuple(key for key in EDITABLE_KEYS if result[key] != current[key])
    return ConfigEdit(content, after if changed else content, changed)


def _insert(env: Container, key: str, value: str | bool) -> None:
    """Adds ``key`` after its commented example, or after the last setting."""
    index = None
    for position, (existing, item) in enumerate(env.body):
        if existing is not None:
            index = position + 1
        elif isinstance(item, Comment):
            example = item.trivia.comment.lstrip("#").lstrip()
            if example.startswith((f"{key} =", f"{key}=")):
                index = position + 1
                break
    if index is None or index >= len(env.body):
        env.append(key, value)
    else:
        # tomlkit has no public way to add a key at a position.
        env._insert_at(index, key, value)


@dataclass(frozen=True)
class SaveConfig:
    """The form's decision to write its values.

    Attributes:
        edit: The text to write, and what the file held when it was made.
    """

    edit: ConfigEdit


@dataclass(frozen=True)
class OpenInEditor:
    """The form's decision to open the file in ``$EDITOR`` instead."""


type ConfigDecision = SaveConfig | OpenInEditor
"""What the configuration form leaves with, for the CLI to carry out."""
