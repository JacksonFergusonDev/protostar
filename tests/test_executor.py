import hashlib
import json
import subprocess
import tomllib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import tomlkit

from protostar.config import UserConfig
from protostar.errors import (
    ConfigurationError,
    FileSystemError,
)
from protostar.executor import SystemExecutor
from protostar.manifest import CollisionStrategy, EnvironmentManifest, Severity

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_config() -> UserConfig:
    """Provides a fresh baseline configuration for DI injections."""
    return UserConfig()


def test_executor_writes_injected_files(mocker, mock_config):
    """Test that the executor flushes queued file injections to disk."""
    manifest = EnvironmentManifest()
    manifest.add_file_injection(".test_config.yaml", "mock content")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_mkdir = mocker.patch("protostar.executor.Path.mkdir")
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_injected_files()

    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_write.assert_called_once_with(Path(".test_config.yaml"), "mock content")


def test_executor_append_files_late_binding(mocker, mock_config):
    """Test that configuration payloads are interpolated with the active python version."""
    manifest = EnvironmentManifest()
    manifest.add_file_append(
        "pyproject.toml", 'python_version = "<% PYTHON_VERSION %>"'
    )
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch(
        "protostar.executor.Path.read_text",
        return_value='[project]\nrequires-python = ">=3.11"\n',
    )

    mock_file = mocker.mock_open(read_data=b'[project]\nrequires-python = ">=3.11"\n')
    mocker.patch("protostar.executor.Path.open", mock_file)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._append_files()

    written_data = mock_write.call_args[0][1]
    parsed_toml = tomllib.loads(written_data)

    # Assert structural integrity rather than string presence
    assert parsed_toml["python_version"] == "3.11"


def test_executor_writes_pre_commit_config(mocker, mock_config):
    """Test that the executor concatenates hooks and interpolates only production Mypy dependencies."""
    manifest = EnvironmentManifest()
    manifest.wants_pre_commit = True
    manifest.add_dependency("fastapi")
    manifest.add_dev_dependency("pytest")

    hook_payload = """  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies:
<% MYPY_DEPENDENCIES %>"""
    manifest.add_pre_commit_hook(hook_payload)

    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_pre_commit_config()

    written_data = mock_write.call_args[0][1]

    assert "# Generic hooks (configured to IGNORE Python)" in written_data
    assert "trailing-whitespace" in written_data
    assert "id: mypy" in written_data
    assert "<% MYPY_DEPENDENCIES %>" not in written_data
    assert "- fastapi" in written_data
    # Verify dev dependencies are deliberately excluded from the mypy hook
    assert "- pytest" not in written_data


def test_executor_writes_pre_commit_config_local_toolchain(mocker, mock_config):
    """Test that the executor aggregates local pre-commit hooks under a single repo: local block."""
    manifest = EnvironmentManifest()
    manifest.wants_pre_commit = True

    ruff_payload = """      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types: [python]
        require_serial: true

      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types: [python]
        require_serial: true"""
    manifest.add_pre_commit_local_hook(ruff_payload)

    mypy_payload = """      - id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        types: [python]
        pass_filenames: true"""
    manifest.add_pre_commit_local_hook(mypy_payload)

    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_pre_commit_config()

    written_data = mock_write.call_args[0][1]

    assert "  # Local Python Toolchain (Managed via uv.lock)" in written_data
    assert "  - repo: local" in written_data
    assert "    hooks:" in written_data
    assert "- id: ruff-check" in written_data
    assert "entry: uv run ruff check --fix" in written_data
    assert "- id: ruff-format" in written_data
    assert "entry: uv run ruff format" in written_data
    assert "- id: mypy" in written_data
    assert "entry: uv run mypy" in written_data
    assert "language: system" in written_data


def test_executor_writes_pre_commit_config_local_and_remote_hooks(mocker, mock_config):
    """Test that the executor formats both local and remote repository hooks."""
    manifest = EnvironmentManifest()
    manifest.wants_pre_commit = True

    ruff_payload = """      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types: [python]
        require_serial: true"""
    manifest.add_pre_commit_local_hook(ruff_payload)

    remote_payload = """  - repo: https://github.com/DavidAnson/markdownlint-cli2
    rev: v0.23.0
    hooks:
      - id: markdownlint-cli2
        args: ["--fix"]"""
    manifest.add_pre_commit_hook(remote_payload)

    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_pre_commit_config()

    written_data = mock_write.call_args[0][1]

    assert "# Generic hooks (configured to IGNORE Python)" in written_data
    assert "  # Local Python Toolchain (Managed via uv.lock)" in written_data
    assert "  - repo: local" in written_data
    assert "- id: ruff-check" in written_data
    assert "  - repo: https://github.com/DavidAnson/markdownlint-cli2" in written_data
    assert "- id: markdownlint-cli2" in written_data


def test_executor_write_pre_commit_config_empty_deps(mocker, mock_config):
    """Test that mypy late-binding cleanly strips additional_dependencies if no production dependencies exist."""
    manifest = EnvironmentManifest()
    manifest.wants_pre_commit = True

    hook_payload = """  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies:
<% MYPY_DEPENDENCIES %>"""
    manifest.add_pre_commit_hook(hook_payload)

    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_pre_commit_config()
    written_data = mock_write.call_args[0][1]

    assert "id: mypy" in written_data
    # Verify the entire key and token block was stripped cleanly
    assert "additional_dependencies" not in written_data
    assert "<% MYPY_DEPENDENCIES %>" not in written_data
    assert "[]" not in written_data


def test_executor_writes_dockerignore(mocker, mock_config):
    """Test that the executor aggregates base ignores and vcs ignores for docker."""
    manifest = EnvironmentManifest()
    manifest.add_vcs_ignore("custom_build_artifact/")
    executor = SystemExecutor(manifest, mock_config, docker=True)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch("protostar.executor.Path.read_text", return_value=".env\n")

    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_docker_artifacts()

    written_data = mock_write.call_args[0][1]
    assert "custom_build_artifact/" in written_data
    assert ".git/" in written_data
    assert "README*" in written_data


def test_executor_writes_gitignore(mocker, mock_config):
    """Test that .gitignore is safely updated without duplicating existing lines."""
    manifest = EnvironmentManifest()
    manifest.add_vcs_ignore("new_ignore.txt")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch(
        "protostar.executor.Path.read_text", return_value="existing_ignore.txt\n"
    )

    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_ignores()
    mock_write.assert_called_once_with(
        Path(".gitignore"), "existing_ignore.txt\nnew_ignore.txt\n"
    )


def test_executor_writes_vscode_settings(mocker, mock_config):
    """Test that IDE settings merge correctly with existing JSON."""
    manifest = EnvironmentManifest()
    manifest.add_ide_setting("files.exclude", {"**/.venv": True})
    executor = SystemExecutor(manifest, mock_config)

    existing_settings = {"files.exclude": {"**/node_modules": True}}

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch(
        "protostar.executor.Path.read_text",
        return_value=json.dumps(existing_settings),
    )
    mock_write_text = mocker.patch("protostar.executor.atomic_write_text")
    mocker.patch("protostar.executor.Path.mkdir")

    executor._write_ide_settings()

    written_data = mock_write_text.call_args[0][1]
    parsed_write = json.loads(written_data)

    assert "**/.venv" in parsed_write["files.exclude"]
    assert "**/node_modules" in parsed_write["files.exclude"]


