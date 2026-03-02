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
) -> Callable[..., tuple[int, str, str, Path]]:
    def _execute(*args: str) -> tuple[int, str, str, Path]:
        monkeypatch.chdir(tmp_path)

        result = subprocess.run(
            ["protostar", *args], capture_output=True, text=True, check=False
        )
        # Now returning a 4-tuple including stderr
        return result.returncode, result.stdout, result.stderr, tmp_path

    return _execute
