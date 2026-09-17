"""Pre-commit pin policy; reconciliation receives already resolved registry inputs."""

from dataclasses import replace
from typing import cast

from packaging.version import InvalidVersion, Version

from .merge import MISSING, ConflictReason, MergeConflict, MergeLocation, Value
from .registry import ResolvedHookRevision
from .sync_state import FileState, HookPinState, PinProvenance
from .yaml_ast import (
    YamlReconciliation,
    decode_yaml_baseline,
    encode_yaml_baseline,
    reconcile_pre_commit,
    validate_pre_commit_baseline,
)

TARGET = ".pre-commit-config.yaml"


def reconcile_hook_config(
    original: str,
    desired: str,
    record: FileState | None,
    revisions: tuple[ResolvedHookRevision, ...],
    previous_pins: tuple[HookPinState, ...],
    *,
    missing_file: bool = False,
    overwrite: bool = False,
) -> tuple[YamlReconciliation, tuple[HookPinState, ...]]:
    """Guards automatic pins and advances provenance only for accepted owned revisions."""
    automatic = {
        pin.hook.value: pin for pin in revisions if pin.hook.placeholder in desired
    }
    for resolved in revisions:
        desired = desired.replace(resolved.hook.placeholder, resolved.revision)
    base = (
        decode_yaml_baseline(record.baseline)
        if record and record.baseline is not None
        else MISSING
    )
    incoming = decode_yaml_baseline(desired)
    validate_pre_commit_baseline(incoming)
    old_pins = {pin.repo: pin for pin in previous_pins if pin.path == TARGET}
    conflicts: list[MergeConflict] = []
    guarded: set[str] = set()
    for repo in cast(list[dict[str, Value]], incoming.get("repos", [])):
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
            # Omission preserves both local content and the prior owned baseline.
            repo.pop("rev", None)
            guarded.add(name)
            conflicts.append(
                MergeConflict(
                    MergeLocation(TARGET, ("repos", name, "rev"), name),
                    ConflictReason.UNSAFE_PIN,
                )
            )
    result = reconcile_pre_commit(
        original,
        encode_yaml_baseline(incoming) if guarded else desired,
        base,
        MergeLocation(TARGET),
        missing_file=missing_file,
        overwrite=overwrite,
    )
    owned = result.baseline if isinstance(result.baseline, dict) else {}
    local = decode_yaml_baseline(result.content) if result.content else {}
    local_repos = cast(list[dict[str, Value]], local.get("repos", []))
    for repo in cast(list[dict[str, Value]], owned.get("repos", [])):
        name = cast(str, repo["repo"])
        revision = repo.get("rev")
        matching = [r for r in local_repos if r.get("repo") == name]
        desired_repos = cast(list[dict[str, Value]], incoming.get("repos", []))
        intended = [r for r in desired_repos if r.get("repo") == name]
        if (
            name in guarded
            or not isinstance(revision, str)
            or len(matching) != 1
            or len(intended) != 1
        ):
            continue
        if matching[0].get("rev") != revision or intended[0].get("rev") != revision:
            continue
        pin = automatic.get(name)
        # Identical fallback responses must not relabel an established registry pin.
        if name in old_pins and old_pins[name].revision == revision:
            continue
        old_pins[name] = HookPinState(
            TARGET, name, revision, pin.provenance if pin else PinProvenance.TEMPLATE
        )
    return replace(result, conflicts=(*conflicts, *result.conflicts)), (
        *(pin for pin in previous_pins if pin.path != TARGET),
        *old_pins.values(),
    )
