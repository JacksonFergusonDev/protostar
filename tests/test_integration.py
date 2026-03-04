import argparse
import shutil
import tomllib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from protostar.cli import handle_init

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


def test_orchestrator_idempotency(run_cli):
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

    # Added the --python flag here
    code2, stdout2, stderr2, _ = run_cli(
        "init", "--python", "--python-version", "3.12", "--ruff"
    )
    assert code2 == 0, f"Second execution failed.\nSTDERR: {stderr2}\nSTDOUT: {stdout2}"

    assert ignore_path.stat().st_size == initial_ignore_size

    with (workspace / "pyproject.toml").open("rb") as f:
        config = tomllib.load(f)
        assert len(config.get("project", {}).get("dependencies", [])) == 0


@pytest.mark.parametrize(
    ("target", "name", "expected_files"),
    [
        # Updated to the correct CLI choices
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


def test_python_version_cohesion_e2e(
    monkeypatch, mocker: MockerFixture, tmp_path: Path
) -> None:
    """Verifies Python version flags correctly propagate to subprocesses and config interpolations."""

    # Natively isolate all pathlib disk I/O to the sandbox
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.config.CONFIG_FILE", tmp_path / "mock_config.toml")

    # Mock subprocess.run to prevent actual uv/git executions on the host
    mock_run = mocker.patch("subprocess.run")

    # Side-effect function to simulate `uv init` creating a pyproject.toml on disk
    def mock_subprocess_run_side_effect(cmd: list[str], *args, **kwargs) -> MagicMock:
        if cmd[:2] == ["uv", "init"]:
            # Extract the version passed to uv
            version = cmd[cmd.index("--python") + 1] if "--python" in cmd else "3.12"
            pyproject = tmp_path / "pyproject.toml"
            pyproject.write_text(f'[project]\nrequires-python = ">={version}"\n')

        return MagicMock(returncode=0)

    mock_run.side_effect = mock_subprocess_run_side_effect

    # Construct mock CLI arguments matching: `protostar init -p --python-version 3.10 --mypy --ruff`
    args = argparse.Namespace(
        command="init",
        PythonModule=True,
        python_version="3.10",
        MypyModule=True,
        RuffModule=True,
        docker=False,
    )

    # Execute the CLI handler
    handle_init(args)

    # 1. Assert uv received the correct Python version flag
    mock_run.assert_any_call(
        ["uv", "init", "--no-workspace", "--bare", "--pin-python", "--python", "3.10"],
        check=True,
        capture_output=True,
        text=True,
    )

    # 2. Assert Mypy received the correct interpolated version in pyproject.toml
    pyproject_content = (tmp_path / "pyproject.toml").read_text()
    assert 'python_version = "3.10"' in pyproject_content, (
        "Mypy failed to interpolate the correct Python version."
    )

    # 3. Assert Ruff config was injected but does NOT have a hardcoded python version
    assert "[tool.ruff]" in pyproject_content
    assert "target-version" not in pyproject_content, (
        "Ruff should rely on requires-python natively."
    )
