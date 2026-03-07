import json
import subprocess

import pytest

from protostar.config import ProtostarConfig
from protostar.executor import SystemExecutor
from protostar.manifest import CollisionStrategy, EnvironmentManifest


def test_executor_writes_injected_files(mocker):
    """Test that the executor flushes queued file injections to disk."""
    manifest = EnvironmentManifest()
    manifest.add_file_injection(".test_config.yaml", "mock content")
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_mkdir = mocker.patch("protostar.executor.Path.mkdir")
    mock_write = mocker.patch("protostar.executor.Path.write_text")

    executor._write_injected_files()

    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_write.assert_called_once_with("mock content")


def test_executor_install_dependencies_uv(mocker):
    """Test that the executor uses uv add --dev for dev dependencies."""
    manifest = EnvironmentManifest()
    manifest.add_dependency("fastapi")
    manifest.add_dev_dependency("pytest")
    executor = SystemExecutor(manifest)

    mock_run_quiet = mocker.patch("protostar.executor.run_quiet")
    mocker.patch("protostar.executor.Path.exists", return_value=True)

    mock_config = mocker.patch("protostar.executor.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="uv")

    executor._install_dependencies()

    mock_run_quiet.assert_any_call(
        ["uv", "add", "fastapi"],
        "Resolving and installing 1 dependencies",
    )
    mock_run_quiet.assert_any_call(
        ["uv", "add", "--dev", "pytest"],
        "Resolving and installing 1 development dependencies",
    )


def test_executor_install_dependencies_pip_freeze(monkeypatch, mocker, tmp_path):
    """Test that the executor runs a local pip installation and writes a freeze state."""
    monkeypatch.chdir(tmp_path)

    manifest = EnvironmentManifest()
    manifest.add_dependency("dummy-pkg")
    manifest.add_dev_dependency("dev-pkg")
    executor = SystemExecutor(manifest)

    mock_run_quiet = mocker.patch("protostar.executor.run_quiet")
    mock_run = mocker.patch("protostar.executor.subprocess.run")

    pip_bin = tmp_path / ".venv" / "bin"
    pip_bin.mkdir(parents=True)
    pip_exe = pip_bin / "pip"
    pip_exe.touch()

    mock_config = mocker.patch("protostar.executor.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="pip")

    mock_run.return_value.stdout = "dummy-pkg==1.0.0\ndev-pkg==2.0.0\n"

    executor._install_dependencies()

    mock_run_quiet.assert_called_once_with(
        [".venv/bin/pip", "install", "dummy-pkg", "dev-pkg"],
        "Resolving and installing 2 total dependencies",
    )

    mock_run.assert_called_once_with(
        [".venv/bin/pip", "freeze"], capture_output=True, text=True, check=True
    )

    assert (
        tmp_path / "requirements.txt"
    ).read_text() == "dummy-pkg==1.0.0\ndev-pkg==2.0.0\n"


def test_executor_append_files_late_binding(mocker):
    """Test that configuration payloads are interpolated with the active python version."""
    manifest = EnvironmentManifest()
    manifest.add_file_append("pyproject.toml", 'python_version = "{{PYTHON_VERSION}}"')
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch(
        "protostar.executor.Path.read_text",
        return_value='[project]\nrequires-python = ">=3.11"\n',
    )

    mock_file = mocker.mock_open(read_data=b'[project]\nrequires-python = ">=3.11"\n')
    mocker.patch("protostar.executor.Path.open", mock_file)
    mock_write = mocker.patch("protostar.executor.Path.write_text")

    executor._append_files()

    written_data = mock_write.call_args[0][0]
    assert 'python_version = "3.11"' in written_data


def test_executor_writes_pre_commit_config(mocker):
    """Test that the executor concatenates hooks and interpolates Mypy dependencies."""
    manifest = EnvironmentManifest()
    manifest.wants_pre_commit = True
    manifest.add_dependency("fastapi")
    manifest.add_dev_dependency("pytest")

    hook_payload = """  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies:
{{MYPY_DEPENDENCIES}}"""
    manifest.add_pre_commit_hook(hook_payload)

    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.Path.write_text")

    executor._write_pre_commit_config()

    written_data = mock_write.call_args[0][0]

    assert "trailing-whitespace" in written_data
    assert "id: mypy" in written_data
    assert "{{MYPY_DEPENDENCIES}}" not in written_data
    assert "- fastapi" in written_data
    assert "- pytest" in written_data


def test_executor_writes_dockerignore(mocker):
    """Test that the executor aggregates base ignores and vcs ignores for docker."""
    manifest = EnvironmentManifest()
    manifest.add_vcs_ignore("custom_build_artifact/")
    executor = SystemExecutor(manifest, docker=True)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch("protostar.executor.Path.read_text", return_value=".env\n")

    mock_file = mocker.mock_open()
    mocker.patch("protostar.executor.Path.open", mock_file)

    executor._write_docker_artifacts()

    written_data = mock_file().write.call_args[0][0]
    assert "custom_build_artifact/" in written_data
    assert ".git/" in written_data
    assert "README*" in written_data


def test_executor_writes_gitignore(mocker):
    """Test that .gitignore is safely updated without duplicating existing lines."""
    manifest = EnvironmentManifest()
    manifest.add_vcs_ignore("new_ignore.txt")
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch(
        "protostar.executor.Path.read_text", return_value="existing_ignore.txt\n"
    )

    mock_file = mocker.mock_open()
    mocker.patch("protostar.executor.Path.open", mock_file)

    executor._write_ignores()
    mock_file().write.assert_called_once_with("new_ignore.txt\n")


def test_executor_writes_vscode_settings(mocker):
    """Test that IDE settings merge correctly with existing JSON."""
    manifest = EnvironmentManifest()
    manifest.add_ide_setting("files.exclude", {"**/.venv": True})
    executor = SystemExecutor(manifest)

    existing_settings = {"files.exclude": {"**/node_modules": True}}

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch(
        "protostar.executor.Path.read_text",
        return_value=json.dumps(existing_settings),
    )
    mock_write_text = mocker.patch("protostar.executor.Path.write_text")
    mocker.patch("protostar.executor.Path.mkdir")

    executor._write_ide_settings()

    written_data = mock_write_text.call_args[0][0]
    parsed_write = json.loads(written_data)

    assert "**/.venv" in parsed_write["files.exclude"]
    assert "**/node_modules" in parsed_write["files.exclude"]


def test_executor_creates_directories(mocker):
    """Test that the executor generates all requested workspace directories."""
    manifest = EnvironmentManifest()
    manifest.add_directory("data")
    manifest.add_directory("src/core")
    executor = SystemExecutor(manifest)

    mock_mkdir = mocker.patch("protostar.executor.Path.mkdir")

    executor._create_directories()

    assert mock_mkdir.call_count == 2
    mock_mkdir.assert_any_call(parents=True, exist_ok=True)


def test_executor_writes_dockerignore_with_uv(mocker):
    """Test that the executor appends .python-version to .dockerignore when uv is used."""
    manifest = EnvironmentManifest()
    manifest.add_system_task(["uv", "init", "--no-workspace", "--bare", "--pin-python"])
    executor = SystemExecutor(manifest, docker=True)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_file = mocker.mock_open()
    mocker.patch("protostar.executor.Path.open", mock_file)

    executor._write_docker_artifacts()

    written_data = mock_file().write.call_args[0][0]
    assert ".python-version" in written_data


def test_executor_append_files_pip_fallback(monkeypatch, tmp_path):
    """Test that the executor scrapes pyvenv.cfg if pyproject.toml is missing."""
    monkeypatch.chdir(tmp_path)

    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.10.12\n")

    manifest = EnvironmentManifest()
    manifest.add_file_append("pyproject.toml", 'python_version = "{{PYTHON_VERSION}}"')
    executor = SystemExecutor(manifest)

    executor._append_files()

    written_data = (tmp_path / "pyproject.toml").read_text()
    assert 'python_version = "3.10"' in written_data


def test_executor_writes_vscode_settings_jsonc_abort(monkeypatch, mocker, tmp_path):
    """Test that IDE settings injection safely aborts if existing JSON has comments."""
    monkeypatch.chdir(tmp_path)

    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    settings_file = vscode_dir / "settings.json"
    settings_file.write_text("// My custom comment\n{}")

    manifest = EnvironmentManifest()
    manifest.add_ide_setting("files.exclude", {"**/.venv": True})
    executor = SystemExecutor(manifest)

    mock_print = mocker.patch("protostar.executor.console.print")

    executor._write_ide_settings()

    mock_print.assert_called_once()
    assert "contains comments or is malformed" in mock_print.call_args[0][0]
    assert settings_file.read_text() == "// My custom comment\n{}"


def test_executor_install_dependencies_pip_reqs_exist(monkeypatch, mocker, tmp_path):
    """Test that pip freeze skips overwriting an existing requirements.txt."""
    monkeypatch.chdir(tmp_path)

    req_file = tmp_path / "requirements.txt"
    req_file.write_text("my-custom-pkg==1.0.0\n")

    manifest = EnvironmentManifest()
    manifest.add_dependency("dummy-pkg")
    executor = SystemExecutor(manifest)

    mock_config = mocker.patch("protostar.executor.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="pip")

    mocker.patch("protostar.executor.run_quiet")
    mock_run = mocker.patch("protostar.executor.subprocess.run")
    mock_print = mocker.patch("protostar.executor.console.print")

    executor._install_dependencies()

    mock_print.assert_called()
    assert "requirements.txt already exists" in mock_print.call_args[0][0]
    mock_run.assert_not_called()
    assert req_file.read_text() == "my-custom-pkg==1.0.0\n"


def test_executor_writes_injected_files_overwrite(mocker):
    """Test that file injections bypass the exists() guard if OVERWRITE is active."""
    manifest = EnvironmentManifest()
    manifest.collision_strategy = CollisionStrategy.OVERWRITE
    manifest.add_file_injection(".test_config.yaml", "new content")
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.Path.write_text")

    executor._write_injected_files()
    mock_write.assert_called_once_with("new content")


def test_executor_deep_merge_tomlkit():
    """Test the recursive dictionary merge algorithm using tomlkit structures."""
    import tomlkit

    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest)

    base_toml = """
    [tool.ruff]
    line-length = 88
    target-version = "py310" # Keep this comment
    """

    payload_toml = """
    [tool.ruff]
    line-length = 100
    
    [tool.mypy]
    strict = true
    """

    base_doc = tomlkit.parse(base_toml)
    payload_doc = tomlkit.parse(payload_toml)

    executor._deep_merge_tomlkit(base_doc, payload_doc)

    merged_dict = base_doc.unwrap()

    assert merged_dict["tool"]["ruff"]["line-length"] == 100
    assert merged_dict["tool"]["ruff"]["target-version"] == "py310"
    assert merged_dict["tool"]["mypy"]["strict"] is True

    dumped = tomlkit.dumps(base_doc)
    assert "# Keep this comment" in dumped


def test_executor_append_files_ast_merge(mocker):
    """Test that _append_files mutates the TOML AST logically based on the MERGE strategy."""
    manifest = EnvironmentManifest()
    manifest.collision_strategy = CollisionStrategy.MERGE
    manifest.add_file_append("pyproject.toml", "[tool.ruff]\nline-length = 88\n")
    executor = SystemExecutor(manifest)

    existing_content = (
        "# My file\n[tool.mypy]\nstrict = true\n\n[tool.ruff]\nline-length = 120\n"
    )
    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch("protostar.executor.Path.read_text", return_value=existing_content)
    mock_write = mocker.patch("protostar.executor.Path.write_text")

    executor._append_files()
    written_data = mock_write.call_args[0][0]

    assert "# My file" in written_data
    assert "[tool.mypy]" in written_data
    assert "strict = true" in written_data
    assert "[tool.ruff]" in written_data
    assert "line-length = 88" in written_data
    assert "line-length = 120" not in written_data


def test_executor_append_files_ast_overwrite(mocker):
    """Test that the OVERWRITE strategy completely replaces colliding TOML tables."""
    manifest = EnvironmentManifest()
    manifest.collision_strategy = CollisionStrategy.OVERWRITE
    manifest.add_file_append("pyproject.toml", "[tool.ruff]\nline-length = 88\n")
    executor = SystemExecutor(manifest)

    existing_content = '[tool.mypy]\nstrict = true\n\n[tool.ruff]\nline-length = 120\ntarget-version = "py310"\n'

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch("protostar.executor.Path.read_text", return_value=existing_content)
    mock_write = mocker.patch("protostar.executor.Path.write_text")

    executor._append_files()

    written_data = mock_write.call_args[0][0]

    assert "[tool.mypy]" in written_data
    assert "strict = true" in written_data
    assert "line-length = 120" not in written_data
    assert 'target-version = "py310"' not in written_data
    assert "[tool.ruff]" in written_data
    assert "line-length = 88" in written_data


def test_executor_write_pre_commit_config_skips_existing_merge(mocker):
    """Test that pre-commit generation aborts if file exists and strategy is not OVERWRITE."""
    manifest = EnvironmentManifest()
    manifest.wants_pre_commit = True
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.Path.write_text")

    executor._write_pre_commit_config()
    mock_write.assert_not_called()


def test_executor_write_pre_commit_config_empty_deps(mocker):
    """Test that mypy late-binding injects an empty array if no python dependencies exist."""
    manifest = EnvironmentManifest()
    manifest.wants_pre_commit = True
    manifest.pre_commit_hooks.append("id: mypy\n{{MYPY_DEPENDENCIES}}")
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.executor.Path.write_text")

    executor._write_pre_commit_config()
    written_data = mock_write.call_args[0][0]
    assert "[]" in written_data


def test_executor_deep_merge_tomlkit_aot_append():
    """Test that arrays of tables (AoT) are appended to when not using OVERWRITE."""
    import tomlkit

    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest)

    base = tomlkit.parse("[[my_array]]\nval = 1\n")
    payload = tomlkit.parse("[[my_array]]\nval = 2\n")

    executor._deep_merge_tomlkit(base, payload, overwrite=False)

    result = base.unwrap()
    assert len(result["my_array"]) == 2
    assert result["my_array"][0]["val"] == 1
    assert result["my_array"][1]["val"] == 2


def test_executor_validate_targets_success(mocker):
    """Test that pre-execution validation passes silently on valid TOML files."""
    manifest = EnvironmentManifest()
    manifest.add_file_append("pyproject.toml", "[tool.ruff]")
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=True)

    mock_file = mocker.mock_open(read_data=b'[project]\nname = "test"\n')
    mocker.patch("protostar.executor.Path.open", mock_file)

    mock_exit = mocker.patch("protostar.executor.sys.exit")

    executor._validate_targets()
    mock_exit.assert_not_called()


