from pathlib import Path

import pytest

from protostar.config import ProtostarConfig
from protostar.errors import ConfigurationError, MissingDependencyError
from protostar.manifest import EnvironmentManifest, Severity
from protostar.modules import (
    CodecovModule,
    CommitizinModule,
    DirenvModule,
    MarkdownLintModule,
    MypyModule,
    PreCommitModule,
    PrekModule,
    PyreflyModule,
    PytestModule,
    PythonCore,
    ReadTheDocsModule,
    RenovateModule,
    RuffModule,
    TyModule,
    ZensicalModule,
)


def test_python_module_uv_build(manifest, mocker):
    """Test Python manifest mutation prioritizes uv by default and enforces bare initialization."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    # Prevent IDE injection to isolate build testing
    mock_config = mocker.patch("protostar.modules.lang_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(ide=None)

    mod = PythonCore()
    mod.build(manifest)

    assert ".venv/" in manifest.vcs_ignores
    assert ".ruff_cache/" not in manifest.vcs_ignores
    assert any(
        t.command
        == [
            "uv",
            "init",
            "--no-workspace",
            "--bare",
            "--pin-python",
            "--python",
            "3.13",
        ]
        for t in manifest.system_tasks
    )

    # Find the uv init task and verify its description
    task = next(t for t in manifest.system_tasks if t.command[0] == "uv")
    assert task.description == "Scaffolding uv virtual environment"


def test_python_module_uv_with_version(manifest, mocker):
    """Test Python manifest includes the specific python version flag alongside bare initialization."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)
    mock_config = mocker.patch("protostar.modules.lang_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(ide=None)

    mod = PythonCore(python_version="3.12")
    mod.build(manifest)

    assert any(
        t.command
        == [
            "uv",
            "init",
            "--no-workspace",
            "--bare",
            "--pin-python",
            "--python",
            "3.12",
        ]
        for t in manifest.system_tasks
    )


def test_python_module_ide_injection_active(manifest, mocker):
    """Test that the Python module dynamically injects the interpreter path for supported IDEs."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    # Mock global config to explicitly request VS Code
    mock_config = mocker.patch("protostar.modules.lang_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(ide="vscode")

    mod = PythonCore()
    mod.build(manifest)

    assert "python.defaultInterpreterPath" in manifest.ide_settings
    assert "/.venv/bin/python" in manifest.ide_settings["python.defaultInterpreterPath"]
    assert manifest.ide_settings["python.terminal.activateEnvironment"] is True


def test_python_module_ide_injection_inactive(manifest, mocker):
    """Test that the Python module skips IDE injection if the preferred IDE is unsupported or None."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    # Mock global config to represent an unconfigured or non-VS Code state
    mock_config = mocker.patch("protostar.modules.lang_layer.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(ide=None)

    mod = PythonCore()
    mod.build(manifest)

    assert "python.defaultInterpreterPath" not in manifest.ide_settings


def test_python_module_pre_flight_missing_uv(mocker):
    """Test PythonCore aborts pre-flight if uv is missing."""
    mod = PythonCore()
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(MissingDependencyError) as exc_info:
        mod.pre_flight()

    assert exc_info.value.dependency == "uv"
    assert "Python scaffolding" in exc_info.value.purpose


# --- DirenvModule Tests ---


def test_direnv_pre_flight_missing(mocker):
    """Test DirenvModule aborts pre-flight if direnv is missing."""
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(MissingDependencyError) as exc_info:
        DirenvModule().pre_flight()

    assert exc_info.value.dependency == "direnv"
    assert "direnv integration" in exc_info.value.purpose


def test_direnv_collision_markers():
    assert DirenvModule().collision_markers == [Path(".envrc")]


def test_direnv_build(manifest, mocker):
    """Test DirenvModule generates the `.envrc` injection and queues evaluation."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)

    mod = DirenvModule()
    mod.build(manifest)

    assert ".envrc.local" in manifest.vcs_ignores
    assert ".direnv/" in manifest.vcs_ignores
    assert ".envrc" in manifest.file_injections
    assert any(t.command == ["direnv", "allow"] for t in manifest.post_install_tasks)


def test_direnv_build_file_exists(manifest, mocker):
    """Test DirenvModule skips `.envrc` injection if it already exists."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=True)
    mod = DirenvModule()
    mod.build(manifest)
    assert ".envrc" not in manifest.file_injections


# --- MarkdownLintModule Tests ---


def test_markdownlint_collision_markers():
    assert MarkdownLintModule().collision_markers == [Path(".markdownlint-cli2.yaml")]


def test_markdownlint_build(manifest, mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)
    mod = MarkdownLintModule()
    mod.build(manifest)

    assert ".markdownlint-cli2.yaml" in manifest.file_injections
    assert any("markdownlint-cli2" in hook for hook in manifest.pre_commit_hooks)


def test_markdownlint_build_file_exists(manifest, mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=True)
    mod = MarkdownLintModule()
    mod.build(manifest)
    assert ".markdownlint-cli2.yaml" not in manifest.file_injections


# --- PytestModule Tests ---


def test_pytest_build(manifest):
    mod = PytestModule()
    mod.build(manifest)

    assert "pytest" in manifest.dev_dependencies
    assert "pytest-mock" in manifest.dev_dependencies
    assert "pytest-cov" not in manifest.dev_dependencies
    assert "tests" in manifest.directories
    assert "pyproject.toml" in manifest.file_appends


def test_ruff_module_base_config():
    manifest = EnvironmentManifest()
    mod = RuffModule()
    mod.build(manifest)

    appends = manifest.file_appends.get("pyproject.toml", [])
    combined = "\n".join(appends)
    assert '"A",' in combined
    assert '"C4",' in combined
    assert '"RUF",' in combined
    assert '"D",' not in combined


def test_ruff_module_adds_pre_commit_hook():
    manifest = EnvironmentManifest()
    mod = RuffModule()
    mod.build(manifest)

    assert len(manifest.pre_commit_local_hooks) == 1
    hook = manifest.pre_commit_local_hooks[0]
    assert "id: ruff-check" in hook
    assert "id: ruff-format" in hook
    assert "entry: uv run ruff check --fix" in hook
    assert "entry: uv run ruff format" in hook
    assert "language: system" in hook


def test_mypy_module_base_config():
    manifest = EnvironmentManifest()
    mod = MypyModule()
    mod.build(manifest)

    appends = manifest.file_appends.get("pyproject.toml", [])
    combined = "\n".join(appends)
    assert "pretty = true" in combined
    assert "check_untyped_defs = true" in combined
    assert "strict = true" not in combined


def test_mypy_module_adds_pre_commit_hook():
    manifest = EnvironmentManifest()
    mod = MypyModule()
    mod.build(manifest)

    assert len(manifest.pre_commit_local_hooks) == 1
    hook = manifest.pre_commit_local_hooks[0]
    assert "id: mypy" in hook
    assert "entry: uv run mypy" in hook
    assert "language: system" in hook
    assert "pass_filenames: true" in hook


def test_ty_module_build():
    manifest = EnvironmentManifest()
    mod = TyModule()
    mod.build(manifest)

    assert "ty" in manifest.dev_dependencies
    assert "astral-sh.ty" in manifest.ide_extensions
    assert len(manifest.pre_commit_local_hooks) == 1
    hook = manifest.pre_commit_local_hooks[0]
    assert "id: ty" in hook
    assert "entry: uv run ty check" in hook
    assert "language: system" in hook
    assert "pass_filenames: false" in hook
    assert "uv run ty check" in manifest.just_typecheck_commands


def test_pyrefly_module_build():
    manifest = EnvironmentManifest()
    mod = PyreflyModule()
    mod.build(manifest)

    assert "pyrefly" in manifest.dev_dependencies
    assert ".pyrefly/" in manifest.vcs_ignores
    assert "meta.pyrefly" in manifest.ide_extensions
    assert len(manifest.pre_commit_local_hooks) == 1
    hook = manifest.pre_commit_local_hooks[0]
    assert "id: pyrefly-check" in hook
    assert "entry: uv run pyrefly check" in hook
    assert "language: system" in hook
    assert "pass_filenames: false" in hook
    assert "uv run pyrefly check" in manifest.just_typecheck_commands


# --- PreCommitModule Tests ---


def test_pre_commit_pre_flight_missing(mocker):
    """Test PreCommitModule aborts pre-flight if git is missing."""
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(MissingDependencyError) as exc_info:
        PreCommitModule().pre_flight()

    assert exc_info.value.dependency == "git"
    assert "pre-commit hooks" in exc_info.value.purpose


def test_pre_commit_collision_markers():
    assert PreCommitModule().collision_markers == [Path(".pre-commit-config.yaml")]


def test_pre_commit_build_uv(manifest, mocker):
    """Test PreCommitModule configures standard hooks routing via uv."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)

    mod = PreCommitModule()
    mod.build(manifest)

    assert manifest.wants_pre_commit is True
    assert "pre-commit" in manifest.dev_dependencies
    assert any(
        t.command
        == [
            "uv",
            "run",
            "pre-commit",
            "install",
            "--hook-type",
            "pre-commit",
            "--hook-type",
            "commit-msg",
        ]
        for t in manifest.post_install_tasks
    )
    assert any(
        t.command == ["uv", "run", "pre-commit", "autoupdate"]
        for t in manifest.post_install_tasks
    )


# --- PrekModule Tests ---


def test_prek_pre_flight_missing(mocker):
    """Test PrekModule aborts pre-flight if git is missing."""
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(MissingDependencyError) as exc_info:
        PrekModule().pre_flight()

    assert exc_info.value.dependency == "git"
    assert "prek hooks" in exc_info.value.purpose


def test_prek_collision_markers():
    assert PrekModule().collision_markers == [Path(".pre-commit-config.yaml")]


def test_prek_build_uv(manifest, mocker):
    """Test PrekModule configures standard hooks routing via uv."""
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)

    mod = PrekModule()
    mod.build(manifest)

    assert manifest.wants_prek is True
    assert "prek" in manifest.dev_dependencies
    assert any(
        t.command
        == [
            "uv",
            "run",
            "prek",
            "install",
            "--hook-type",
            "pre-commit",
            "--hook-type",
            "commit-msg",
        ]
        for t in manifest.post_install_tasks
    )
    assert any(
        t.command == ["uv", "run", "prek", "update"]
        for t in manifest.post_install_tasks
    )


def test_direnv_skips_when_file_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".envrc").touch()

    manifest = EnvironmentManifest()
    mod = DirenvModule()
    mod.build(manifest)

    skip_events = [d for d in manifest.diagnostics if d.severity == Severity.SKIP]
    assert len(skip_events) == 1
    assert skip_events[0].phase == mod.name
    assert "already exists" in skip_events[0].message
    assert ".envrc" not in manifest.file_injections


def test_markdownlint_skips_when_file_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".markdownlint-cli2.yaml").touch()

    manifest = EnvironmentManifest()
    mod = MarkdownLintModule()
    mod.build(manifest)

    skip_events = [d for d in manifest.diagnostics if d.severity == Severity.SKIP]
    assert len(skip_events) == 1
    assert skip_events[0].phase == mod.name
    assert "already exists" in skip_events[0].message
    assert ".markdownlint-cli2.yaml" not in manifest.file_injections


def test_markdownlint_module_injects_ide_extension():
    manifest = EnvironmentManifest()
    module = MarkdownLintModule()
    module.build(manifest)
    assert "DavidAnson.vscode-markdownlint" in manifest.ide_extensions


def test_ruff_module_injects_ide_extension():
    manifest = EnvironmentManifest()
    module = RuffModule()
    module.build(manifest)
    assert "charliermarsh.ruff" in manifest.ide_extensions


def test_mypy_module_injects_ide_extension():
    manifest = EnvironmentManifest()
    module = MypyModule()
    module.build(manifest)

    # Assert the fallback tuple is injected rather than a single string
    assert ("ms-python.mypy-type-checker", "matangover.mypy") in manifest.ide_extensions


def test_python_core_pre_flight_missing_uv(mocker):
    mocker.patch("shutil.which", return_value=None)
    module = PythonCore()

    with pytest.raises(MissingDependencyError) as exc_info:
        module.pre_flight()

    assert exc_info.value.dependency == "uv"
    assert "Python scaffolding" in exc_info.value.purpose


def test_direnv_module_pre_flight_missing_direnv(mocker):
    mocker.patch("shutil.which", return_value=None)
    module = DirenvModule()

    with pytest.raises(MissingDependencyError) as exc_info:
        module.pre_flight()

    assert exc_info.value.dependency == "direnv"


def test_pre_commit_module_pre_flight_missing_git(mocker):
    mocker.patch("shutil.which", return_value=None)
    module = PreCommitModule()

    with pytest.raises(MissingDependencyError) as exc_info:
        module.pre_flight()

    assert exc_info.value.dependency == "git"


def test_commitizen_module_injects_dev_dependency():
    manifest = EnvironmentManifest()
    module = CommitizinModule()
    module.build(manifest)

    assert "commitizen" in manifest.dev_dependencies


def test_commitizen_module_appends_pyproject_config():
    manifest = EnvironmentManifest()
    module = CommitizinModule()
    module.build(manifest)

    appends = manifest.file_appends.get("pyproject.toml", [])
    assert any("[tool.commitizen]" in block for block in appends)


def test_commitizen_module_appends_pyproject_version_provider():
    manifest = EnvironmentManifest()
    module = CommitizinModule()
    module.build(manifest)

    appends = manifest.file_appends.get("pyproject.toml", [])
    combined = "\n".join(appends)
    assert 'version_provider = "pep621"' in combined
    assert 'version_scheme = "semver2"' in combined
    assert 'tag_format = "v$version"' in combined


def test_commitizen_module_adds_pre_commit_hook():
    manifest = EnvironmentManifest()
    module = CommitizinModule()
    module.build(manifest)

    assert any(
        "commitizen-tools/commitizen" in hook for hook in manifest.pre_commit_hooks
    )


def test_commitizen_module_adds_gitignore_entry():
    manifest = EnvironmentManifest()
    module = CommitizinModule()
    module.build(manifest)

    assert ".cz-cache/" in manifest.vcs_ignores
    assert ".cz-cache/" in manifest.workspace_hides


def test_renovate_module_properties():
    module = RenovateModule()
    assert module.name == "Renovate"
    assert module.cli_flags == ("--renovate",)
    assert module.config_key == "renovate"
    assert module.collision_markers == [Path(".github/renovate.json")]


def test_renovate_module_injects_file(mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)
    manifest = EnvironmentManifest()
    module = RenovateModule()
    module.build(manifest)

    assert ".github/renovate.json" in manifest.file_injections
    content = manifest.file_injections[".github/renovate.json"]
    assert "renovate-schema.json" in content
    assert "config:best-practices" in content
    assert "before 4am on monday" in content
    assert "python-dev-tools" in content
    assert "github-actions" in content


def test_renovate_module_adds_pre_commit_hook():
    manifest = EnvironmentManifest()
    module = RenovateModule()
    module.build(manifest)

    assert any(
        "renovatebot/pre-commit-hooks" in hook and "renovate-config-validator" in hook
        for hook in manifest.pre_commit_hooks
    )


def test_renovate_module_skips_when_file_exists(mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=True)
    manifest = EnvironmentManifest()
    module = RenovateModule()
    module.build(manifest)

    assert ".github/renovate.json" not in manifest.file_injections
    assert any(
        d.phase == "Renovate" and d.severity == Severity.SKIP
        for d in manifest.diagnostics
    )


def test_codecov_module_properties():
    module = CodecovModule()
    assert module.name == "Codecov"
    assert module.cli_flags == ("--codecov",)
    assert module.config_key == "codecov"
    assert module.collision_markers == [Path(".github/codecov.yml")]


def test_codecov_module_injects_file(mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)
    manifest = EnvironmentManifest()
    module = CodecovModule()
    module.build(manifest)

    assert ".github/codecov.yml" in manifest.file_injections
    content = manifest.file_injections[".github/codecov.yml"]
    assert 'range: "80...100"' in content
    assert "target: 80%" in content
    assert "require_changes: true" in content
    assert "tests/**" in content


def test_codecov_module_skips_when_file_exists(mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=True)
    manifest = EnvironmentManifest()
    module = CodecovModule()
    module.build(manifest)

    assert ".github/codecov.yml" not in manifest.file_injections
    assert any(
        d.phase == "Codecov" and d.severity == Severity.SKIP
        for d in manifest.diagnostics
    )


def test_zensical_module_properties():
    module = ZensicalModule()
    assert module.name == "Zensical"
    assert module.cli_flags == ("--zensical",)
    assert module.config_key == "zensical"
    assert module.collision_markers == [Path("mkdocs.yml"), Path("docs/")]


def test_zensical_module_build(mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)
    manifest = EnvironmentManifest()
    module = ZensicalModule()
    module.build(manifest)

    assert "mkdocstrings[python]" in manifest.docs_dependencies
    assert "zensical" in manifest.docs_dependencies
    assert "site/" in manifest.vcs_ignores
    assert "docs" in manifest.directories
    assert "docs/index.md" in manifest.file_injections
    assert "mkdocs.yml" in manifest.file_injections
    assert "pyproject.toml" in manifest.file_appends


def test_readthedocs_module_properties():
    module = ReadTheDocsModule()
    assert module.name == "Read the Docs"
    assert module.cli_flags == ("--readthedocs",)
    assert module.config_key == "readthedocs"
    assert module.collision_markers == [Path(".readthedocs.yaml")]


def test_readthedocs_module_requires_zensical():
    manifest = EnvironmentManifest()
    module = ReadTheDocsModule()

    with pytest.raises(
        ConfigurationError,
        match="Read the Docs scaffolding requires the Zensical module to be enabled",
    ):
        module.build(manifest)


def test_readthedocs_module_injects_file(mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=False)
    manifest = EnvironmentManifest()
    ZensicalModule().build(manifest)
    module = ReadTheDocsModule()
    module.build(manifest)

    assert ".readthedocs.yaml" in manifest.file_injections
    content = manifest.file_injections[".readthedocs.yaml"]
    assert "version: 2" in content
    assert "os: ubuntu-24.04" in content
    assert 'python: "3.12"' in content
    assert "pip install uv" in content
    assert 'uv venv "${READTHEDOCS_VIRTUALENV_PATH}"' in content
    assert (
        'UV_PROJECT_ENVIRONMENT="${READTHEDOCS_VIRTUALENV_PATH}" uv sync --only-group'
        " docs" in content
    )
    assert 'mkdir -p "$READTHEDOCS_OUTPUT/html"' in content
    assert (
        'UV_PROJECT_ENVIRONMENT="${READTHEDOCS_VIRTUALENV_PATH}" uv run zensical build'
        in content
    )
    assert 'cp -r site/* "$READTHEDOCS_OUTPUT/html/"' in content


def test_readthedocs_module_skips_when_file_exists(mocker):
    mocker.patch("protostar.modules.tooling_layer.Path.exists", return_value=True)
    manifest = EnvironmentManifest()
    manifest.add_docs_dependency("zensical")
    module = ReadTheDocsModule()
    module.build(manifest)

    assert ".readthedocs.yaml" not in manifest.file_injections
    assert any(
        d.phase == "Read the Docs" and d.severity == Severity.SKIP
        for d in manifest.diagnostics
    )
