"""Transactional hook updates use one frozen registry snapshot and no live processes."""

from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.errors import ConfigurationError, FileSystemError
from protostar.executor import SystemExecutor
from protostar.manifest import CollisionStrategy, EnvironmentManifest, HookRunner
from protostar.registry import RemoteHook, ResolvedHookRevision
from protostar.sync_state import PinProvenance, deserialize_state
from protostar.yaml_ast import decode_yaml_baseline

TARGET = Path(".pre-commit-config.yaml")
STATE = Path(".protostar.lock.toml")


def intent(runner=HookRunner.PRE_COMMIT, extra=False, hook_types=()):
    manifest = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    manifest.tooling.hook_runner = runner
    manifest.tooling.pre_commit_install_hook_types.update(hook_types)
    if extra:
        manifest.tooling.add_pre_commit_local_hook(
            "      - id: extra\n        entry: extra\n        language: system"
        )
    return manifest


def executor(manifest, mocker, version="v1.0.0", provenance=PinProvenance.REGISTRY):
    resolve = mocker.patch(
        "protostar.executor.resolve_hook_revisions",
        return_value=tuple(
            ResolvedHookRevision(hook, version, provenance) for hook in RemoteHook
        ),
    )
    result = SystemExecutor(manifest, UserConfig())
    resolve.assert_called_once_with()
    resolve.side_effect = AssertionError("must not refetch")
    process = mocker.patch.object(
        result.process_runner,
        "run",
        side_effect=AssertionError("no subprocess expected"),
    )
    mocker.patch.object(result, "_check_ide_extensions")
    return result, process


def run(manifest, mocker, **kwargs):
    result, process = executor(manifest, mocker, **kwargs)
    result.execute()
    process.assert_not_called()
    return result


def test_create_repeat_update_and_offline(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(intent(), mocker)
    initial = TARGET.read_bytes(), STATE.read_bytes()
    for _ in range(2):
        result = run(intent(), mocker)
        assert not result.journal.touched_paths
        assert (TARGET.read_bytes(), STATE.read_bytes()) == initial
    TARGET.write_text(
        TARGET.read_text().replace(
            "    hooks:", "    custom: yes # user\n    hooks:", 1
        )
    )
    result = run(intent(extra=True), mocker, version="v2.0.0")
    assert "id: extra" in TARGET.read_text()
    assert "rev: v2.0.0" in TARGET.read_text()
    assert "# user" in TARGET.read_text()
    state = deserialize_state(STATE.read_text())
    assert all(pin.revision == "v2.0.0" for pin in state.hook_pins)
    assert all("custom" not in (r.baseline or "") for r in state.files)
    before = TARGET.read_bytes(), STATE.read_bytes()
    fallback = run(
        intent(extra=True), mocker, version="v1.0.0", provenance=PinProvenance.FALLBACK
    )
    assert (TARGET.read_bytes(), STATE.read_bytes()) == before
    assert not fallback.journal.touched_paths
    assert any(d.conflict for d in fallback.diagnostics)


def test_runner_and_install_types_change(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(intent(hook_types=("commit-msg", "pre-push")), mocker)
    result = run(intent(HookRunner.PREK), mocker)
    config = decode_yaml_baseline(TARGET.read_text())
    assert config["default_install_hook_types"] == ["pre-commit"]
    assert config["default_stages"] == ["pre-commit"]
    records = config["repos"]
    assert isinstance(records, list)
    assert any(isinstance(repo, dict) and repo["repo"] == "builtin" for repo in records)
    assert not any(d.conflict for d in result.diagnostics)


@pytest.mark.parametrize("failure", ["_check_ide_extensions", "_write_state"])
def test_rollback_restores_file_state_bytes_modes(
    tmp_path, monkeypatch, mocker, failure
):
    monkeypatch.chdir(tmp_path)
    run(intent(), mocker)
    TARGET.chmod(0o640)
    STATE.chmod(0o600)
    before = [(p.read_bytes(), p.stat().st_mode) for p in (TARGET, STATE)]
    result, _ = executor(intent(extra=True), mocker, version="v2.0.0")
    original = getattr(result, failure)

    def fail():
        original()
        raise ConfigurationError("injected failure")

    mocker.patch.object(result, failure, side_effect=fail)
    with pytest.raises(ConfigurationError):
        result.execute()
    assert [(p.read_bytes(), p.stat().st_mode) for p in (TARGET, STATE)] == before


@pytest.mark.parametrize("content", [b"repos: [", b"repos: []\nrepos: []", b"\xff"])
def test_bad_yaml_rolls_back_earlier_injections(tmp_path, monkeypatch, mocker, content):
    monkeypatch.chdir(tmp_path)
    TARGET.write_bytes(content)
    manifest = intent()
    manifest.filesystem.add_file_injection("new.txt", "new")
    with pytest.raises((ConfigurationError, FileSystemError)):
        run(manifest, mocker)
    assert TARGET.read_bytes() == content
    assert not STATE.exists()
    assert not Path("new.txt").exists()


def test_deleted_file_retains_state_and_pin(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(intent(), mocker)
    TARGET.unlink()
    before = STATE.read_bytes()
    run(intent(extra=True), mocker, version="v2.0.0")
    assert not TARGET.exists()
    assert STATE.read_bytes() == before
