import json
import subprocess
from pathlib import Path

import pytest

from protostar.config import ProtostarConfig
from protostar.manifest import CollisionStrategy
from protostar.modules import BootstrapModule
from protostar.orchestrator import Orchestrator
from protostar.presets.base import PresetModule


class DummyModule(BootstrapModule):
    """A mock module for testing the orchestrator lifecycle."""

    @property
    def name(self):
        return "Dummy"

    @property
    def collision_markers(self):
        return [Path("dummy_marker.txt")]

    def pre_flight(self):
        self.pre_flight_called = True

    def build(self, manifest):
        manifest.add_vcs_ignore("dummy_file.txt")
        manifest.add_system_task(["echo", "dummy"])
        manifest.add_dependency("dummy-pkg")


class DummyPreset(PresetModule):
    """A mock preset for testing the orchestrator lifecycle."""

    @property
    def name(self):
        return "DummyPreset"

    def build(self, manifest):
        manifest.add_dependency("dummy-preset-pkg")


def test_orchestrator_lifecycle(mocker):
    """Test that the orchestrator calls pre_flight, build, and executes tasks."""
    mock_run_quiet = mocker.patch("protostar.orchestrator.run_quiet")
    mocker.patch("protostar.orchestrator.Orchestrator._write_injected_files")
    mocker.patch("protostar.orchestrator.Orchestrator._write_pre_commit_config")
    mocker.patch("protostar.orchestrator.Orchestrator._write_ignores")
    mocker.patch("protostar.orchestrator.Orchestrator._write_docker_artifacts")
    mocker.patch("protostar.orchestrator.Orchestrator._write_ide_settings")

    # Mock the global config lookup inside _install_dependencies
    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="uv")

    dummy_mod = DummyModule()
    dummy_preset = DummyPreset()

    # Pass both the module and the preset
    orchestrator = Orchestrator([dummy_mod], presets=[dummy_preset])

    orchestrator.run()

    assert dummy_mod.pre_flight_called is True
    assert "dummy_file.txt" in orchestrator.manifest.vcs_ignores

    # Verify tasks and dependencies were executed (1 from module, 1 from preset)
    mock_run_quiet.assert_any_call(["echo", "dummy"], "Executing echo")
    mock_run_quiet.assert_any_call(
        ["uv", "add", "dummy-pkg", "dummy-preset-pkg"],
        "Resolving and installing 2 dependencies",
    )