def test_executor_creates_directories(mocker, mock_config):
    """Test that the executor generates all requested workspace directories."""
    manifest = EnvironmentManifest()
    manifest.add_directory("data")
    manifest.add_directory("src/core")
    executor = SystemExecutor(manifest, mock_config)

    mock_mkdir = mocker.patch("protostar.executor.Path.mkdir")

    executor._create_directories()

    assert mock_mkdir.call_count == 2
    mock_mkdir.assert_any_call(parents=True, exist_ok=True)


def test_executor_writes_dockerignore_with_uv(mocker, mock_config):
    """Test that the executor appends .python-version to .dockerignore when uv is used."""
    manifest = EnvironmentManifest()
    manifest.add_system_task(["uv", "init", "--no-workspace", "--bare", "--pin-python"])
    executor = SystemExecutor(manifest, mock_config, docker=True)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_docker_artifacts()

    written_paths = {call[0][0]: call[0][1] for call in mock_write.call_args_list}
    assert ".python-version" in written_paths[Path(".dockerignore")]
    assert "FROM ghcr.io/astral-sh/uv:python" in written_paths[Path("Dockerfile")]


def test_executor_writes_dockerfile_default(mocker, mock_config):
    """Test that the executor writes a multi-stage Dockerfile with default configuration."""
    manifest = EnvironmentManifest()
    manifest.metadata = {"python_version": "3.12"}
    executor = SystemExecutor(manifest, mock_config, docker=True)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_docker_artifacts()

    written_paths = {call[0][0]: call[0][1] for call in mock_write.call_args_list}
    dockerfile_content = written_paths[Path("Dockerfile")]

    assert (
        "FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder"
        in dockerfile_content
    )
    assert "FROM python:3.12-slim-bookworm AS runtime" in dockerfile_content
    assert "RUN useradd -m -u 10001 appuser" in dockerfile_content
    assert "USER appuser" in dockerfile_content
    assert "COPY --from=builder --chown=appuser:appuser /app /app" in dockerfile_content
    assert 'ENV PATH="/app/.venv/bin:$PATH"' in dockerfile_content
    assert 'CMD ["python", "-m", "protostar"]' in dockerfile_content


def test_executor_writes_dockerfile_with_api_preset(mocker, mock_config):
    """Test that the executor writes an API-tailored Dockerfile when FastAPI/uvicorn is present."""
    manifest = EnvironmentManifest()
    manifest.dependencies = ["fastapi", "uvicorn"]
    manifest.metadata = {"docker_port": "8080", "python_version": "3.13"}
    executor = SystemExecutor(manifest, mock_config, docker=True)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_docker_artifacts()

    written_paths = {call[0][0]: call[0][1] for call in mock_write.call_args_list}
    dockerfile_content = written_paths[Path("Dockerfile")]

    assert "EXPOSE 8080" in dockerfile_content
    assert (
        'CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8080"]'
        in dockerfile_content
    )


def test_executor_writes_dockerfile_with_cli_preset(mocker, mock_config):
    """Test that the executor writes a CLI-tailored Dockerfile when typer/project.scripts is present."""
    manifest = EnvironmentManifest()
    manifest.dependencies = ["typer"]
    manifest.add_file_append(
        "pyproject.toml", "[project.scripts]\nmy-cli = 'my_cli.cli:app'\n"
    )
    executor = SystemExecutor(manifest, mock_config, docker=True)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_docker_artifacts()

    written_paths = {call[0][0]: call[0][1] for call in mock_write.call_args_list}
    dockerfile_content = written_paths[Path("Dockerfile")]

    assert 'ENTRYPOINT ["protostar"]' in dockerfile_content


def test_executor_skips_dockerfile_on_collision(mocker, mock_config):
    """Test that existing Dockerfile is skipped when collision strategy is not overwrite."""
    manifest = EnvironmentManifest()
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest, mock_config, docker=True)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch("protostar.executor.Path.read_text", return_value="")
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_docker_artifacts()

    written_paths = [call[0][0] for call in mock_write.call_args_list]
    assert Path(".dockerignore") in written_paths
    assert Path("Dockerfile") not in written_paths
    assert any(
        "Skipping Dockerfile generation" in d.message for d in manifest.diagnostics
    )


def test_write_dockerfile_handles_os_error(mocker, mock_config):
    """Test that Dockerfile write errors raise FileSystemError."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config, docker=True)

    mocker.patch("protostar.executor.Path.exists", return_value=False)

    def write_side_effect(path, content):
        if path == Path("Dockerfile"):
            raise OSError(13, "Permission denied")

    mocker.patch("protostar.executor.atomic_write_text", side_effect=write_side_effect)

    with pytest.raises(FileSystemError) as exc_info:
        executor._write_docker_artifacts()

    assert (
        "scaffold container runtime configurations (Dockerfile)"
        in exc_info.value.operation
    )
    assert "Dockerfile" in exc_info.value.path


def test_executor_writes_vscode_settings_jsonc_abort(
    monkeypatch, mocker, tmp_path, mock_config
):
    """Test that IDE settings injection safely aborts if existing JSON has comments."""
    monkeypatch.chdir(tmp_path)

    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    settings_file = vscode_dir / "settings.json"
    settings_file.write_text("// My custom comment\n{}")

    manifest = EnvironmentManifest()
    manifest.add_ide_setting("files.exclude", {"**/.venv": True})
    executor = SystemExecutor(manifest, mock_config)

    executor._write_ide_settings()

    assert any(
        "is malformed" in d.message
        for d in executor.manifest.diagnostics
        if d.severity == Severity.WARNING
    )


def test_executor_writes_injected_files_overwrite(mocker, mock_config):
    """Test that file injections bypass the exists() guard if OVERWRITE is active."""
    manifest = EnvironmentManifest()
    manifest.collision_strategy = CollisionStrategy.OVERWRITE
    manifest.add_file_injection(".test_config.yaml", "new content")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_injected_files()
    mock_write.assert_called_once_with(Path(".test_config.yaml"), "new content")


def test_executor_mkdir_os_error_propagation(mocker, mock_config):
    """Test that the executor correctly propagates OSErrors during directory creation."""
    manifest = EnvironmentManifest()
    manifest.add_directory("protected_dir")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch(
        "protostar.executor.Path.mkdir", side_effect=OSError("Read-only file system")
    )

    with pytest.raises(FileSystemError, match="Read-only file system"):
        executor._create_directories()


def test_executor_write_text_permission_error_propagation(mocker, mock_config):
    """Test that the executor propagates PermissionErrors during file injections."""
    manifest = EnvironmentManifest()
    manifest.add_file_injection("system_config.yaml", "secret")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mocker.patch("protostar.executor.Path.mkdir")
    mocker.patch(
        "protostar.executor.atomic_write_text",
        side_effect=PermissionError("Permission denied"),
    )

    # CHANGED: Expect FileSystemError instead of raw PermissionError
    with pytest.raises(FileSystemError, match="Permission denied"):
        executor._write_injected_files()


def test_executor_deep_merge_tomlkit(mock_config):
    """Test the recursive dictionary merge algorithm using chaotic tomlkit structures."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    base_content = (FIXTURES_DIR / "base_complex.toml").read_text()
    payload_content = (FIXTURES_DIR / "payload_complex.toml").read_text()

    base_doc = tomlkit.parse(base_content)
    payload_doc = tomlkit.parse(payload_content)

    executor._deep_merge_tomlkit(base_doc, payload_doc)

    merged_dict = base_doc.unwrap()

    # 1. Verify scalar overrides (line-length changed 120 -> 88)
    assert merged_dict["tool"]["ruff"]["line-length"] == 88

    # 2. Verify non-colliding existing keys were preserved
    assert merged_dict["tool"]["ruff"]["target-version"] == "py310"
    assert merged_dict["project"]["name"] == "protostar-test"

    # 3. Verify nested list replacements
    assert "UP" in merged_dict["tool"]["ruff"]["lint"]["select"]

    # 4. Verify new root tables were injected
    assert merged_dict["tool"]["mypy"]["strict"] is True

    # 5. Verify Array of Tables (AoT) concatenation (MERGE strategy default behavior)
    assert len(merged_dict["tool"]["mypy"]["overrides"]) == 2
    assert merged_dict["tool"]["mypy"]["overrides"][0]["module"] == "tests.*"
    assert merged_dict["tool"]["mypy"]["overrides"][1]["module"] == "legacy_module.*"

    # 6. Verify comments survived the AST manipulation
    dumped = tomlkit.dumps(base_doc)
    assert "# We expect this comment to survive the merge" in dumped
    assert "# A random comment inside an array" in dumped