def test_executor_validate_targets_malformed_toml(mocker):
    """Test that malformed existing TOML triggers a hard abort during pre-execution validation."""
    manifest = EnvironmentManifest()
    manifest.add_file_append("test.toml", "[section]\nkey = 'val'\n")
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=True)

    mock_file = mocker.mock_open(read_data=b"[invalid toml == \n")
    mocker.patch("protostar.executor.Path.open", mock_file)
    mock_print = mocker.patch("protostar.executor.console.print")

    with pytest.raises(SystemExit) as exc:
        executor._validate_targets()

    assert exc.value.code == 1
    printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
    assert "Validation Failure" in printed
    assert "Syntax error in existing workspace file" in printed


def test_executor_append_files_malformed_payload_toml(mocker):
    """Test that malformed payload TOML triggers an internal error abort during execution."""
    manifest = EnvironmentManifest()
    manifest.add_file_append("test.toml", "[invalid payload == \n")
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch(
        "protostar.executor.Path.read_text", return_value="[existing]\nval = 1\n"
    )

    mock_file = mocker.mock_open(read_data=b"[project]\n")
    mocker.patch("protostar.executor.Path.open", mock_file)

    mock_print = mocker.patch("protostar.executor.console.print")

    with pytest.raises(SystemExit) as exc:
        executor._append_files()

    assert exc.value.code == 1
    printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
    assert "Internal Error" in printed
    assert "Failed to parse injected TOML payload" in printed