def test_orchestrator_writes_injected_files(mocker):
    """Test that the orchestrator flushes queued file injections to disk."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])
    orchestrator.manifest.add_file_injection(".test_config.yaml", "mock content")

    mocker.patch("protostar.orchestrator.Path.exists", return_value=False)
    mock_mkdir = mocker.patch("protostar.orchestrator.Path.mkdir")
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._write_injected_files()

    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_write.assert_called_once_with("mock content")


def test_orchestrator_install_dependencies_uv(mocker):
    """Test that the orchestrator uses uv add --dev for dev dependencies."""
    mock_run_quiet = mocker.patch("protostar.orchestrator.run_quiet")
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)

    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="uv")

    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    orchestrator.manifest.add_dependency("fastapi")
    orchestrator.manifest.add_dev_dependency("pytest")

    orchestrator._install_dependencies()

    mock_run_quiet.assert_any_call(
        ["uv", "add", "fastapi"],
        "Resolving and installing 1 dependencies",
    )
    mock_run_quiet.assert_any_call(
        ["uv", "add", "--dev", "pytest"],
        "Resolving and installing 1 development dependencies",
    )


def test_orchestrator_install_dependencies_pip_freeze(monkeypatch, mocker, tmp_path):
    """Test that the orchestrator executes a local pip installation and writes a freeze state."""
    # Natively isolate all disk I/O to the sandbox
    monkeypatch.chdir(tmp_path)

    mock_run_quiet = mocker.patch("protostar.orchestrator.run_quiet")
    mock_run = mocker.patch("protostar.orchestrator.subprocess.run")

    # Create a fake pip executable in the sandbox to satisfy the existence check naturally
    pip_bin = tmp_path / ".venv" / "bin"
    pip_bin.mkdir(parents=True)
    pip_exe = pip_bin / "pip"
    pip_exe.touch()

    # Mock config to force the pip route
    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="pip")

    # Mock the stdout of the freeze command
    mock_run.return_value.stdout = "dummy-pkg==1.0.0\ndev-pkg==2.0.0\n"

    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # Manually populate the manifest
    orchestrator.manifest.add_dependency("dummy-pkg")
    orchestrator.manifest.add_dev_dependency("dev-pkg")

    orchestrator._install_dependencies()

    # Pip lacks native dev dependency segregation, so they are installed collectively
    mock_run_quiet.assert_called_once_with(
        [".venv/bin/pip", "install", "dummy-pkg", "dev-pkg"],
        "Resolving and installing 2 total dependencies",
    )

    mock_run.assert_called_once_with(
        [".venv/bin/pip", "freeze"], capture_output=True, text=True, check=True
    )

    # Verify the file was actually written safely inside the sandbox
    assert (
        tmp_path / "requirements.txt"
    ).read_text() == "dummy-pkg==1.0.0\ndev-pkg==2.0.0\n"


def test_orchestrator_append_files_late_binding(mocker):
    """Test that configuration payloads are interpolated with the active python version."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    orchestrator.manifest.add_file_append(
        "pyproject.toml", 'python_version = "{{PYTHON_VERSION}}"'
    )

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch(
        "protostar.orchestrator.Path.read_text",
        return_value='[project]\nrequires-python = ">=3.11"\n',
    )

    # Mock binary read for tomllib
    mock_file = mocker.mock_open(read_data=b'[project]\nrequires-python = ">=3.11"\n')
    mocker.patch("protostar.orchestrator.Path.open", mock_file)
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._append_files()

    written_data = mock_write.call_args[0][0]
    # Verify the regex successfully extracted '3.11' and interpolated the {{PYTHON_VERSION}} token
    assert 'python_version = "3.11"' in written_data


def test_orchestrator_writes_pre_commit_config(mocker):
    """Test that the orchestrator concatenates hooks and interpolates Mypy dependencies."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # 1. Flag activation and populate dynamic dependencies
    orchestrator.manifest.wants_pre_commit = True
    orchestrator.manifest.add_dependency("fastapi")
    orchestrator.manifest.add_dev_dependency("pytest")

    # 2. Queue a hook with the interpolation token
    hook_payload = """  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies:
{{MYPY_DEPENDENCIES}}"""
    orchestrator.manifest.add_pre_commit_hook(hook_payload)

    mocker.patch("protostar.orchestrator.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._write_pre_commit_config()

    # Verify what was written to the .pre-commit-config.yaml file
    written_data = mock_write.call_args[0][0]

    # Verify base hooks were prepended
    assert "trailing-whitespace" in written_data
    # Verify the target hook was appended
    assert "id: mypy" in written_data

    # Verify the dependency token was successfully evaluated and formatted
    assert "{{MYPY_DEPENDENCIES}}" not in written_data
    assert "- fastapi" in written_data
    assert "- pytest" in written_data


def test_orchestrator_writes_dockerignore(mocker):
    """Test that the orchestrator aggregates base ignores and vcs ignores for docker."""
    dummy_mod = DummyModule()

    # Initialize with the docker flag set to True
    orchestrator = Orchestrator([dummy_mod], docker=True)
    orchestrator.manifest.add_vcs_ignore("custom_build_artifact/")

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.Path.read_text", return_value=".env\n")

    mock_file = mocker.mock_open()
    mocker.patch("protostar.orchestrator.Path.open", mock_file)

    orchestrator._write_docker_artifacts()

    # Verify what was written to the .dockerignore file
    written_data = mock_file().write.call_args[0][0]

    # Should contain our custom manifest ignore
    assert "custom_build_artifact/" in written_data

    # Should contain the standard daemon exclusions appended by the orchestrator
    assert ".git/" in written_data
    assert "README*" in written_data


def test_orchestrator_writes_gitignore(mocker):
    """Test that .gitignore is safely updated without duplicating existing lines."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])
    orchestrator.manifest.add_vcs_ignore("new_ignore.txt")

    # Patch Path methods directly to avoid Path division (__truediv__) mock issues
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch(
        "protostar.orchestrator.Path.read_text", return_value="existing_ignore.txt\n"
    )

    # Use mocker.mock_open to correctly simulate the file context manager
    mock_file = mocker.mock_open()
    mocker.patch("protostar.orchestrator.Path.open", mock_file)

    orchestrator._write_ignores()

    # Since the mock file content already ends with \n, the prefix is empty.
    mock_file().write.assert_called_once_with("new_ignore.txt\n")


