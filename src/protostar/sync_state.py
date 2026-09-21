"""Deterministic schema-v1 state codec; callers own reads and transactional writes."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath
from typing import cast
from urllib.parse import urlsplit

import tomlkit
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from tomlkit.exceptions import TOMLKitError

from .errors import ConfigurationError
from .intent import (
    DependencyGroup,
    TemplateOrigin,
    TemplateReference,
    validate_region_id,
)
from .jsonc_ast import decode_jsonc_baseline, encode_jsonc_baseline
from .merge import Value, validate_value
from .registry import PinProvenance as PinProvenance

SCHEMA_VERSION = 1


class FilePolicy(StrEnum):
    """Currently supported persisted ownership policies."""

    TOML = "structured-toml"
    YAML = "structured-yaml"
    JSONC = "structured-jsonc"
    CHECKSUM = "checksum"
    SEED = "seed-only"
    REGIONS = "regions"


def _invalid(detail: str) -> ConfigurationError:
    return ConfigurationError(
        f"Invalid Protostar state: {detail}",
        hint="Correct the state record before retrying; unsupported state cannot be migrated or adopted automatically.",
    )


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise _invalid(f"{label} must be a non-empty string.")
    return value


def _digest(value: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise _invalid("digests must be lowercase SHA-256 hex strings.")


def _tag(value: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{8}", value):
        raise _invalid("tags must be 8-character lowercase hex strings.")


def validate_state_path(path: str) -> None:
    """Requires a canonical relative POSIX workspace path inside the path jail."""
    _text(path, "path")
    target = PurePosixPath(path)
    if (
        target.is_absolute()
        or PureWindowsPath(path).drive
        or "\\" in path
        or "\x00" in path
        or ".." in target.parts
        or path != target.as_posix()
        or path == "."
        or any(part in (".protostar.lock.toml", "uv.lock") for part in target.parts)
    ):
        raise _invalid(f"unsafe or reserved workspace path '{path}'.")


@dataclass(frozen=True)
class RegionState:
    """Delimited tag, stable logical identity, and applied digest for an append region."""

    tag: str
    id: str
    digest: str

    def __post_init__(self) -> None:
        """Validates the persisted ownership contract at construction."""
        _tag(self.tag)
        validate_region_id(self.id)
        _digest(self.digest)


@dataclass(frozen=True)
class FileState:
    """Only owned contributions, never a snapshot of foreign workspace content."""

    path: str
    policy: FilePolicy
    baseline: str | None = None
    digest: str | None = None
    regions: tuple[RegionState, ...] = ()

    def __post_init__(self) -> None:
        """Validates the persisted ownership contract at construction."""
        validate_state_path(self.path)
        if not isinstance(self.policy, FilePolicy):
            raise _invalid("unknown file policy.")
        if self.policy in (FilePolicy.TOML, FilePolicy.YAML, FilePolicy.JSONC):
            if (
                type(self.baseline) is not str
                or self.digest is not None
                or self.regions
            ):
                raise _invalid(
                    "structured configuration requires only a baseline document string."
                )
            if self.policy is FilePolicy.TOML:
                from .documents import pyproject

                value = decode_toml_baseline(self.baseline)
                if self.path == pyproject.TARGET:
                    tool = value.get("tool", {})
                    if not isinstance(tool, dict) or "protostar" in tool:
                        raise _invalid("tool.protostar cannot be owned.")
            elif self.policy is FilePolicy.JSONC:
                decode_jsonc_baseline(self.baseline)
            else:
                from .documents import YAML_DOCUMENTS
                from .yaml_ast import decode_yaml_baseline, validate_yaml_baseline

                value = decode_yaml_baseline(self.baseline)
                if (spec := YAML_DOCUMENTS.get(self.path)) is not None:
                    validate_yaml_baseline(spec, value)
        elif self.policy is FilePolicy.CHECKSUM:
            if self.digest is None or self.baseline is not None:
                raise _invalid("checksum policy requires only a digest.")
            _digest(self.digest)
        elif self.policy is FilePolicy.SEED:
            if self.baseline is not None or self.digest is not None or self.regions:
                raise _invalid("seed-only policy records only the seeded path.")
        elif self.baseline is not None or self.digest is not None:
            raise _invalid("region policy records only region digests.")
        if len({region.id for region in self.regions}) != len(self.regions):
            raise _invalid("duplicate region identities.")
        if len({region.tag for region in self.regions}) != len(self.regions):
            raise _invalid("duplicate region tags.")


@dataclass(frozen=True)
class DependencyState:
    """Declared intent and resolver-materialized requirement for an owned identity."""

    path: str
    group: DependencyGroup
    name: str
    marker: str
    declared: str
    materialized: str

    def __post_init__(self) -> None:
        """Validates the persisted ownership contract at construction."""
        validate_state_path(self.path)
        if not isinstance(self.group, DependencyGroup):
            raise _invalid("unsupported dependency group.")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.name):
            raise _invalid("dependency name must be canonical.")
        if type(self.marker) is not str:
            raise _invalid("dependency marker must be a string.")
        _text(self.declared, "declared requirement")
        _text(self.materialized, "materialized requirement")
        for content in (self.declared, self.materialized):
            try:
                requirement = Requirement(content)
            except InvalidRequirement as e:
                raise _invalid("malformed dependency requirement.") from e
            marker = str(requirement.marker) if requirement.marker is not None else ""
            if (
                canonicalize_name(requirement.name) != self.name
                or marker != self.marker
            ):
                raise _invalid(
                    "dependency requirement does not match its stored name/marker identity."
                )

    @property
    def identity(self) -> tuple[str, str, str, str]:
        """Returns the path/group/name/marker identity, without ignoring markers."""
        return self.path, self.group.value, self.name, self.marker


@dataclass(frozen=True)
class HookPinState:
    """Repository revision and applied provenance; hook fields live in baselines."""

    path: str
    repo: str
    revision: str
    provenance: PinProvenance

    def __post_init__(self) -> None:
        """Validates the persisted ownership contract at construction."""
        validate_state_path(self.path)
        _text(self.repo, "hook repository")
        _text(self.revision, "hook revision")
        if not isinstance(self.provenance, PinProvenance):
            raise _invalid("unsupported hook pin provenance.")


@dataclass(frozen=True)
class SyncState:
    """Immutable committed or in-memory candidate state for one reconciliation run."""

    producer_version: str
    template: TemplateReference | None = None
    files: tuple[FileState, ...] = ()
    dependencies: tuple[DependencyState, ...] = ()
    hook_pins: tuple[HookPinState, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Validates the persisted ownership contract at construction."""
        if (
            type(self.schema_version) is not int
            or self.schema_version != SCHEMA_VERSION
        ):
            raise _invalid("unsupported schema version.")
        _text(self.producer_version, "producer version")
        if self.template is not None:
            ref = self.template
            if not isinstance(ref.origin, TemplateOrigin):
                raise _invalid("unsupported template origin.")
            _text(ref.locator, "template locator")
            _digest(ref.digest)
            for value in (ref.display_name, ref.version, ref.source_revision):
                if value is not None:
                    _text(value, "template provenance")
            if ref.origin is TemplateOrigin.BUILT_IN and (
                PurePosixPath(ref.locator).is_absolute()
                or PureWindowsPath(ref.locator).drive
            ):
                raise _invalid("built-in identity cannot be an installation path.")
            if ref.origin is TemplateOrigin.REMOTE:
                try:
                    locator = urlsplit(ref.locator)
                    if locator.username is not None or locator.password is not None:
                        raise _invalid("template locators cannot contain credentials.")
                except ValueError as e:
                    raise _invalid("malformed remote template locator.") from e
        identities = (
            [record.path for record in self.files],
            [record.identity for record in self.dependencies],
            [(record.path, record.repo) for record in self.hook_pins],
        )
        if any(len(set(entries)) != len(entries) for entries in identities):
            raise _invalid("duplicate file, dependency, or repository identity.")

    def with_file(self, record: FileState) -> SyncState:
        """Stages one successful/composite file record without changing committed state."""
        return replace(
            self,
            files=(*(item for item in self.files if item.path != record.path), record),
        )


