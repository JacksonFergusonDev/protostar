import os

os.environ["PYTHONIOENCODING"] = "utf-8"
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from protostar.manifest import EnvironmentManifest
from protostar.system_deps import GlobalExecutable


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


@pytest.fixture(autouse=True)
def missing_executables(mocker) -> set[GlobalExecutable]:
    """Executables every test treats as missing from ``PATH``; none by default.

    Planning never reads the host's ``PATH`` in a test: add an executable to
    the returned set to simulate it missing.
    """
    missing: set[GlobalExecutable] = set()
    mocker.patch(
        "protostar.system_deps.installed",
        side_effect=lambda executable: executable not in missing,
    )
    return missing


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


class FakeRepository:
    """One in-memory forge repository: commits, tags, and branches."""

    def __init__(self, locator: str, default_branch: str = "main") -> None:
        self.locator = locator
        self.default_branch = default_branch
        self.commits: dict[str, dict[str, bytes]] = {}
        self.tags: dict[str, str] = {}
        self.branches: dict[str, str] = {}

    def commit(
        self,
        files: dict[str, str | bytes],
        *,
        tag: str | None = None,
        branch: str | None = None,
    ) -> str:
        """Records a commit of ``files``, optionally tagging or advancing a branch."""
        import hashlib

        revision = hashlib.sha1(
            f"{self.locator}:{len(self.commits)}".encode()
        ).hexdigest()
        self.commits[revision] = {
            path: content.encode() if isinstance(content, str) else content
            for path, content in files.items()
        }
        if tag is not None:
            self.tags[tag] = revision
        if branch is not None:
            self.branches[branch] = revision
        return revision

    def advertisement(self) -> bytes:
        """Returns the Git smart-HTTP ref advertisement for this repository."""

        def line(text: str) -> bytes:
            data = text.encode()
            return f"{len(data) + 4:04x}".encode() + data

        refs = [
            *(
                (revision, f"refs/heads/{name}")
                for name, revision in self.branches.items()
            ),
            *((revision, f"refs/tags/{name}") for name, revision in self.tags.items()),
        ]
        head = self.branches.get(self.default_branch, "0" * 40)
        capabilities = f"symref=HEAD:refs/heads/{self.default_branch} agent=fake"
        body = line("# service=git-upload-pack\n") + b"0000"
        body += line(f"{head} HEAD\0{capabilities}\n")
        for revision, name in refs:
            body += line(f"{revision} {name}\n")
        return body + b"0000"

    def archive(self, revision: str, *, tar: bool) -> bytes:
        """Returns the repository at ``revision`` as a forge would archive it."""
        import io
        import tarfile
        import zipfile

        top = f"{self.locator.rsplit('/', 1)[1]}-{revision}"
        buffer = io.BytesIO()
        if tar:
            with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
                for path, content in self.commits[revision].items():
                    info = tarfile.TarInfo(f"{top}/{path}")
                    info.size = len(content)
                    archive.addfile(info, io.BytesIO(content))
        else:
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(f"{top}/", "")
                for path, content in self.commits[revision].items():
                    archive.writestr(f"{top}/{path}", content)
        return buffer.getvalue()


class FakeForge:
    """Serves repositories over the URLs Protostar requests, entirely in memory."""

    def __init__(self) -> None:
        self.repositories: dict[str, FakeRepository] = {}
        self.plain: dict[str, bytes] = {}
        self.requests: list[str] = []
        self.offline = False

    def repository(self, locator: str, default_branch: str = "main") -> FakeRepository:
        """Creates the repository served at ``locator``."""
        repository = FakeRepository(locator, default_branch)
        self.repositories[locator] = repository
        return repository

    def respond(self, url: str) -> bytes:
        """Returns the body for ``url`` or raises the error a server would."""
        from urllib.error import HTTPError, URLError

        self.requests.append(url)
        if self.offline:
            raise URLError("offline")
        if url in self.plain:
            return self.plain[url]
        for locator, repository in self.repositories.items():
            owner_repo = locator.split("/", 3)[3]
            raw_prefix = f"https://raw.githubusercontent.com/{owner_repo}/"
            if not url.startswith((f"{locator}/", f"{locator}.git/", raw_prefix)):
                continue
            if url.endswith("/info/refs?service=git-upload-pack"):
                return repository.advertisement()
            for revision, files in repository.commits.items():
                marker = f"{revision}/"
                if url.endswith((f"{revision}.zip", f"-{revision}.zip")):
                    return repository.archive(revision, tar=False)
                if url.endswith(f"{revision}.tar.gz"):
                    return repository.archive(revision, tar=True)
                if marker in url:
                    path = url.split(marker, 1)[1]
                    if path in files:
                        return files[path]
        raise HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    def open(self, url: str, timeout: float | None = None):
        """Mimics ``OpenerDirector.open`` for a context-managed response."""
        import io
        from contextlib import closing

        body = self.respond(url)

        class Response(io.BytesIO):
            def read(self, size: int | None = -1) -> bytes:
                return super().read(-1 if size is None else size)

        return closing(Response(body))


@pytest.fixture
def forge(mocker) -> FakeForge:
    """Routes every template download and ref listing to an in-memory forge."""
    fake = FakeForge()
    mocker.patch("protostar.network._get_opener", return_value=fake)
    return fake
