import hashlib
import tomllib
from pathlib import Path
from typing import cast

import pytest

from protostar.config import UserConfig
from protostar.errors import (
    ConfigurationError,
    FileSystemError,
)
from protostar.executor import SystemExecutor
from protostar.manifest import (
    CollisionStrategy,
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    ProjectMetadata,
    Severity,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_config() -> UserConfig:
    """Provides a fresh baseline configuration for DI injections."""
    return UserConfig()


def test_executor_writes_injected_files(mocker, mock_config):
    """Test that the executor flushes queued file injections to disk."""
    manifest = EnvironmentManifest()
    manifest.filesystem.add_file_injection(".test_config.yaml", "mock content")
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
    manifest.filesystem.add_file_append(
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
    manifest.tooling.wants_pre_commit = True
    manifest.dependencies.add("fastapi")
    manifest.dependencies.add_dev("pytest")

    hook_payload = """  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies:
<% MYPY_DEPENDENCIES %>"""
    manifest.tooling.add_pre_commit_hook(hook_payload)

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
    manifest.tooling.wants_pre_commit = True

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
    manifest.tooling.add_pre_commit_local_hook(ruff_payload)

    mypy_payload = """      - id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        types: [python]
        require_serial: true"""
    manifest.tooling.add_pre_commit_local_hook(mypy_payload)

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
    assert "repo: https://github.com/pre-commit/pre-commit-hooks" in written_data
    assert "rev: v6.0.0" in written_data


def test_executor_writes_prek_config(mocker, mock_config):
    """Test that the executor scaffolds builtin generic hooks for prek."""
    manifest = EnvironmentManifest()
    manifest.tooling.wants_prek = True

    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_pre_commit_config()

    written_data = mock_write.call_args[0][1]
    assert "  - repo: builtin" in written_data
    assert "check-merge-conflict" in written_data
    assert "check-toml" in written_data
    assert "gitleaks" in written_data
    assert "uv-lock-check" in written_data


def test_executor_writes_pre_commit_config_local_and_remote_hooks(mocker, mock_config):
    """Test that the executor formats both local and remote repository hooks."""
    manifest = EnvironmentManifest()
    manifest.tooling.wants_pre_commit = True

    ruff_payload = """      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types: [python]
        require_serial: true"""
    manifest.tooling.add_pre_commit_local_hook(ruff_payload)

    remote_payload = """  - repo: https://github.com/DavidAnson/markdownlint-cli2
    rev: v0.23.0
    hooks:
      - id: markdownlint-cli2
        args: ["--fix"]"""
    manifest.tooling.add_pre_commit_hook(remote_payload)

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
    manifest.tooling.wants_pre_commit = True

    hook_payload = """  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies:
<% MYPY_DEPENDENCIES %>"""
    manifest.tooling.add_pre_commit_hook(hook_payload)

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
    manifest.filesystem.add_vcs_ignore("custom_build_artifact/")
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
    manifest.filesystem.add_vcs_ignore("new_ignore.txt")
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


def test_executor_creates_directories(mocker, mock_config):
    """Test that the executor generates all requested workspace directories."""
    manifest = EnvironmentManifest()
    manifest.filesystem.add_directory("data")
    manifest.filesystem.add_directory("src/core")
    executor = SystemExecutor(manifest, mock_config)

    mock_mkdir = mocker.patch("protostar.executor.Path.mkdir")

    executor._create_directories()

    assert mock_mkdir.call_count == 2
    mock_mkdir.assert_any_call(parents=True, exist_ok=True)


def test_executor_writes_dockerignore_with_uv(mocker, mock_config):
    """Test that the executor appends .python-version to .dockerignore when uv is used."""
    manifest = EnvironmentManifest()
    manifest.tasks.add_system_task(
        ["uv", "init", "--no-workspace", "--bare", "--pin-python"]
    )
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
    manifest.metadata = cast(ProjectMetadata, {"python_version": "3.12"})
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
    manifest.dependencies.dependencies = ["fastapi", "uvicorn"]
    manifest.metadata = cast(
        ProjectMetadata, {"docker_port": "8080", "python_version": "3.13"}
    )
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
    manifest.dependencies.dependencies = ["typer"]
    manifest.filesystem.add_file_append(
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
        "Skipping Dockerfile generation" in d.message for d in executor.diagnostics
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


def test_executor_writes_injected_files_overwrite(mocker, mock_config):
    """Test that file injections bypass the exists() guard if OVERWRITE is active."""
    manifest = EnvironmentManifest()
    manifest.collision_strategy = CollisionStrategy.OVERWRITE
    manifest.filesystem.add_file_injection(".test_config.yaml", "new content")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_injected_files()
    mock_write.assert_called_once_with(Path(".test_config.yaml"), "new content")


def test_executor_mkdir_os_error_propagation(mocker, mock_config):
    """Test that the executor correctly propagates OSErrors during directory creation."""
    manifest = EnvironmentManifest()
    manifest.filesystem.add_directory("protected_dir")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch(
        "protostar.executor.Path.mkdir", side_effect=OSError("Read-only file system")
    )

    with pytest.raises(FileSystemError, match="Read-only file system"):
        executor._create_directories()


def test_executor_write_text_permission_error_propagation(mocker, mock_config):
    """Test that the executor propagates PermissionErrors during file injections."""
    manifest = EnvironmentManifest()
    manifest.filesystem.add_file_injection("system_config.yaml", "secret")
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


def test_executor_append_files_ast_no_op_write(mocker, mock_config):
    """Test that file writing is bypassed if the merged AST yields identical content."""
    original_content = "[tool.fake_tool]\nstrict = true\n"

    manifest = EnvironmentManifest()
    # Queue a payload that is perfectly identical to the existing base document
    manifest.filesystem.add_file_append("pyproject.toml", original_content)
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


def test_executor_append_files_ast_merge(mocker, mock_config):
    """Test that _append_files mutates the TOML AST logically based on the MERGE strategy."""
    base_content = (FIXTURES_DIR / "base_complex.toml").read_text()
    payload_content = (FIXTURES_DIR / "payload_complex.toml").read_text()

    manifest = EnvironmentManifest()
    manifest.collision_strategy = CollisionStrategy.MERGE
    manifest.filesystem.add_file_append("pyproject.toml", payload_content)
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
    manifest.filesystem.add_file_append("pyproject.toml", payload_content)
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
    manifest.tooling.wants_pre_commit = True
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_pre_commit_config()
    mock_write.assert_not_called()


def test_executor_validate_targets_success(mocker, mock_config):
    """Test that pre-execution validation passes silently on valid TOML files."""

    manifest = EnvironmentManifest()
    manifest.filesystem.add_file_append("pyproject.toml", "[tool.ruff]")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)

    mock_file = mocker.mock_open(read_data=b'[project]\nname = "test"\n')
    mocker.patch("protostar.executor.Path.open", mock_file)

    # Should execute cleanly without raising any exceptions
    executor._validate_targets()


def test_executor_validate_targets_malformed_toml(mocker, mock_config):
    """Test that malformed existing TOML triggers a ConfigurationError during pre-execution."""
    manifest = EnvironmentManifest()
    manifest.filesystem.add_file_append("test.toml", "[section]\nkey = 'val'\n")
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
    manifest.filesystem.add_file_append("test.toml", "[invalid payload == \n")
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
    manifest.filesystem.add_file_append("test.txt", payload)
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
    manifest.filesystem.add_file_append("config.ini", "new_payload_1")
    manifest.filesystem.add_file_append("config.ini", "new_payload_2")
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


def test_executor_append_files_early_return(mocker, mock_config):
    """Test that _append_files cleanly returns if there are no payloads queued."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    mock_exists = mocker.patch("protostar.executor.Path.exists")
    executor._append_files()

    mock_exists.assert_not_called()


def test_executor_lifecycle_ordering(mocker, mock_config):
    """Test that the executor strictly adheres to the execution DAG order."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)

    # Use a parent mock to track chronological execution sequence across methods
    manager = mocker.Mock()

    manager.attach_mock(mocker.patch.object(executor, "_run_tasks"), "run_tasks")
    manager.attach_mock(
        mocker.patch.object(executor, "_install_dependencies"), "install"
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
        call for call in manager.mock_calls if call[0] in ("run_tasks", "install")
    ]

    expected_call_order = [
        mocker.call.run_tasks(manifest.tasks.system_tasks),
        mocker.call.install(),
        mocker.call.run_tasks(manifest.tasks.post_install_tasks),
    ]

    assert actual_calls == expected_call_order


def test_executor_run_tasks(mocker, mock_config):
    """Test that _run_tasks iterates and calls execute_subprocess with boundaries."""
    manifest = EnvironmentManifest()
    manifest.tasks.add_post_install_task(["uv", "first_task"])
    manifest.tasks.add_post_install_task(["uv", "second_task"], timeout=45)

    executor = SystemExecutor(manifest, mock_config)

    mock_execute = mocker.patch("protostar.executor.execute_subprocess")

    executor._run_tasks(manifest.tasks.post_install_tasks)

    assert mock_execute.call_count == 2
    mock_execute.assert_any_call(["uv", "first_task"], timeout=30)
    mock_execute.assert_any_call(["uv", "second_task"], timeout=45)


def test_executor_uses_custom_task_description(mocker):
    # Mock the logger and subprocess
    mock_info = mocker.patch("protostar.executor.logger.info")
    mocker.patch("protostar.executor.execute_subprocess")

    manifest = EnvironmentManifest()
    manifest.tasks.add_system_task(["git", "init"], description="Initializing git repo")

    # We only need a dummy config to init the executor
    config = UserConfig()
    executor = SystemExecutor(manifest, config)

    executor._run_tasks(manifest.tasks.system_tasks)

    mock_info.assert_called_with("Initializing git repo")


def test_executor_task_description_fallback(mocker):
    mock_info = mocker.patch("protostar.executor.logger.info")
    mocker.patch("protostar.executor.execute_subprocess")

    manifest = EnvironmentManifest()
    # Provide a command with a path, but NO description
    manifest.tasks.add_system_task([".venv/bin/pre-commit", "install"])

    config = UserConfig()
    executor = SystemExecutor(manifest, config)

    executor._run_tasks(manifest.tasks.system_tasks)

    # Verify the fallback logic stripped the path and grabbed the binary name
    mock_info.assert_called_once_with("Running: pre-commit")


def test_executor_handles_write_permission_denied(mocker):
    manifest = EnvironmentManifest()
    manifest.tooling.wants_pre_commit = True
    manifest.tooling.pre_commit_hooks.append("  - repo: local")

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
    manifest.filesystem.add_directory("src/core")

    config = UserConfig()
    executor = SystemExecutor(manifest, config)

    mocker.patch.object(
        Path, "mkdir", side_effect=OSError(28, "No space left on device")
    )

    with pytest.raises(FileSystemError) as exc_info:
        executor._create_directories()

    assert "create scaffolding directory" in exc_info.value.operation
    assert "src" in str(exc_info.value.path)
    assert "core" in str(exc_info.value.path)


def test_append_files_handles_read_or_mkdir_failure(mocker):
    manifest = EnvironmentManifest()
    manifest.filesystem.add_file_append("pyproject.toml", '[tool.custom]\nkey = "val"')
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
    manifest.filesystem.add_file_append("pyproject.toml", '[tool.custom]\nkey = "val"')
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
    manifest.filesystem.add_file_append(".envrc", "export FOO=bar")
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
    manifest.filesystem.add_vcs_ignore(".venv/")
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
    manifest.filesystem.add_vcs_ignore(".venv/")
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


def test_executor_interpolates_package_name_in_injected_files(
    tmp_path, mock_config, monkeypatch
):
    """Test that <% PACKAGE_NAME %> and <% PROJECT_NAME %> are interpolated into injected files and paths."""
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    manifest.metadata = cast(ProjectMetadata, {"project_name": "my-cool-tool"})
    manifest.filesystem.add_file_injection(
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
    manifest.metadata = cast(ProjectMetadata, {"project_name": "my-cool-tool"})
    manifest.filesystem.add_directory("src/<% PACKAGE_NAME %>")
    executor = SystemExecutor(manifest, mock_config)
    executor._create_directories()

    assert (tmp_path / "src" / "my_cool_tool").is_dir()


def test_executor_interpolates_package_name_in_file_appends(
    tmp_path, mock_config, monkeypatch
):
    """Test that <% PACKAGE_NAME %> and <% PROJECT_NAME %> are interpolated into TOML and text file appends."""
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    manifest.metadata = cast(ProjectMetadata, {"project_name": "my-cool-tool"})
    manifest.filesystem.add_file_append(
        "pyproject.toml",
        '[project.scripts]\n<% PROJECT_NAME %> = "<% PACKAGE_NAME %>.cli:app"\n',
    )
    manifest.filesystem.add_file_append(
        "script.sh",
        'echo "Running <% PROJECT_NAME %> from <% PACKAGE_NAME %>"\n',
    )
    executor = SystemExecutor(manifest, mock_config)
    executor._append_files()

    pyproject_content = (tmp_path / "pyproject.toml").read_text()
    assert 'my-cool-tool = "my_cool_tool.cli:app"' in pyproject_content

    script_content = (tmp_path / "script.sh").read_text()
    assert 'echo "Running my-cool-tool from my_cool_tool"' in script_content


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
    manifest.filesystem.add_file_append(
        "pyproject.toml", "[tool.ruff]\nline-length = 88\n"
    )
    manifest.filesystem.add_file_append(
        "pyproject.toml", '[tool.mypy]\nmypy_path = "src"\n'
    )
    manifest.filesystem.add_file_append(
        "pyproject.toml",
        '[tool.pytest.ini_options]\naddopts = "--strict-markers"\ntestpaths = ["tests"]\n',
    )
    manifest.filesystem.add_file_append(
        "pyproject.toml", '[tool.commitizen]\nname = "cz_conventional_commits"\n'
    )
    manifest.filesystem.add_file_append(
        "pyproject.toml", '[dependency-groups]\ndev = [{ include-group = "docs" }]\n'
    )

    # CLI Template appends late-binding injections
    manifest.filesystem.add_file_append(
        "pyproject.toml", '[tool.ruff.lint]\nselect = ["A", "B"]\n'
    )
    manifest.filesystem.add_file_append(
        "pyproject.toml",
        '[[tool.mypy.overrides]]\nmodule = ["tests.*"]\ndisallow_untyped_defs = false\n',
    )
    manifest.filesystem.add_file_append(
        "pyproject.toml",
        "[tool.coverage.run]\nbranch = true\n\n[tool.coverage.report]\nshow_missing = true\n",
    )
    manifest.filesystem.add_file_append(
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
    manifest.filesystem.add_file_append(
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


def test_executor_diagnostic_collection(mock_config):
    """Test that SystemExecutor collects diagnostics correctly."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)
    assert len(executor.diagnostics) == 0

    executor.add_diagnostic(
        phase="TestPhase",
        message="A test warning occurred.",
        severity=Severity.WARNING,
        detail="Some traceback or detail",
    )

    assert len(executor.diagnostics) == 1
    event = executor.diagnostics[0]
    assert isinstance(event, DiagnosticEvent)
    assert event.phase == "TestPhase"
    assert event.message == "A test warning occurred."
    assert event.severity == Severity.WARNING
    assert event.detail == "Some traceback or detail"


def test_executor_diagnostic_collection_with_enum(mock_config):
    """Test that SystemExecutor handles DiagnosticPhase enum in diagnostics."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest, mock_config)
    executor.add_diagnostic(
        phase=DiagnosticPhase.EXECUTOR,
        message="Execution warning",
        severity=Severity.WARNING,
    )

    assert len(executor.diagnostics) == 1
    event = executor.diagnostics[0]
    assert event.phase == DiagnosticPhase.EXECUTOR
    assert event.phase == "Executor"


def test_executor_skips_pre_commit_when_file_exists(mocker, mock_config):
    """Test that existing .pre-commit-config.yaml is skipped and logs a diagnostic."""
    manifest = EnvironmentManifest()
    manifest.tooling.wants_pre_commit = True
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_pre_commit_config()

    mock_write.assert_not_called()
    assert len(executor.diagnostics) == 1
    assert executor.diagnostics[0].phase == DiagnosticPhase.PRE_COMMIT
    assert executor.diagnostics[0].severity == Severity.SKIP
    assert (
        "Skipping .pre-commit-config.yaml generation" in executor.diagnostics[0].message
    )


def test_executor_skips_injected_files_when_file_exists(mocker, mock_config):
    """Test that existing injected files are skipped and log a diagnostic."""
    manifest = EnvironmentManifest()
    manifest.filesystem.add_file_injection(".envrc", "export FOO=bar")
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_injected_files()

    mock_write.assert_not_called()
    assert len(executor.diagnostics) == 1
    assert executor.diagnostics[0].phase == DiagnosticPhase.EXECUTOR
    assert executor.diagnostics[0].severity == Severity.SKIP
    assert "Skipping .envrc generation" in executor.diagnostics[0].message


def test_executor_skips_justfile_when_file_exists(mocker, mock_config):
    """Test that existing justfile is skipped and logs a diagnostic."""
    manifest = EnvironmentManifest()
    manifest.tooling.wants_just = True
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_justfile()

    mock_write.assert_not_called()
    assert len(executor.diagnostics) == 1
    assert executor.diagnostics[0].phase == DiagnosticPhase.JUST
    assert executor.diagnostics[0].severity == Severity.SKIP
    assert "Skipping justfile generation" in executor.diagnostics[0].message


def test_executor_writes_pre_commit_config_resolves_placeholders(mocker, mock_config):
    """Test that _write_pre_commit_config replaces RemoteHook placeholders dynamically."""
    from protostar.registry import RemoteHook

    manifest = EnvironmentManifest()
    manifest.tooling.wants_pre_commit = True

    hook_payload = f"""  - repo: {RemoteHook.MARKDOWNLINT.value}
    rev: {RemoteHook.MARKDOWNLINT.placeholder}
    hooks:
      - id: markdownlint-cli2"""
    manifest.tooling.add_pre_commit_hook(hook_payload)

    executor = SystemExecutor(manifest, mock_config)
    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.atomic_write_text")

    executor._write_pre_commit_config()

    written_data = mock_write.call_args[0][1]
    assert RemoteHook.MARKDOWNLINT.placeholder not in written_data
    assert RemoteHook.PRE_COMMIT_HOOKS.placeholder not in written_data
    assert RemoteHook.GITLEAKS.placeholder not in written_data
    assert "https://github.com/DavidAnson/markdownlint-cli2" in written_data
    assert "https://github.com/pre-commit/pre-commit-hooks" in written_data
    assert "https://github.com/gitleaks/gitleaks" in written_data


def test_sync_rumdl_vscode_extension_success(mocker, mock_config):
    """Test that rumdl vscode extension sync runs when IDE is vscode and succeeds cleanly."""
    from unittest.mock import MagicMock

    mock_config.ide = "vscode"
    manifest = EnvironmentManifest()
    manifest.tooling.add_ide_extension("rvben.rumdl")
    executor = SystemExecutor(manifest, mock_config)

    mock_run = mocker.patch(
        "protostar.executor.subprocess.run", return_value=MagicMock(returncode=0)
    )
    executor._sync_rumdl_vscode_extension()

    mock_run.assert_called_once_with(
        ["uv", "run", "rumdl", "vscode"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert not any(
        d.message == "rumdl failed to install vscode extension"
        for d in executor.diagnostics
    )


def test_sync_rumdl_vscode_extension_failure_adds_skip_diagnostic(mocker, mock_config):
    """Test that rumdl vscode failure logs a gentle skip diagnostic rather than aborting."""
    from unittest.mock import MagicMock

    mock_config.ide = "vscode"
    manifest = EnvironmentManifest()
    manifest.tooling.add_ide_extension("rvben.rumdl")
    executor = SystemExecutor(manifest, mock_config)

    mocker.patch(
        "protostar.executor.subprocess.run", return_value=MagicMock(returncode=1)
    )
    executor._sync_rumdl_vscode_extension()

    skip_events = [
        d
        for d in executor.diagnostics
        if d.message == "rumdl failed to install vscode extension"
    ]
    assert len(skip_events) == 1
    assert skip_events[0].severity == Severity.SKIP
    assert skip_events[0].phase == DiagnosticPhase.IDE


def test_sync_rumdl_vscode_extension_skipped_when_ide_not_vscode(mocker, mock_config):
    """Test that rumdl vscode is not called when IDE is not vscode."""
    mock_config.ide = None
    manifest = EnvironmentManifest()
    manifest.tooling.add_ide_extension("rvben.rumdl")
    executor = SystemExecutor(manifest, mock_config)

    mock_run = mocker.patch("protostar.executor.subprocess.run")
    executor._sync_rumdl_vscode_extension()

    mock_run.assert_not_called()
    assert len(executor.diagnostics) == 0