def test_executor_deep_merge_tomlkit_empty_aot(mock_config):
    """Test that injecting an empty Array of Tables safely bypasses the newline append logic."""
    import tomlkit

    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    base = tomlkit.document()
    payload = tomlkit.document()

    # Inject a structurally empty Array of Tables
    payload.append("empty_array", tomlkit.aot())

    executor._deep_merge_tomlkit(base, payload)

    result = base.unwrap()
    assert "empty_array" in result
    assert len(result["empty_array"]) == 0


def test_executor_append_files_ast_no_op_write(mocker, mock_config):
    """Test that file writing is bypassed if the merged AST yields identical content."""
    original_content = "[tool.fake_tool]\nstrict = true\n"

    manifest = EnvironmentManifest()
    # Queue a payload that is perfectly identical to the existing base document
    manifest.add_file_append("pyproject.toml", original_content)
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch("protostar.executor.Path.read_text", return_value=original_content)

    # mock_open resolves the python_version lookup gracefully
    mock_file = mocker.mock_open(read_data=original_content.encode("utf-8"))
    mocker.patch("protostar.executor.Path.open", mock_file)

    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._append_files()

    # The AST was parsed, evaluated, and merged (ast_mutated = True),
    # but since the stripped strings matched, it correctly avoided disk I/O.
    mock_write.assert_not_called()


def test_executor_deep_merge_tomlkit_new_populated_aot(mock_config):
    """Test that injecting a novel, populated Array of Tables appends a newline to its last element."""
    import tomlkit

    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    base = tomlkit.document()
    # Inject a populated AoT that does not exist in the base document
    payload = tomlkit.parse("[[plugins]]\nname = 'alpha'\n[[plugins]]\nname = 'beta'\n")

    executor._deep_merge_tomlkit(base, payload)

    dumped = tomlkit.dumps(base)

    # Verify the AoT was injected and the newline was appended to the final element
    assert "name = 'beta'\n\n" in dumped

    result = base.unwrap()
    assert len(result["plugins"]) == 2
    assert result["plugins"][1]["name"] == "beta"


def test_executor_append_files_ast_merge(mocker, mock_config):
    """Test that _append_files mutates the TOML AST logically based on the MERGE strategy."""
    base_content = (FIXTURES_DIR / "base_complex.toml").read_text()
    payload_content = (FIXTURES_DIR / "payload_complex.toml").read_text()

    manifest = EnvironmentManifest()
    manifest.collision_strategy = CollisionStrategy.MERGE
    manifest.add_file_append("pyproject.toml", payload_content)
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch("protostar.executor.Path.read_text", return_value=base_content)

    # mock_open needs to return the pyproject string to resolve the python version
    mock_file = mocker.mock_open(read_data=base_content.encode("utf-8"))
    mocker.patch("protostar.executor.Path.open", mock_file)

    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._append_files()
    written_data = mock_write.call_args[0][1]

    parsed_toml = tomllib.loads(written_data)

    # Verify structural merge logic via the AST
    assert parsed_toml["tool"]["mypy"]["strict"] is True
    assert parsed_toml["tool"]["ruff"]["line-length"] == 88
    assert parsed_toml["tool"]["ruff"]["target-version"] == "py310"  # Preserved!

    # Verify the late-binding variable <% PYTHON_VERSION %> was interpolated correctly
    # based on the `requires-python = ">=3.11"` in base_complex.toml
    assert parsed_toml["tool"]["mypy"]["python_version"] == "3.11"


def test_executor_append_files_ast_overwrite(mocker, mock_config):
    """Test that the OVERWRITE strategy completely replaces colliding TOML tables."""
    base_content = (FIXTURES_DIR / "base_complex.toml").read_text()
    payload_content = (FIXTURES_DIR / "payload_complex.toml").read_text()

    manifest = EnvironmentManifest()
    manifest.collision_strategy = CollisionStrategy.OVERWRITE
    manifest.add_file_append("pyproject.toml", payload_content)
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch("protostar.executor.Path.read_text", return_value=base_content)

    mock_file = mocker.mock_open(read_data=base_content.encode("utf-8"))
    mocker.patch("protostar.executor.Path.open", mock_file)

    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._append_files()

    written_data = mock_write.call_args[0][1]
    parsed_toml = tomllib.loads(written_data)

    # Verify the table was entirely replaced in the AST, not just merged
    assert parsed_toml["tool"]["mypy"]["strict"] is True
    assert parsed_toml["tool"]["ruff"]["line-length"] == 88

    # Under OVERWRITE, target-version should have been purged because it existed
    # in the old [tool.ruff] table but not in the payload [tool.ruff] table.
    assert "target-version" not in parsed_toml["tool"]["ruff"]

    # Under OVERWRITE, the original [[tool.mypy.overrides]] should be wiped
    assert len(parsed_toml["tool"]["mypy"]["overrides"]) == 1
    assert parsed_toml["tool"]["mypy"]["overrides"][0]["module"] == "legacy_module.*"


def test_executor_write_pre_commit_config_skips_existing_merge(mocker, mock_config):
    """Test that pre-commit generation aborts if file exists and strategy is not OVERWRITE."""
    manifest = EnvironmentManifest()
    manifest.wants_pre_commit = True
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_pre_commit_config()
    mock_write.assert_not_called()


def test_executor_deep_merge_tomlkit_aot_append(mock_config):
    """Test that arrays of tables (AoT) are appended to when not using OVERWRITE."""
    import tomlkit

    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    base = tomlkit.parse("[[my_array]]\nval = 1\n")
    payload = tomlkit.parse("[[my_array]]\nval = 2\n")

    executor._deep_merge_tomlkit(base, payload, overwrite=False)

    result = base.unwrap()
    assert len(result["my_array"]) == 2
    assert result["my_array"][0]["val"] == 1
    assert result["my_array"][1]["val"] == 2


def test_executor_validate_targets_success(mocker, mock_config):
    """Test that pre-execution validation passes silently on valid TOML files."""

    manifest = EnvironmentManifest()
    manifest.add_file_append("pyproject.toml", "[tool.ruff]")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)

    mock_file = mocker.mock_open(read_data=b'[project]\nname = "test"\n')
    mocker.patch("protostar.executor.Path.open", mock_file)

    # Should execute cleanly without raising any exceptions
    executor._validate_targets()


def test_executor_validate_targets_malformed_toml(mocker, mock_config):
    """Test that malformed existing TOML triggers a ConfigurationError during pre-execution."""
    manifest = EnvironmentManifest()
    manifest.add_file_append("test.toml", "[section]\nkey = 'val'\n")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)

    mock_file = mocker.mock_open(read_data=b"[invalid toml == \n")
    mocker.patch("protostar.executor.Path.open", mock_file)

    with pytest.raises(
        ConfigurationError, match="Syntax error in existing workspace file"
    ):
        executor._validate_targets()


