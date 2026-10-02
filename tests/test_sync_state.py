from dataclasses import replace
from datetime import UTC, date, datetime, time
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from protostar import sync_state
from protostar.errors import (
    ConfigurationError,
    OutdatedProtostarError,
    UnsupportedFilesystemNodeError,
)
from protostar.intent import (
    DependencyGroup,
    TemplateOrigin,
    TemplateReference,
    region_tag,
)
from protostar.jsonc_ast import encode_jsonc_baseline
from protostar.merge import Value, semantic_equal
from protostar.sync_state import (
    DependencyState,
    FilePolicy,
    FileState,
    HookPinState,
    PinProvenance,
    RegionState,
    SyncState,
    check_one_shot_workspace,
    check_producer_version,
    check_template_identity,
    check_workspace_identity,
    decode_toml_baseline,
    deserialize_state,
    encode_toml_baseline,
    read_workspace_state,
    serialize_state,
)

DIGEST = "a" * 64
REGION = "# region: protostar 12345678\nexport A=1\n# endregion: protostar 12345678"
PROPERTY = settings(max_examples=200, deadline=None)
REF = TemplateReference(
    TemplateOrigin.REMOTE,
    "https://github.com/org/template",
    DIGEST,
    "my-alias",
    "v1",
    path="api",
    ref="v1.0.0",
    revision="b" * 40,
)


@pytest.fixture(autouse=True)
def _fresh_baseline_caches():
    """Decoding and encoding are cached per text; a test must never see another's result."""
    sync_state._decode_toml_baseline.cache_clear()
    sync_state._canonical_baseline.cache_clear()


def sample_state():
    return SyncState(
        "0.9.0",
        REF,
        (
            FileState(
                "pyproject.toml",
                FilePolicy.TOML,
                encode_toml_baseline(
                    {"tool": {"example": {"enabled": True, "select": ["A", "B"]}}}
                ),
            ),
            FileState("justfile", FilePolicy.TEXT, 'build:\n    uv build "."\r\n'),
            FileState("src/app.py", FilePolicy.SEED),
            FileState(
                ".envrc",
                FilePolicy.REGIONS,
                regions=(
                    RegionState(region_tag("module:direnv"), "module:direnv", REGION),
                    RegionState(
                        region_tag("template:api/environment"),
                        "template:api/environment",
                        REGION.replace("A=1", "B=2"),
                    ),
                ),
            ),
        ),
        (
            DependencyState(
                "pyproject.toml",
                DependencyGroup.DEV,
                "pytest",
                "",
                "pytest",
                "pytest>=9",
            ),
            DependencyState(
                "pyproject.toml",
                DependencyGroup.MAIN,
                "httpx",
                'python_version > "3.12"',
                'httpx[socks]>=1; python_version > "3.12"',
                'httpx[socks]>=1; python_version > "3.12"',
            ),
        ),
        (
            HookPinState(
                ".pre-commit-config.yaml",
                "https://example.org/hooks",
                "v2",
                PinProvenance.REGISTRY,
            ),
        ),
    )


def test_complete_state_round_trip_is_canonical_and_byte_stable():
    state = sample_state()
    content = serialize_state(state)
    parsed = deserialize_state(content)
    assert serialize_state(parsed) == content
    assert sorted(parsed.files, key=lambda r: r.path) == sorted(
        state.files, key=lambda r: r.path
    )
    assert sorted(parsed.dependencies, key=lambda r: r.identity) == sorted(
        state.dependencies, key=lambda r: r.identity
    )
    assert parsed.template == REF
    assert parsed.hook_pins == state.hook_pins
    assert "timestamp" not in content
    assert "fully_synced" not in content
    assert "trust" not in content


def test_record_and_baseline_order_do_not_change_serialized_bytes():
    state = sample_state()
    reversed_state = replace(
        state,
        files=tuple(reversed(state.files)),
        dependencies=tuple(reversed(state.dependencies)),
    )
    assert serialize_state(state) == serialize_state(reversed_state)
    assert encode_toml_baseline(
        {"b": {"y": 2, "x": 1}, "a": 3}
    ) == encode_toml_baseline({"a": 3, "b": {"x": 1, "y": 2}})