def check_template_identity(
    state: SyncState, desired: TemplateReference | None
) -> None:
    """Rejects template switching and alias retargeting, allowing ordinary revisions."""
    if (state.template is None) != (desired is None) or (
        state.template is not None
        and desired is not None
        and state.template.identity != desired.identity
    ):
        raise ConfigurationError(
            "Selected template differs from the tracked project identity.",
            hint="Select the same template source explicitly; template switching and adoption are unsupported.",
        )


def decode_toml_baseline(content: str) -> dict[str, Value]:
    """Decodes owned TOML snapshots while retaining native date/time scalar types."""
    try:
        value = cast(dict[str, Value], tomlkit.parse(content).unwrap())
    except (TOMLKitError, ValueError, TypeError, RecursionError) as e:
        raise _invalid("malformed TOML baseline.") from e
    validate_value(value)
    return value


def encode_toml_baseline(value: dict[str, Value]) -> str:
    """Encodes only supplied owned values, with canonical mapping order and no trivia."""
    validate_value(value)

    def ordered(node: Value) -> Value:
        if isinstance(node, dict):
            return {key: ordered(node[key]) for key in sorted(node)}
        if isinstance(node, list):
            return [ordered(child) for child in node]
        return node

    try:
        content = tomlkit.dumps(cast(dict[str, object], ordered(value)))
    except (TOMLKitError, ValueError, TypeError, RecursionError) as e:
        raise _invalid("baseline contains values unsupported by TOML.") from e
    decode_toml_baseline(content)
    return content