def test_orchestrator_writes_vscode_settings(mocker):
    """Test that IDE settings merge correctly with existing JSON."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # We are injecting an update to files.exclude
    orchestrator.manifest.add_ide_setting("files.exclude", {"**/.venv": True})

    # The existing file ALSO has a files.exclude dictionary
    existing_settings = {"files.exclude": {"**/node_modules": True}}

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch(
        "protostar.orchestrator.Path.read_text",
        return_value=json.dumps(existing_settings),
    )
    mock_write_text = mocker.patch("protostar.orchestrator.Path.write_text")
    mocker.patch("protostar.orchestrator.Path.mkdir")

    orchestrator._write_ide_settings()

    written_data = mock_write_text.call_args[0][0]
    parsed_write = json.loads(written_data)

    # Verify BOTH rules exist inside the unified files.exclude dictionary
    assert "**/.venv" in parsed_write["files.exclude"]
    assert "**/node_modules" in parsed_write["files.exclude"]


def test_orchestrator_creates_directories(mocker):
    """Test that the orchestrator generates all requested workspace directories."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # Queue directory scaffolding
    orchestrator.manifest.add_directory("data")
    orchestrator.manifest.add_directory("src/core")

    mock_mkdir = mocker.patch("protostar.orchestrator.Path.mkdir")

    orchestrator._create_directories()

    assert mock_mkdir.call_count == 2
    mock_mkdir.assert_any_call(parents=True, exist_ok=True)


def test_orchestrator_writes_dockerignore_with_uv(mocker):
    """Test that the orchestrator appends .python-version to .dockerignore when uv is used."""
    dummy_mod = DummyModule()

    # Initialize with docker flag to trigger artifact generation
    orchestrator = Orchestrator([dummy_mod], docker=True)

    # Inject the uv init task to trigger the dynamic exclusion condition
    orchestrator.manifest.add_system_task(
        ["uv", "init", "--no-workspace", "--bare", "--pin-python"]
    )

    mocker.patch("protostar.orchestrator.Path.exists", return_value=False)

    mock_file = mocker.mock_open()
    mocker.patch("protostar.orchestrator.Path.open", mock_file)

    orchestrator._write_docker_artifacts()

    written_data = mock_file().write.call_args[0][0]

    # Verify the host-side interpreter pin is successfully isolated from the container
    assert ".python-version" in written_data