def test_baseline_preserves_native_toml_shapes():
    values: dict[str, Value] = {
        "str": "text",
        "bool": True,
        "int": 1,
        "float": 1.0,
        "date": date(2026, 1, 1),
        "time": time(12, 30, 1),
        "datetime": datetime(2026, 1, 1),
        "offset": datetime(2026, 1, 1, tzinfo=UTC),
        "nan": float("nan"),
        "inf": float("inf"),
        "array": [1, "mixed", True],
        "records": [{"id": "a"}, {"id": "b"}],
        "empty": {},
    }
    assert semantic_equal(decode_toml_baseline(encode_toml_baseline(values)), values)


@pytest.mark.parametrize(
    "values", [{"null": None}, {"nested": [None]}, {"unsupported": object()}]
)
def test_toml_codec_rejects_lossy_or_unsupported_shapes(values):
    with pytest.raises(ConfigurationError):
        encode_toml_baseline(values)


@pytest.mark.parametrize(
    "path",
    [
        "/absolute",
        "../escape",
        "a/../../escape",
        "a/../b",
        "./file",
        "a//b",
        "",
        ".",
        "C:/escape",
        "C:\\escape",
        "\\server\\share",
        "a\\b",
        "protostar.lock",
        "a/protostar.lock",
        "uv.lock",
        "a/uv.lock",
        "bad\x00path",
    ],
)
def test_rejects_noncanonical_escaping_and_reserved_paths(path):
    with pytest.raises(ConfigurationError):
        FileState(path, FilePolicy.SEED)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not toml",
        'schema_version = 2\nproducer_version = "x"',
        'schema_version = true\nproducer_version = "x"',
        'schema_version = 1\nproducer_version = ""',
        'schema_version = 1\nproducer_version = "x"\ntimestamp = "today"',
        'schema_version = 1\nproducer_version = "x"\nfiles = "bad"',
        'schema_version = 1\nproducer_version = "x"\n[[files]]\npath = "../bad"\npolicy = "seed-only"',
        'schema_version = 1\nproducer_version = "x"\n[[files]]\npath = "file"\npolicy = "unknown"',
        'schema_version = 1\nproducer_version = "x"\n[[files]]\npath = "file"\npolicy = "structured-toml"\nbaseline = "bad TOML"',
        'schema_version = 1\nproducer_version = "x"\n[[files]]\npath = "file"\npolicy = "structured-toml"\nbaseline = 42',
        'schema_version = 1\nproducer_version = "x"\n[template]\norigin = "unknown"\nlocator = "api"\ndigest = "bad"',
    ],
)
def test_corrupt_state_is_fatal_with_actionable_hint(content):
    with pytest.raises(ConfigurationError) as exc:
        deserialize_state(content)
    assert exc.value.hint


@pytest.mark.parametrize(
    "record",
    [
        lambda: FileState("file", FilePolicy.TEXT),
        lambda: FileState("file", FilePolicy.SEED, baseline="x = 1"),
        lambda: FileState(
            "file", FilePolicy.TOML, "x = 1", (RegionState("12345678", "a", REGION),)
        ),
        lambda: FileState("file", FilePolicy.REGIONS, baseline="text"),
        lambda: FileState(
            "file",
            FilePolicy.REGIONS,
            regions=(
                RegionState("12345678", "a", REGION),
                RegionState("12345678", "a", REGION),
            ),
        ),
        lambda: FileState(
            "file",
            FilePolicy.REGIONS,
            regions=(
                RegionState("12345678", "a", REGION),
                RegionState("87654321", "a", REGION),
            ),
        ),
        lambda: FileState(
            "file",
            FilePolicy.REGIONS,
            regions=(
                RegionState("12345678", "a", REGION),
                RegionState("12345678", "b", REGION),
            ),
        ),
        lambda: RegionState("bad_tag", "a", REGION),
        lambda: RegionState("12345678", "bad identity", REGION),
        lambda: DependencyState(
            "pyproject.toml", DependencyGroup.MAIN, "Not_Canonical", "", "x", "x"
        ),
        lambda: HookPinState("hooks.yml", "", "v1", PinProvenance.TEMPLATE),
    ],
)
def test_invalid_policy_fields_and_records_are_rejected(record):
    with pytest.raises(ConfigurationError):
        record()