def _record(
    value: object, required: set[str], optional: set[str] | frozenset[str] = frozenset()
) -> dict[str, object]:
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.keys() - required - optional
    ):
        raise _invalid("missing or unknown record fields.")
    return cast(dict[str, object], value)


def _records(value: object) -> list[object]:
    if not isinstance(value, list):
        raise _invalid("record collection must be an array.")
    return cast(list[object], value)


def deserialize_state(content: str) -> SyncState:
    """Parses and validates schema v1; missing state is represented by the caller."""
    try:
        raw = tomlkit.parse(content).unwrap()
        root = _record(
            raw,
            {"schema_version", "producer_version"},
            {"template", "files", "dependencies", "hook_pins"},
        )
        version = root["schema_version"]
        if type(version) is not int or version != SCHEMA_VERSION:
            raise _invalid("unsupported schema version.")
        template = None
        if "template" in root:
            ref = _record(
                root["template"],
                {"origin", "locator", "digest"},
                {"display_name", "version", "source_revision"},
            )
            template = TemplateReference(
                TemplateOrigin(_text(ref["origin"], "template origin")),
                _text(ref["locator"], "template locator"),
                _text(ref["digest"], "template digest"),
                *(
                    _text(ref[key], key) if key in ref else None
                    for key in ("display_name", "version", "source_revision")
                ),
            )
        files = []
        for item in _records(root.get("files", [])):
            record = _record(
                item, {"path", "policy"}, {"baseline", "digest", "regions"}
            )
            regions = []
            for region in _records(record.get("regions", [])):
                fields = _record(region, {"tag", "id", "digest"})
                regions.append(
                    RegionState(
                        _text(fields["tag"], "region tag"),
                        _text(fields["id"], "region id"),
                        _text(fields["digest"], "region digest"),
                    )
                )
            baseline = record.get("baseline")
            if baseline is not None and type(baseline) is not str:
                raise _invalid("baseline must be a document string.")
            files.append(
                FileState(
                    _text(record["path"], "file path"),
                    FilePolicy(_text(record["policy"], "file policy")),
                    baseline,
                    _text(record["digest"], "file digest")
                    if "digest" in record
                    else None,
                    tuple(regions),
                )
            )
        dependencies = []
        for item in _records(root.get("dependencies", [])):
            record = _record(
                item, {"path", "group", "name", "marker", "declared", "materialized"}
            )
            marker = record["marker"]
            if type(marker) is not str:
                raise _invalid("dependency marker must be a string.")
            dependencies.append(
                DependencyState(
                    _text(record["path"], "dependency path"),
                    DependencyGroup(_text(record["group"], "dependency group")),
                    _text(record["name"], "dependency name"),
                    marker,
                    _text(record["declared"], "declared requirement"),
                    _text(record["materialized"], "materialized requirement"),
                )
            )
        pins = []
        for item in _records(root.get("hook_pins", [])):
            record = _record(item, {"path", "repo", "revision", "provenance"})
            pins.append(
                HookPinState(
                    _text(record["path"], "hook path"),
                    _text(record["repo"], "repository"),
                    _text(record["revision"], "revision"),
                    PinProvenance(_text(record["provenance"], "pin provenance")),
                )
            )
        return SyncState(
            _text(root["producer_version"], "producer version"),
            template,
            tuple(files),
            tuple(dependencies),
            tuple(pins),
            version,
        )
    except (TOMLKitError, ValueError, TypeError, RecursionError) as e:
        raise _invalid("malformed or unsupported record.") from e