def test_executor_append_files_malformed_payload_toml(mocker, mock_config):
    """Test that malformed payload TOML triggers a ConfigurationError during execution."""
    manifest = EnvironmentManifest()
    manifest.add_file_append("test.toml", "[invalid payload == \n")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch(
        "protostar.executor.Path.read_text", return_value="[existing]\nval = 1\n"
    )

    mock_file = mocker.mock_open(read_data=b"[project]\n")
    mocker.patch("protostar.executor.Path.open", mock_file)

    with pytest.raises(
        ConfigurationError, match="Failed to parse injected TOML payload"
    ):
        executor._append_files()


def test_executor_append_files_string_fallback_redundant(mocker, mock_config):
    """Test that the string fallback skips writing if the payload hash is already in the file."""
    payload = "line1\nline2"
    payload_hash = hashlib.md5(payload.encode("utf-8")).hexdigest()[:8]
    existing_content = f"existing\n# --- Protostar Injection: {payload_hash} ---\n{payload}\n# --- End Protostar Injection ---"

    manifest = EnvironmentManifest()
    manifest.add_file_append("test.txt", payload)
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.read_text", return_value=existing_content)
    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._append_files()
    mock_write.assert_not_called()


def test_executor_early_returns_on_empty_manifest(mocker, mock_config):
    """Test that functions execute early returns when manifest data is absent."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)
    mock_exists = mocker.patch("protostar.executor.Path.exists")

    executor._write_ignores()
    executor._write_ide_settings()
    executor._install_dependencies()

    mock_exists.assert_not_called()


def test_executor_append_files_string_fallback_append(mocker, mock_config):
    """Test that the string fallback successfully appends missing payloads wrapped in hash markers."""
    manifest = EnvironmentManifest()
    manifest.add_file_append("config.ini", "new_payload_1")
    manifest.add_file_append("config.ini", "new_payload_2")
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch("protostar.executor.Path.read_text", return_value="existing_data")
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._append_files()

    hash1 = hashlib.md5(b"new_payload_1").hexdigest()[:8]
    hash2 = hashlib.md5(b"new_payload_2").hexdigest()[:8]
    expected_data = (
        "existing_data\n\n"
        f"# --- Protostar Injection: {hash1} ---\nnew_payload_1\n# --- End Protostar Injection ---\n\n"
        f"# --- Protostar Injection: {hash2} ---\nnew_payload_2\n# --- End Protostar Injection ---\n"
    )

    written_data = mock_write.call_args[0][1]
    assert written_data == expected_data


def test_executor_deep_merge_tomlkit_table_collision(mock_config):
    """Test that TOML table injections safely skip when colliding with a scalar type."""
    import tomlkit

    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    base = tomlkit.parse("tool = 'not a table'\n")
    payload = tomlkit.parse("[tool]\nnew_key = 1\n")

    executor._deep_merge_tomlkit(base, payload)

    assert base["tool"] == "not a table"
    warnings = [
        d for d in executor.manifest.diagnostics if d.severity == Severity.WARNING
    ]
    assert len(warnings) == 1


def test_executor_deep_merge_tomlkit_aot_collision(mock_config):
    """Test that TOML Array of Tables injections safely skip when colliding with a scalar type."""
    import tomlkit

    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    base = tomlkit.parse("my_array = 'string'\n")
    payload = tomlkit.parse("[[my_array]]\nval = 1\n")

    executor._deep_merge_tomlkit(base, payload)

    assert base["my_array"] == "string"
    warnings = [
        d for d in executor.manifest.diagnostics if d.severity == Severity.WARNING
    ]
    assert len(warnings) == 1


def test_executor_deep_merge_tomlkit_aot_overwrite(mock_config):
    """Test that the OVERWRITE strategy replaces an entire Array of Tables."""
    import tomlkit

    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    base = tomlkit.parse("[[my_array]]\nval = 1\n")
    payload = tomlkit.parse("[[my_array]]\nval = 2\n")

    executor._deep_merge_tomlkit(base, payload, overwrite=True)

    result = base.unwrap()
    assert len(result["my_array"]) == 1
    assert result["my_array"][0]["val"] == 2


def test_executor_append_files_early_return(mocker, mock_config):
    """Test that _append_files cleanly returns if there are no payloads queued."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    mock_exists = mocker.patch("protostar.executor.Path.exists")
    executor._append_files()

    mock_exists.assert_not_called()


def test_executor_writes_vscode_settings_empty_file(monkeypatch, tmp_path, mock_config):
    """Test that an entirely empty settings.json file is safely initialized as a dictionary."""
    import json

    monkeypatch.chdir(tmp_path)

    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    settings_file = vscode_dir / "settings.json"
    settings_file.write_text("   \n  \t")  # Empty except for whitespace

    manifest = EnvironmentManifest()
    manifest.add_ide_setting("files.exclude", {"**/.venv": True})
    executor = SystemExecutor(manifest, mock_config)

    executor._write_ide_settings()

    written_data = json.loads(settings_file.read_text())
    assert "**/.venv" in written_data["files.exclude"]


def test_executor_writes_vscode_settings_root_not_dict(
    monkeypatch, mocker, tmp_path, mock_config
):
    """Test that a settings.json file containing a non-dict primitive triggers the abort sequence."""
    monkeypatch.chdir(tmp_path)

    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    settings_file = vscode_dir / "settings.json"
    settings_file.write_text('["I am an array, not a dictionary"]')

    manifest = EnvironmentManifest()
    manifest.add_ide_setting("files.exclude", {"**/.venv": True})
    executor = SystemExecutor(manifest, mock_config)

    executor._write_ide_settings()

    warnings = [
        d for d in executor.manifest.diagnostics if d.severity == Severity.WARNING
    ]
    assert len(warnings) == 1
    assert "is malformed" in warnings[0].message


