import os
from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.errors import SecurityViolationError
from protostar.executor import SystemExecutor
from protostar.fs import safe_extract_zip
from protostar.manifest import EnvironmentManifest, SystemTask


@pytest.fixture
def mock_executor(tmp_path: Path, monkeypatch) -> SystemExecutor:
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    config = UserConfig(python_version="3.13")
    return SystemExecutor(manifest=manifest, config=config)


def test_path_traversal_file_injection(mock_executor: SystemExecutor, tmp_path: Path):
    mock_executor.manifest.file_injections = {"../../../../etc/passwd": "hacked"}
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        mock_executor._write_injected_files()


def test_path_traversal_directory_scaffolding(
    mock_executor: SystemExecutor, tmp_path: Path
):
    mock_executor.manifest.directories = {"../outside_dir"}
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        mock_executor._create_directories()


def test_path_traversal_symlink_bypass(mock_executor: SystemExecutor, tmp_path: Path):
    # Create a symlink in the temp dir that points outside (e.g. to /tmp)
    symlink_path = tmp_path / "logs"
    outside_dir = Path("/tmp")
    os.symlink(outside_dir, symlink_path)

    # Attempt to write into the symlink
    mock_executor.manifest.file_injections = {"logs/passwd": "hacked"}
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        mock_executor._write_injected_files()


def test_binary_safelist_deny(mock_executor: SystemExecutor):
    mock_executor.manifest.system_tasks = [
        SystemTask(command=["bash", "-c", "echo hacked"])
    ]
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        mock_executor._execute_tasks()

    mock_executor.manifest.system_tasks = [SystemTask(command=["env", "bash"])]
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        mock_executor._execute_tasks()


def test_binary_safelist_allow(mock_executor: SystemExecutor, monkeypatch):
    # Mock execute_subprocess to prevent actual execution
    from protostar import executor

    monkeypatch.setattr(executor, "execute_subprocess", lambda *args, **kwargs: None)

    # Also mock rich.console.Console to prevent test output pollution
    monkeypatch.setattr(
        executor,
        "console",
        type(
            "MockConsole",
            (),
            {
                "status": lambda self, msg: type(
                    "MockStatus",
                    (),
                    {"__enter__": lambda s: None, "__exit__": lambda s, *a: None},
                )()
            },
        )(),
    )

    mock_executor.manifest.system_tasks = [SystemTask(command=["uv", "run", "pytest"])]
    # Should not raise
    mock_executor._execute_tasks()


def test_safe_extract_zip_denies_traversal(tmp_path: Path):
    import zipfile

    # Create a malicious zip file
    zip_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../etc/passwd", "hacked")

    target_dir = tmp_path / "target"
    target_dir.mkdir()

    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        safe_extract_zip(zip_path, target_dir)
