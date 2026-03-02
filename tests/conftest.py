import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from protostar.manifest import EnvironmentManifest


@pytest.fixture
def manifest():
    """Provides a fresh EnvironmentManifest for each test."""
    return EnvironmentManifest()


@pytest.fixture
def mock_path(mocker):
    """Mocks pathlib.Path to prevent accidental disk writes during tests."""
    return mocker.patch("protostar.orchestrator.Path")


@pytest.fixture
def run_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., tuple[int, str, Path]]:
    """Provides a sandboxed execution environment for the Protostar CLI.

    This fixture alters the current working directory to an ephemeral temporary
    path, ensuring that subprocess executions and disk I/O do not pollute the
    host file system. It intercepts standard output and returns the execution
    state alongside the isolated workspace path.

    Args:
        tmp_path: Pytest fixture providing a unique temporary directory.
        monkeypatch: Pytest fixture for safely mutating environment variables/state.

    Returns:
        A callable that accepts CLI arguments and returns a tuple containing:
        - The integer return code of the subprocess.
        - The captured standard output as a string.
        - The `pathlib.Path` object pointing to the temporary workspace.
    """

    def _execute(*args: str) -> tuple[int, str, Path]:
        monkeypatch.chdir(tmp_path)

        result = subprocess.run(
            ["protostar", *args], capture_output=True, text=True, check=False
        )
        return result.returncode, result.stdout, tmp_path

    return _execute
