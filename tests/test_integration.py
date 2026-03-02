import shutil
import tomllib

import pytest

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
