"""GitHub Actions workflow merge spec and guards for foreign jobs and action refs."""

from typing import cast

from ..merge import (
    MISSING,
    ConflictReason,
    MergeConflict,
    MergeLocation,
    MergePolicy,
    Value,
)
from ..yaml_ast import WILDCARD, KeyedSequence, YamlDocumentSpec, YamlGuard, keyed_view
from .locations import DocumentLocations

CI_TARGET = ".github/workflows/ci.yml"
RELEASE_TARGET = ".github/workflows/release.yml"
# GitHub runs every `.yml` and `.yaml` file as its own workflow, so the other
# extension is followed and adopted but never reported as a competing copy.
CI_LOCATIONS = DocumentLocations(
    CI_TARGET, aliases=(".github/workflows/ci.yaml",), exclusive=False
)
RELEASE_LOCATIONS = DocumentLocations(
    RELEASE_TARGET, aliases=(".github/workflows/release.yaml",), exclusive=False
)
# One GitHub Actions schema for every generated workflow: a workflow is one
# generator's complete output, and steps are matched by the name Protostar wrote.
SPEC = YamlDocumentSpec(
    "GitHub Actions workflow",
    keyed=(KeyedSequence(("jobs", WILDCARD, "steps"), "name"),),
    policy=MergePolicy(complete=True),
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


def guard_workflow(target: str, desired: Value, local: Value, base: Value) -> YamlGuard:
    """Holds foreign jobs and user-owned action refs before a workflow merge.

    - A job that exists locally but that Protostar does not own is left whole and
      reported as ``unowned``; Protostar never grafts its steps into it.
    - When an owned step's local ``uses`` names the same action Protostar last
      wrote but a different ref (a Renovate SHA pin or a manual bump), the ref
      belongs to the user: it is kept without a conflict.

    Args:
        target: Workspace-relative workflow path.
        desired: Decoded generated workflow.
        local: Decoded workspace workflow, empty when the file is absent.
        base: Previously owned baseline, or ``MISSING``.

    Returns:
        The holds and ``unowned`` conflicts for this workflow.
    """
    local = keyed_view(SPEC, local)
    wanted = keyed_view(SPEC, desired, strict=True)
    owned = keyed_view(SPEC, base) if base is not MISSING else {}

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

    return YamlGuard(tuple(holds), tuple(conflicts))
