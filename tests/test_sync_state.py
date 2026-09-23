from dataclasses import replace
from datetime import UTC, date, datetime, time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from protostar.errors import ConfigurationError
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
    check_template_identity,
    decode_toml_baseline,
    deserialize_state,
    encode_toml_baseline,
    serialize_state,
)

DIGEST = "a" * 64
REGION = "# region: protostar 12345678\nexport A=1\n# endregion: protostar 12345678"
PROPERTY = settings(max_examples=200, deadline=None)
REF = TemplateReference(
    TemplateOrigin.BUILT_IN, "api", DIGEST, "my-alias", "v1", "revision"
)


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
        ".protostar.lock.toml",
        "a/.protostar.lock.toml",
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


def test_same_source_revision_is_allowed_but_alias_retargeting_is_rejected():
    state = sample_state()
    check_template_identity(
        state, replace(REF, digest="b" * 64, version="v2", display_name="other alias")
    )
    for ref in (
        None,
        replace(REF, locator="cli"),
        replace(REF, origin=TemplateOrigin.REMOTE),
    ):
        with pytest.raises(ConfigurationError):
            check_template_identity(state, ref)
    with pytest.raises(ConfigurationError):
        check_template_identity(SyncState("0.9.0"), REF)
    check_template_identity(SyncState("0.9.0"), None)


def test_state_rejects_template_credentials_and_installation_identity():
    for ref in (
        replace(
            REF,
            origin=TemplateOrigin.REMOTE,
            locator="https://user:secret@example.org/a",
        ),
        replace(REF, locator="/installed/package/api.toml"),
        replace(REF, digest="bad"),
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
