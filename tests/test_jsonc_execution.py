"""Transactional JSONC acceptance for Renovate and VS Code settings, without subprocesses."""

from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.errors import ConfigurationError, FileSystemError
from protostar.executor import SystemExecutor
from protostar.jsonc_ast import decode_jsonc, decode_jsonc_baseline
from protostar.manifest import CollisionStrategy, EnvironmentManifest, Severity
from protostar.merge import ConflictReason
from protostar.models import ExecutionResult
from protostar.reconciliation import Reconciliation
from protostar.sync_state import FilePolicy, deserialize_state

RENOVATE = Path(".github/renovate.json")
SETTINGS = Path(".vscode/settings.json")
STATE = Path("protostar.lock")

CONFIG_V1 = """\
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:best-practices"],
  "schedule": ["before 4am on monday"],
  "vulnerabilityAlerts": {"schedule": ["at any time"]}
}
"""
CONFIG_V2 = CONFIG_V1.replace("before 4am", "before 6am")


def renovate_manifest(content=CONFIG_V1, strategy=CollisionStrategy.MERGE):
    intent = EnvironmentManifest(collision_strategy=strategy)
    intent.filesystem.add_file_injection(RENOVATE.as_posix(), content)
    return intent


def settings_manifest(interpreter=".venv/bin/python", strategy=CollisionStrategy.MERGE):
    intent = EnvironmentManifest(collision_strategy=strategy)
    intent.add_ide_setting("python.defaultInterpreterPath", interpreter)
    intent.add_ide_setting("python.terminal.activateEnvironment", True)
    return intent


def run(intent, mocker):
    executor = SystemExecutor(intent, UserConfig())
    process = mocker.patch.object(executor.process_runner, "run")
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    process.assert_not_called()
    return executor


def record(path):
    return next(
        (
            r
            for r in deserialize_state(STATE.read_text()).files
            if r.path == path.as_posix()
        ),
        None,
    )


def owned(path):
    found = record(path)
    assert found is not None
    assert found.policy is FilePolicy.JSONC
    assert found.baseline is not None
    return decode_jsonc_baseline(found.baseline)


# --- Renovate ---------------------------------------------------------------


def test_renovate_create_repeat_update_and_conflict(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)

    first = run(renovate_manifest(), mocker)

    assert RENOVATE.read_text() == CONFIG_V1
    assert RENOVATE.as_posix() in first.journal.created_paths
    assert owned(RENOVATE) == decode_jsonc(CONFIG_V1)
    initial = (RENOVATE.read_bytes(), STATE.read_bytes())
    for _ in range(2):
        repeated = run(renovate_manifest(), mocker)
        assert not repeated.journal.touched_paths
        assert (RENOVATE.read_bytes(), STATE.read_bytes()) == initial

    RENOVATE.write_text(
        CONFIG_V1.replace(
            '  "schedule"', '  // my note\n  "labels": ["deps"],\n  "schedule"'
        )
    )
    updated = run(renovate_manifest(CONFIG_V2), mocker)

    assert updated.journal.mutated_paths == {RENOVATE.as_posix(), STATE.as_posix()}
    text = RENOVATE.read_text()
    assert "// my note" in text
    assert '"labels": ["deps"]' in text
    assert "before 6am" in text
    assert "labels" not in owned(RENOVATE)
    assert owned(RENOVATE)["schedule"] == ["before 6am on monday"]

    RENOVATE.write_text(text.replace("before 6am", "before 9pm"))
    conflicted = run(renovate_manifest(CONFIG_V2.replace("6am", "7am")), mocker)

    assert "before 9pm" in RENOVATE.read_text()
    assert owned(RENOVATE)["schedule"] == ["before 6am on monday"]
    payload = ExecutionResult(
        conflicted.journal.created_paths,
        conflicted.journal.mutated_paths,
        tuple(conflicted.diagnostics),
    ).to_dict()
    assert any(
        d.get("conflict", {}).get("file") == RENOVATE.as_posix()
        and d["conflict"]["reason"] == ConflictReason.DIVERGED.value
        for d in payload["diagnostics"]
    )


