from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protostar.cli import main
from protostar.config import UserConfig
from protostar.errors import ExecutionInterruptedError
from protostar.executor import SystemExecutor
from protostar.fs import atomic_write_text
from protostar.manifest import EnvironmentManifest
from protostar.models import RollbackContext
from protostar.orchestrator import Orchestrator


def test_executor_record_touch_relative_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    config = UserConfig()
    executor = SystemExecutor(manifest, config)

    # Relative path
    executor.journal.record_mutation(Path("src/main.py"))
    # Absolute path inside cwd
    executor.journal.record_mutation(tmp_path / "pyproject.toml")
    # String path
    executor.journal.record_mutation(Path(".github/workflows/ci.yml"))

    assert executor.journal.touched_paths == frozenset(
        {
            "src/main.py",
            "pyproject.toml",
            ".github/workflows/ci.yml",
        }
    )


def test_atomic_write_text_cleans_up_temp_file_on_keyboard_interrupt(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    target_file = tmp_path / "critical_file.txt"
    payload = "temporary payload"

    mocker.patch("os.replace", side_effect=KeyboardInterrupt)

    with pytest.raises(KeyboardInterrupt):
        atomic_write_text(target_file, payload)

    assert not target_file.exists()
    leftovers = [f for f in tmp_path.iterdir() if f.name.endswith(".tmp")]
    assert len(leftovers) == 0, (
        f"Temporary files leaked on KeyboardInterrupt: {leftovers}"
    )


def test_orchestrator_raises_execution_interrupted_error_when_files_touched(
    mocker: MockerFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    user_config = UserConfig()
    orchestrator = Orchestrator(modules=[], user_config=user_config)

    def fake_execute(self_executor: SystemExecutor) -> None:
        self_executor.journal.record_mutation(Path("src"))
        self_executor.journal.record_mutation(Path("pyproject.toml"))
        raise KeyboardInterrupt

    mocker.patch.object(SystemExecutor, "execute", fake_execute)
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = orchestrator.plan()

    with pytest.raises(ExecutionInterruptedError) as exc_info:
        orchestrator.execute(manifest)

    assert exc_info.value.rollback_context is not None
    assert exc_info.value.rollback_context.touched_paths == frozenset(
        {"src", "pyproject.toml"}
    )


def test_orchestrator_raises_execution_interrupted_error_when_no_files_touched(
    mocker: MockerFixture,
) -> None:
    user_config = UserConfig()
    orchestrator = Orchestrator(modules=[], user_config=user_config)

    def fake_execute(_self_executor: SystemExecutor) -> None:
        raise KeyboardInterrupt

    mocker.patch.object(SystemExecutor, "execute", fake_execute)
    mocker.patch.object(Path, "exists", return_value=False)

    manifest = orchestrator.plan()

    with pytest.raises(ExecutionInterruptedError):
        orchestrator.execute(manifest)


def test_cli_routes_execution_interrupted_to_exit_130(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards",
        side_effect=ExecutionInterruptedError(
            RollbackContext(frozenset({"pyproject.toml"}), (), None, False)
        ),
    )
    mock_exit = mocker.patch("protostar.cli.main.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(130)


def test_system_executor_records_touches_during_scaffolding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    manifest.filesystem.add_directory("src")
    manifest.filesystem.add_file_injection("src/hello.py", "print('hello')")
    manifest.filesystem.add_vcs_ignore(".venv")
    manifest.tooling.wants_just = True

    config = UserConfig()
    executor = SystemExecutor(manifest, config)
    executor.execute()

    assert "src" in executor.journal.touched_paths
    assert "src/hello.py" in executor.journal.touched_paths
    assert ".gitignore" in executor.journal.touched_paths
    assert "justfile" in executor.journal.touched_paths
