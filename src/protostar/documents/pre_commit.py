"""Pre-commit merge spec and pin policy over already resolved registry inputs."""

from dataclasses import dataclass
from typing import cast

from packaging.version import InvalidVersion, Version

from ..merge import ConflictReason, MergeConflict, MergeLocation, Value
from ..registry import ResolvedHookRevision
from ..sync_state import HookPinState, PinProvenance
from ..yaml_ast import (
    WILDCARD,
    KeyedSequence,
    YamlDocumentSpec,
    YamlGuard,
    decode_yaml_baseline,
    validate_yaml_baseline,
)

TARGET = ".pre-commit-config.yaml"
SPEC = YamlDocumentSpec(
    "pre-commit",
    keyed=(
        KeyedSequence(("repos",), "repo", string_fields=("rev",)),
        KeyedSequence(("repos", WILDCARD, "hooks"), "id"),
    ),
)


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
    """

    desired: str
    guard: YamlGuard
    automatic: dict[str, ResolvedHookRevision]
    previous: tuple[HookPinState, ...]

    def advance(self, content: str, baseline: Value) -> tuple[HookPinState, ...]:
        """Advances pin provenance only for accepted, owned, unguarded revisions.

        Args:
            content: Configuration text the reconciliation under ``guard`` emitted.
            baseline: Owned baseline that reconciliation recorded.

        Returns:
            The complete pin state, with this file's pins updated.
        """
        guarded = {held[1] for held in self.guard.holds}
        pins = {pin.repo: pin for pin in self.previous if pin.path == TARGET}
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
                TARGET,
                name,
                revision,
                pin.provenance if pin else PinProvenance.TEMPLATE,
            )
        return (
            *(pin for pin in self.previous if pin.path != TARGET),
            *pins.values(),
        )


def plan_hook_pins(
    desired: str,
    revisions: tuple[ResolvedHookRevision, ...],
    previous: tuple[HookPinState, ...],
) -> HookPinPlan:
    """Substitutes resolved pins and holds any automatic pin that is unsafe to apply.

    An automatic pin is unsafe when it came from the offline fallback or moves an
    established pin backwards; holding keeps both local content and the prior
    owned baseline.

    Args:
        desired: Generated configuration text with pin placeholders.
        revisions: Pins resolved from the registry or its fallback.
        previous: Pin provenance recorded before this run.

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
    old_pins = {pin.repo: pin for pin in previous if pin.path == TARGET}
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
                    MergeLocation(TARGET, ("repos", name, "rev"), name),
                    ConflictReason.UNSAFE_PIN,
                )
            )
    return HookPinPlan(
        desired, YamlGuard(tuple(holds), tuple(conflicts)), automatic, previous
    )
