from pathlib import Path

import pytest

from protostar.config import ProtostarConfig
from protostar.modules import (
    CppModule,
    DirenvModule,
    LatexModule,
    LinuxModule,
    MacOSModule,
    MarkdownLintModule,
    MypyModule,
    NodeModule,
    PytestModule,
    PythonModule,
    RuffModule,
    RustModule,
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

    assert ["direnv", "allow"] in manifest.post_install_tasks


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

    # Mock config to test the 'uv' routing path
    mock_config = mocker.patch("protostar.modules.tooling_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="uv")

    mod = PreCommitModule()
    mod.build(manifest)

    assert manifest.wants_pre_commit is True
    assert "pre-commit" in manifest.dev_dependencies
    assert ["git", "init"] in manifest.system_tasks

    assert ["uv", "run", "pre-commit", "install"] in manifest.post_install_tasks


def test_pre_commit_module_build_skips_git_init(manifest, mocker):
    """Test that PreCommitModule bypasses git init if the repository is already initialized."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=True)

    # Mock config to test the 'pip' routing path
    mock_config = mocker.patch("protostar.modules.tooling_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(python_package_manager="pip")

    mod = PreCommitModule()
    mod.build(manifest)

    assert ["git", "init"] not in manifest.system_tasks

    assert [".venv/bin/pre-commit", "install"] in manifest.post_install_tasks


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


def test_macos_module_properties():
    """Test the macOS module defines its UI name correctly."""
    mod = MacOSModule()
    assert mod.name == "macOS"


def test_linux_module_properties_and_build(manifest):
    """Test the Linux module defines its UI name and applies temporary file ignores."""
    mod = LinuxModule()
    assert mod.name == "Linux"

    mod.build(manifest)
    assert "*~" in manifest.vcs_ignores
    assert "*~" in manifest.workspace_hides


def test_python_module_pre_flight_missing_uv(mocker):
    """Test PythonModule aborts pre-flight if uv is missing."""
    mod = PythonModule(package_manager="uv")
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(RuntimeError, match="Missing dependency: 'uv' is required"):
        mod.pre_flight()


def test_python_module_pre_flight_missing_pip(mocker):
    """Test PythonModule aborts pre-flight if python/python3 are missing."""
    mod = PythonModule(package_manager="pip")
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(RuntimeError, match="Missing dependency: 'python' is required"):
        mod.pre_flight()


def test_rust_module_pre_flight_missing_cargo(mocker):
    """Test RustModule aborts pre-flight if cargo is missing."""
    mod = RustModule()
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(RuntimeError, match="Missing dependency: 'cargo' is required"):
        mod.pre_flight()


def test_rust_module_collision_markers():
    """Test RustModule defines Cargo.toml as a collision marker."""
    mod = RustModule()
    assert Path("Cargo.toml") in mod.collision_markers


def test_rust_module_build(manifest, mocker):
    """Test RustModule queues the correct build artifacts and git hooks."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)
    mod = RustModule()
    mod.build(manifest)

    assert "target/" in manifest.vcs_ignores
    assert "target/" in manifest.workspace_hides
    assert ["cargo", "init"] in manifest.system_tasks
    assert any("id: clippy" in hook for hook in manifest.pre_commit_hooks)


def test_node_module_pre_flight_missing_manager(mocker):
    """Test NodeModule aborts pre-flight if the package manager is missing."""
    mod = NodeModule(package_manager="yarn")
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(RuntimeError, match="Missing dependency: 'yarn' is required"):
        mod.pre_flight()


def test_node_module_build_npm_y_flag(manifest, mocker):
    """Test NodeModule automatically appends the -y flag when using npm."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)
    mod = NodeModule(package_manager="npm")
    mod.build(manifest)

    assert ["npm", "init", "-y"] in manifest.system_tasks


def test_cpp_module_build(manifest):
    """Test CppModule queues the correct build artifacts and git hooks."""
    mod = CppModule()
    mod.build(manifest)

    assert "build/" in manifest.vcs_ignores
    assert "*.o" in manifest.vcs_ignores
    assert any("id: clang-format" in hook for hook in manifest.pre_commit_hooks)


def test_latex_module_build(manifest):
    """Test LatexModule queues the correct build artifacts and git hooks."""
    mod = LatexModule()
    mod.build(manifest)

    assert "*.aux" in manifest.vcs_ignores
    assert "*.synctex.gz" in manifest.workspace_hides
    assert any("id: tex-fmt" in hook for hook in manifest.pre_commit_hooks)
