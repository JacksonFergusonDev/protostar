"""Pre-commit merge spec, locations per hook runner, and pin policy."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import cast

from packaging.version import InvalidVersion, Version

from ..merge import ConflictReason, MergeConflict, MergeLocation, Value
from ..registry import ResolvedHookRevision
from ..sync_state import HookPinState, PinProvenance
from ..workflows import HookRunner
from ..yaml_ast import (
    WILDCARD,
    KeyedSequence,
    YamlDocumentSpec,
    YamlGuard,
    decode_yaml_baseline,
    validate_yaml_baseline,
)
from .locations import DocumentLocations

TARGET = ".pre-commit-config.yaml"
_YML = ".pre-commit-config.yml"
# pre-commit reads only the canonical name. It ignores a `.yml` copy, but a lone
# one means the user's hooks are not running, so Protostar reports it instead of
# creating a second configuration. prek reads prek.toml first, then either name.
LOCATIONS: Mapping[HookRunner, DocumentLocations] = MappingProxyType(
    {
        HookRunner.PRE_COMMIT: DocumentLocations(TARGET, competitors=(_YML,)),
        HookRunner.PREK: DocumentLocations(
            TARGET, aliases=(_YML,), competitors=("prek.toml",)
        ),
    }
)
SPEC = YamlDocumentSpec(
    "pre-commit",
    keyed=(
        KeyedSequence(("repos",), "repo", string_fields=("rev",)),
        KeyedSequence(("repos", WILDCARD, "hooks"), "id"),
    ),
)


_DOCUMENT_FILES = re.compile(r"<% FILES (\S+) %>")


def document_files(target: str) -> str:
    """Returns a hook ``files`` placeholder for a managed document.

    The placeholder is replaced with the path of the file that holds the document
    in this run, so a hook that validates a configuration names exactly that file.

    Args:
        target: The document's canonical workspace path.

    Returns:
        The placeholder to use as the hook's ``files`` value.
    """
    return f"<% FILES {target} %>"


def resolve_document_files(
    content: str,
    locate: Callable[[str], str | None],
    locations: Callable[[str], DocumentLocations],
) -> str:
    """Replaces each document files placeholder with an anchored path regex.

    Args:
        content: Generated configuration text.
        locate: Returns the path holding a document in this run, or ``None`` when
            the document is held because Protostar cannot tell which file it is.
        locations: Returns the locations a document's tool reads it from.

    Returns:
        The configuration with every placeholder resolved. A held document
        matches each path the tool may read it from.
    """

    def files(match: re.Match[str]) -> str:
        target = match.group(1)
        path = locate(target)
        if path is not None:
            return f"^{re.escape(path)}$"
        paths = locations(target).editable
        return "^(" + "|".join(re.escape(p) for p in paths) + ")$"

    return _DOCUMENT_FILES.sub(files, content)


def _repos(document: Value) -> list[dict[str, Value]]:
    return cast(
        list[dict[str, Value]],
        document.get("repos", []) if isinstance(document, dict) else [],
    )


@dataclass(frozen=True)
class HookPinPlan:
    """Resolved desired configuration plus the pin guard for one reconciliation.

    Attributes:
        desired: Desired configuration text with every resolved pin substituted.
        guard: Holds for automatic pins that would move to an unsafe revision.
        automatic: Resolved pins by repository, for pins the configuration uses.
        previous: Pin provenance recorded before this run, for every file.
        path: Workspace path of the configuration this run reconciles.
        sources: Paths whose pins belong to this configuration: ``path`` and the
            path it was followed from after a rename.
    """

    desired: str
    guard: YamlGuard
    automatic: dict[str, ResolvedHookRevision]
    previous: tuple[HookPinState, ...]
    path: str
    sources: frozenset[str]

    def advance(self, content: str, baseline: Value) -> tuple[HookPinState, ...]:
        """Advances pin provenance only for accepted, owned, unguarded revisions.

        Pins recorded for the path the configuration was followed from move to
        ``path`` with it.

        Args:
            content: Configuration text the reconciliation under ``guard`` emitted.
            baseline: Owned baseline that reconciliation recorded.

        Returns:
            The complete pin state, with this file's pins updated.
        """
        guarded = {held[1] for held in self.guard.holds}
        pins = {
            pin.repo: replace(pin, path=self.path)
            for pin in self.previous
            if pin.path in self.sources
        }
        local = decode_yaml_baseline(content) if content else {}
        desired = decode_yaml_baseline(self.desired)
        for repo in _repos(baseline):
            name = cast(str, repo["repo"])
            revision = repo.get("rev")
            matching = [r for r in _repos(local) if r.get("repo") == name]
            intended = [r for r in _repos(desired) if r.get("repo") == name]
            if (
                name in guarded
                or not isinstance(revision, str)
                or len(matching) != 1
                or len(intended) != 1
            ):
                continue
            if matching[0].get("rev") != revision or intended[0].get("rev") != revision:
                continue
            pin = self.automatic.get(name)
            # Identical fallback responses must not relabel an established registry pin.
            if name in pins and pins[name].revision == revision:
                continue
            pins[name] = HookPinState(
                self.path,
                name,
                revision,
                pin.provenance if pin else PinProvenance.TEMPLATE,
            )
        return (
            *(pin for pin in self.previous if pin.path not in self.sources),
            *pins.values(),
        )


def plan_hook_pins(
    desired: str,
    revisions: tuple[ResolvedHookRevision, ...],
    previous: tuple[HookPinState, ...],
    path: str = TARGET,
    owner: str | None = None,
) -> HookPinPlan:
    """Substitutes resolved pins and holds any automatic pin that is unsafe to apply.

    An automatic pin is unsafe when it came from the offline fallback or moves an
    established pin backwards; holding keeps both local content and the prior
    owned baseline.

    Args:
        desired: Generated configuration text with pin placeholders.
        revisions: Pins resolved from the registry or its fallback.
        previous: Pin provenance recorded before this run.
        path: Workspace path of the configuration being reconciled.
        owner: Path of the ownership record the configuration was followed from,
            whose pins move to ``path``.

    Returns:
        The resolved configuration, its guard, and what ``advance`` needs.
    """
    automatic = {
        pin.hook.value: pin for pin in revisions if pin.hook.placeholder in desired
    }
    for resolved in revisions:
        desired = desired.replace(resolved.hook.placeholder, resolved.revision)
    incoming = decode_yaml_baseline(desired)
    validate_yaml_baseline(SPEC, incoming)
    sources = frozenset({path, owner or path})
    old_pins = {pin.repo: pin for pin in previous if pin.path in sources}
    holds: list[tuple[str, ...]] = []
    conflicts: list[MergeConflict] = []
    for repo in _repos(incoming):
        name = cast(str, repo.get("repo"))
        pin = automatic.get(name)
        old = old_pins.get(name)
        if pin is None or old is None or pin.revision == old.revision:
            continue
        unsafe = pin.provenance is PinProvenance.FALLBACK
        try:
            unsafe |= Version(pin.revision) < Version(old.revision)
        except InvalidVersion:
            unsafe = True
        if unsafe:
            holds.append(("repos", name, "rev"))
            conflicts.append(
                MergeConflict(
                    MergeLocation(path, ("repos", name, "rev"), name),
                    ConflictReason.UNSAFE_PIN,
                )
            )
    return HookPinPlan(
        desired,
        YamlGuard(tuple(holds), tuple(conflicts)),
        automatic,
        previous,
        path,
        sources,
    )