def test_renovate_deleted_file_stays_deleted(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(renovate_manifest(), mocker)
    RENOVATE.unlink()
    state = STATE.read_bytes()

    run(renovate_manifest(CONFIG_V2), mocker)

    assert not RENOVATE.exists()
    assert STATE.read_bytes() == state


def test_renovate_existing_file_receives_only_missing_keys(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    RENOVATE.parent.mkdir()
    RENOVATE.write_text('{\n  // team config\n  "extends": ["local"]\n}\n')

    executor = run(renovate_manifest(), mocker)

    local = decode_jsonc(RENOVATE.read_text())
    assert local["extends"] == ["local"]
    assert local["schedule"] == ["before 4am on monday"]
    assert "// team config" in RENOVATE.read_text()
    assert "extends" not in owned(RENOVATE)
    assert any(d.conflict for d in executor.diagnostics)


def test_renovate_equal_existing_content_is_not_adopted(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    RENOVATE.parent.mkdir()
    RENOVATE.write_text(CONFIG_V1)

    run(renovate_manifest(), mocker)

    assert RENOVATE.read_text() == CONFIG_V1
    assert record(RENOVATE) is None


def test_renovate_overwrite_owns_declared_values(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    RENOVATE.parent.mkdir()
    RENOVATE.write_text('{\n  "extends": ["mine"], // mine\n  "custom": 1\n}\n')

    run(renovate_manifest(strategy=CollisionStrategy.OVERWRITE), mocker)

    local = decode_jsonc(RENOVATE.read_text())
    assert local["extends"] == ["config:best-practices"]
    assert local["custom"] == 1
    assert "// mine" in RENOVATE.read_text()
    assert owned(RENOVATE) == decode_jsonc(CONFIG_V1)


@pytest.mark.parametrize(
    "alternate", ["renovate.json5", ".renovaterc.json5", ".github/renovate.json5"]
)
def test_renovate_json5_configuration_is_preserved(
    tmp_path, monkeypatch, mocker, alternate
):
    monkeypatch.chdir(tmp_path)
    target = Path(alternate)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"// comments\n{}")

    executor = run(renovate_manifest(), mocker)

    [conflict] = [d.conflict for d in executor.diagnostics if d.conflict]
    assert conflict.reason is ConflictReason.UNOWNED
    assert conflict.location.file == RENOVATE.as_posix()
    assert target.read_bytes() == b"// comments\n{}"
    assert not RENOVATE.exists()


@pytest.mark.parametrize("alias", ["renovate.json", ".renovaterc", "renovate.jsonc"])
def test_renovate_configuration_elsewhere_is_merged_in_place(
    tmp_path, monkeypatch, mocker, alias
):
    monkeypatch.chdir(tmp_path)
    target = Path(alias)
    target.write_text('// mine\n{"custom": 1}\n')

    executor = run(renovate_manifest(), mocker)

    assert not [d for d in executor.diagnostics if d.conflict]
    assert not RENOVATE.exists()
    local = decode_jsonc(target.read_text())
    assert local["custom"] == 1
    assert local["extends"] == ["config:best-practices"]
    assert "// mine" in target.read_text()
    assert owned(target) == decode_jsonc(CONFIG_V1)


@pytest.mark.parametrize("content", ["{broken", "[]", ""])
def test_invalid_generated_renovate_fails_before_mutation(
    tmp_path, monkeypatch, mocker, content
):
    monkeypatch.chdir(tmp_path)
    intent = renovate_manifest(content)
    intent.filesystem.add_file_injection("seed.py", "seed")

    with pytest.raises(ConfigurationError):
        run(intent, mocker)

    assert not Path("seed.py").exists()
    assert not RENOVATE.exists()
    assert not STATE.exists()


@pytest.mark.parametrize(
    "content", [b'{"a": 1, "a": 2}', b"{", b"[]", b"\xff"], ids=str
)
def test_invalid_existing_renovate_fails_before_mutation(
    tmp_path, monkeypatch, mocker, content
):
    monkeypatch.chdir(tmp_path)
    RENOVATE.parent.mkdir()
    RENOVATE.write_bytes(content)
    intent = renovate_manifest()
    intent.filesystem.add_file_injection("seed.py", "seed")

    with pytest.raises((ConfigurationError, FileSystemError)):
        run(intent, mocker)

    assert RENOVATE.read_bytes() == content
    assert not Path("seed.py").exists()
    assert not STATE.exists()


@pytest.mark.parametrize("failure", ["_check_ide_extensions", "_write_state"])
def test_failure_restores_exact_renovate_and_state_bytes_modes(
    tmp_path, monkeypatch, mocker, failure
):
    monkeypatch.chdir(tmp_path)
    run(renovate_manifest(), mocker)
    RENOVATE.chmod(0o640)
    STATE.chmod(0o600)
    before = [(p.read_bytes(), p.stat().st_mode) for p in (RENOVATE, STATE)]
    executor = SystemExecutor(renovate_manifest(CONFIG_V2), UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    original = getattr(executor, failure)

    def fail():
        original()
        raise ConfigurationError("injected failure")

    mocker.patch.object(executor, failure, side_effect=fail)
    with pytest.raises(ConfigurationError):
        executor.execute()

    assert [(p.read_bytes(), p.stat().st_mode) for p in (RENOVATE, STATE)] == before


def test_preserved_crlf_bom_and_odd_formatting(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(renovate_manifest(), mocker)
    local = "﻿" + CONFIG_V1.replace("\n", "\r\n").replace('  "$schema"', '\t"$schema"')
    RENOVATE.write_bytes(local.encode())

    run(renovate_manifest(CONFIG_V2), mocker)

    assert RENOVATE.read_bytes() == local.replace("before 4am", "before 6am").encode()


# --- VS Code settings -------------------------------------------------------


def test_settings_create_repeat_and_update(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)

    first = run(settings_manifest(), mocker)

    assert SETTINGS.read_text() == (
        '{\n    "python.defaultInterpreterPath": ".venv/bin/python",\n'
        '    "python.terminal.activateEnvironment": true\n}\n'
    )
    assert SETTINGS.as_posix() in first.journal.created_paths
    assert owned(SETTINGS) == decode_jsonc(SETTINGS.read_text())
    initial = (SETTINGS.read_bytes(), STATE.read_bytes())
    repeated = run(settings_manifest(), mocker)
    assert not repeated.journal.touched_paths
    assert (SETTINGS.read_bytes(), STATE.read_bytes()) == initial

    run(settings_manifest("python3"), mocker)

    assert (
        decode_jsonc(SETTINGS.read_text())["python.defaultInterpreterPath"] == "python3"
    )


def test_settings_with_comments_merge_without_losing_user_content(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    SETTINGS.parent.mkdir()
    SETTINGS.write_text(
        '{\n  // my editor\n  "editor.rulers": [80, 100], /* keep */\n'
        '  "files.exclude": {"**/.git": true,},\n}\n'
    )

    run(settings_manifest(), mocker)

    text = SETTINGS.read_text()
    assert "// my editor" in text
    assert "/* keep */" in text
    assert decode_jsonc(text) == {
        "editor.rulers": [80, 100],
        "files.exclude": {"**/.git": True},
        "python.defaultInterpreterPath": ".venv/bin/python",
        "python.terminal.activateEnvironment": True,
    }
    assert owned(SETTINGS) == {
        "python.defaultInterpreterPath": ".venv/bin/python",
        "python.terminal.activateEnvironment": True,
    }


def test_settings_user_value_is_preserved_with_a_warning(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    SETTINGS.parent.mkdir()
    SETTINGS.write_text('{"python.defaultInterpreterPath": "/usr/bin/python3"}\n')

    executor = run(settings_manifest(), mocker)

    assert (
        decode_jsonc(SETTINGS.read_text())["python.defaultInterpreterPath"]
        == "/usr/bin/python3"
    )
    assert any(
        d.conflict and d.conflict.reason is ConflictReason.UNOWNED
        for d in executor.diagnostics
    )


def test_settings_overwrite_takes_declared_values(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    SETTINGS.parent.mkdir()
    SETTINGS.write_text('{"python.defaultInterpreterPath": "/usr/bin/python3", "a": 1}')

    run(settings_manifest(strategy=CollisionStrategy.OVERWRITE), mocker)

    assert decode_jsonc(SETTINGS.read_text()) == {
        "python.defaultInterpreterPath": ".venv/bin/python",
        "python.terminal.activateEnvironment": True,
        "a": 1,
    }


@pytest.mark.parametrize("content", ["   \n  \t", "// only a comment\n"])
def test_settings_blank_or_comment_only_file_is_populated(
    tmp_path, monkeypatch, mocker, content
):
    monkeypatch.chdir(tmp_path)
    SETTINGS.parent.mkdir()
    SETTINGS.write_text(content)

    run(settings_manifest(), mocker)

    assert SETTINGS.read_text().startswith(content)
    assert (
        decode_jsonc(SETTINGS.read_text())["python.terminal.activateEnvironment"]
        is True
    )


@pytest.mark.parametrize(
    "content",
    [
        "{\n  // unterminated\n  'key': 'val',\n}",
        '{"a": 1, "a": 2}',
        "['not', 'an', 'object']",
        "[1]",
    ],
)
def test_settings_malformed_file_is_skipped_with_a_warning(
    tmp_path, monkeypatch, mocker, content
):
    monkeypatch.chdir(tmp_path)
    SETTINGS.parent.mkdir()
    SETTINGS.write_text(content)

    executor = run(settings_manifest(), mocker)

    assert SETTINGS.read_text() == content
    if STATE.exists():
        assert record(SETTINGS) is None
    assert SETTINGS.as_posix() not in executor.journal.touched_paths
    warnings = [d for d in executor.diagnostics if d.severity is Severity.WARNING]
    assert any("Skipping IDE settings injection" in d.message for d in warnings)


def direct(mocker, *, exists=True):
    workspace = mocker.MagicMock()
    workspace.exists.return_value = exists
    fs = mocker.MagicMock()
    decisions = Reconciliation(
        settings_manifest(), UserConfig(), workspace, fs, mocker.MagicMock()
    )
    # A mock workspace has no filesystem nodes to validate.
    mocker.patch.object(decisions, "_validate_node")
    return decisions, workspace, fs


def test_settings_read_error_is_a_domain_error(mocker):
    decisions, workspace, fs = direct(mocker)
    workspace.read_bytes.side_effect = OSError(5, "Input/output error")

    with pytest.raises(FileSystemError) as caught:
        decisions._write_ide_settings()

    assert "inspect active IDE settings files" in caught.value.operation
    assert "settings.json" in caught.value.path
    fs.write_text.assert_not_called()


def test_settings_undecodable_file_is_a_domain_error(mocker):
    decisions, workspace, _ = direct(mocker)
    workspace.read_bytes.return_value = b"\xff"

    with pytest.raises(FileSystemError):
        decisions._write_ide_settings()


def test_settings_write_error_is_a_domain_error(mocker):
    decisions, _, fs = direct(mocker, exists=False)
    fs.write_text.side_effect = OSError(13, "Permission denied")

    with pytest.raises(FileSystemError) as caught:
        decisions._write_ide_settings()

    assert "reconcile settings.json configuration" in caught.value.operation
    assert "settings.json" in caught.value.path


def test_settings_write_failure_through_the_executor_rolls_back(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    executor = SystemExecutor(settings_manifest(), UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    mocker.patch.object(
        executor.fs, "write_bytes", side_effect=OSError(13, "Permission denied")
    )

    with pytest.raises(FileSystemError) as caught:
        executor.execute()

    assert "settings.json" in caught.value.path
    assert not SETTINGS.exists()
    assert not STATE.exists()