def test_executor_lifecycle_ordering(mocker, mock_config):
    """Test that the executor strictly adheres to the execution DAG order."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    # Use a parent mock to track chronological execution sequence across methods
    manager = mocker.Mock()

    manager.attach_mock(mocker.patch.object(executor, "_execute_tasks"), "sys_tasks")
    manager.attach_mock(
        mocker.patch.object(executor, "_install_dependencies"), "install"
    )
    manager.attach_mock(
        mocker.patch.object(executor, "_execute_post_install_tasks"), "post_install"
    )

    # Silence all other disk I/O mutations
    mocker.patch.object(executor, "_validate_targets")
    mocker.patch.object(executor, "_create_directories")
    mocker.patch.object(executor, "_write_injected_files")
    mocker.patch.object(executor, "_write_pre_commit_config")
    mocker.patch.object(executor, "_append_files")
    mocker.patch.object(executor, "_write_ignores")
    mocker.patch.object(executor, "_write_docker_artifacts")
    mocker.patch.object(executor, "_write_ide_settings")

    executor.execute()

    # Filter calls to isolate our specific topological phases
    actual_calls = [
        call
        for call in manager.mock_calls
        if call[0] in ("sys_tasks", "install", "post_install")
    ]

    expected_call_order = [
        mocker.call.sys_tasks(),
        mocker.call.install(),
        mocker.call.post_install(),
    ]

    assert actual_calls == expected_call_order


def test_executor_execute_post_install_tasks(mocker, mock_config):
    """Test that _execute_post_install_tasks iterates and calls execute_subprocess with boundaries."""
    manifest = EnvironmentManifest()
    manifest.add_post_install_task(["uv", "first_task"])
    manifest.add_post_install_task(["uv", "second_task"], timeout=45)

    executor = SystemExecutor(manifest, mock_config)

    mock_execute = mocker.patch("protostar.executor.execute_subprocess")

    executor._execute_post_install_tasks()

    assert mock_execute.call_count == 2
    mock_execute.assert_any_call(["uv", "first_task"], timeout=30)
    mock_execute.assert_any_call(["uv", "second_task"], timeout=45)


def test_executor_uses_custom_task_description(mocker):
    # Mock the console and subprocess
    mock_status = mocker.patch("protostar.executor.console.status")
    mocker.patch("protostar.executor.execute_subprocess")

    manifest = EnvironmentManifest()
    manifest.add_system_task(["git", "init"], description="Initializing git repo")

    # We only need a dummy config to init the executor
    config = UserConfig()
    executor = SystemExecutor(manifest, config)

    executor._execute_tasks()

    # Verify the exact string was passed to the rich console status
    mock_status.assert_called_once_with("Initializing git repo")


def test_executor_task_description_fallback(mocker):
    mock_status = mocker.patch("protostar.executor.console.status")
    mocker.patch("protostar.executor.execute_subprocess")

    manifest = EnvironmentManifest()
    # Provide a command with a path, but NO description
    manifest.add_system_task([".venv/bin/pre-commit", "install"])

    config = UserConfig()
    executor = SystemExecutor(manifest, config)

    executor._execute_tasks()

    # Verify the fallback logic stripped the path and grabbed the binary name
    mock_status.assert_called_once_with("Propelling sequence: pre-commit")


def test_executor_toml_merge_type_collision() -> None:
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, UserConfig())

    base = tomlkit.document()
    base["tool"] = tomlkit.table()

    payload = tomlkit.document()
    payload["tool"] = tomlkit.aot()  # Array of Tables colliding with a standard Table

    executor._deep_merge_tomlkit(base, payload)

    assert len(manifest.diagnostics) == 1
    warning = manifest.diagnostics[0]
    assert warning.severity == Severity.WARNING
    assert warning.phase == "Executor"
    assert "TOML Merge Collision" in warning.message


def test_executor_skips_malformed_ide_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    # Queue up an IDE setting injection
    manifest = EnvironmentManifest()
    manifest.add_ide_setting("python.defaultInterpreterPath", "/fake/path")

    # Create a malformed JSON file
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    settings_file = vscode_dir / "settings.json"
    settings_file.write_text("{ broken_json: true, }")

    executor = SystemExecutor(manifest, UserConfig())
    executor._write_ide_settings()

    assert len(manifest.diagnostics) == 1
    warning = manifest.diagnostics[0]
    assert warning.severity == Severity.WARNING
    assert "is malformed" in warning.message
    assert "Skipping IDE settings injection" in warning.message


@pytest.fixture
def ide_manifest():
    """Fixture providing a manifest seeded with extension IDs."""
    manifest = EnvironmentManifest()
    manifest.ide_extensions = {"charliermarsh.ruff", "ms-python.mypy-type-checker"}
    return manifest


def test_ide_extension_check_bypassed_if_wrong_ide(ide_manifest, mocker):
    config = UserConfig(ide="none")
    executor = SystemExecutor(ide_manifest, config)
    mock_which = mocker.patch("protostar.executor.shutil.which")

    executor._check_ide_extensions()

    # It shouldn't even search for the binary
    mock_which.assert_not_called()


def test_ide_extension_check_bypassed_if_binary_missing(ide_manifest, mocker):
    config = UserConfig(ide="vscode")
    executor = SystemExecutor(ide_manifest, config)
    mock_which = mocker.patch("protostar.executor.shutil.which", return_value=None)
    mock_run = mocker.patch("protostar.executor.subprocess.run")

    executor._check_ide_extensions()

    mock_which.assert_called_once_with("code")
    mock_run.assert_not_called()


def test_ide_extension_check_succeeds_without_warnings(ide_manifest, mocker):
    config = UserConfig(ide="cursor")
    executor = SystemExecutor(ide_manifest, config)

    mocker.patch(
        "protostar.executor.shutil.which", return_value="/usr/local/bin/cursor"
    )

    mock_result = MagicMock()
    mock_result.stdout = (
        "charliermarsh.ruff\nms-python.mypy-type-checker\nsome-other-ext\n"
    )
    mock_run = mocker.patch(
        "protostar.executor.subprocess.run", return_value=mock_result
    )

    executor._check_ide_extensions()

    mock_run.assert_called_once_with(
        ["cursor", "--list-extensions"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    assert not executor.manifest.diagnostics


def test_ide_extension_check_flags_missing_extensions(ide_manifest, mocker):
    config = UserConfig(ide="vscode")
    executor = SystemExecutor(ide_manifest, config)

    mocker.patch("protostar.executor.shutil.which", return_value="/usr/local/bin/code")

    # Simulate a system where Mypy is missing
    mock_result = MagicMock()
    mock_result.stdout = "charliermarsh.ruff\n"
    mocker.patch("protostar.executor.subprocess.run", return_value=mock_result)

    executor._check_ide_extensions()

    assert len(executor.manifest.diagnostics) == 1
    diagnostic = executor.manifest.diagnostics[0]

    assert diagnostic.phase == "IDE"
    assert diagnostic.severity == Severity.WARNING
    assert "ms-python.mypy-type-checker" in diagnostic.message


def test_ide_extension_check_adds_skip_diagnostic_on_subprocess_error(
    ide_manifest, mocker
):
    config = UserConfig(ide="vscode")
    executor = SystemExecutor(ide_manifest, config)

    mocker.patch("protostar.executor.shutil.which", return_value="/usr/local/bin/code")

    # Simulate a timeout or CLI crash
    mocker.patch(
        "protostar.executor.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="code", timeout=5),
    )

    executor._check_ide_extensions()

    # It should no longer fail silently, but append a SKIP diagnostic
    assert len(executor.manifest.diagnostics) == 1
    diagnostic = executor.manifest.diagnostics[0]

    assert diagnostic.phase == "IDE"
    assert diagnostic.severity.value == "skip"
    assert "skipped due to an unexpected error" in diagnostic.message


def test_executor_handles_write_permission_denied(mocker):
    manifest = EnvironmentManifest()
    manifest.wants_pre_commit = True
    manifest.pre_commit_hooks.append("  - repo: local")

    config = UserConfig()
    executor = SystemExecutor(manifest, config)

    # CHANGED: Stub Path.exists to prevent the file existence check from triggering an early return
    mocker.patch.object(Path, "exists", return_value=False)

    # Force atomic write helper to crash out mimicking a blocked access request
    mocker.patch(
        "protostar.executor.atomic_write_text",
        side_effect=PermissionError(13, "Permission denied"),
    )

    with pytest.raises(FileSystemError) as exc_info:
        executor._write_pre_commit_config()

    assert "write configuration file" in exc_info.value.operation
    assert ".pre-commit-config.yaml" in exc_info.value.path
    assert isinstance(exc_info.value.original, PermissionError)


def test_executor_handles_mkdir_io_failure(mocker):
    manifest = EnvironmentManifest()
    manifest.add_directory("src/core")

    config = UserConfig()
    executor = SystemExecutor(manifest, config)

    mocker.patch.object(
        Path, "mkdir", side_effect=OSError(28, "No space left on device")
    )

    with pytest.raises(FileSystemError) as exc_info:
        executor._create_directories()

    assert "create scaffolding directory" in exc_info.value.operation
    assert "src/core" in exc_info.value.path


def test_append_files_handles_read_or_mkdir_failure(mocker):
    manifest = EnvironmentManifest()
    manifest.add_file_append("pyproject.toml", '[tool.custom]\nkey = "val"')
    executor = SystemExecutor(manifest, UserConfig())

    # Mock target.exists to return False so it hits the parent directory creation path
    mocker.patch.object(Path, "exists", return_value=False)
    mocker.patch.object(Path, "mkdir", side_effect=OSError(13, "Permission denied"))

    with pytest.raises(FileSystemError) as exc_info:
        executor._append_files()

    assert "read target append context" in exc_info.value.operation
    assert "pyproject.toml" in exc_info.value.path


def test_append_files_handles_toml_write_failure(mocker):
    manifest = EnvironmentManifest()
    manifest.add_file_append("pyproject.toml", '[tool.custom]\nkey = "val"')
    executor = SystemExecutor(manifest, UserConfig())

    # Simulate an existing valid pyproject.toml on disk
    mocker.patch.object(Path, "exists", return_value=True)
    mocker.patch.object(Path, "read_text", return_value="[project]\nname = 'test'")
    mocker.patch(
        "protostar.executor.atomic_write_text",
        side_effect=OSError(28, "No space left on device"),
    )

    with pytest.raises(FileSystemError) as exc_info:
        executor._append_files()

    assert "mutate configuration AST" in exc_info.value.operation
    assert "pyproject.toml" in exc_info.value.path


def test_append_files_handles_string_block_write_failure(mocker):
    manifest = EnvironmentManifest()
    manifest.add_file_append(".envrc", "export FOO=bar")
    executor = SystemExecutor(manifest, UserConfig())

    mocker.patch.object(Path, "exists", return_value=True)
    mocker.patch.object(Path, "read_text", return_value="")
    mocker.patch(
        "protostar.executor.atomic_write_text",
        side_effect=OSError(5, "Input/output error"),
    )

    with pytest.raises(FileSystemError) as exc_info:
        executor._append_files()

    assert "append configurations block" in exc_info.value.operation
    assert ".envrc" in exc_info.value.path


def test_write_ignores_handles_os_error(mocker):
    manifest = EnvironmentManifest()
    manifest.add_vcs_ignore(".venv/")
    executor = SystemExecutor(manifest, UserConfig())

    mocker.patch.object(Path, "exists", return_value=True)
    mocker.patch.object(Path, "read_text", return_value="")
    mocker.patch(
        "protostar.executor.atomic_write_text",
        side_effect=OSError(13, "Permission denied"),
    )

    with pytest.raises(FileSystemError) as exc_info:
        executor._write_ignores()

    assert "update workspace ignore manifest (.gitignore)" in exc_info.value.operation
    assert ".gitignore" in exc_info.value.path


def test_write_docker_artifacts_handles_os_error(mocker):
    manifest = EnvironmentManifest()
    manifest.add_vcs_ignore(".venv/")
    # Force docker attribute to true to enter the block
    executor = SystemExecutor(manifest, UserConfig(), docker=True)

    mocker.patch.object(Path, "exists", return_value=True)
    mocker.patch.object(Path, "read_text", return_value="")
    mocker.patch(
        "protostar.executor.atomic_write_text",
        side_effect=OSError(13, "Permission denied"),
    )

    with pytest.raises(FileSystemError) as exc_info:
        executor._write_docker_artifacts()

    assert (
        "scaffold container runtime ignore configurations" in exc_info.value.operation
    )
    assert ".dockerignore" in exc_info.value.path


def test_write_ide_settings_handles_read_os_error(mocker):
    manifest = EnvironmentManifest()
    manifest.add_ide_setting("foo", "bar")
    executor = SystemExecutor(manifest, UserConfig())

    # Force .vscode/settings.json to exist but crash out when read
    mocker.patch.object(Path, "exists", return_value=True)
    mocker.patch.object(Path, "read_text", side_effect=OSError(5, "Input/output error"))

    with pytest.raises(FileSystemError) as exc_info:
        executor._write_ide_settings()

    assert "inspect active IDE settings files" in exc_info.value.operation
    assert "settings.json" in exc_info.value.path


def test_write_ide_settings_handles_write_os_error(mocker):
    manifest = EnvironmentManifest()
    manifest.add_ide_setting("foo", "bar")
    executor = SystemExecutor(manifest, UserConfig())

    # Let reading work smoothly (or assume no file exists)
    mocker.patch.object(Path, "exists", return_value=False)
    mocker.patch.object(Path, "mkdir")  # swallow directory creation
    mocker.patch(
        "protostar.executor.atomic_write_text",
        side_effect=OSError(13, "Permission denied"),
    )

    with pytest.raises(FileSystemError) as exc_info:
        executor._write_ide_settings()

    assert "synchronize IDE workspace preferences" in exc_info.value.operation
    assert "settings.json" in exc_info.value.path


def test_ide_extension_check_satisfies_primary_in_tuple(mocker):
    """Verifies that the first element in an extension tuple satisfies the requirement."""
    manifest = EnvironmentManifest()
    manifest.add_ide_extension(("ms-python.mypy-type-checker", "matangover.mypy"))

    config = UserConfig(ide="vscode")
    executor = SystemExecutor(manifest, config)

    # Mock shutil.which to pretend 'code' is installed
    mocker.patch("protostar.executor.shutil.which", return_value="/usr/local/bin/code")

    # Mock subprocess to return the primary extension
    mock_run = mocker.patch("protostar.executor.subprocess.run")
    mock_run.return_value = MagicMock(
        stdout="ms-python.mypy-type-checker\nother.extension\n"
    )

    executor._check_ide_extensions()

    # No diagnostic warnings should be generated
    assert not any(d.severity == Severity.WARNING for d in manifest.diagnostics)


def test_ide_extension_check_satisfies_fallback_in_tuple(mocker):
    """Verifies that the secondary element in an extension tuple satisfies the requirement."""
    manifest = EnvironmentManifest()
    manifest.add_ide_extension(("ms-python.mypy-type-checker", "matangover.mypy"))

    config = UserConfig(ide="vscode")
    executor = SystemExecutor(manifest, config)

    mocker.patch("protostar.executor.shutil.which", return_value="/usr/local/bin/code")

    # Mock subprocess to return the fallback extension instead
    mock_run = mocker.patch("protostar.executor.subprocess.run")
    mock_run.return_value = MagicMock(stdout="matangover.mypy\nother.extension\n")

    executor._check_ide_extensions()

    # No diagnostic warnings should be generated
    assert not any(d.severity == Severity.WARNING for d in manifest.diagnostics)


def test_ide_extension_check_fails_missing_tuple(mocker):
    """Verifies that an unfulfilled tuple generates a properly formatted diagnostic."""
    manifest = EnvironmentManifest()
    manifest.add_ide_extension(("ms-python.mypy-type-checker", "matangover.mypy"))
    manifest.add_ide_extension("charliermarsh.ruff")

    config = UserConfig(ide="vscode")
    executor = SystemExecutor(manifest, config)

    mocker.patch("protostar.executor.shutil.which", return_value="/usr/local/bin/code")

    # Mock subprocess to return neither mypy extension, but return ruff
    mock_run = mocker.patch("protostar.executor.subprocess.run")
    mock_run.return_value = MagicMock(stdout="charliermarsh.ruff\nother.extension\n")

    executor._check_ide_extensions()

    warnings = [d for d in manifest.diagnostics if d.severity == Severity.WARNING]
    assert len(warnings) == 1

    # Ensure the diagnostic cleanly formats the unfulfilled tuple with 'or'
    assert "ms-python.mypy-type-checker or matangover.mypy" in warnings[0].message
    assert "charliermarsh.ruff" not in warnings[0].message


def test_executor_toml_table_replace(mock_config):
    """Test that __replace__ = true cleanly replaces an existing TOML table."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    base_doc = tomlkit.parse("""