def test_orchestrator_crash_reporter(mocker):
    """Test that unhandled exceptions generate telemetry payloads and prompt for issues."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # Force a critical internal failure during the pre-flight phase
    mocker.patch.object(
        dummy_mod, "pre_flight", side_effect=TypeError("Unhandled null pointer")
    )

    mock_console = mocker.patch("protostar.orchestrator.console.print")
    mock_exit = mocker.patch("protostar.orchestrator.sys.exit")

    orchestrator.run()

    mock_exit.assert_called_once_with(1)

    # Aggregate console outputs to verify telemetry URL generation
    printed_output = " ".join(
        call.args[0] for call in mock_console.call_args_list if call.args
    )

    assert "CRITICAL FAILURE" in printed_output
    assert (
        "https://github.com/jacksonfergusondev/protostar/issues/new" in printed_output
    )
    assert "Crash+Report" in printed_output


def test_orchestrator_append_files_pip_fallback(monkeypatch, tmp_path):
    """Test that the orchestrator scrapes pyvenv.cfg if pyproject.toml is missing."""
    monkeypatch.chdir(tmp_path)

    # Simulate a pip virtual environment config
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.10.12\n")

    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # Add a payload that requires python version interpolation
    orchestrator.manifest.add_file_append(
        "pyproject.toml", 'python_version = "{{PYTHON_VERSION}}"'
    )

    orchestrator._append_files()

    written_data = (tmp_path / "pyproject.toml").read_text()
    assert 'python_version = "3.10"' in written_data


def test_orchestrator_writes_vscode_settings_jsonc_abort(monkeypatch, mocker, tmp_path):
    """Test that IDE settings injection safely aborts if existing JSON has comments."""
    monkeypatch.chdir(tmp_path)

    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    settings_file = vscode_dir / "settings.json"

    # Write JSONC (JSON with comments) which will cause json.loads() to fail
    settings_file.write_text("// My custom comment\n{}")

    orchestrator = Orchestrator([])
    orchestrator.manifest.add_ide_setting("files.exclude", {"**/.venv": True})

    mock_print = mocker.patch("protostar.orchestrator.console.print")

    orchestrator._write_ide_settings()

    # Verify the warning was printed
    mock_print.assert_called_once()
    assert "contains comments or is malformed" in mock_print.call_args[0][0]

    # Verify the file was NOT overwritten
    assert settings_file.read_text() == "// My custom comment\n{}"


def test_orchestrator_install_dependencies_pip_reqs_exist(
    monkeypatch, mocker, tmp_path
):
    """Test that pip freeze skips overwriting an existing requirements.txt."""
    monkeypatch.chdir(tmp_path)

    # Pre-create a requirements.txt file with custom data
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("my-custom-pkg==1.0.0\n")

    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="pip")

    orchestrator = Orchestrator([])
    orchestrator.manifest.add_dependency("dummy-pkg")

    mocker.patch("protostar.orchestrator.run_quiet")
    mock_run = mocker.patch("protostar.orchestrator.subprocess.run")
    mock_print = mocker.patch("protostar.orchestrator.console.print")

    orchestrator._install_dependencies()

    # Verify the warning was printed
    mock_print.assert_called()
    printed_warning = mock_print.call_args[0][0]
    assert "requirements.txt already exists" in printed_warning

    # Verify pip freeze was skipped
    mock_run.assert_not_called()

    # Verify the file is untouched
    assert req_file.read_text() == "my-custom-pkg==1.0.0\n"


def test_orchestrator_evaluate_collisions_headless_aborts_by_default(mocker):
    """Test that a headless environment safely aborts on collision without the force flag."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    # Simulate the marker existing and a headless environment
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=False)

    # Configure the mock to actually raise SystemExit, preventing fall-through
    mock_exit = mocker.patch("protostar.orchestrator.sys.exit", side_effect=SystemExit)
    mock_console = mocker.patch("protostar.orchestrator.console.print")

    # Catch the exit to prevent it from failing the test
    with pytest.raises(SystemExit):
        orchestrator._evaluate_collisions()

    # Verify it halted the process with code 1
    mock_exit.assert_called_once_with(1)

    # Verify the warning instructs the user to use the --force flag
    printed_output = " ".join(
        call.args[0] for call in mock_console.call_args_list if call.args
    )
    assert "--force" in printed_output


def test_orchestrator_evaluate_collisions_headless_with_force_merges(mocker):
    """Test that a headless environment respects the --force flag and defaults to MERGE."""
    dummy_mod = DummyModule()

    # Initialize with the force flag enabled
    orchestrator = Orchestrator([dummy_mod], force=True)

    # Simulate the marker existing and a headless environment
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=False)

    orchestrator._evaluate_collisions()

    assert orchestrator.manifest.collision_strategy == CollisionStrategy.MERGE


def test_orchestrator_evaluate_collisions_interactive_abort(mocker):
    """Test that selecting ABORT in the collision TUI triggers a safe exit."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=True)

    mocker.patch.dict("os.environ", clear=True)

    # Mock questionary to return ABORT
    mock_questionary = mocker.patch("questionary.select")
    mock_questionary.return_value.ask.return_value = CollisionStrategy.ABORT

    mock_exit = mocker.patch("protostar.orchestrator.sys.exit")

    orchestrator._evaluate_collisions()
    mock_exit.assert_called_once_with(1)


def test_orchestrator_evaluate_collisions_interactive_overwrite(mocker):
    """Test that selecting OVERWRITE correctly updates the manifest strategy."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.sys.stdin.isatty", return_value=True)

    mocker.patch.dict("os.environ", clear=True)

    mock_questionary = mocker.patch("questionary.select")
    mock_questionary.return_value.ask.return_value = CollisionStrategy.OVERWRITE

    orchestrator._evaluate_collisions()
    assert orchestrator.manifest.collision_strategy == CollisionStrategy.OVERWRITE


