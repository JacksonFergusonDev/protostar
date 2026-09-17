"""Transactional Codecov pilot acceptance without subprocesses."""

from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.errors import ConfigurationError, FileSystemError
from protostar.executor import SystemExecutor
from protostar.intent import StructuredFormat
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.models import ExecutionResult
from protostar.sync_state import FilePolicy, deserialize_state
from protostar.yaml_ast import decode_yaml_baseline

TARGET = Path(".github/codecov.yml")
STATE = Path(".protostar.lock.toml")


def manifest(target="80%", ignores="tests/**, docs/**"):
    intent = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    intent.filesystem.add_structured(
        TARGET.as_posix(),
        f'coverage: {{target: "{target}"}}\nignore: [{ignores}]\n',
        producer="module:codecov",
        document_format=StructuredFormat.YAML,
    )
    return intent


def run(intent, mocker):
    executor = SystemExecutor(intent, UserConfig())
    process = mocker.patch.object(executor.process_runner, "run")
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    process.assert_not_called()
    return executor


def baseline():
    record = next(
        r
        for r in deserialize_state(STATE.read_text()).files
        if r.path == TARGET.as_posix()
    )
    assert record.policy is FilePolicy.YAML
    assert record.baseline is not None
    return decode_yaml_baseline(record.baseline)


def test_create_repeat_update_conflict_and_deletion(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    first = run(manifest(), mocker)
    assert TARGET.as_posix() in first.journal.created_paths
    initial = (TARGET.read_bytes(), STATE.read_bytes())
    for _ in range(2):
        repeated = run(manifest(), mocker)
        assert not repeated.journal.touched_paths
        assert (TARGET.read_bytes(), STATE.read_bytes()) == initial
    changed = run(manifest("85%"), mocker)
    assert changed.journal.mutated_paths == {TARGET.as_posix(), STATE.as_posix()}
    assert baseline()["coverage"]["target"] == "85%"
    TARGET.write_text(
        '# comment\ncoverage: {target: "90%"} # local\nignore: [tests/**, custom/**]\nforeign: true\n'
    )
    changed = run(manifest("87%", "tests/**, docs/**, scripts/**"), mocker)
    local = decode_yaml_baseline(TARGET.read_text())
    assert isinstance(local["coverage"], dict)
    assert local["coverage"]["target"] == "90%"
    assert local["ignore"] == ["tests/**", "custom/**", "scripts/**"]
    assert "# comment" in TARGET.read_text()
    assert "# local" in TARGET.read_text()
    assert baseline()["coverage"]["target"] == "85%"
    assert "foreign" not in baseline()
    result = ExecutionResult(
        changed.journal.created_paths,
        changed.journal.mutated_paths,
        tuple(changed.diagnostics),
    )
    payload = result.to_dict()
    assert any(
        d.get("conflict", {}).get("file") == TARGET.as_posix()
        for d in payload["diagnostics"]
    )
    TARGET.unlink()
    state_before = STATE.read_bytes()
    run(manifest("88%"), mocker)
    assert not TARGET.exists()
    assert STATE.read_bytes() == state_before


def test_existing_equal_content_stays_unowned(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    TARGET.parent.mkdir()
    original = '# original\ncoverage: {target: "80%"}\nignore: [tests/**, docs/**]\n'
    TARGET.write_text(original)
    run(manifest(), mocker)
    assert TARGET.read_text() == original
    assert not deserialize_state(STATE.read_text()).files
    changed = run(manifest("85%"), mocker)
    assert TARGET.read_text() == original
    assert changed.diagnostics


@pytest.mark.parametrize("content", [b"a: [bad", b"a: 1\na: 2\n", b"\xff"])
def test_invalid_yaml_fails_before_mutation(tmp_path, monkeypatch, mocker, content):
    monkeypatch.chdir(tmp_path)
    TARGET.parent.mkdir()
    TARGET.write_bytes(content)
    intent = manifest()
    intent.filesystem.add_file_injection("new.txt", "should not be written")
    with pytest.raises((ConfigurationError, FileSystemError)):
        run(intent, mocker)
    assert TARGET.read_bytes() == content
    assert not Path("new.txt").exists()
    assert not STATE.exists()


@pytest.mark.parametrize("failure", ["_write_ignores", "_write_state"])
def test_failure_restores_exact_yaml_and_state_bytes_modes(
    tmp_path, monkeypatch, mocker, failure
):
    monkeypatch.chdir(tmp_path)
    run(manifest(), mocker)
    TARGET.chmod(0o640)
    STATE.chmod(0o600)
    before = [(p.read_bytes(), p.stat().st_mode) for p in (TARGET, STATE)]
    executor = SystemExecutor(manifest("85%"), UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    original = getattr(executor, failure)

    def fail():
        original()
        raise ConfigurationError("injected failure")

    mocker.patch.object(executor, failure, side_effect=fail)
    with pytest.raises(ConfigurationError):
        executor.execute()
    assert [(p.read_bytes(), p.stat().st_mode) for p in (TARGET, STATE)] == before


def test_yaml_manifest_rejects_ambiguous_or_unsupported_declarations():
    intent = manifest()
    with pytest.raises(ConfigurationError):
        intent.filesystem.add_structured(
            TARGET.as_posix(),
            "{}",
            producer="other",
            document_format=StructuredFormat.YAML,
        )
    with pytest.raises(ConfigurationError):
        intent.filesystem.add_file_injection(TARGET.as_posix(), "{}")
    with pytest.raises(ConfigurationError):
        intent.filesystem.add_structured(
            "foreign.yml", "{}", producer="other", document_format=StructuredFormat.YAML
        )