@PROPERTY
@given(st.text())
def test_text_baselines_round_trip_exactly(text):
    state = SyncState("0.9.0", files=(FileState("justfile", FilePolicy.TEXT, text),))

    assert deserialize_state(serialize_state(state)).files[0].baseline == text


def test_digest_only_region_records_are_rejected():
    content = (
        'schema_version = 1\nproducer_version = "x"\n[[files]]\npath = ".envrc"\n'
        'policy = "regions"\n[[files.regions]]\ntag = "12345678"\nid = "test:id"\n'
        f'digest = "{DIGEST}"\n'
    )

    with pytest.raises(ConfigurationError):
        deserialize_state(content)


def test_digest_only_generated_records_are_rejected():
    content = (
        'schema_version = 1\nproducer_version = "x"\n[[files]]\npath = "justfile"\n'
        f'policy = "checksum"\ndigest = "{DIGEST}"\n'
    )

    with pytest.raises(ConfigurationError):
        deserialize_state(content)


@pytest.mark.parametrize("field", ["files", "dependencies", "hook_pins"])
def test_duplicate_identities_are_rejected(field):
    state = sample_state()
    records = getattr(state, field)
    with pytest.raises(ConfigurationError):
        replace(state, **{field: records + records[:1]})


def test_tooling_only_state_and_candidate_update():
    state = SyncState("0.9.0")
    assert deserialize_state(serialize_state(state)) == state
    record = FileState("pyproject.toml", FilePolicy.TOML, "x = 1\n")
    candidate = state.with_file(record)
    assert not state.files
    assert candidate.files == (record,)
    updated = candidate.with_file(replace(record, baseline="x = 2\n"))
    assert len(updated.files) == 1
    assert candidate.files[0].baseline == "x = 1\n"


def test_another_revision_is_allowed_but_another_source_is_rejected():
    state = sample_state()
    # Moving to another ref of the same repository keeps the identity.
    check_template_identity(
        state,
        replace(
            REF,
            digest="b" * 64,
            version="v2",
            display_name="other alias",
            ref="v2.0.0",
            revision="c" * 40,
        ),
    )
    for ref in (
        None,
        replace(REF, locator="https://github.com/org/other"),
        replace(REF, path="cli"),
        replace(REF, path=""),
        replace(REF, origin=TemplateOrigin.LOCAL, ref=None, revision=None, path=""),
    ):
        with pytest.raises(ConfigurationError):
            check_template_identity(state, ref)
    with pytest.raises(ConfigurationError):
        check_template_identity(SyncState("0.9.0"), REF)
    check_template_identity(SyncState("0.9.0"), None)


@pytest.mark.parametrize(
    ("recorded", "installed", "refused"),
    [
        ("0.9.0", "0.9.0", False),
        ("0.9.0", "0.10.0", False),
        ("0.10.0", "0.9.0", True),
        ("0.9.1", "0.9.1.dev3", True),
        ("0.9.0", "unknown", False),
        ("x", "0.9.0", False),
    ],
)
def test_only_an_older_installed_protostar_is_refused(recorded, installed, refused):
    state = SyncState(recorded)
    if not refused:
        check_producer_version(state, installed)
        return
    with pytest.raises(OutdatedProtostarError) as caught:
        check_producer_version(state, installed)
    assert caught.value.details() == {
        "recorded_version": recorded,
        "installed_version": installed,
    }
    assert caught.value.hint


def test_workspace_state_from_a_newer_protostar_is_refused(tmp_path):
    state = replace(sample_state(), producer_version="999.0")
    (tmp_path / "protostar.lock").write_text(serialize_state(state))
    with pytest.raises(OutdatedProtostarError, match=r"999\.0"):
        read_workspace_state(tmp_path)


def test_workspace_state_is_read_without_following_links(tmp_path):
    assert read_workspace_state(tmp_path) is None
    content = serialize_state(sample_state())
    state_file = tmp_path / "protostar.lock"
    state_file.write_text(content)
    assert read_workspace_state(tmp_path) == deserialize_state(content)
    state_file.write_bytes(b"\xff")
    with pytest.raises(ConfigurationError, match="ownership state"):
        read_workspace_state(tmp_path)
    state_file.unlink()
    (tmp_path / "elsewhere.toml").write_text(content)
    state_file.symlink_to(tmp_path / "elsewhere.toml")
    with pytest.raises(UnsupportedFilesystemNodeError):
        read_workspace_state(tmp_path)