def test_orchestrator_writes_injected_files_overwrite(mocker):
    """Test that file injections bypass the exists() guard if OVERWRITE is active."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])
    orchestrator.manifest.collision_strategy = CollisionStrategy.OVERWRITE
    orchestrator.manifest.add_file_injection(".test_config.yaml", "new content")

    # File exists, but the overwrite strategy should force the write
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._write_injected_files()
    mock_write.assert_called_once_with("new content")


def test_orchestrator_deep_merge_tomlkit():
    """Test the recursive dictionary merge algorithm using tomlkit structures."""
    import tomlkit

    orchestrator = Orchestrator([])

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

    orchestrator._deep_merge_tomlkit(base_doc, payload_doc)

    # Unwrap the AST document into a standard Python dict for type-safe assertions
    merged_dict = base_doc.unwrap()

    # Existing key updated
    assert merged_dict["tool"]["ruff"]["line-length"] == 100
    # Existing non-overlapping key preserved
    assert merged_dict["tool"]["ruff"]["target-version"] == "py310"
    # New branch injected
    assert merged_dict["tool"]["mypy"]["strict"] is True

    # Assert comment preservation (using the original AST document, not the unwrapped dict)
    dumped = tomlkit.dumps(base_doc)
    assert "# Keep this comment" in dumped


def test_orchestrator_append_files_ast_merge(mocker):
    """Test that _append_files mutates the TOML AST logically based on the MERGE strategy."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])
    orchestrator.manifest.collision_strategy = CollisionStrategy.MERGE

    # Queue an update to [tool.ruff]
    orchestrator.manifest.add_file_append(
        "pyproject.toml", "[tool.ruff]\nline-length = 88\n"
    )

    existing_content = (
        "# My file\n[tool.mypy]\nstrict = true\n\n[tool.ruff]\nline-length = 120\n"
    )
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.Path.read_text", return_value=existing_content)
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._append_files()
    written_data = mock_write.call_args[0][0]

    # Mypy block and comments should be entirely untouched
    assert "# My file" in written_data
    assert "[tool.mypy]" in written_data
    assert "strict = true" in written_data

    # Ruff block should be merged logically
    assert "[tool.ruff]" in written_data
    assert "line-length = 88" in written_data
    assert "line-length = 120" not in written_data


def test_orchestrator_append_files_ast_overwrite(mocker):
    """Test that the OVERWRITE strategy completely replaces colliding TOML tables."""
    dummy_mod = DummyModule()
    orchestrator = Orchestrator([dummy_mod])
    orchestrator.manifest.collision_strategy = CollisionStrategy.OVERWRITE

    # Queue an update to [tool.ruff]
    orchestrator.manifest.add_file_append(
        "pyproject.toml", "[tool.ruff]\nline-length = 88\n"
    )

    # Existing file has a conflicting [tool.ruff] table with extra keys
    existing_content = '[tool.mypy]\nstrict = true\n\n[tool.ruff]\nline-length = 120\ntarget-version = "py310"\n'

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch("protostar.orchestrator.Path.read_text", return_value=existing_content)
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._append_files()

    written_data = mock_write.call_args[0][0]

    # The safe table should still be there
    assert "[tool.mypy]" in written_data
    assert "strict = true" in written_data

    # The old tool.ruff values should be purged completely
    assert "line-length = 120" not in written_data
    assert 'target-version = "py310"' not in written_data

    # The new tool.ruff payload should be injected
    assert "[tool.ruff]" in written_data
    assert "line-length = 88" in written_data