def test_executor_append_files_string_fallback_redundant(mocker):
    """Test that the string fallback skips writing if the payload is already in the file."""
    manifest = EnvironmentManifest()
    manifest.add_file_append("test.txt", "line1\nline2")
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest)

    mocker.patch(
        "protostar.executor.Path.read_text", return_value="existing\nline1\nline2"
    )
    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.executor.Path.write_text")

    executor._append_files()
    mock_write.assert_not_called()


def test_executor_early_returns_on_empty_manifest(mocker):
    """Test that functions execute early returns when manifest data is absent."""
    manifest = EnvironmentManifest()
    executor = SystemExecutor(manifest)
    mock_exists = mocker.patch("protostar.executor.Path.exists")

    executor._write_ignores()
    executor._write_ide_settings()
    executor._install_dependencies()

    mock_exists.assert_not_called()


def test_executor_install_dependencies_pip_freeze_exception(mocker):
    """Test that a pip freeze subprocess crash is gracefully aggregated in warnings."""
    manifest = EnvironmentManifest()
    manifest.dependencies = ["requests"]
    executor = SystemExecutor(manifest)

    mock_config = mocker.patch("protostar.executor.ProtostarConfig.load")
    mock_config.return_value.python_package_manager = "pip"

    mocker.patch("protostar.executor.run_quiet")
    mocker.patch("protostar.executor.Path.exists", return_value=False)

    mocker.patch(
        "protostar.executor.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "pip freeze"),
    )

    executor._install_dependencies()

    assert any(
        "Failed to freeze dependencies to requirements.txt" in w
        for w in executor.warnings
    )


