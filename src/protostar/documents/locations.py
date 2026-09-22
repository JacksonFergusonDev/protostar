"""Where a tool reads each managed document, and which file Protostar edits.

Whether two paths hold the same configuration is a fact about the tool that reads
them, not about the file format: Read the Docs reads `.readthedocs.yml` as its
configuration, pre-commit ignores `.pre-commit-config.yml`, and GitHub Actions
runs `ci.yml` and `ci.yaml` as two workflows. Each document therefore declares
its tool's locations, and one resolver decides which file a run edits.
"""

from collections.abc import Callable, Collection
from dataclasses import dataclass

from ..merge import ConflictReason, MergeConflict, MergeLocation


@dataclass(frozen=True)
class DocumentLocations:
    """The workspace paths one tool reads a managed document from.

    Attributes:
        target: Canonical path, where Protostar creates the document.
        aliases: Other paths the tool reads as this document, in a form Protostar
            edits. Protostar edits the document wherever it is: an existing alias
            is adopted, and a renamed document is followed with its ownership.
        competitors: Paths of configurations the tool may read instead, in a form
            Protostar does not edit. Protostar never creates the document while
            one of them exists.
        exclusive: Whether the tool reads a single configuration among all these
            paths, so a second one present is ignored or shadows the first.
    """

    target: str
    aliases: tuple[str, ...] = ()
    competitors: tuple[str, ...] = ()
    exclusive: bool = True

    @property
    def editable(self) -> tuple[str, ...]:
        """Returns the target and its aliases, in declaration order."""
        return (self.target, *self.aliases)

    @property
    def paths(self) -> tuple[str, ...]:
        """Returns every path the tool may read, editable ones first."""
        return (*self.editable, *self.competitors)


@dataclass(frozen=True)
class Resolution:
    """Which file one reconciliation edits, and what it reports about the others.

    Attributes:
        path: File to reconcile, or ``None`` when the document is held.
        owner: Path of the ownership record that supplies the baseline, or
            ``None`` when nothing is owned. It differs from ``path`` when a renamed
            document is followed, and the record then moves to ``path``.
        conflicts: Competing or ambiguous configurations.
    """

    path: str | None
    owner: str | None
    conflicts: tuple[MergeConflict, ...] = ()


def resolve_location(
    locations: DocumentLocations,
    owned: Collection[str],
    exists: Callable[[str], bool],
) -> Resolution:
    """Decides which file holds a document in this run.

    - An owned file that exists is edited in place.
    - Otherwise a single existing editable file is adopted, or followed when an
      ownership record names another path (a rename, in either direction).
    - An owned file that no longer exists, with nothing to follow, keeps its
      record, so the deletion is kept by the merge.
    - For a tool that reads one configuration, every other configuration present
      next to the edited file is reported as ``duplicate-identity``. When several
      are present and none is owned, or only competitors are, nothing is edited:
      Protostar cannot tell which one the tool reads, or cannot edit it.
    - A tool that reads every file (``exclusive`` unset) never conflicts: the
      owned file, else the target, else the single alias is edited.

    Args:
        locations: The document's locations.
        owned: Paths that have an ownership record.
        exists: Reports whether a workspace path exists.

    Returns:
        The file to reconcile, the record it continues, and conflicts to report.
    """
    present = [path for path in locations.editable if exists(path)]
    competing = [path for path in locations.competitors if exists(path)]
    records = [path for path in locations.editable if path in owned]
    owner = next((path for path in records if exists(path)), None) or next(
        iter(records), None
    )

    if owner is not None and exists(owner):
        path = owner
    elif not locations.exclusive:
        if locations.target in present:
            path = locations.target
        else:
            path = present[0] if present else owner or locations.target
    elif not present and not competing:
        path = owner or locations.target
    elif len(present) == 1 and not competing:
        path = present[0]
    elif not present:
        return Resolution(
            None,
            owner,
            (MergeConflict(MergeLocation(locations.target), ConflictReason.UNOWNED),),
        )
    else:
        return Resolution(None, owner, _duplicates([*present, *competing]))

    others = [p for p in (*present, *competing) if p != path]
    return Resolution(path, owner, _duplicates(others) if locations.exclusive else ())


def _duplicates(paths: list[str]) -> tuple[MergeConflict, ...]:
    return tuple(
        MergeConflict(MergeLocation(path), ConflictReason.DUPLICATE_IDENTITY)
        for path in paths
    )