def test_orchestrator_run_global_injections(mocker):
    """Test that global dev dependencies and pyproject injections are added in Phase 3."""
    orchestrator = Orchestrator([])

    # Mock everything after Phase 3 to prevent actual execution
    for method in [
        "_evaluate_collisions",
        "_create_directories",
        "_write_injected_files",
        "_write_pre_commit_config",
        "_execute_tasks",
        "_validate_targets",
        "_append_files",
        "_write_ignores",
        "_write_docker_artifacts",
        "_write_ide_settings",
        "_install_dependencies",
    ]:
        mocker.patch.object(orchestrator, method)

    # Mock the global configuration
    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value.global_dev_dependencies = ["test-global-dep"]
    mock_config.return_value.pyproject_injections = {"custom_key": "custom_payload"}

    orchestrator.run()

    assert "test-global-dep" in orchestrator.manifest.dev_dependencies
    assert "custom_payload" in orchestrator.manifest.file_appends["pyproject.toml"]


def test_orchestrator_run_known_exception(mocker):
    """Test that known exceptions (e.g. FileExistsError) abort cleanly without stack traces."""
    orchestrator = Orchestrator([])
    mocker.patch.object(
        orchestrator, "_evaluate_collisions", side_effect=FileExistsError("Known error")
    )
    mock_exit = mocker.patch("protostar.orchestrator.sys.exit", side_effect=SystemExit)
    mock_print = mocker.patch("protostar.orchestrator.console.print")

    with pytest.raises(SystemExit):
        orchestrator.run()

    mock_exit.assert_called_once_with(1)
    printed = " ".join(
        call.args[0]
        for call in mock_print.call_args_list
        if call.args and isinstance(call.args[0], str)
    )
    assert "ABORTED" in printed
    assert "Known error" in printed


def test_orchestrator_run_unknown_exception(mocker):
    """Test that unknown exceptions trigger the telemetry generation URL and full traceback."""
    orchestrator = Orchestrator([])
    mocker.patch.object(
        orchestrator, "_evaluate_collisions", side_effect=KeyError("Unknown crash")
    )
    mock_exit = mocker.patch("protostar.orchestrator.sys.exit", side_effect=SystemExit)
    mock_print = mocker.patch("protostar.orchestrator.console.print")

    with pytest.raises(SystemExit):
        orchestrator.run()

    mock_exit.assert_called_once_with(1)
    printed = " ".join(
        call.args[0]
        for call in mock_print.call_args_list
        if call.args and isinstance(call.args[0], str)
    )
    assert "CRITICAL FAILURE" in printed
    assert "https://github.com/" in printed


def test_write_pre_commit_config_skips_existing_merge(mocker):
    """Test that pre-commit generation aborts if file exists and strategy is not OVERWRITE."""
    orchestrator = Orchestrator([])
    orchestrator.manifest.wants_pre_commit = True
    orchestrator.manifest.collision_strategy = CollisionStrategy.MERGE

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._write_pre_commit_config()
    mock_write.assert_not_called()


def test_write_pre_commit_config_empty_deps(mocker):
    """Test that mypy late-binding injects an empty array if no python dependencies exist."""
    orchestrator = Orchestrator([])
    orchestrator.manifest.wants_pre_commit = True
    orchestrator.manifest.pre_commit_hooks.append("id: mypy\n{{MYPY_DEPENDENCIES}}")

    mocker.patch("protostar.orchestrator.Path.exists", return_value=False)
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._write_pre_commit_config()
    written_data = mock_write.call_args[0][0]
    assert "[]" in written_data


def test_deep_merge_tomlkit_aot_append():
    """Test that arrays of tables (AoT) are appended to when not using OVERWRITE."""
    import tomlkit

    orchestrator = Orchestrator([])
    base = tomlkit.parse("[[my_array]]\nval = 1\n")
    payload = tomlkit.parse("[[my_array]]\nval = 2\n")

    orchestrator._deep_merge_tomlkit(base, payload, overwrite=False)

    # Unwrap the tomlkit document to a standard Python dict for type-safe assertions
    result = base.unwrap()
    assert len(result["my_array"]) == 2
    assert result["my_array"][0]["val"] == 1
    assert result["my_array"][1]["val"] == 2


