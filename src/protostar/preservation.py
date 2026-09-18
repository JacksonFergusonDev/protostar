"""Informational inspection of retained ownership deviations, never merge decisions."""

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .appends import get_comment_markers
from .dependencies import (
    normalized_requirement,
    requirement_entries,
    requirement_identity,
)
from .jsonc_ast import decode_jsonc
from .merge import MISSING, MergeConflict, MergeLocation, Value, semantic_equal
from .review_workspace import ReviewWorkspace
from .sync_state import FilePolicy, SyncState, decode_toml_baseline
from .yaml_ast import decode_yaml_baseline


@dataclass(frozen=True)
class PreservedDeviation:
    """A local edit/deletion retained without pending desired work at this location."""

    location: MergeLocation
    deleted: bool


def preserved_deviations(
    workspace: ReviewWorkspace,
    before: SyncState,
    after: SyncState,
    conflicts: tuple[MergeConflict, ...],
) -> tuple[PreservedDeviation, ...]:
    """Describes local drift beneath unchanged accepted baselines.

    Only ownership already held before preparation is inspected. This function
    cannot accept edits, adopt foreign content, or change candidate ownership.
    """
    preserved: list[PreservedDeviation] = []

    def blocked(location: MergeLocation) -> bool:
        return any(
            conflict.location.file == location.file
            and (
                not conflict.location.keys
                or conflict.location.keys[: len(location.keys)] == location.keys
                or location.keys[: len(conflict.location.keys)]
                == conflict.location.keys
            )
            and (
                not conflict.location.identity
                or not location.identity
                or conflict.location.identity == location.identity
            )
            for conflict in conflicts
        )

    def inspect(
        location: MergeLocation, old: Value, candidate: Value, local: Value
    ) -> None:
        if isinstance(old, dict) and isinstance(candidate, dict):
            for key, value in old.items():
                inspect(
                    MergeLocation(location.file, (*location.keys, key)),
                    value,
                    candidate.get(key, MISSING),
                    local.get(key, MISSING) if isinstance(local, dict) else MISSING,
                )
        elif (
            location.file == ".pre-commit-config.yaml"
            and location.keys
            and location.keys[-1] in {"repos", "hooks"}
            and isinstance(old, list)
            and isinstance(candidate, list)
        ):
            identity = "repo" if location.keys[-1] == "repos" else "id"
            for record in old:
                if not isinstance(record, dict):
                    continue
                record_identity = record.get(identity)
                if not isinstance(record_identity, str):
                    continue
                candidate_records = [
                    item
                    for item in candidate
                    if isinstance(item, dict) and item.get(identity) == record_identity
                ]
                local_records = (
                    [
                        item
                        for item in local
                        if isinstance(item, dict)
                        and item.get(identity) == record_identity
                    ]
                    if isinstance(local, list)
                    else []
                )
                if len(candidate_records) == 1 and len(local_records) <= 1:
                    inspect(
                        MergeLocation(location.file, (*location.keys, record_identity)),
                        record,
                        candidate_records[0],
                        local_records[0] if local_records else MISSING,
                    )
        elif (
            semantic_equal(old, candidate)
            and not semantic_equal(old, local)
            and not blocked(location)
        ):
            preserved.append(PreservedDeviation(location, local is MISSING))

    for record in before.files:
        candidate = next(
            (item for item in after.files if item.path == record.path), None
        )
        if candidate is None:
            continue
        target = Path(record.path)
        exists = workspace.exists(target)
        location = MergeLocation(record.path)
        if (
            record.policy in (FilePolicy.TOML, FilePolicy.YAML, FilePolicy.JSONC)
            and record.baseline
            and candidate.baseline
        ):
            decode = {
                FilePolicy.TOML: decode_toml_baseline,
                FilePolicy.YAML: decode_yaml_baseline,
                FilePolicy.JSONC: decode_jsonc,
            }[record.policy]
            local = decode(workspace.read_text(target)) if exists else MISSING
            inspect(
                location, decode(record.baseline), decode(candidate.baseline), local
            )
        elif record.digest and record.digest == candidate.digest:
            content = workspace.read_bytes(target) if exists else None
            if (
                content is None or hashlib.sha256(content).hexdigest() != record.digest
            ) and not blocked(location):
                preserved.append(PreservedDeviation(location, not exists))
        elif record.policy is FilePolicy.SEED and not exists and not blocked(location):
            preserved.append(PreservedDeviation(location, True))
        if record.regions:
            region_content = workspace.read_text(target) if exists else ""
            start, end = get_comment_markers(target)
            for region in record.regions:
                candidate_region = next(
                    (item for item in candidate.regions if item.id == region.id), None
                )
                region_location = MergeLocation(record.path, identity=region.id)
                if candidate_region != region or blocked(region_location):
                    continue
                begin = f"{start} --- Protostar Region: {region.id} --- {end}".strip()
                finish = (
                    f"{start} --- End Protostar Region: {region.id} --- {end}".strip()
                )
                offset = region_content.find(begin)
                stop = region_content.find(finish, offset) if offset >= 0 else -1
                local_digest = (
                    hashlib.sha256(
                        region_content[offset : stop + len(finish)].encode()
                    ).hexdigest()
                    if stop >= 0
                    else None
                )
                if local_digest != region.digest:
                    preserved.append(PreservedDeviation(region_location, stop < 0))
    target = Path("pyproject.toml")
    data = (
        tomllib.loads(workspace.read_text(target)) if workspace.exists(target) else {}
    )
    for dependency in before.dependencies:
        candidate_dependency = next(
            (
                item
                for item in after.dependencies
                if item.identity == dependency.identity
            ),
            None,
        )
        location = MergeLocation(
            dependency.path,
            ("dependencies", dependency.group.value),
            ":".join((dependency.name, dependency.marker)),
        )
        if candidate_dependency != dependency or blocked(location):
            continue
        entries = [
            entry
            for entry in requirement_entries(data, dependency.group)
            if requirement_identity(entry) == (dependency.name, dependency.marker)
        ]
        if len(entries) != 1 or normalized_requirement(
            entries[0]
        ) != normalized_requirement(dependency.materialized):
            preserved.append(PreservedDeviation(location, not entries))
    return tuple(
        sorted(
            preserved,
            key=lambda item: (
                item.location.file,
                item.location.keys,
                item.location.identity or "",
            ),
        )
    )
