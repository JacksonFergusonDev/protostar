"""GitHub Actions workflow policy; reconciliation runs through the YAML spec adapter."""

from typing import cast

from .merge import MISSING, ConflictReason, MergeConflict, MergeLocation, Value
from .sync_state import FileState
from .yaml_ast import (
    WORKFLOW_SPEC,
    YamlReconciliation,
    decode_yaml_baseline,
    keyed_view,
    reconcile_yaml,
    validate_yaml_baseline,
)

_LOCAL_ACTION_PREFIXES = ("./", "docker://")


def _action_and_ref(uses: Value) -> tuple[str, str] | None:
    """Splits a ``uses`` reference into its action and ref, when it has a ref."""
    if not isinstance(uses, str) or uses.startswith(_LOCAL_ACTION_PREFIXES):
        return None
    action, separator, ref = uses.partition("@")
    return (action, ref) if separator and action and ref else None


def _mapping(value: Value, key: str) -> dict[str, Value]:
    child = value.get(key) if isinstance(value, dict) else None
    return child if isinstance(child, dict) else {}


def reconcile_workflow(
    target: str,
    original: str,
    desired: str,
    record: FileState | None,
    *,
    missing_file: bool = False,
    overwrite: bool = False,
) -> YamlReconciliation:
    """Reconciles a generated workflow, guarding foreign jobs and local action refs.

    Two guards run before the merge, both as holds:

    - A job that exists locally but that Protostar does not own is left whole and
      reported as ``unowned``; Protostar never grafts its steps into it.
    - When an owned step's local ``uses`` names the same action Protostar last
      wrote but a different ref (a Renovate SHA pin or a manual bump), the ref
      belongs to the user: it is kept without a conflict.

    Args:
        target: Workspace-relative workflow path.
        original: Current workspace text; ignored when ``missing_file`` is set.
        desired: Generated workflow text.
        record: Previously committed ownership for this path, if any.
        missing_file: Whether the workspace file is absent.
        overwrite: Whether explicit overwrite owns declared values.

    Returns:
        Emitted text, the composite owned baseline, and structured conflicts.
    """
    base: Value = (
        decode_yaml_baseline(record.baseline)
        if record and record.baseline is not None
        else MISSING
    )
    validate_yaml_baseline(WORKFLOW_SPEC, decode_yaml_baseline(desired))
    local = keyed_view(
        WORKFLOW_SPEC, {} if missing_file else decode_yaml_baseline(original)
    )
    wanted = keyed_view(WORKFLOW_SPEC, decode_yaml_baseline(desired))
    owned = keyed_view(WORKFLOW_SPEC, base) if base is not MISSING else {}

    holds: list[tuple[str, ...]] = []
    conflicts: list[MergeConflict] = []
    owned_jobs = _mapping(owned, "jobs")
    local_jobs = _mapping(local, "jobs")
    for job, desired_job in _mapping(wanted, "jobs").items():
        if job not in local_jobs:
            continue
        if job not in owned_jobs:
            holds.append(("jobs", job))
            conflicts.append(
                MergeConflict(
                    MergeLocation(target, ("jobs", job)), ConflictReason.UNOWNED
                )
            )
            continue
        owned_steps = _mapping(owned_jobs[job], "steps")
        local_steps = _mapping(local_jobs[job], "steps")
        for name, desired_step in _mapping(desired_job, "steps").items():
            step_path = ("jobs", job, "steps", name, "uses")
            previous = _action_and_ref(_mapping(owned_steps, name).get("uses"))
            current = _action_and_ref(_mapping(local_steps, name).get("uses"))
            wanted_ref = _action_and_ref(
                cast(dict[str, Value], desired_step).get("uses")
            )
            if (
                previous is not None
                and current is not None
                and wanted_ref is not None
                and previous[0] == current[0] == wanted_ref[0]
                and current[1] != previous[1]
                and current[1] != wanted_ref[1]
            ):
                holds.append(step_path)

    result = reconcile_yaml(
        WORKFLOW_SPEC,
        original,
        desired,
        base,
        MergeLocation(target),
        holds=tuple(holds),
        missing_file=missing_file,
        overwrite=overwrite,
    )
    return YamlReconciliation(
        result.content, result.baseline, (*conflicts, *result.conflicts)
    )