[tool.example]
keep_this = true

[tool.example.nested]
old_key = 1
""")

    payload_doc = tomlkit.parse("""
[tool.example.nested]
__replace__ = true
new_key = 2
""")

    executor._deep_merge_tomlkit(base_doc, payload_doc)

    # Verify keep_this was preserved
    assert base_doc["tool"]["example"]["keep_this"] is True

    # Verify the nested table was replaced and old_key is gone
    nested = base_doc["tool"]["example"]["nested"]
    assert "new_key" in nested
    assert "old_key" not in nested
    assert "__replace__" not in nested


def test_executor_interpolates_package_name_in_injected_files(
    tmp_path, mock_config, monkeypatch
):
    """Test that <% PACKAGE_NAME %> and <% PROJECT_NAME %> are interpolated into injected files and paths."""
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    manifest.metadata = {"project_name": "my-cool-tool"}
    manifest.add_file_injection(
        "src/<% PACKAGE_NAME %>/__init__.py",
        '"""<% PROJECT_NAME %> package (<% PACKAGE_NAME %>)."""\n',
    )
    executor = SystemExecutor(manifest, mock_config)
    executor._write_injected_files()

    target_file = tmp_path / "src" / "my_cool_tool" / "__init__.py"
    assert target_file.exists()
    assert target_file.read_text() == '"""my-cool-tool package (my_cool_tool)."""\n'


def test_executor_interpolates_package_name_in_directories(
    tmp_path, mock_config, monkeypatch
):
    """Test that <% PACKAGE_NAME %> and <% PROJECT_NAME %> are interpolated into created directories."""
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    manifest.metadata = {"project_name": "my-cool-tool"}
    manifest.add_directory("src/<% PACKAGE_NAME %>")
    executor = SystemExecutor(manifest, mock_config)
    executor._create_directories()

    assert (tmp_path / "src" / "my_cool_tool").is_dir()


def test_executor_interpolates_package_name_in_file_appends(
    tmp_path, mock_config, monkeypatch
):
    """Test that <% PACKAGE_NAME %> and <% PROJECT_NAME %> are interpolated into TOML and text file appends."""
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    manifest.metadata = {"project_name": "my-cool-tool"}
    manifest.add_file_append(
        "pyproject.toml",
        '[project.scripts]\n<% PROJECT_NAME %> = "<% PACKAGE_NAME %>.cli:app"\n',
    )
    manifest.add_file_append(
        "script.sh",
        'echo "Running <% PROJECT_NAME %> from <% PACKAGE_NAME %>"\n',
    )
    executor = SystemExecutor(manifest, mock_config)
    executor._append_files()

    pyproject_content = (tmp_path / "pyproject.toml").read_text()
    assert 'my-cool-tool = "my_cool_tool.cli:app"' in pyproject_content

    script_content = (tmp_path / "script.sh").read_text()
    assert 'echo "Running my-cool-tool from my_cool_tool"' in script_content


def test_executor_toml_table_replace_nested_hierarchy(mock_config):
    """Test that __replace__ = true cleanly replaces an existing TOML table and brings nested tables along."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    base_doc = tomlkit.parse("""
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["A", "B"]
ignore = ["E501"]
""")

    payload_doc = tomlkit.parse("""