def serialize_state(state: SyncState) -> str:
    """Returns deterministic TOML bytes-as-text without timestamps or secrets."""
    data: dict[str, object] = {
        "schema_version": state.schema_version,
        "producer_version": state.producer_version,
    }
    if state.template is not None:
        data["template"] = {
            key: value
            for key, value in state.template.to_dict().items()
            if value is not None
        }
    files: list[dict[str, object]] = []
    for record in sorted(state.files, key=lambda item: item.path):
        fields: dict[str, object] = {"path": record.path, "policy": record.policy.value}
        if record.baseline is not None:
            if record.policy is FilePolicy.YAML:
                from .yaml_ast import (
                    decode_yaml_baseline,
                    encode_yaml_baseline,
                )

                fields["baseline"] = encode_yaml_baseline(
                    decode_yaml_baseline(record.baseline)
                )
            elif record.policy is FilePolicy.JSONC:
                fields["baseline"] = encode_jsonc_baseline(
                    decode_jsonc_baseline(record.baseline)
                )
            else:
                fields["baseline"] = encode_toml_baseline(
                    decode_toml_baseline(record.baseline)
                )
        if record.digest is not None:
            fields["digest"] = record.digest
        if record.regions:
            fields["regions"] = [
                {"tag": region.tag, "id": region.id, "digest": region.digest}
                for region in sorted(
                    record.regions, key=lambda item: (item.tag, item.id)
                )
            ]
        files.append(fields)
    data["files"] = files
    data["dependencies"] = [
        {
            "path": record.path,
            "group": record.group.value,
            "name": record.name,
            "marker": record.marker,
            "declared": record.declared,
            "materialized": record.materialized,
        }
        for record in sorted(state.dependencies, key=lambda item: item.identity)
    ]
    data["hook_pins"] = [
        {
            "path": record.path,
            "repo": record.repo,
            "revision": record.revision,
            "provenance": record.provenance.value,
        }
        for record in sorted(state.hook_pins, key=lambda item: (item.path, item.repo))
    ]
    try:
        content = tomlkit.dumps(data)
    except (TOMLKitError, ValueError, TypeError, RecursionError) as e:
        raise _invalid("cannot serialize state.") from e
    deserialize_state(content)
    return content