def test_workspace_identity_rejects_only_a_recorded_other_template(tmp_path):
    check_workspace_identity(tmp_path, replace(REF, locator="cli"))
    (tmp_path / "protostar.lock").write_text(serialize_state(sample_state()))
    check_workspace_identity(tmp_path, replace(REF, digest="b" * 64))
    with pytest.raises(ConfigurationError, match="differs") as caught:
        check_workspace_identity(tmp_path, replace(REF, locator="cli"))
    assert caught.value.hint


def test_state_rejects_template_credentials_installation_identity_and_bad_revisions():
    for ref in (
        replace(
            REF,
            origin=TemplateOrigin.REMOTE,
            locator="https://user:secret@example.org/a",
        ),
        replace(
            REF,
            origin=TemplateOrigin.BUILT_IN,
            locator="/installed/package/api.toml",
            path="",
            ref=None,
            revision=None,
        ),
        replace(REF, digest="bad"),
        replace(REF, revision="not-a-sha"),
        replace(REF, revision=None),
        replace(REF, ref=None),
        replace(REF, origin=TemplateOrigin.LOCAL),
    ):
        with pytest.raises(ConfigurationError):
            SyncState("0.9.0", ref)


@pytest.mark.parametrize(
    ("name", "marker", "declared", "materialized"),
    [
        ("pytest", "", "broken requirement !!!", "pytest"),
        ("pytest", "", "pytest", "httpx"),
        ("pytest", "garbage syntax", "pytest", "pytest"),
        ("pytest", "", 'pytest; python_version > "3.12"', "pytest"),
        (
            "pytest",
            'python_version > "3.12"',
            'pytest; python_version > "3.12"',
            'pytest; python_version > "3.13"',
        ),
    ],
)
def test_dependency_records_reject_corrupt_requirements_or_identity(
    name, marker, declared, materialized
):
    with pytest.raises(ConfigurationError):
        DependencyState(
            "pyproject.toml", DependencyGroup.MAIN, name, marker, declared, materialized
        )


def test_dependency_values_preserve_extras_direct_urls_and_materialized_bounds():
    records = (
        DependencyState(
            "pyproject.toml",
            DependencyGroup.DEV,
            "my-package",
            "",
            "My_Package[test] @ https://example.org/package.whl",
            "my-package[test] @ https://example.org/package.whl",
        ),
        DependencyState(
            "pyproject.toml", DependencyGroup.MAIN, "pytest", "", "pytest", "pytest>=9"
        ),
    )
    state = SyncState("0.9.0", dependencies=records)
    assert deserialize_state(serialize_state(state)).dependencies == tuple(
        sorted(records, key=lambda r: r.identity)
    )


def test_state_codec_is_filesystem_subprocess_and_output_free(mocker, capsys):
    read = mocker.patch("pathlib.Path.read_text", side_effect=AssertionError("read"))
    write = mocker.patch("pathlib.Path.write_text", side_effect=AssertionError("write"))
    run = mocker.patch("subprocess.run", side_effect=AssertionError("subprocess"))
    deserialize_state(serialize_state(sample_state()))
    read.assert_not_called()
    write.assert_not_called()
    run.assert_not_called()
    assert capsys.readouterr() == ("", "")


def test_jsonc_baseline_round_trips_canonically_and_keeps_nulls():
    unordered = '{"b": {"y": null, "x": [1, 2.5]}, "a": true}'
    state = SyncState(
        "0.9.0",
        None,
        (FileState(".vscode/settings.json", FilePolicy.JSONC, unordered),),
    )

    content = serialize_state(state)
    parsed = deserialize_state(content)

    assert "structured-jsonc" in content
    record = parsed.files[0]
    assert record.policy is FilePolicy.JSONC
    assert record.baseline == encode_jsonc_baseline(
        {"a": True, "b": {"x": [1, 2.5], "y": None}}
    )
    assert serialize_state(parsed) == content


