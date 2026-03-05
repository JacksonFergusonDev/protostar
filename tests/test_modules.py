from pathlib import Path

import pytest

from protostar.config import ProtostarConfig
from protostar.modules import (
    DirenvModule,
    MacOSModule,
    MarkdownLintModule,
    MypyModule,
    NodeModule,
    PytestModule,
    PythonModule,
    RuffModule,
    VSCodeModule,
)
from protostar.modules.tooling_layer import PreCommitModule


def test_macos_module(manifest):
    """Test that the macOS layer appends correct system ignores."""
    mod = MacOSModule()
    mod.build(manifest)
    assert ".DS_Store" in manifest.vcs_ignores


def test_python_module_uv_build(manifest, mocker):
    """Test Python manifest mutation prioritizes uv by default and enforces bare initialization."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonModule(package_manager="uv")
    mod.build(manifest)

    assert ".venv/" in manifest.vcs_ignores
    assert ".ruff_cache/" not in manifest.vcs_ignores
    assert [
        "uv",
        "init",
        "--no-workspace",
        "--bare",
        "--pin-python",
    ] in manifest.system_tasks


def test_python_module_uv_with_version(manifest, mocker):
    """Test Python manifest includes the specific python version flag alongside bare initialization."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonModule(package_manager="uv", python_version="3.12")
    mod.build(manifest)

    assert [
        "uv",
        "init",
        "--no-workspace",
        "--bare",
        "--pin-python",
        "--python",
        "3.12",
    ] in manifest.system_tasks


def test_ruff_module_build(manifest):
    """Test Ruff module drops its dev dependency, ignores, hooks, and configuration."""
    mod = RuffModule()
    mod.build(manifest)

    assert "ruff" in manifest.dev_dependencies
    assert ".ruff_cache/" in manifest.vcs_ignores
    assert "pyproject.toml" in manifest.file_appends
    assert "[tool.ruff]" in manifest.file_appends["pyproject.toml"][0]
    assert any("id: ruff" in hook for hook in manifest.pre_commit_hooks)


def test_mypy_module_build(manifest):
    """Test Mypy module drops its dev dependency, ignores, hooks, and late-binding token."""
    mod = MypyModule()
    mod.build(manifest)

    assert "mypy" in manifest.dev_dependencies
    assert ".mypy_cache/" in manifest.vcs_ignores
    assert "pyproject.toml" in manifest.file_appends
    assert "{{PYTHON_VERSION}}" in manifest.file_appends["pyproject.toml"][0]
    assert any("{{MYPY_DEPENDENCIES}}" in hook for hook in manifest.pre_commit_hooks)


def test_pytest_module_build(manifest):
    """Test Pytest module drops testing dependencies and ignores."""
    mod = PytestModule()
    mod.build(manifest)

    assert "pytest" in manifest.dev_dependencies
    assert "pytest-cov" in manifest.dev_dependencies
    assert ".pytest_cache/" in manifest.vcs_ignores
    assert "htmlcov/" in manifest.vcs_ignores
    assert "pyproject.toml" in manifest.file_appends
    assert "[tool.pytest.ini_options]" in manifest.file_appends["pyproject.toml"][0]


def test_python_module_pip_build(manifest, mocker):
    """Test Python manifest correctly initializes standard library venv for pip."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonModule(package_manager="pip")
    mod.build(manifest)

    assert ".venv/" in manifest.vcs_ignores
    assert ["python3", "-m", "venv", ".venv"] in manifest.system_tasks


def test_python_module_pip_with_version(manifest, mocker):
    """Test Python manifest formats the python executable correctly for pip venvs."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = PythonModule(package_manager="pip", python_version="3.11")
    mod.build(manifest)

    assert ["python3.11", "-m", "venv", ".venv"] in manifest.system_tasks