[tool.ruff.lint]
__replace__ = true
select = ["A", "B", "C4", "D"]
ignore = ["D100"]

[tool.ruff.lint.pydocstyle]
convention = "google"
""")

    executor._deep_merge_tomlkit(base_doc, payload_doc)

    # Verify tool.ruff.line-length is preserved
    assert base_doc["tool"]["ruff"]["line-length"] == 88

    # Verify tool.ruff.lint is replaced with new select/ignore and has nested pydocstyle
    lint = base_doc["tool"]["ruff"]["lint"]
    assert lint["select"] == ["A", "B", "C4", "D"]
    assert lint["ignore"] == ["D100"]
    assert lint["pydocstyle"]["convention"] == "google"
    assert "__replace__" not in lint


def test_format_pyproject_toml_canonical_ordering():
    """Test that tool tables injected in reverse/random order are sorted canonically."""
    raw = """
[tool.commitizen]
name = "cz"

[tool.coverage.run]
branch = true

[tool.pytest.ini_options]
addopts = "-v"

[tool.pyrefly]
type-checking-mode = "strict"

[tool.ty.rules]
redundant-cast = "warn"

[tool.mypy]
strict = true

[tool.ruff]
line-length = 88
"""
    doc = tomlkit.parse(raw)
    formatted = SystemExecutor._format_pyproject_toml(doc)

    ruff_pos = formatted.find("# ---- Ruff ---- #")
    mypy_pos = formatted.find("# ---- Mypy ---- #")
    ty_pos = formatted.find("# ---- Ty ---- #")
    pyrefly_pos = formatted.find("# ---- Pyrefly ---- #")
    pytest_pos = formatted.find("# ---- Pytest ---- #")
    cz_pos = formatted.find("# ---- Commitizen ---- #")

    assert 0 < ruff_pos < mypy_pos < ty_pos < pyrefly_pos < pytest_pos < cz_pos


def test_format_pyproject_toml_coverage_grouped_under_pytest():
    """Test that coverage tables are placed directly under Pytest and before Commitizen."""
    raw = """
[project]
name = "demo"

[tool.commitizen]
name = "cz"

[tool.pytest.ini_options]
addopts = "--strict-markers"

[tool.coverage.run]
branch = true

[tool.coverage.report]
show_missing = true
"""
    doc = tomlkit.parse(raw)
    formatted = SystemExecutor._format_pyproject_toml(doc)

    pytest_header_pos = formatted.find("# ---- Pytest ---- #")
    pytest_ini_pos = formatted.find("[tool.pytest.ini_options]")
    cov_run_pos = formatted.find("[tool.coverage.run]")
    cov_rep_pos = formatted.find("[tool.coverage.report]")
    cz_header_pos = formatted.find("# ---- Commitizen ---- #")
    cz_pos = formatted.find("[tool.commitizen]")

    assert (
        pytest_header_pos
        < pytest_ini_pos
        < cov_run_pos
        < cov_rep_pos
        < cz_header_pos
        < cz_pos
    )


def test_format_pyproject_toml_root_table_ordering():
    """Test that root scalars, project, build-system, dependency-groups, and tool tables are ordered."""
    raw = """
[tool.ruff]
line-length = 88

[dependency-groups]
dev = ["pytest"]

[build-system]
requires = ["hatchling"]

[project]
name = "app"
version = "0.1.0"
"""
    doc = tomlkit.parse(raw)
    formatted = SystemExecutor._format_pyproject_toml(doc)

    project_pos = formatted.find("[project]")
    build_pos = formatted.find("[build-system]")
    dep_pos = formatted.find("[dependency-groups]")
    tool_pos = formatted.find("# ==================================================")

    assert 0 <= project_pos < build_pos < dep_pos < tool_pos


def test_format_pyproject_toml_idempotency():
    """Test that re-running _format_pyproject_toml on already formatted TOML produces identical output."""
    raw = """
[project]
name = "app"
version = "0.1.0"

[project.scripts]
app = "app.cli:app"

[dependency-groups]
dev = ["pytest", "pytest-cov", "ruff"]

[tool.ruff]
line-length = 88