@pytest.mark.parametrize(
    "baseline",
    [
        "",
        "[]",
        '{"a": 1, // comment\n}',
        '{"a": 1,}',
        '{"a": 1, "a": 2}',
        "{broken",
    ],
)
def test_jsonc_baseline_must_be_a_strict_json_object(baseline):
    with pytest.raises(ConfigurationError):
        FileState(".github/renovate.json", FilePolicy.JSONC, baseline)


@pytest.mark.parametrize(
    "fields",
    [
        {"regions": (RegionState("12345678", "test:id", REGION),)},
        {},
    ],
)
def test_jsonc_records_hold_only_a_baseline(fields):
    with pytest.raises(ConfigurationError):
        FileState(".github/renovate.json", FilePolicy.JSONC, **fields)


HINT = (
    "Correct the state record before retrying; "
    "unsupported state cannot be migrated or adopted automatically."
)
HEAD = 'schema_version = 1\nproducer_version = "x"\n'
TEMPLATE = (
    f'[template]\norigin = "remote"\nlocator = "https://e.org/t"\ndigest = "{DIGEST}"\n'
)
FILE = '[[files]]\npath = "justfile"\npolicy = "text"\nbaseline = "x"\n'
REGION_RECORD = (
    '[[files]]\npath = ".envrc"\npolicy = "regions"\n[[files.regions]]\n'
    'tag = "12345678"\nid = "a"\nbaseline = "x"\n'
)
DEPENDENCY = (
    '[[dependencies]]\npath = "pyproject.toml"\ngroup = "dev"\nname = "pytest"\n'
    'marker = ""\ndeclared = "pytest"\nmaterialized = "pytest"\n'
)
PIN = (
    '[[hook_pins]]\npath = "h.yml"\nrepo = "r"\nrevision = "v1"\n'
    'provenance = "registry"\n'
)


def wrong(value: object) -> Any:
    """Passes a value of the wrong type to a constructor that must reject it."""
    return value


def refused(build, detail):
    with pytest.raises(ConfigurationError) as caught:
        build()
    assert str(caught.value) == f"Invalid Protostar state: {detail}"
    assert caught.value.hint == HINT


def blank(section, key):
    """Returns the section with one of its values set to an empty string."""
    lines = section.splitlines()
    return "\n".join(
        f'{key} = ""' if line.startswith(f"{key} =") else line for line in lines
    )


@pytest.mark.parametrize(
    ("section", "key", "label"),
    [
        (TEMPLATE, "origin", "template origin"),
        (TEMPLATE, "locator", "template locator"),
        (TEMPLATE, "digest", "template digest"),
        (TEMPLATE + 'display_name = "n"\n', "display_name", "display_name"),
        (TEMPLATE + 'version = "v"\n', "version", "version"),
        (TEMPLATE + 'path = "p"\n', "path", "template path"),
        (TEMPLATE + 'ref = "r"\n', "ref", "ref"),
        (TEMPLATE + 'revision = "r"\n', "revision", "revision"),
        (TEMPLATE + 'migrated = "m"\n', "migrated", "migrated"),
        (FILE, "path", "file path"),
        (FILE, "policy", "file policy"),
        (
            FILE.replace("text", "seed-only").replace(
                'baseline = "x"', f'digest = "{DIGEST}"'
            ),
            "digest",
            "file digest",
        ),
        (REGION_RECORD, "tag", "region tag"),
        (REGION_RECORD, "id", "region id"),
        (REGION_RECORD, "baseline", "region baseline"),
        (DEPENDENCY, "path", "dependency path"),
        (DEPENDENCY, "group", "dependency group"),
        (DEPENDENCY, "name", "dependency name"),
        (DEPENDENCY, "declared", "declared requirement"),
        (DEPENDENCY, "materialized", "materialized requirement"),
        (PIN, "path", "hook path"),
        (PIN, "repo", "repository"),
        (PIN, "revision", "revision"),
        (PIN, "provenance", "pin provenance"),
    ],
)
def test_every_stored_field_names_itself_when_empty(section, key, label):
    document = HEAD + blank(section, key) + "\n"

    refused(lambda: deserialize_state(document), f"{label} must be a non-empty string.")