def test_node_module_custom_manager(manifest, mocker):
    """Test that NodeModule respects custom package managers and queues hooks."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    mod = NodeModule(package_manager="pnpm")
    mod.build(manifest)

    assert ["pnpm", "init"] in manifest.system_tasks
    assert "node_modules/" in manifest.vcs_ignores
    assert any("id: prettier" in hook for hook in manifest.pre_commit_hooks)


def test_vscode_module_aliases():
    """Test that IDE aliases expose the correct mapping strings."""
    mod = VSCodeModule()
    assert "vscode" in mod.aliases
    assert "cursor" in mod.aliases


def test_vscode_module_build(manifest):
    """Test that VS Code successfully translates hides into workspace exclusions."""
    manifest.add_workspace_hide(".venv/")
    manifest.add_workspace_hide("build/")

    mod = VSCodeModule()
    mod.build(manifest)

    assert "files.exclude" in manifest.ide_settings
    exclusions = manifest.ide_settings["files.exclude"]

    assert exclusions["**/.venv"] is True
    assert exclusions["**/build"] is True


def test_direnv_module_pre_flight_fails(mocker):
    """Test that direnv preflight fails loudly if direnv is missing from PATH."""
    mocker.patch("protostar.modules.tooling_layer.shutil.which", return_value=None)
    mod = DirenvModule()

    with pytest.raises(RuntimeError, match="direnv is not installed"):
        mod.pre_flight()


def test_direnv_module_build_uv(manifest, mocker):
    """Test that direnv queue correctly formats .envrc files prioritizing uv."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)

    mock_config = mocker.patch("protostar.modules.tooling_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="uv")

    mod = DirenvModule()
    mod.build(manifest)

    assert ".envrc.local" in manifest.vcs_ignores
    assert ".envrc" in manifest.file_injections
    assert "uv sync" in manifest.file_injections[".envrc"]
    assert ["direnv", "allow"] in manifest.system_tasks


def test_markdownlint_module_build(manifest, mocker):
    """Test that MarkdownLint injects the configured ruleset and queues hooks."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)

    mod = MarkdownLintModule()
    mod.build(manifest)

    assert ".markdownlint.yaml" in manifest.file_injections
    assert "MD013: false" in manifest.file_injections[".markdownlint.yaml"]
    assert any("id: markdownlint" in hook for hook in manifest.pre_commit_hooks)


def test_pre_commit_module_pre_flight_fails(mocker):
    """Test that PreCommitModule aborts if the git binary is missing from PATH."""
    mocker.patch("protostar.modules.tooling_layer.shutil.which", return_value=None)
    mod = PreCommitModule()

    with pytest.raises(RuntimeError, match="Missing dependency: 'git' is required"):
        mod.pre_flight()


def test_pre_commit_module_build_initializes_git(manifest, mocker):
    """Test that PreCommitModule queues git init when no .git directory exists."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)

    mod = PreCommitModule()
    mod.build(manifest)

    assert manifest.wants_pre_commit is True
    assert "pre-commit" in manifest.dev_dependencies
    assert ["git", "init"] in manifest.system_tasks
    assert ["pre-commit", "install"] in manifest.system_tasks


def test_pre_commit_module_build_skips_git_init(manifest, mocker):
    """Test that PreCommitModule bypasses git init if the repository is already initialized."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=True)

    mod = PreCommitModule()
    mod.build(manifest)

    assert ["git", "init"] not in manifest.system_tasks
    assert ["pre-commit", "install"] in manifest.system_tasks


def test_python_module_collision_markers():
    """Test that Python modules expose the correct collision markers based on the package manager."""
    mod_uv = PythonModule(package_manager="uv")
    assert Path("pyproject.toml") in mod_uv.collision_markers

    mod_pip = PythonModule(package_manager="pip")
    assert Path("requirements.txt") in mod_pip.collision_markers


def test_node_module_collision_markers():
    """Test that Node modules expose package.json as a collision marker."""
    mod = NodeModule()
    assert Path("package.json") in mod.collision_markers


def test_tooling_module_collision_markers():
    """Test that various tooling modules expose their configuration files as collision markers."""
    assert Path(".envrc") in DirenvModule().collision_markers
    assert Path(".markdownlint.yaml") in MarkdownLintModule().collision_markers
    assert Path(".pre-commit-config.yaml") in PreCommitModule().collision_markers
