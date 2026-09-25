"""Template-declared migrations: the changes three-way merging cannot express.

A template's ownership model already carries most updates across versions. A
migration covers the rest: a file the template moved, a file it no longer
ships, and a variable it renamed. Migrations are declarative, so a review
shows each one before anything changes and a failed run rolls it back.
Each is guarded by ownership, so applying one twice changes nothing.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from packaging.version import InvalidVersion, Version

from .errors import ConfigurationError, TemplateResolutionError
from .interpolation import BUILT_IN_VARIABLES, VARIABLE_NAME

__all__ = [
    "Migration",
    "MigrationOutcome",
    "MigrationStep",
    "Rename",
    "parse_migrations",
    "rename_variables",
    "select_migrations",
]

_HINT = (
    "Declare each as [[migrations]] with a PEP 440 version and any of rename, "
    'remove, and rename_variables, for example rename = [{ from = "a.py", '
    'to = "b.py" }].'
)


@dataclass(frozen=True)
class Rename:
    """One path or variable name, and what it is called from now on."""

    source: str
    target: str

    def to_dict(self) -> dict[str, str]:
        """Serializes the rename as the template declares it."""
        return {"from": self.source, "to": self.target}


@dataclass(frozen=True)
class Migration:
    """The changes a project makes as it moves past one template version.

    Attributes:
        version: The template version that introduced the changes. A project
            applies them when it moves from before this version to it or later.
        rename: Owned seed files that moved, local edits included.
        remove: Owned seed files the template no longer ships.
        rename_variables: Template variables whose recorded values move to a
            new name.
    """

    version: str
    rename: tuple[Rename, ...] = ()
    remove: tuple[str, ...] = ()
    rename_variables: tuple[Rename, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serializes the migration deterministically."""
        return {
            "version": self.version,
            "rename": [item.to_dict() for item in self.rename],
            "remove": list(self.remove),
            "rename_variables": [item.to_dict() for item in self.rename_variables],
        }


class MigrationOutcome(StrEnum):
    """What one migrated file did in this project."""

    MOVED = "moved"
    """The file, local edits included, and its ownership moved to the new path."""
    TARGET_EXISTS = "target-exists"
    """The new path already exists, so the file stayed where it is, as the user's."""
    REMOVED = "removed"
    """The file was unedited, so it was deleted."""
    RETIRED = "retired"
    """The file has local edits, so it stays a decision until settled."""
    FORGOTTEN = "forgotten"
    """The file was already deleted, so only its ownership was dropped."""
    NOT_OWNED = "not-owned"
    """Protostar doesn't own the file as a seed, so the migration left it alone."""


@dataclass(frozen=True)
class MigrationStep:
    """One file a migration renamed or removed, and what happened to it.

    Attributes:
        version: The migration's version.
        path: The file, as the migration names it for this project.
        target: Where a rename moves it, or None for a removal.
        outcome: What happened.
    """

    version: str
    path: str
    target: str | None
    outcome: MigrationOutcome

    def to_dict(self) -> dict[str, Any]:
        """Serializes the step."""
        return {
            "version": self.version,
            "path": self.path,
            "target": self.target,
            "outcome": self.outcome.value,
        }


def _version(value: str | None) -> Version | None:
    try:
        return Version(value) if value else None
    except InvalidVersion:
        return None


def _path(value: object, target: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).drive
        or ".." in PurePosixPath(value).parts
        or "\\" in value
        or "\x00" in value
    ):
        raise TemplateResolutionError(
            target,
            f"Migration path {value!r} is not a relative path inside the project.",
            hint=_HINT,
        )
    return value


def _renames(value: object, target: str, *, variables: bool) -> tuple[Rename, ...]:
    if not isinstance(value, list):
        raise TemplateResolutionError(
            target, "A migration's renames must be an array.", hint=_HINT
        )
    renames = []
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != {"from", "to"}
            or item["from"] == item["to"]
        ):
            raise TemplateResolutionError(
                target,
                "Each rename needs a different 'from' and 'to'.",
                hint=_HINT,
            )
        if variables:
            for name in (item["from"], item["to"]):
                if (
                    not isinstance(name, str)
                    or not VARIABLE_NAME.fullmatch(name)
                    or name in BUILT_IN_VARIABLES
                ):
                    raise TemplateResolutionError(
                        target,
                        f"Migration variable {name!r} is not a custom variable name.",
                        hint="Built-in variables can't be renamed.",
                    )
            renames.append(Rename(item["from"], item["to"]))
        else:
            renames.append(
                Rename(_path(item["from"], target), _path(item["to"], target))
            )
    return tuple(renames)