def test_a_missing_producer_version_names_itself():
    refused(
        lambda: deserialize_state('schema_version = 1\nproducer_version = ""\n'),
        "producer version must be a non-empty string.",
    )
    refused(lambda: SyncState(""), "producer version must be a non-empty string.")


def test_a_state_without_records_reads_as_empty():
    state = deserialize_state(HEAD)

    assert state == SyncState("x")
    assert (state.files, state.dependencies, state.hook_pins) == ((), (), ())
    assert deserialize_state(HEAD + FILE).files[0].path == "justfile"
    assert deserialize_state(HEAD + DEPENDENCY).dependencies[0].name == "pytest"
    assert deserialize_state(HEAD + PIN).hook_pins[0].repo == "r"


def test_a_record_that_is_not_an_array_or_has_other_fields_is_refused():
    refused(
        lambda: deserialize_state(HEAD + 'files = "bad"'),
        "record collection must be an array.",
    )
    refused(
        lambda: deserialize_state(HEAD + FILE + 'extra = "no"\n'),
        "missing or unknown record fields.",
    )
    refused(
        lambda: deserialize_state(HEAD + '[[files]]\npolicy = "text"\n'),
        "missing or unknown record fields.",
    )


@pytest.mark.parametrize(
    ("content", "detail"),
    [
        ("not toml", "malformed or unsupported record."),
        (
            HEAD + '[[files]]\npath = "f"\npolicy = "text"\nbaseline = 42\n',
            "baseline must be a document string.",
        ),
        (
            HEAD + DEPENDENCY.replace('marker = ""', "marker = 1"),
            "dependency marker must be a string.",
        ),
        ('schema_version = 2\nproducer_version = "x"\n', "unsupported schema version."),
        (
            'schema_version = true\nproducer_version = "x"\n',
            "unsupported schema version.",
        ),
    ],
)
def test_corrupt_state_says_what_is_wrong(content, detail):
    refused(lambda: deserialize_state(content), detail)


def test_a_state_must_use_the_current_schema_version():
    for version in (0, 2, True, "1"):
        refused(
            lambda version=version: SyncState("x", schema_version=version),
            "unsupported schema version.",
        )
    assert SyncState("x", schema_version=1).schema_version == 1