[tool.pytest.ini_options]
addopts = "--strict-markers"

[tool.coverage.run]
branch = true

[tool.commitizen]
name = "cz"
"""
    doc1 = tomlkit.parse(raw)
    pass1 = SystemExecutor._format_pyproject_toml(doc1)

    doc2 = tomlkit.parse(pass1)
    pass2 = SystemExecutor._format_pyproject_toml(doc2)

    assert pass1 == pass2
    assert pass1.endswith("\n")
    assert not pass1.endswith("\n\n")


def test_format_pyproject_toml_preserves_comments():
    """Test that non-managed user comments inside tables and inline comments survive."""
    raw = """
[project]
name = "app" # inline project comment

[tool.ruff]
line-length = 88 # inline ruff comment

# User custom lint comment
[tool.ruff.lint]
select = ["E", "F"]
"""
    doc = tomlkit.parse(raw)
    formatted = SystemExecutor._format_pyproject_toml(doc)

    assert "# inline project comment" in formatted
    assert "# inline ruff comment" in formatted
    assert "# User custom lint comment" in formatted
    assert formatted.endswith("\n")
    assert not formatted.endswith("\n\n")


def test_format_pyproject_toml_parity_fallback(mocker):
    """Test that formatting gracefully falls back to direct AST dump if validation encounters an error."""
    raw = """
[project]
name = "app"

[tool.ruff]
line-length = 88
"""
    doc = tomlkit.parse(raw)
    mocker.patch("tomllib.loads", side_effect=ValueError("Simulated corrupt parse"))
    formatted = SystemExecutor._format_pyproject_toml(doc)
    assert "[tool.ruff]" in formatted
    assert formatted.endswith("\n")
    assert not formatted.endswith("\n\n")


def test_executor_append_files_cli_template_full_lifecycle(
    tmp_path, monkeypatch, mock_config
):
    """Test end-to-end pyproject.toml append lifecycle for CLI template with coverage grouped under pytest."""
    monkeypatch.chdir(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "demo-project"\nversion = "0.1.0"\nrequires-python = ">=3.13"\n'
    )

    manifest = EnvironmentManifest()
    # Tooling modules append baseline configurations
    manifest.add_file_append("pyproject.toml", "[tool.ruff]\nline-length = 88\n")
    manifest.add_file_append("pyproject.toml", '[tool.mypy]\nmypy_path = "src"\n')
    manifest.add_file_append(
        "pyproject.toml",
        '[tool.pytest.ini_options]\naddopts = "--strict-markers"\ntestpaths = ["tests"]\n',
    )
    manifest.add_file_append(
        "pyproject.toml", '[tool.commitizen]\nname = "cz_conventional_commits"\n'
    )
    manifest.add_file_append(
        "pyproject.toml", '[dependency-groups]\ndev = [{ include-group = "docs" }]\n'
    )

    # CLI Template appends late-binding injections
    manifest.add_file_append(
        "pyproject.toml", '[tool.ruff.lint]\nselect = ["A", "B"]\n'
    )
    manifest.add_file_append(
        "pyproject.toml",
        '[[tool.mypy.overrides]]\nmodule = ["tests.*"]\ndisallow_untyped_defs = false\n',
    )
    manifest.add_file_append(
        "pyproject.toml",
        "[tool.coverage.run]\nbranch = true\n\n[tool.coverage.report]\nshow_missing = true\n",
    )
    manifest.add_file_append(
        "pyproject.toml", '[project.scripts]\ndemo-project = "demo_project.cli:app"\n'
    )

    executor = SystemExecutor(manifest, mock_config)
    executor._append_files()

    result = pyproject.read_text()

    assert result.endswith("\n")
    assert not result.endswith("\n\n")
    assert tomllib.loads(result)

    banner_pos = result.find("# Tool Configuration")
    ruff_pos = result.find("# ---- Ruff ---- #")
    mypy_pos = result.find("# ---- Mypy ---- #")
    pytest_pos = result.find("# ---- Pytest ---- #")
    cov_run_pos = result.find("[tool.coverage.run]")
    cov_rep_pos = result.find("[tool.coverage.report]")
    cz_pos = result.find("# ---- Commitizen ---- #")

    assert (
        0
        < banner_pos
        < ruff_pos
        < mypy_pos
        < pytest_pos
        < cov_run_pos
        < cov_rep_pos
        < cz_pos
    )


def test_executor_append_files_recleans_existing_managed_headers(
    tmp_path, monkeypatch, mock_config
):
    """Test that existing managed banners are stripped and cleanly regenerated without duplication."""
    monkeypatch.chdir(tmp_path)
    pyproject = tmp_path / "pyproject.toml"

    # Pre-existing file with misordered banners and user comments
    existing = """[project]
name = "demo"

# ==================================================
# Tool Configuration
# ==================================================

# ---- Commitizen ---- #

[tool.commitizen]
name = "cz"

# Keep this user comment
# ---- Ruff ---- #

[tool.ruff]
line-length = 88
"""
    pyproject.write_text(existing)

    manifest = EnvironmentManifest()
    manifest.add_file_append(
        "pyproject.toml", '[tool.pytest.ini_options]\naddopts = "-v"\n'
    )

    executor = SystemExecutor(manifest, mock_config)
    executor._append_files()

    result = pyproject.read_text()

    # Banners should appear exactly once
    assert result.count("# Tool Configuration") == 1
    assert result.count("# ---- Ruff ---- #") == 1
    assert result.count("# ---- Pytest ---- #") == 1
    assert result.count("# ---- Commitizen ---- #") == 1

    # User comment preserved
    assert "# Keep this user comment" in result

    # Order maintained
    ruff_pos = result.find("# ---- Ruff ---- #")
    pytest_pos = result.find("# ---- Pytest ---- #")
    cz_pos = result.find("# ---- Commitizen ---- #")
    assert ruff_pos < pytest_pos < cz_pos
    assert result.endswith("\n")
    assert not result.endswith("\n\n")


def test_format_pyproject_toml_aot_and_subtables_only():
    """Test that subtables and array of tables without root tables are detected and formatted with headers."""
    raw = """
[[tool.mypy.overrides]]
module = ["tests.*"]
ignore_errors = true

[tool.ty.rules]
redundant-cast = "warn"

[tool.coverage.report]
fail_under = 80
"""
    doc = tomlkit.parse(raw)
    formatted = SystemExecutor._format_pyproject_toml(doc)

    assert "# ---- Mypy ---- #\n\n[[tool.mypy.overrides]]" in formatted
    assert "# ---- Ty ---- #\n\n[tool.ty.rules]" in formatted
    assert "# ---- Pytest ---- #\n\n[tool.coverage.report]" in formatted
    assert formatted.endswith("\n")
    assert not formatted.endswith("\n\n")


def test_format_pyproject_toml_semantic_data_mismatch_fallback(mocker):
    """Test that formatting safely falls back to raw dump if parsed check data differs from expected."""
    raw = """
[project]
name = "app"

[tool.ruff]
line-length = 88
"""
    doc = tomlkit.parse(raw)

    # Mock tomllib.loads: first call (raw_dump) returns dict A, second call (new_content) returns dict B
    calls = [
        {"project": {"name": "app"}, "tool": {"ruff": {"line-length": 88}}},
        {"project": {"name": "corrupted"}},
    ]
    mocker.patch("tomllib.loads", side_effect=lambda _: calls.pop(0))

    formatted = SystemExecutor._format_pyproject_toml(doc)
    assert "[tool.ruff]" in formatted
    assert formatted.endswith("\n")
    assert not formatted.endswith("\n\n")
