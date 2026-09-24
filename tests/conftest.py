import os

os.environ["PYTHONIOENCODING"] = "utf-8"
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from protostar.manifest import EnvironmentManifest


@pytest.fixture(autouse=True)
def mock_global_config_file(mocker, tmp_path):
    """Mocks the global configuration file and clears singleton caches for all tests."""
    mock_config = tmp_path / "config.toml"
    mock_config.write_text("[env]\n")
    mocker.patch("protostar.config.CONFIG_FILE", mock_config)
    # Neither an inherited PROTOSTAR_CONFIG nor a selection leaked from an
    # earlier test may redirect the suite away from the mocked file.
    mocker.patch("protostar.config._config_override", None)
    mocker.patch.dict(os.environ, {}, clear=False)
    os.environ.pop("PROTOSTAR_CONFIG", None)
    from protostar.config import clear_user_config_cache
    from protostar.registry import clear_hook_registry_cache

    clear_user_config_cache()
    clear_hook_registry_cache()
    yield
    clear_user_config_cache()
    clear_hook_registry_cache()


@pytest.fixture(autouse=True)
def isolate_git_repository(monkeypatch):
    """Keeps a caller's git repository from leaking into any test.

    ``git push`` from a linked worktree exports ``GIT_DIR`` to the pre-push
    hook that runs this suite; a test running real git would then operate on
    the developer's repository instead of its temporary one.
    """
    from protostar.system import GIT_REPOSITORY_VARIABLES

    for name in GIT_REPOSITORY_VARIABLES:
        monkeypatch.delenv(name, raising=False)


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

        # Remove any leaked environment variables that might interfere with isolation
        env.pop("VIRTUAL_ENV", None)
        env.pop("PRE_COMMIT_HOME", None)
        env.pop("XDG_CACHE_HOME", None)
        env.pop("XDG_CONFIG_HOME", None)  # Ensure XDG_CONFIG_HOME doesn't leak
        env.pop("GIT_CONFIG_GLOBAL", None)
        env.pop("GIT_CONFIG_SYSTEM", None)

        # Force execution via the local python module instead of the global binary
        result = subprocess.run(
            [sys.executable, "-m", "protostar.cli", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=env,  # Inject the sandboxed environment
        )
        return result.returncode, result.stdout, result.stderr, tmp_path

    return _execute


@pytest.fixture
def seed_global_config(tmp_path: Path) -> Callable[[str], None]:
    """Dynamically seeds the sandboxed global configuration for integration tests."""

    def _seed(toml_content: str) -> None:
        config_dir = tmp_path / ".config" / "protostar"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.toml").write_text(toml_content)

    return _seed


class RecordedProgress:
    """Progress hook that records each step's start and outcome in order."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    @contextmanager
    def __call__(self, label: str) -> Iterator[None]:
        self.events.append(("start", label))
        try:
            yield
        except BaseException:
            self.events.append(("fail", label))
            raise
        self.events.append(("done", label))

    def steps(self) -> list[str]:
        """Returns the labels of steps that completed, in order."""
        return [label for event, label in self.events if event == "done"]


@pytest.fixture
def progress() -> RecordedProgress:
    """Provides a progress hook that records the engine's execution steps."""
    return RecordedProgress()