@pytest.mark.parametrize(
    ("build", "detail"),
    [
        (
            lambda: RegionState("bad_tag", "a", REGION),
            "tags must be 8-character lowercase hex strings.",
        ),
        (
            lambda: RegionState("12345678", "a", wrong(None)),
            "regions record their last applied text.",
        ),
        (
            lambda: FileState("f", FilePolicy.SEED, digest="bad"),
            "digests must be lowercase SHA-256 hex strings.",
        ),
        (
            lambda: FileState("f", FilePolicy.SEED, digest="A" * 64),
            "digests must be lowercase SHA-256 hex strings.",
        ),
        (lambda: FileState("f", wrong("bogus")), "unknown file policy."),
        (
            lambda: FileState(
                "f", FilePolicy.TOML, "x = 1", (RegionState("12345678", "a", REGION),)
            ),
            "structured configuration requires only a baseline document string.",
        ),
        (
            lambda: FileState("f", FilePolicy.YAML, None),
            "structured configuration requires only a baseline document string.",
        ),
        (
            lambda: FileState(
                "pyproject.toml", FilePolicy.TOML, "[tool.protostar]\nx = 1\n"
            ),
            "tool.protostar cannot be owned.",
        ),
        (
            lambda: FileState("pyproject.toml", FilePolicy.TOML, "tool = 1\n"),
            "tool.protostar cannot be owned.",
        ),
        (
            lambda: FileState("f", FilePolicy.TEXT),
            "text policy requires the last applied text.",
        ),
        (
            lambda: FileState("f", FilePolicy.SEED, "x"),
            "seed-only policy records only the seeded path.",
        ),
        (
            lambda: FileState("f", FilePolicy.REGIONS, "x"),
            "region policy records only its regions.",
        ),
        (
            lambda: FileState("f", FilePolicy.TEXT, "x", digest=DIGEST),
            "only a seed records a digest or retirement.",
        ),
        (
            lambda: FileState("f", FilePolicy.TEXT, "x", retired=True),
            "only a seed records a digest or retirement.",
        ),
        (
            lambda: FileState("f", FilePolicy.SEED, retired=wrong(1)),
            "retired must be a boolean.",
        ),
        (
            lambda: FileState(
                "f",
                FilePolicy.REGIONS,
                regions=(
                    RegionState("12345678", "a", REGION),
                    RegionState("87654321", "a", REGION),
                ),
            ),
            "duplicate region identities.",
        ),
        (
            lambda: FileState(
                "f",
                FilePolicy.REGIONS,
                regions=(
                    RegionState("12345678", "a", REGION),
                    RegionState("12345678", "b", REGION),
                ),
            ),
            "duplicate region tags.",
        ),
        (
            lambda: DependencyState(
                "pyproject.toml", DependencyGroup.MAIN, "Bad", "", "x", "x"
            ),
            "dependency name must be canonical.",
        ),
        (
            lambda: DependencyState(
                "pyproject.toml", wrong("bogus"), "x", "", "x", "x"
            ),
            "unsupported dependency group.",
        ),
        (
            lambda: DependencyState(
                "pyproject.toml", DependencyGroup.MAIN, "x", wrong(1), "x", "x"
            ),
            "dependency marker must be a string.",
        ),
        (
            lambda: DependencyState(
                "pyproject.toml", DependencyGroup.MAIN, "x", "", "!!", "x"
            ),
            "malformed dependency requirement.",
        ),
        (
            lambda: DependencyState(
                "pyproject.toml", DependencyGroup.MAIN, "x", "", "y", "y"
            ),
            "dependency requirement does not match its stored name/marker identity.",
        ),
        (
            lambda: DependencyState(
                "pyproject.toml", DependencyGroup.MAIN, "x", "", "", "x"
            ),
            "declared requirement must be a non-empty string.",
        ),
        (
            lambda: DependencyState(
                "pyproject.toml", DependencyGroup.MAIN, "x", "", "x", ""
            ),
            "materialized requirement must be a non-empty string.",
        ),
        (
            lambda: HookPinState("h.yml", "r", "v1", wrong("bogus")),
            "unsupported hook pin provenance.",
        ),
        (
            lambda: HookPinState("h.yml", "", "v1", PinProvenance.TEMPLATE),
            "hook repository must be a non-empty string.",
        ),
        (
            lambda: HookPinState("h.yml", "r", "", PinProvenance.TEMPLATE),
            "hook revision must be a non-empty string.",
        ),
        (
            lambda: FileState("../x", FilePolicy.SEED),
            "unsafe or reserved workspace path '../x'.",
        ),
        (lambda: FileState("", FilePolicy.SEED), "path must be a non-empty string."),
    ],
)
def test_invalid_records_say_what_is_wrong(build, detail):
    refused(build, detail)


@pytest.mark.parametrize(
    ("ref", "detail"),
    [
        (replace(REF, origin=wrong("bogus")), "unsupported template origin."),
        (replace(REF, locator=""), "template locator must be a non-empty string."),
        (replace(REF, digest="bad"), "digests must be lowercase SHA-256 hex strings."),
        (
            replace(REF, display_name=""),
            "template provenance must be a non-empty string.",
        ),
        (replace(REF, ref=""), "template provenance must be a non-empty string."),
        (replace(REF, path=wrong(5)), "template path must be a string."),
        (replace(REF, revision="abc"), "template revision must be a full commit SHA."),
        (
            replace(REF, revision="B" * 40),
            "template revision must be a full commit SHA.",
        ),
        (
            replace(REF, revision=None),
            "only a remote template records a ref and its commit.",
        ),
        (
            replace(REF, ref=None),
            "only a remote template records a ref and its commit.",
        ),
        (
            replace(
                REF, origin=TemplateOrigin.LOCAL, ref=None, revision=None, path="p"
            ),
            "only a remote template records a ref and its commit.",
        ),
        (
            replace(REF, origin=TemplateOrigin.LOCAL, revision=None),
            "only a remote template records a ref and its commit.",
        ),
        (
            replace(
                REF,
                origin=TemplateOrigin.BUILT_IN,
                locator="/abs/api",
                path="",
                ref=None,
                revision=None,
            ),
            "built-in identity cannot be an installation path.",
        ),
        (
            replace(
                REF,
                origin=TemplateOrigin.BUILT_IN,
                locator="C:\\api",
                path="",
                ref=None,
                revision=None,
            ),
            "built-in identity cannot be an installation path.",
        ),
        (
            replace(REF, locator="https://user:pw@e.org/t"),
            "template locators cannot contain credentials.",
        ),
        (
            replace(REF, locator="https://user@e.org/t"),
            "template locators cannot contain credentials.",
        ),
        (
            replace(REF, locator="https://:pw@e.org/t"),
            "template locators cannot contain credentials.",
        ),
        (replace(REF, locator="https://[bad/t"), "malformed remote template locator."),
    ],
)
def test_an_invalid_template_says_what_is_wrong(ref, detail):
    refused(lambda: SyncState("x", ref), detail)


