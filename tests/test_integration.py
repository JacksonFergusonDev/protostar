import argparse
import shutil
import tomllib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from protostar.cli import handle_init
from protostar.manifest import CollisionStrategy

pytestmark = pytest.mark.integration


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv executable required")
@pytest.mark.parametrize(
    ("flags", "expected_tools"),
    [
        (["--ruff", "--pytest"], ["ruff", "pytest", "pytest-cov"]),
        (["--mypy"], ["mypy"]),
        (["--ruff", "--mypy", "--pytest"], ["ruff", "mypy", "pytest"]),
    ],
    ids=["ruff_pytest", "mypy_only", "full_suite"],
)
def test_python_environment_scaffolding(run_cli, flags, expected_tools):
    code, stdout, stderr, workspace = run_cli(
        "init", "--python", "--python-version", "3.12", *flags
    )

    assert code == 0, f"CLI Failed.\nSTDOUT: {stdout}\nSTDERR: {stderr}"

    # Attach diagnostic buffers to the existence assertions
    assert (workspace / ".venv").exists(), (
        f"Missing .venv\nSTDOUT: {stdout}\nSTDERR: {stderr}"
    )

    pyproject_path = workspace / "pyproject.toml"
    assert pyproject_path.exists(), (
        f"Missing pyproject.toml\nSTDOUT: {stdout}\nSTDERR: {stderr}"
    )

    with pyproject_path.open("rb") as f:
        config = tomllib.load(f)

    project_deps = config.get("dependency-groups", {}).get("dev", [])
    for tool in expected_tools:
        assert any(tool in dep for dep in project_deps), (
            f"Missing {tool} in dev dependencies"
        )


def test_pip_fallback_integration(run_cli, seed_global_config):
    """Verifies pip package manager gracefully degrades and outputs to requirements.txt."""
    seed_global_config('[env]\npython_package_manager = "pip"\n')

    code, stdout, stderr, workspace = run_cli(
        "init", "--python", "--python-version", "3.12", "--ruff"
    )

    assert code == 0, f"CLI Failed.\nSTDOUT: {stdout}\nSTDERR: {stderr}"
    assert (workspace / ".venv").exists()

    req_path = workspace / "requirements.txt"
    assert req_path.exists(), "pip fallback failed to generate requirements.txt"

    reqs = req_path.read_text().lower()
    assert "ruff" in reqs, "ruff missing from requirements.txt"


def test_orchestrator_idempotency(run_cli, seed_global_config):
    seed_global_config(
        '[dev.pyproject]\ncustom_ruff = "[tool.ruff]\\nline-length = 150"\n'
    )

    code1, stdout1, stderr1, workspace = run_cli(
        "init", "--python", "--python-version", "3.12", "--ruff"
    )
    assert code1 == 0, f"First execution failed.\nSTDERR: {stderr1}\nSTDOUT: {stdout1}"

    ignore_path = workspace / ".gitignore"

    # Assert existence before checking file size
    assert ignore_path.exists(), (
        f"Missing .gitignore\nSTDOUT: {stdout1}\nSTDERR: {stderr1}"
    )
    initial_ignore_size = ignore_path.stat().st_size

    # --force flag to authorize the headless merge
    code2, stdout2, stderr2, _ = run_cli(
        "init", "--python", "--python-version", "3.12", "--ruff", "--force"
    )
    assert code2 == 0, f"Second execution failed.\nSTDERR: {stderr2}\nSTDOUT: {stdout2}"

    assert ignore_path.stat().st_size == initial_ignore_size

    with (workspace / "pyproject.toml").open("rb") as f:
        config = tomllib.load(f)
        assert len(config.get("project", {}).get("dependencies", [])) == 0


