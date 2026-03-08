import os
import subprocess
import sys
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

        # Sandbox the subprocess environment to prevent reading the user's global config
        env = os.environ.copy()

        # Preserve the uv cache so we don't redownload massive ML libraries
        # when the HOME directory changes
        if "UV_CACHE_DIR" not in env:
            if sys.platform == "darwin":
                env["UV_CACHE_DIR"] = str(Path.home() / "Library" / "Caches" / "uv")
            elif sys.platform == "win32":
                env["UV_CACHE_DIR"] = str(
                    Path.home() / "AppData" / "Local" / "uv" / "cache"
                )
            else:
                env["UV_CACHE_DIR"] = str(Path.home() / ".cache" / "uv")

        # Isolate the Protostar configuration and Git configurations
        env["HOME"] = str(tmp_path)
        env["USERPROFILE"] = str(tmp_path)

        # Force execution via the local python module instead of the global binary
        result = subprocess.run(
            [sys.executable, "-m", "protostar.cli", *args],
            capture_output=True,
            text=True,
            check=False,
            env=env,  # Inject the sandboxed environment
        )
        return result.returncode, result.stdout, result.stderr, tmp_path

    return _execute