def parse_migrations(data: Mapping[str, object], target: str) -> tuple[Migration, ...]:
    """Reads a template's ``[[migrations]]``, oldest first.

    Args:
        data: The template's root table.
        target: The template, for errors.

    Raises:
        TemplateResolutionError: If a migration is malformed, the template
            declares no PEP 440 ``version``, or a migration is newer than it.
    """
    raw = data.get("migrations", [])
    if not isinstance(raw, list):
        raise TemplateResolutionError(
            target, "migrations must be an array of tables.", hint=_HINT
        )
    if not raw:
        return ()
    declared = data.get("version")
    current = _version(declared) if isinstance(declared, str) else None
    if current is None:
        raise TemplateResolutionError(
            target,
            "A template with migrations must declare its version.",
            hint='Declare a PEP 440 version at the root, such as version = "1.4.0".',
        )
    migrations: list[Migration] = []
    for entry in raw:
        if (
            not isinstance(entry, dict)
            or "version" not in entry
            or set(entry) - {"version", "rename", "remove", "rename_variables"}
        ):
            raise TemplateResolutionError(
                target, "A migration has missing or unknown fields.", hint=_HINT
            )
        version = (
            _version(entry["version"]) if isinstance(entry["version"], str) else None
        )
        if version is None:
            raise TemplateResolutionError(
                target,
                f"Migration version {entry['version']!r} is not a PEP 440 version.",
                hint=_HINT,
            )
        if version > current:
            raise TemplateResolutionError(
                target,
                f"Migration {entry['version']} is newer than the template's "
                f"version {declared}.",
                hint="A migration belongs to the version that introduced it.",
            )
        remove = entry.get("remove", [])
        if not isinstance(remove, list):
            raise TemplateResolutionError(
                target, "A migration's remove must be an array of paths.", hint=_HINT
            )
        migrations.append(
            Migration(
                entry["version"],
                _renames(entry.get("rename", []), target, variables=False),
                tuple(_path(path, target) for path in remove),
                _renames(entry.get("rename_variables", []), target, variables=True),
            )
        )
    versions = [Version(migration.version) for migration in migrations]
    if len(set(versions)) != len(versions):
        raise TemplateResolutionError(
            target,
            "Two migrations declare the same version.",
            hint="Combine the changes of one version into one migration.",
        )
    return tuple(sorted(migrations, key=lambda item: Version(item.version)))


def select_migrations(
    migrations: Sequence[Migration],
    applied: str | None,
    current: str | None,
    migrated: str | None = None,
) -> tuple[Migration, ...]:
    """Returns the migrations a project runs moving between two versions.

    A project whose applied version is unknown runs every migration up to
    ``current``: each is guarded by ownership, so one that already happened
    changes nothing. An older template can't know the migrations a newer one
    made, so the project's newest applied migration is the floor it can
    never move back below.

    Args:
        migrations: The new template's migrations, oldest first.
        applied: The template version the project last applied, if known.
        current: The template version being applied.
        migrated: The newest migration the project has applied, if any.

    Raises:
        ConfigurationError: If ``current`` comes before ``migrated``, or can't
            be ordered against it.
    """
    new = _version(current)
    floor = _version(migrated)
    if floor is not None and (new is None or new < floor):
        raise ConfigurationError(
            f"Moving the template to {current or 'an unversioned revision'} "
            f"would undo its {migrated} migration.",
            hint=f"Migrations only run forward. Stay on {migrated} or later, "
            "or undo its changes by hand and remove 'migrated' from protostar.lock.",
        )
    if not migrations or new is None:
        return ()
    old = _version(applied)
    if old is not None and new <= old:
        return ()
    return tuple(
        migration
        for migration in migrations
        if (old is None or Version(migration.version) > old)
        and Version(migration.version) <= new
    )


def rename_variables(
    values: Mapping[str, str], migrations: Sequence[Migration]
) -> dict[str, str]:
    """Moves recorded variable values to the names migrations gave them.

    A value already recorded under the new name wins, so this is idempotent.
    """
    renamed = dict(values)
    for migration in migrations:
        for rename in migration.rename_variables:
            if rename.source in renamed and rename.target not in renamed:
                renamed[rename.target] = renamed.pop(rename.source)
    return renamed
