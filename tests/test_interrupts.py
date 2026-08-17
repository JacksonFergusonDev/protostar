from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protostar.cli import main
from protostar.config import UserConfig
from protostar.errors import ExecutionAbortedError, PartialExecutionAbortedError
from protostar.executor import SystemExecutor
from protostar.fs import atomic_write_text
from protostar.manifest import EnvironmentManifest
from protostar.orchestrator import Orchestrator


def test_partial_execution_aborted_error_formatting_with_paths() -> None:
    touched = {"src/app.py", "pyproject.toml", ".github/workflows/ci.yml"}
    err = PartialExecutionAbortedError(touched)

    assert err.touched_paths == touched
    err_str = str(err)
    assert (
        "Execution was interrupted before Protostar could finish setting up the"
        " environment." in err_str
    )
    assert "- .github/workflows/ci.yml" in err_str
    assert "- pyproject.toml" in err_str
    assert "- src/app.py" in err_str
    assert (
        "Note: External commands (e.g., uv, git) may have also modified"
        " workspace files." in err_str
    )
    assert err.hint is not None
    assert "Inspect the modified paths" in err.hint


def test_partial_execution_aborted_error_formatting_without_paths() -> None:
    err = PartialExecutionAbortedError(set())

    assert err.touched_paths == set()
    err_str = str(err)
    assert (
        "Execution was interrupted before Protostar could finish setting up the"
        " environment." in err_str
    )
    assert "The following paths were modified" not in err_str
    assert (
        "Note: External commands (e.g., uv, git) may have also modified"
        " workspace files." in err_str
    )
    assert err.hint is not None


def test_manifest_record_touch_relative_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()

    # Relative path
    manifest.record_touch(Path("src/main.py"))
    # Absolute path inside cwd
    manifest.record_touch(tmp_path / "pyproject.toml")
    # String path
    manifest.record_touch(".github/workflows/ci.yml")

    assert manifest.touched_paths == {
        "src/main.py",
        "pyproject.toml",
        ".github/workflows/ci.yml",
    }


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


def test_orchestrator_raises_partial_execution_aborted_error_when_files_touched(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    user_config = UserConfig()
    orchestrator = Orchestrator(modules=[], user_config=user_config)

    def fake_execute(self_executor: SystemExecutor) -> None:
        self_executor.manifest.record_touch("src")
        self_executor.manifest.record_touch("pyproject.toml")
        raise KeyboardInterrupt

    mocker.patch.object(SystemExecutor, "execute", fake_execute)

    with pytest.raises(PartialExecutionAbortedError) as exc_info:
        orchestrator.run()

    assert exc_info.value.touched_paths == {"src", "pyproject.toml"}


def test_orchestrator_raises_execution_aborted_error_when_no_files_touched(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    user_config = UserConfig()
    orchestrator = Orchestrator(modules=[], user_config=user_config)

    def fake_execute(self_executor: SystemExecutor) -> None:
        raise KeyboardInterrupt

    mocker.patch.object(SystemExecutor, "execute", fake_execute)

    with pytest.raises(
        ExecutionAbortedError, match=r"Environment initialization cancelled by user\."
    ):
        orchestrator.run()


def test_cli_routes_partial_execution_aborted_to_exit_130(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "protostar.cli.intercept_interactive_wizards",
        side_effect=PartialExecutionAbortedError({"pyproject.toml"}),
    )
    mock_exit = mocker.patch("protostar.cli.sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        main()

    mock_exit.assert_called_once_with(130)


def test_system_executor_records_touches_during_scaffolding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    manifest.add_directory("src")
    manifest.add_file_injection("src/hello.py", "print('hello')")
    manifest.add_vcs_ignore(".venv")
    manifest.wants_just = True

    config = UserConfig()
    executor = SystemExecutor(manifest, config)
    executor.execute()

    assert "src" in manifest.touched_paths
    assert "src/hello.py" in manifest.touched_paths
    assert ".gitignore" in manifest.touched_paths
    assert "justfile" in manifest.touched_paths
