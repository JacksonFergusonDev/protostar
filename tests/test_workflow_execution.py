"""Transactional GitHub Actions workflow reconciliation without subprocesses."""

from pathlib import Path
from typing import Any

import pytest

from protostar.config import UserConfig
from protostar.documents.github_workflows import CI_TARGET, RELEASE_TARGET
from protostar.errors import ConfigurationError, FileSystemError
from protostar.executor import SystemExecutor
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.sync_state import FilePolicy, deserialize_state
from protostar.workflows import generate_release_workflow
from protostar.yaml_ast import decode_yaml_baseline

CI = Path(CI_TARGET)
RELEASE = Path(RELEASE_TARGET)
STATE = Path("protostar.lock")


def manifest(*, codecov: bool = False) -> EnvironmentManifest:
    intent = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    intent.metadata = {"supported_os": ["Linux"], "minimum_python": "3.14"}
    intent.tooling.wants_ci = True
    intent.tooling.wants_release = True
    intent.tooling.ci_flags = {"pytest", "codecov"} if codecov else {"pytest"}
    intent.tooling.ci_steps = [
        "      - name: Run Ruff Linter\n        run: uv run ruff check ."
    ]
    return intent


def run(intent: EnvironmentManifest, mocker) -> SystemExecutor:
    executor = SystemExecutor(intent, UserConfig())
    process = mocker.patch.object(executor.process_runner, "run")
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    process.assert_not_called()
    return executor


def owned(path: Path) -> Any:
    record = next(
        r
        for r in deserialize_state(STATE.read_text()).files
        if r.path == path.as_posix()
    )
    assert record.policy is FilePolicy.YAML
    assert record.baseline is not None
    return decode_yaml_baseline(record.baseline)


def test_create_repeat_and_update_are_transactional(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    first = run(manifest(codecov=True), mocker)
    assert {CI.as_posix(), RELEASE.as_posix()} <= first.journal.created_paths
    assert RELEASE.read_text() == generate_release_workflow()
    initial = (CI.read_bytes(), RELEASE.read_bytes(), STATE.read_bytes())
    repeated = run(manifest(codecov=True), mocker)
    assert not repeated.journal.touched_paths
    assert (CI.read_bytes(), RELEASE.read_bytes(), STATE.read_bytes()) == initial

    CI.write_text(CI.read_text().replace("on:\n", "on:\n  workflow_dispatch:\n"))
    changed = run(manifest(), mocker)
    assert changed.journal.mutated_paths == {CI.as_posix(), STATE.as_posix()}
    assert not [d for d in changed.diagnostics if d.conflict]
    local: Any = decode_yaml_baseline(CI.read_text())
    assert "workflow_dispatch" in local["on"]
    assert "Upload coverage to Codecov" not in CI.read_text()
    assert "workflow_dispatch" not in owned(CI)["on"]
    assert "Upload coverage to Codecov" not in STATE.read_text()


@pytest.mark.parametrize("content", [b"a: [bad", b"jobs: {}\njobs: {}\n", b"\xff"])
def test_invalid_workflow_fails_before_mutation(tmp_path, monkeypatch, mocker, content):
    monkeypatch.chdir(tmp_path)
    CI.parent.mkdir(parents=True)
    CI.write_bytes(content)
    intent = manifest()
    intent.filesystem.add_file_injection("new.txt", "should not be written")
    with pytest.raises((ConfigurationError, FileSystemError)):
        run(intent, mocker)
    assert CI.read_bytes() == content
    assert not RELEASE.exists()
    assert not Path("new.txt").exists()
    assert not STATE.exists()


@pytest.mark.parametrize("failure", ["_check_ide_extensions", "_write_state"])
def test_failure_restores_exact_workflow_and_state_bytes_modes(
    tmp_path, monkeypatch, mocker, failure
):
    monkeypatch.chdir(tmp_path)
    run(manifest(codecov=True), mocker)
    CI.chmod(0o640)
    STATE.chmod(0o600)
    before = [(p.read_bytes(), p.stat().st_mode) for p in (CI, STATE)]
    executor = SystemExecutor(manifest(), UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    original = getattr(executor, failure)

    def fail():
        original()
        raise ConfigurationError("injected failure")

    mocker.patch.object(executor, failure, side_effect=fail)
    with pytest.raises(ConfigurationError):
        executor.execute()
    assert [(p.read_bytes(), p.stat().st_mode) for p in (CI, STATE)] == before


def test_workflow_targets_reject_append_regions():
    intent = EnvironmentManifest()
    with pytest.raises(ConfigurationError):
        intent.filesystem.add_region(CI_TARGET, "x: 1\n", identity="t:ci")
    with pytest.raises(ConfigurationError):
        intent.filesystem.add_region(RELEASE_TARGET, "x: 1\n", identity="t:r")