@pytest.mark.parametrize(
    ("target", "name", "expected_files"),
    [
        (
            "cpp-class",
            "OrbitalMechanics",
            ["OrbitalMechanics.hpp", "OrbitalMechanics.cpp"],
        ),
        ("tex", "main", ["main.tex"]),
    ],
)
def test_generator_routing(run_cli, target, name, expected_files):
    code, stdout, stderr, workspace = run_cli("generate", target, name)
    assert code == 0, f"Generator failed.\nSTDERR: {stderr}\nSTDOUT: {stdout}"

    for filename in expected_files:
        assert (workspace / filename).exists()

    assert not (workspace / "pyproject.toml").exists()


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv executable required")
def test_python_version_cohesion_e2e(
    monkeypatch, mocker: MockerFixture, tmp_path: Path
) -> None:
    """Verifies Python version flags correctly propagate to subprocesses and config interpolations."""

    # Natively isolate all pathlib disk I/O to the sandbox
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "mock_config.toml")

    # Construct mock CLI arguments matching: `protostar init -p --python-version 3.10 --mypy --ruff`
    args = argparse.Namespace(
        command="init",
        PythonModule=True,
        python_version="3.10",
        MypyModule=True,
        RuffModule=True,
        docker=False,
    )

    # Execute the CLI handler. Because we are no longer mocking subprocess.run,
    # this will execute the actual system `uv init` command inside `tmp_path`.
    handle_init(args)

    pyproject_content = (tmp_path / "pyproject.toml").read_text()

    # 1. Assert uv successfully initialized the project and pinned the requested version natively
    assert 'requires-python = ">=3.10"' in pyproject_content, (
        "uv failed to pin the requested Python version in pyproject.toml."
    )

    # 2. Assert Mypy received the correct interpolated version from our orchestrator injection
    assert 'python_version = "3.10"' in pyproject_content, (
        "Mypy failed to interpolate the correct Python version."
    )

    # 3. Assert Ruff config was injected but does NOT have a hardcoded python version
    assert "[tool.ruff]" in pyproject_content
    assert "target-version" not in pyproject_content, (
        "Ruff should rely on requires-python natively, target-version should not be injected."
    )


def test_collision_overwrite_e2e(monkeypatch, mocker, tmp_path, seed_global_config):
    monkeypatch.chdir(tmp_path)

    # Strip the pytest environment variable so the Orchestrator doesn't default to MERGE
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    # 1. Setup existing conflicting workspace
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test"\n\n[tool.ruff]\nline-length = 150\n')

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    seed_global_config("[system]\nheadless_overwrite = true\n")

    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))

    # 2. Mock the interactive environment
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=True)
    mock_questionary = mocker.patch("questionary.select")
    mock_questionary.return_value.ask.return_value = CollisionStrategy.OVERWRITE

    # 3. Construct arguments mimicking: `protostar init -p --ruff`
    args = argparse.Namespace(
        command="init",
        PythonModule=True,
        python_version=None,
        RuffModule=True,
        docker=False,
    )

    handle_init(args)

    # 4. Verify TUI was triggered
    mock_questionary.assert_called_once()

    # 5. Verify the file was overwritten correctly (purging line-length=150 and replacing with 88)
    final_content = pyproject.read_text()

    assert '[project]\nname = "test"' in final_content, (
        "Should not wipe non-conflicting root tables"
    )
    assert "line-length = 150" not in final_content, "Failed to purge old state"
    assert "line-length = 88" in final_content, "Failed to inject new state"


@pytest.mark.skipif(
    shutil.which("uv") is None or shutil.which("git") is None,
    reason="uv and git executables required for pre-commit lifecycle",
)
def test_pre_commit_lifecycle_integration(run_cli, seed_global_config):
    seed_global_config("[env]\npre_commit = true\n")

    code, stdout, stderr, workspace = run_cli(
        "init", "--python", "--python-version", "3.12"
    )

    assert code == 0, f"CLI Failed.\nSTDOUT: {stdout}\nSTDERR: {stderr}"

    assert (workspace / ".git").exists(), "Git was not initialized"
    assert (workspace / ".pre-commit-config.yaml").exists(), "Pre-commit config missing"
    assert (workspace / ".git" / "hooks" / "pre-commit").exists(), (
        "Pre-commit binary failed to map git hooks"
    )


@pytest.mark.skipif(shutil.which("direnv") is None, reason="direnv executable required")
def test_direnv_lifecycle_integration(run_cli):
    """Verifies direnv shell commands execute without crashing in the post-install phase."""
    code, stdout, stderr, workspace = run_cli("init", "--python", "--direnv")

    assert code == 0, f"CLI Failed.\nSTDOUT: {stdout}\nSTDERR: {stderr}"
    assert (workspace / ".envrc").exists()


def test_virtual_env_isolation(run_cli, monkeypatch):
    """Verifies Protostar correctly executes even if the parent shell has an active virtual environment."""
    monkeypatch.setenv("VIRTUAL_ENV", "/fake/parent/venv")

    code, _, stderr, workspace = run_cli("init", "--python", "--python-version", "3.12")

    assert code == 0, f"Failed execution with parent VIRTUAL_ENV set.\nSTDERR: {stderr}"
    assert (workspace / "pyproject.toml").exists()


def test_crash_reporter_e2e(run_cli):
    """Verifies the hidden crash flag triggers a clean telemetry message in the terminal."""
    code, stdout, stderr, _ = run_cli("init", "--python", "--crash-test")

    # Ensure it hard-fails
    assert code == 1
    output = stdout + stderr

    # Assert structural integrity of the crash telemetry UI
    assert "CRITICAL FAILURE:" in output
    assert "Click here to open a GitHub issue with your telemetry" in output