def test_executor_install_dependencies_graceful_degradation_uv(mocker):
    """Test that uv resolution failures are appended to warnings without aborting."""
    manifest = EnvironmentManifest()
    manifest.dependencies = ["invalid-pkg"]
    manifest.dev_dependencies = ["invalid-dev-pkg"]
    executor = SystemExecutor(manifest)

    mock_config = mocker.patch("protostar.executor.ProtostarConfig.load")
    mock_config.return_value.python_package_manager = "uv"

    mocker.patch(
        "protostar.executor.run_quiet",
        side_effect=RuntimeError("Resolution failed"),
    )

    executor._install_dependencies()

    assert len(executor.warnings) == 2
    assert (
        "Standard dependency resolution failed: Resolution failed"
        in executor.warnings[0]
    )
    assert (
        "Development dependency resolution failed: Resolution failed"
        in executor.warnings[1]
    )


def test_executor_install_dependencies_graceful_degradation_pip(mocker):
    """Test that pip resolution failures are appended to warnings without aborting."""
    manifest = EnvironmentManifest()
    manifest.dependencies = ["invalid-pkg"]
    executor = SystemExecutor(manifest)

    mock_config = mocker.patch("protostar.executor.ProtostarConfig.load")
    mock_config.return_value.python_package_manager = "pip"

    mocker.patch(
        "protostar.executor.run_quiet",
        side_effect=RuntimeError("Pip installation failed"),
    )
    mocker.patch("protostar.executor.Path.exists", return_value=True)

    executor._install_dependencies()

    assert len(executor.warnings) == 1
    assert (
        "Pip dependency resolution failed: Pip installation failed"
        in executor.warnings[0]
    )