def test_valid_templates_are_accepted():
    local = replace(REF, origin=TemplateOrigin.LOCAL, ref=None, revision=None, path="")
    built_in = replace(local, origin=TemplateOrigin.BUILT_IN, locator="api")
    plain = replace(REF, ref=None, revision=None, path="")
    sha256 = replace(REF, revision="c" * 64)

    for ref in (REF, local, built_in, plain, sha256):
        assert SyncState("x", ref).template == ref


def test_duplicate_identities_say_so():
    state = sample_state()

    refused(
        lambda: replace(state, files=state.files + state.files[:1]),
        "duplicate file, dependency, or repository identity.",
    )


def test_unsafe_workspace_paths_are_named():
    refused(
        lambda: FileState("a/../b", FilePolicy.SEED),
        "unsafe or reserved workspace path 'a/../b'.",
    )


def test_the_toml_codec_names_what_it_cannot_encode():
    refused(
        lambda: encode_toml_baseline({"null": None}),
        "baseline contains values unsupported by TOML.",
    )
    with pytest.raises(ConfigurationError, match="Unsupported semantic value type"):
        encode_toml_baseline({"unsupported": wrong(object())})
    with pytest.raises(ConfigurationError, match="malformed TOML baseline") as caught:
        decode_toml_baseline("not toml")
    assert caught.value.hint == HINT


def test_a_template_switch_is_refused_in_plain_words():
    with pytest.raises(ConfigurationError) as caught:
        check_template_identity(sample_state(), None)

    assert (
        str(caught.value)
        == "Selected template differs from the tracked project identity."
    )
    assert caught.value.hint == (
        "Select the same template source explicitly; "
        "template switching and adoption are unsupported."
    )


def test_an_unreadable_state_file_says_how_to_fix_it(tmp_path):
    (tmp_path / "protostar.lock").write_bytes(b"\xff")

    with pytest.raises(ConfigurationError) as caught:
        read_workspace_state(tmp_path)

    assert str(caught.value) == "Invalid project ownership state."
    assert caught.value.hint == "Correct protostar.lock encoding."


def test_one_shot_requires_an_untracked_project(tmp_path):
    check_one_shot_workspace(tmp_path)
    (tmp_path / "protostar.lock").write_text(serialize_state(sample_state()))

    with pytest.raises(ConfigurationError) as caught:
        check_one_shot_workspace(tmp_path)

    assert str(caught.value) == "One-shot initialization requires an untracked project."
    assert (
        caught.value.hint == "Run init without --one-shot to update a tracked project."
    )


def test_a_recipe_alone_also_marks_a_tracked_project(tmp_path, mocker):
    mocker.patch("protostar.recipe.read_recipe", return_value=object())

    with pytest.raises(ConfigurationError, match="untracked project"):
        check_one_shot_workspace(tmp_path)


def test_a_state_tomlkit_cannot_write_is_refused(mocker):
    mocker.patch("protostar.sync_state.tomlkit.dumps", side_effect=ValueError("boom"))

    with pytest.raises(ConfigurationError) as caught:
        serialize_state(SyncState("x"))

    assert str(caught.value) == "Invalid Protostar state: cannot serialize state."
    assert caught.value.hint == HINT
    assert isinstance(caught.value.__cause__, ValueError)