def test_validate_targets_success(mocker):
    """Test that pre-execution validation passes silently on valid TOML files."""
    orchestrator = Orchestrator([])
    orchestrator.manifest.add_file_append("pyproject.toml", "[tool.ruff]")

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)

    # Provide valid binary TOML for tomllib to parse
    mock_file = mocker.mock_open(read_data=b'[project]\nname = "test"\n')
    mocker.patch("protostar.orchestrator.Path.open", mock_file)

    mock_exit = mocker.patch("protostar.orchestrator.sys.exit")

    orchestrator._validate_targets()
    mock_exit.assert_not_called()


def test_validate_targets_malformed_toml(mocker):
    """Test that malformed existing TOML triggers a hard abort during pre-execution validation."""
    orchestrator = Orchestrator([])
    orchestrator.manifest.add_file_append("test.toml", "[section]\nkey = 'val'\n")

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)

    # Provide invalid binary TOML
    mock_file = mocker.mock_open(read_data=b"[invalid toml == \n")
    mocker.patch("protostar.orchestrator.Path.open", mock_file)

    mock_print = mocker.patch("protostar.orchestrator.console.print")

    with pytest.raises(SystemExit) as exc:
        orchestrator._validate_targets()

    assert exc.value.code == 1
    printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list)

    assert "Validation Failure" in printed
    assert "Syntax error in existing workspace file" in printed


def test_append_files_malformed_payload_toml(mocker):
    """Test that malformed payload TOML triggers an internal error abort during execution."""
    orchestrator = Orchestrator([])
    orchestrator.manifest.add_file_append("test.toml", "[invalid payload == \n")

    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mocker.patch(
        "protostar.orchestrator.Path.read_text", return_value="[existing]\nval = 1\n"
    )

    # Fulfill the binary open for version scraping just in case
    mock_file = mocker.mock_open(read_data=b"[project]\n")
    mocker.patch("protostar.orchestrator.Path.open", mock_file)

    mock_print = mocker.patch("protostar.orchestrator.console.print")

    with pytest.raises(SystemExit) as exc:
        orchestrator._append_files()

    assert exc.value.code == 1
    printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list)

    assert "Internal Error" in printed
    assert "Failed to parse injected TOML payload" in printed


def test_append_files_string_fallback_redundant(mocker):
    """Test that the string fallback skips writing if the payload is already in the file."""
    orchestrator = Orchestrator([])
    orchestrator.manifest.add_file_append("test.txt", "line1\nline2")
    orchestrator.manifest.collision_strategy = CollisionStrategy.MERGE

    mocker.patch(
        "protostar.orchestrator.Path.read_text", return_value="existing\nline1\nline2"
    )
    mocker.patch("protostar.orchestrator.Path.exists", return_value=True)
    mock_write = mocker.patch("protostar.orchestrator.Path.write_text")

    orchestrator._append_files()
    mock_write.assert_not_called()


def test_early_returns_on_empty_manifest(mocker):
    """Test that functions execute early returns when manifest data is absent."""
    orchestrator = Orchestrator([])
    mock_exists = mocker.patch("protostar.orchestrator.Path.exists")

    orchestrator._write_ignores()
    orchestrator._write_ide_settings()
    orchestrator._install_dependencies()

    mock_exists.assert_not_called()


def test_install_dependencies_pip_freeze_exception(mocker):
    """Test that a pip freeze subprocess crash is caught and logged as a warning."""
    orchestrator = Orchestrator([])
    orchestrator.manifest.dependencies = ["requests"]

    mock_config = mocker.patch("protostar.orchestrator.ProtostarConfig.load")
    mock_config.return_value.python_package_manager = "pip"

    mocker.patch("protostar.orchestrator.run_quiet")
    mocker.patch("protostar.orchestrator.Path.exists", return_value=False)

    # Simulate a crash during `pip freeze`
    mocker.patch(
        "protostar.orchestrator.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "pip freeze"),
    )
    mock_print = mocker.patch("protostar.orchestrator.console.print")

    orchestrator._install_dependencies()

    printed = " ".join(
        call.args[0]
        for call in mock_print.call_args_list
        if call.args and isinstance(call.args[0], str)
    )
    assert "Failed to freeze dependencies to requirements.txt" in printed