def test_executor_append_files_pyproject_parse_exception(mocker):
    """Test that pyproject.toml parsing failures are caught and logged during late-binding."""
    manifest = EnvironmentManifest()
    manifest.add_file_append("dummy.txt", "content")
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=True)

    mock_file = mocker.mock_open()
    mocker.patch("protostar.executor.Path.open", mock_file)
    mocker.patch(
        "protostar.executor.tomllib.load",
        side_effect=Exception("Mocked parse error"),
    )

    mock_logger = mocker.patch("protostar.executor.logger.debug")
    mocker.patch("protostar.executor.Path.write_text")

    executor._append_files()

    mock_logger.assert_any_call(
        "Failed to parse pyproject.toml for python version: Mocked parse error"
    )


def test_executor_append_files_string_fallback_append(mocker):
    """Test that the string fallback successfully appends missing payloads to non-TOML files."""
    manifest = EnvironmentManifest()
    manifest.add_file_append("config.ini", "new_payload_1")
    manifest.add_file_append("config.ini", "new_payload_2")
    manifest.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(manifest)

    mocker.patch("protostar.executor.Path.exists", return_value=True)
    mocker.patch("protostar.executor.Path.read_text", return_value="existing_data")
    mock_write = mocker.patch("protostar.executor.Path.write_text")

    executor._append_files()

    written_data = mock_write.call_args[0][0]
    assert written_data == "existing_data\n\nnew_payload_1\n\nnew_payload_2\n"
