import hashlib
import re
from pathlib import Path
from typing import cast

import pytest

from protostar.documents import codecov, readthedocs
from protostar.errors import ConfigurationError
from protostar.ide import IDEType
from protostar.intent import (
    AppendContribution,
    DependencyGroup,
    DependencyInclude,
    ResolverFootprint,
    StructuredContribution,
    StructuredFormat,
    TemplateOrigin,
    TemplateReference,
)
from protostar.manifest import (
    CollisionStrategy,
    DependencyManifest,
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    FilesystemManifest,
    HookRunner,
    MissingTool,
    ProjectMetadata,
    Severity,
    SystemTask,
    TaskManifest,
    ToolingManifest,
    missing_tools_record,
)
from protostar.migrations import Migration
from protostar.recipe import ProjectRecipe, Tool
from protostar.system_deps import GlobalExecutable
from protostar.workflows import CIFlag


def test_manifest_initialization(manifest):
    """Test that the manifest initializes with empty, correct data structures."""
    assert isinstance(manifest.filesystem.vcs_ignores, set)
    assert isinstance(manifest.filesystem.workspace_hides, set)
    assert isinstance(manifest.ide_settings, dict)
    assert isinstance(manifest.dependencies.dependencies, list)
    assert isinstance(manifest.dependencies.dev_dependencies, list)
    assert isinstance(manifest.tasks.system_tasks, list)
    assert isinstance(manifest.filesystem.directories, set)
    assert isinstance(manifest.filesystem.file_injections, dict)
    assert isinstance(manifest.filesystem.structured, dict)
    assert manifest.tooling.hook_runner == HookRunner.NONE
    assert manifest.tooling.wants_hooks is False
    assert isinstance(manifest.tooling.pre_commit_hooks, list)
    assert isinstance(manifest.tooling.pre_commit_local_hooks, list)
    assert manifest.collision_strategy == CollisionStrategy.MERGE


def test_tooling_manifest_set_hook_runner(manifest):
    """Test that setting a hook runner is idempotent but conflicts raise ConfigurationError."""
    assert manifest.tooling.hook_runner == HookRunner.NONE
    manifest.tooling.set_hook_runner(HookRunner.PRE_COMMIT)
    assert manifest.tooling.hook_runner == HookRunner.PRE_COMMIT
    assert manifest.tooling.wants_hooks is True

    # Idempotent assignment succeeds
    manifest.tooling.set_hook_runner(HookRunner.PRE_COMMIT)
    assert manifest.tooling.hook_runner == HookRunner.PRE_COMMIT

    # Conflicting assignment raises ConfigurationError
    with pytest.raises(
        ConfigurationError,
        match="Cannot configure 'prek' when 'pre-commit' is already active",
    ):
        manifest.tooling.set_hook_runner(HookRunner.PREK)


def test_add_vcs_ignore(manifest):
    """Test that VCS ignore patterns are correctly added and deduplicated."""
    manifest.filesystem.add_vcs_ignore(".DS_Store")
    manifest.filesystem.add_vcs_ignore(".DS_Store")  # Should not duplicate
    manifest.filesystem.add_vcs_ignore("node_modules/")

    assert len(manifest.filesystem.vcs_ignores) == 2
    assert ".DS_Store" in manifest.filesystem.vcs_ignores


def test_add_workspace_hide(manifest):
    """Test that workspace hides are correctly added and deduplicated."""
    manifest.filesystem.add_workspace_hide(".venv/")
    manifest.filesystem.add_workspace_hide(".venv/")  # Should not duplicate
    manifest.filesystem.add_workspace_hide("build/")

    assert len(manifest.filesystem.workspace_hides) == 2
    assert ".venv/" in manifest.filesystem.workspace_hides


def test_add_ide_setting(manifest):
    """Test that IDE settings are stored correctly."""
    manifest.add_ide_setting("python.formatting.provider", "ruff")
    assert manifest.ide_settings["python.formatting.provider"] == "ruff"


def test_add_system_task(manifest):
    """Test that system tasks are queued sequentially as SystemTask dataclasses."""
    manifest.tasks.add_system_task(["uv", "init"])
    manifest.tasks.add_system_task(["cargo", "init"], timeout=45)

    assert len(manifest.tasks.system_tasks) == 2
    assert manifest.tasks.system_tasks[0].command == ["uv", "init"]
    assert manifest.tasks.system_tasks[0].timeout == 30
    assert manifest.tasks.system_tasks[1].command == ["cargo", "init"]
    assert manifest.tasks.system_tasks[1].timeout == 45


def test_add_system_task_with_description():
    manifest = EnvironmentManifest()
    manifest.tasks.add_system_task(
        ["git", "init"], timeout=10, description="Initializing git repository"
    )

    assert len(manifest.tasks.system_tasks) == 1
    task = manifest.tasks.system_tasks[0]
    assert task.command == ["git", "init"]
    assert task.timeout == 10
    assert task.description == "Initializing git repository"


def test_add_post_install_task_with_description():
    manifest = EnvironmentManifest()
    manifest.tasks.add_post_install_task(
        ["direnv", "allow"], description="Authorizing direnv workspace"
    )

    assert len(manifest.tasks.post_install_tasks) == 1
    task = manifest.tasks.post_install_tasks[0]
    assert task.command == ["direnv", "allow"]
    assert task.description == "Authorizing direnv workspace"


def test_add_post_install_task(manifest):
    """Test that post-install tasks are queued sequentially with explicit timeout bindings."""
    manifest.tasks.add_post_install_task(["direnv", "allow"])
    manifest.tasks.add_post_install_task(["pre-commit", "autoupdate"], timeout=300)

    assert len(manifest.tasks.post_install_tasks) == 2
    assert manifest.tasks.post_install_tasks[0].command == ["direnv", "allow"]
    assert manifest.tasks.post_install_tasks[0].timeout == 30
    assert manifest.tasks.post_install_tasks[1].command == ["pre-commit", "autoupdate"]
    assert manifest.tasks.post_install_tasks[1].timeout == 300


def test_add_dependency_deduplication(manifest):
    """Test that dependencies are queued and deduplicated."""
    manifest.dependencies.add("numpy")
    manifest.dependencies.add("pandas")
    manifest.dependencies.add("numpy")  # Should not duplicate

    assert len(manifest.dependencies.dependencies) == 2
    assert manifest.dependencies.dependencies == ["numpy", "pandas"]


def test_add_dev_dependency_deduplication(manifest):
    """Test that dev dependencies are queued and deduplicated independently."""
    manifest.dependencies.add_dev("pytest")
    manifest.dependencies.add_dev("ruff")
    manifest.dependencies.add_dev("pytest")  # Should not duplicate

    assert len(manifest.dependencies.dev_dependencies) == 2
    assert manifest.dependencies.dev_dependencies == ["pytest", "ruff"]


def test_manifest_directories_initialization(manifest):
    """Test that the manifest initializes the directories set."""
    assert isinstance(manifest.filesystem.directories, set)


def test_add_directory(manifest):
    """Test that directories are correctly queued and deduplicated."""
    manifest.filesystem.add_directory("data")
    manifest.filesystem.add_directory("data")  # Should not duplicate
    manifest.filesystem.add_directory("src")

    assert len(manifest.filesystem.directories) == 2
    assert "data" in manifest.filesystem.directories
    assert "src" in manifest.filesystem.directories


def test_add_file_injection(manifest):
    """Test that file injections are queued and idempotent for identical content."""
    manifest.filesystem.add_file_injection(".envrc", "export FOO=bar")
    manifest.filesystem.add_file_injection(
        ".envrc", "export FOO=bar"
    )  # Idempotent re-registration

    assert len(manifest.filesystem.file_injections) == 1
    assert manifest.filesystem.file_injections[".envrc"] == "export FOO=bar"


def test_add_file_injection_raises_on_conflict(manifest):
    """Test that registering conflicting file content for the same path raises ConfigurationError."""
    manifest.filesystem.add_file_injection(".envrc", "export FOO=bar")

    with pytest.raises(
        ConfigurationError,
        match=re.escape("Conflicting file injections for '.envrc'"),
    ):
        manifest.filesystem.add_file_injection(".envrc", "export FOO=baz")


def test_add_file_append(manifest):
    """Test that file appends queue successfully to the target path list."""
    manifest.filesystem.add_structured(
        "pyproject.toml", "[tool.ruff]", producer="module:test_manifest"
    )
    manifest.filesystem.add_structured(
        "pyproject.toml", "[tool.mypy]", producer="module:test_manifest"
    )

    assert len(manifest.filesystem.structured) == 1
    assert len(manifest.filesystem.structured["pyproject.toml"]) == 2
    assert [c.content for c in manifest.filesystem.structured["pyproject.toml"]] == [
        "[tool.ruff]",
        "[tool.mypy]",
    ]


def test_add_pre_commit_hook(manifest):
    """Test that pre-commit hooks are queued and deduplicated correctly."""
    manifest.tooling.add_pre_commit_hook("- id: ruff")
    manifest.tooling.add_pre_commit_hook("- id: ruff")  # Should not duplicate
    manifest.tooling.add_pre_commit_hook("- id: mypy")

    assert len(manifest.tooling.pre_commit_hooks) == 2
    assert "- id: ruff" in manifest.tooling.pre_commit_hooks
    assert "- id: mypy" in manifest.tooling.pre_commit_hooks


def test_add_pre_commit_local_hook(manifest):
    """Test that local pre-commit hooks are queued and deduplicated correctly."""
    manifest.tooling.add_pre_commit_local_hook("- id: ruff-check")
    manifest.tooling.add_pre_commit_local_hook(
        "- id: ruff-check"
    )  # Should not duplicate
    manifest.tooling.add_pre_commit_local_hook("- id: mypy")

    assert len(manifest.tooling.pre_commit_local_hooks) == 2
    assert "- id: ruff-check" in manifest.tooling.pre_commit_local_hooks
    assert "- id: mypy" in manifest.tooling.pre_commit_local_hooks


def test_add_pre_commit_hook_type(manifest):
    """Test that pre-commit hook types are queued and deduplicated correctly."""
    manifest.tooling.add_pre_commit_hook_type("commit-msg")
    manifest.tooling.add_pre_commit_hook_type("commit-msg")  # Duplicate
    manifest.tooling.add_pre_commit_hook_type("pre-push")

    assert len(manifest.tooling.pre_commit_install_hook_types) == 2
    assert "commit-msg" in manifest.tooling.pre_commit_install_hook_types
    assert "pre-push" in manifest.tooling.pre_commit_install_hook_types


def test_add_ide_extension_aggregates_uniquely():
    manifest = EnvironmentManifest()
    manifest.tooling.add_ide_extension("charliermarsh.ruff")
    manifest.tooling.add_ide_extension("ms-python.mypy-type-checker")

    # Attempt to add a duplicate
    manifest.tooling.add_ide_extension("charliermarsh.ruff")

    assert len(manifest.tooling.ide_extensions) == 2
    assert "charliermarsh.ruff" in manifest.tooling.ide_extensions
    assert "ms-python.mypy-type-checker" in manifest.tooling.ide_extensions


def test_manifest_accepts_mixed_ide_extensions():
    """Verifies the manifest correctly stores both strings and tuples for extensions."""
    manifest = EnvironmentManifest()
    manifest.tooling.add_ide_extension("charliermarsh.ruff")
    manifest.tooling.add_ide_extension(
        ("ms-python.mypy-type-checker", "matangover.mypy")
    )

    assert len(manifest.tooling.ide_extensions) == 2
    assert "charliermarsh.ruff" in manifest.tooling.ide_extensions
    assert (
        "ms-python.mypy-type-checker",
        "matangover.mypy",
    ) in manifest.tooling.ide_extensions


def test_tooling_manifest_wants_docker():
    """Verifies wants_docker defaults to False and serializes correctly in to_dict."""
    manifest = EnvironmentManifest()
    assert manifest.tooling.wants_docker is False
    assert manifest.tooling.to_dict()["wants_docker"] is False

    manifest.tooling.wants_docker = True
    assert manifest.tooling.to_dict()["wants_docker"] is True


def test_manifest_target_files_comprehensive():
    """Verifies target_files aggregates injected files, appends, and tooling files with interpolation."""
    manifest = EnvironmentManifest()
    manifest.metadata.update(cast(ProjectMetadata, {"package_name": "my_pkg"}))

    manifest.filesystem.add_file_injection("src/<% PACKAGE_NAME %>/main.py", "content")
    manifest.filesystem.add_structured(
        "pyproject.toml", "[tool.foo]\nbar = 1", producer="module:test_manifest"
    )
    manifest.filesystem.add_directory("docs")
    manifest.filesystem.add_vcs_ignore(".DS_Store")

    manifest.tooling.set_hook_runner(HookRunner.PREK)
    manifest.tooling.wants_ci = True
    manifest.tooling.wants_release = True
    manifest.tooling.wants_just = True
    manifest.tooling.wants_docker = True

    targets = manifest.target_files()

    assert Path("src/my_pkg/main.py") in targets
    assert Path("pyproject.toml") in targets
    assert Path(".pre-commit-config.yaml") in targets
    assert Path(".github/workflows/ci.yml") in targets
    assert Path(".github/workflows/release.yml") in targets
    assert Path("justfile") in targets
    assert Path("Dockerfile") in targets
    assert Path(".dockerignore") in targets

    # Non-destructive directories and VCS ignores must NOT be target files
    assert Path("docs") not in targets
    assert Path(".DS_Store") not in targets
    assert Path(".gitignore") not in targets


def test_planned_files_add_command_outputs_resolver_files_and_state():
    """The preview lists every file a run leaves, not only those Protostar writes."""
    manifest = EnvironmentManifest()
    manifest.filesystem.add_file_injection("README.md", "# Readme\n")
    manifest.tasks.add_system_task(
        ["uv", "init"], owned_files=["pyproject.toml", ".python-version"]
    )
    manifest.tasks.add_system_task(["git", "init"], owned_trees=[".git"])
    manifest.tasks.add_post_install_task(
        ["prek", "install"], owned_files=[".git/hooks/pre-commit"]
    )

    assert manifest.planned_files() == {
        Path("README.md"),
        Path("pyproject.toml"),
        Path(".python-version"),
        Path("protostar.lock"),
    }

    manifest.dependencies.dev_dependencies.append("ruff")
    assert Path("uv.lock") in manifest.planned_files()


def test_one_shot_plans_no_reconciliation_state():
    assert EnvironmentManifest(one_shot=True).planned_files() == set()
    assert EnvironmentManifest().planned_files() == {Path("protostar.lock")}


def test_manifest_previews_rendered_directories_and_every_written_file():
    """Previews add .gitignore and IDE settings; collision targets still exclude them."""
    manifest = EnvironmentManifest()
    manifest.metadata.update(cast(ProjectMetadata, {"package_name": "my_pkg"}))
    manifest.filesystem.add_directory("src/<% PACKAGE_NAME %>")
    manifest.filesystem.add_file_injection("README.md", "# Readme\n")
    manifest.filesystem.add_vcs_ignore(".DS_Store")
    manifest.add_ide_setting("python.terminal.activateEnvironment", True)

    assert manifest.target_directories() == {Path("src/my_pkg")}
    assert manifest.written_files() == {
        Path("README.md"),
        Path(".gitignore"),
        Path(".vscode/settings.json"),
    }
    assert manifest.target_files() == {Path("README.md")}


@pytest.mark.parametrize(
    "requirement", ["--index-url=https://evil.example/simple", "not a requirement"]
)
def test_invalid_requirements_are_rejected_when_planned(requirement):
    # Rejected at planning, so a dry run reports it too, never reaching `uv add`.
    manifest = EnvironmentManifest()
    for add in (
        manifest.dependencies.add,
        manifest.dependencies.add_dev,
        manifest.dependencies.add_docs,
    ):
        with pytest.raises(ConfigurationError, match="Invalid dependency requirement"):
            add(requirement)


# ---- declarations: values the rest of the engine and its JSON depend on ----


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_diagnostic_phases_and_severities_keep_their_wording() -> None:
    assert {phase.name: phase.value for phase in DiagnosticPhase} == {
        "CONFIG": "Config",
        "DIRENV": "Direnv",
        "IDE": "IDE",
        "PRE_COMMIT": "Pre-commit",
        "JUST": "Just",
        "EXECUTOR": "Executor",
        "DOCKER": "Docker",
        "CI": "CI",
        "GIT": "Git",
        "MARKDOWNLINT": "MarkdownLint",
    }
    assert {level.name: level.value for level in Severity} == {
        "INFO": "info",
        "SKIP": "skip",
        "WARNING": "warning",
    }
    assert {item.name: item.value for item in CollisionStrategy} == {
        "MERGE": "merge",
        "OVERWRITE": "overwrite",
    }


def test_a_diagnostic_event_holds_only_what_it_is_given() -> None:
    event = DiagnosticEvent(DiagnosticPhase.GIT, "skipped", Severity.SKIP)

    assert (event.detail, event.conflict, event.resolved) == (None, None, None)


def test_missing_tools_serialize_sorted_by_executable_then_tool() -> None:
    missing = frozenset(
        {
            MissingTool(GlobalExecutable.JUST, Tool.RUFF),
            MissingTool(GlobalExecutable.DIRENV, Tool.RUFF),
            MissingTool(GlobalExecutable.DIRENV, Tool.DIRENV),
        }
    )

    assert missing_tools_record(missing) == [
        {"executable": "direnv", "tool": "direnv"},
        {"executable": "direnv", "tool": "ruff"},
        {"executable": "just", "tool": "ruff"},
    ]
    assert missing_tools_record(frozenset()) == []


def test_a_system_task_defaults_to_no_owned_paths_of_its_own() -> None:
    first, second = SystemTask(["a"]), SystemTask(["b"])

    assert (first.description, first.timeout) == (None, None)
    assert first.owned_files == []
    assert first.owned_trees == []
    first.owned_files.append("x")
    assert second.owned_files == []
    assert SystemTask(
        ["a"], "go", 5, owned_files=["f"], owned_trees=["t"]
    ).to_dict() == {
        "command": ["a"],
        "description": "go",
        "timeout": 5,
        "owned_files": ["f"],
        "owned_trees": ["t"],
    }


# ---- dependencies ----


def test_a_requirement_is_checked_before_anything_is_recorded() -> None:
    calls: list[tuple[str, ...]] = []
    dependencies = DependencyManifest(observe=calls.append)

    with pytest.raises(ConfigurationError) as raised:
        dependencies.add("not a requirement")

    assert str(raised.value) == "Invalid dependency requirement 'not a requirement'."
    assert raised.value.hint == (
        "Use a valid PEP 508 requirement, such as 'requests>=2'."
    )
    assert raised.value.__cause__ is not None
    assert calls == []
    assert dependencies.dependencies == []
    dependencies.add("requests>=2; python_version >= '3.9'")
    assert dependencies.dependencies == ["requests>=2; python_version >= '3.9'"]


def test_each_dependency_group_records_its_own_observation_and_list() -> None:
    calls: list[tuple[str, ...]] = []
    dependencies = DependencyManifest(observe=calls.append)

    dependencies.add("a")
    dependencies.add("a")
    dependencies.add_dev("b")
    dependencies.add_docs("c")

    assert calls == [
        ("dependencies", "a"),
        ("dependencies", "a"),
        ("dev_dependencies", "b"),
        ("docs_dependencies", "c"),
    ]
    assert (
        dependencies.dependencies,
        dependencies.dev_dependencies,
        dependencies.docs_dependencies,
    ) == (["a"], ["b"], ["c"])


def test_docs_dependencies_are_deduplicated_too() -> None:
    dependencies = DependencyManifest()

    dependencies.add_docs("zensical")
    dependencies.add_docs("zensical")

    assert dependencies.docs_dependencies == ["zensical"]


@pytest.mark.parametrize(
    ("group", "include"),
    [
        (DependencyGroup.MAIN, DependencyGroup.DEV),
        (DependencyGroup.DEV, DependencyGroup.MAIN),
        (DependencyGroup.MAIN, DependencyGroup.DOCS),
        (DependencyGroup.DOCS, DependencyGroup.MAIN),
        (DependencyGroup.DEV, DependencyGroup.DEV),
        (DependencyGroup.DOCS, DependencyGroup.DOCS),
    ],
)
def test_only_dev_and_docs_may_include_each_other(group, include) -> None:
    calls: list[tuple[str, ...]] = []
    dependencies = DependencyManifest(observe=calls.append)

    with pytest.raises(ConfigurationError) as raised:
        dependencies.add_include(group, include)

    assert str(raised.value) == "Unsupported dependency include edge."
    assert raised.value.hint == "Include docs in dev or dev in docs without cycles."
    assert calls == [("includes", group.value, include.value)]
    assert dependencies.includes == []


def test_an_include_is_recorded_once_and_never_in_both_directions() -> None:
    dependencies = DependencyManifest()
    dev, docs = DependencyGroup.DEV, DependencyGroup.DOCS

    dependencies.add_include(dev, docs)
    dependencies.add_include(dev, docs)

    assert dependencies.includes == [DependencyInclude(dev, docs)]
    with pytest.raises(ConfigurationError) as raised:
        dependencies.add_include(docs, dev)
    assert str(raised.value) == "Cyclic dependency includes."
    assert raised.value.hint == "Remove the cyclic include-group declaration."
    assert dependencies.includes == [DependencyInclude(dev, docs)]


def test_the_other_include_direction_is_allowed_alone() -> None:
    dependencies = DependencyManifest()

    dependencies.add_include(DependencyGroup.DOCS, DependencyGroup.DEV)

    assert dependencies.includes == [
        DependencyInclude(DependencyGroup.DOCS, DependencyGroup.DEV)
    ]


def test_dependencies_serialize_in_order_with_sorted_includes_and_footprint() -> None:
    dependencies = DependencyManifest(
        resolver_footprint=ResolverFootprint(("uv.lock", "pyproject.toml"))
    )
    dependencies.add("b")
    dependencies.add("a")
    dependencies.add_dev("d")
    dependencies.add_docs("z")
    dependencies.includes.append(
        DependencyInclude(DependencyGroup.DOCS, DependencyGroup.DEV)
    )
    dependencies.includes.append(
        DependencyInclude(DependencyGroup.DEV, DependencyGroup.DOCS)
    )

    record = dependencies.to_dict()

    assert record == {
        "dependencies": ["b", "a"],
        "dev_dependencies": ["d"],
        "docs_dependencies": ["z"],
        "includes": [
            {"group": "dev", "include": "docs"},
            {"group": "docs", "include": "dev"},
        ],
        "resolver_footprint": {"paths": ["pyproject.toml", "uv.lock"]},
    }
    record["dependencies"].append("x")
    assert dependencies.dependencies == ["b", "a"]


# ---- filesystem ----


def _filesystem() -> tuple[FilesystemManifest, list[tuple[str, ...]]]:
    calls: list[tuple[str, ...]] = []
    return FilesystemManifest(observe=calls.append), calls


def test_a_directory_is_observed_as_given_and_stored_normalized() -> None:
    filesystem, calls = _filesystem()

    filesystem.add_directory("docs//guide/")

    assert calls == [("directories", "docs//guide/")]
    assert filesystem.directories == {"docs/guide"}


@pytest.mark.parametrize("path", ["../escape", "/abs", ".git/hooks"])
def test_a_target_that_escapes_is_refused(path: str) -> None:
    filesystem, _ = _filesystem()

    for add in (
        filesystem.add_directory,
        lambda p: filesystem.add_file_injection(p, "x"),
        lambda p: filesystem.add_structured(p + ".toml", "a = 1", producer="m"),
        lambda p: filesystem.add_region(p, "x", identity="r"),
    ):
        with pytest.raises(ConfigurationError, match="Unsupported contribution target"):
            add(path)


@pytest.mark.parametrize("path", ["protostar.lock", "uv.lock", "sub/uv.lock"])
def test_the_engines_own_files_are_not_a_contribution_target(path: str) -> None:
    filesystem, _ = _filesystem()

    with pytest.raises(ConfigurationError, match="Unsupported contribution target"):
        filesystem.add_file_injection(path, "x")


def test_a_file_is_observed_as_given_and_stored_normalized() -> None:
    filesystem, calls = _filesystem()

    filesystem.add_file_injection("./a//b.txt", "body")

    assert calls == [("file_injections", "./a//b.txt")]
    assert filesystem.file_injections == {"a/b.txt": "body"}


@pytest.mark.parametrize("path", ["pyproject.toml", "./pyproject.toml"])
def test_pyproject_is_never_written_whole(path: str) -> None:
    filesystem, _ = _filesystem()

    with pytest.raises(ConfigurationError) as raised:
        filesystem.add_file_injection(path, "x")

    assert str(raised.value) == "Free-form pyproject.toml replacement is unsupported."
    assert raised.value.hint == (
        "Declare structured TOML contributions; tool.protostar is reserved."
    )


def test_a_free_form_file_cannot_share_a_path_with_structure_or_a_region() -> None:
    filesystem, _ = _filesystem()
    filesystem.add_structured("a.toml", "x = 1", producer="m")
    filesystem.add_region("b.txt", "x", identity="r")

    for path in ("a.toml", "b.txt"):
        with pytest.raises(ConfigurationError) as raised:
            filesystem.add_file_injection(path, "x")
        assert str(raised.value) == f"Ambiguous contributions for '{path}'."
        assert raised.value.hint == (
            "Do not combine free-form files with structured configuration or regions."
        )


def test_conflicting_content_for_one_file_is_refused() -> None:
    filesystem, _ = _filesystem()
    filesystem.add_file_injection("a.txt", "one")

    with pytest.raises(ConfigurationError) as raised:
        filesystem.add_file_injection("./a.txt", "two")

    assert str(raised.value) == (
        "Conflicting file injections for 'a.txt': multiple sources registered "
        "different content."
    )
    assert raised.value.hint == (
        "Check for conflicting module configurations or overlapping template "
        "definitions."
    )
    assert filesystem.file_injections == {"a.txt": "one"}


def test_structured_toml_is_observed_and_collected_per_target() -> None:
    filesystem, calls = _filesystem()

    filesystem.add_structured("a.toml", "x = 1", producer="one")
    filesystem.add_structured("./a.toml", "y = 2", producer="two")

    assert calls == [("structured", "a.toml", "one"), ("structured", "./a.toml", "two")]
    assert filesystem.structured == {
        "a.toml": [
            StructuredContribution("one", "x = 1"),
            StructuredContribution("two", "y = 2"),
        ]
    }


def test_structured_toml_needs_a_toml_target() -> None:
    filesystem, _ = _filesystem()

    with pytest.raises(ConfigurationError) as raised:
        filesystem.add_structured("a.cfg", "x = 1", producer="m")

    assert str(raised.value) == "Structured contributions require TOML targets."
    assert raised.value.hint == "Use a named append region for non-TOML files."
    assert filesystem.structured == {}


def test_structured_toml_cannot_share_a_target_with_a_file_or_a_region() -> None:
    filesystem, _ = _filesystem()
    filesystem.add_file_injection("f.toml", "x = 1")
    filesystem.add_region("r.txt", "x", identity="r")

    for path in ("f.toml", "r.txt"):
        with pytest.raises(ConfigurationError) as raised:
            filesystem.add_structured(path, "x = 1", producer="m")
        assert str(raised.value) == f"Ambiguous contributions for '{path}'."
        assert raised.value.hint == "Use one contribution policy per target."


def test_a_yaml_contribution_is_one_producer_for_a_supported_target() -> None:
    filesystem, calls = _filesystem()

    filesystem.add_structured(
        readthedocs.TARGET,
        "version: 2\n",
        producer="one",
        document_format=StructuredFormat.YAML,
    )

    assert calls == [("structured", readthedocs.TARGET, "one")]
    assert filesystem.structured == {
        readthedocs.TARGET: [
            StructuredContribution("one", "version: 2\n", format=StructuredFormat.YAML)
        ]
    }
    with pytest.raises(ConfigurationError) as raised:
        filesystem.add_structured(
            readthedocs.TARGET,
            "version: 2\n",
            producer="two",
            document_format=StructuredFormat.YAML,
        )
    assert str(raised.value) == "Ambiguous YAML producers."
    assert raised.value.hint == (
        f"Declare one contribution to '{readthedocs.TARGET}' per manifest."
    )


def test_a_yaml_contribution_to_an_unsupported_target_names_the_supported_ones() -> (
    None
):
    filesystem, _ = _filesystem()

    with pytest.raises(ConfigurationError) as raised:
        filesystem.add_structured(
            "other.yml", "a: 1\n", producer="m", document_format=StructuredFormat.YAML
        )

    assert str(raised.value) == "Unsupported structured YAML target."
    assert raised.value.hint == (
        f"Declare a contribution to one of: {codecov.TARGET}, {readthedocs.TARGET}."
    )


def test_a_yaml_contribution_that_is_not_yaml_is_refused_before_it_is_kept() -> None:
    filesystem, _ = _filesystem()

    with pytest.raises(ConfigurationError):
        filesystem.add_structured(
            codecov.TARGET,
            "a: [unclosed",
            producer="m",
            document_format=StructuredFormat.YAML,
        )

    assert filesystem.structured == {}


def test_yaml_cannot_share_a_target_with_a_file_or_a_region() -> None:
    filesystem, _ = _filesystem()
    filesystem.add_file_injection(codecov.TARGET, "a: 1\n")

    with pytest.raises(ConfigurationError, match="Ambiguous contributions"):
        filesystem.add_structured(
            codecov.TARGET,
            "a: 1\n",
            producer="m",
            document_format=StructuredFormat.YAML,
        )


def test_a_region_is_observed_and_collected_per_target() -> None:
    filesystem, calls = _filesystem()

    filesystem.add_region("./notes.txt", "one", identity="a")
    filesystem.add_region("notes.txt", "two", identity="b")

    assert calls == [("regions", "./notes.txt", "a"), ("regions", "notes.txt", "b")]
    assert filesystem.regions == {
        "notes.txt": [AppendContribution("a", "one"), AppendContribution("b", "two")]
    }


def test_a_region_needs_a_marker_safe_identity() -> None:
    filesystem, _ = _filesystem()

    with pytest.raises(ConfigurationError, match="Invalid append identity 'a b'"):
        filesystem.add_region("notes.txt", "x", identity="a b")


def test_a_region_is_refused_where_text_cannot_be_appended() -> None:
    filesystem, _ = _filesystem()

    with pytest.raises(ConfigurationError) as toml:
        filesystem.add_region("a.toml", "x", identity="r")
    assert str(toml.value) == "TOML append regions are unsupported."
    assert toml.value.hint == "Use dev.pyproject structured configuration."

    with pytest.raises(ConfigurationError) as yaml:
        filesystem.add_region(codecov.TARGET, "x", identity="r")
    assert str(yaml.value) == f"Append regions are unsupported for '{codecov.TARGET}'."
    assert yaml.value.hint == (
        "Protostar merges this YAML file by structure; appended text cannot be merged."
    )
    assert filesystem.regions == {}


def test_a_region_cannot_share_a_target_with_a_file_or_structure() -> None:
    filesystem, _ = _filesystem()
    filesystem.add_file_injection("f.txt", "x")
    filesystem.add_structured("s.toml", "x = 1", producer="m")

    with pytest.raises(ConfigurationError) as file:
        filesystem.add_region("f.txt", "x", identity="r")
    assert str(file.value) == "Ambiguous contributions for 'f.txt'."
    assert file.value.hint == "Use one contribution policy per target."


def test_a_region_identity_is_unique_per_target() -> None:
    filesystem, _ = _filesystem()
    filesystem.add_region("a.txt", "x", identity="r")
    filesystem.add_region("b.txt", "x", identity="r")

    with pytest.raises(ConfigurationError) as raised:
        filesystem.add_region("a.txt", "y", identity="r")

    assert str(raised.value) == "Duplicate append identity 'r' for 'a.txt'."
    assert raised.value.hint == "Give every region a unique stable ID."
    assert len(filesystem.regions["a.txt"]) == 1


def test_ignores_and_hides_are_observed_and_an_artifact_is_both() -> None:
    filesystem, calls = _filesystem()

    filesystem.add_vcs_ignore("a")
    filesystem.add_workspace_hide("b")
    filesystem.add_environment_artifact(".venv/")

    assert calls == [
        ("vcs_ignores", "a"),
        ("workspace_hides", "b"),
        ("vcs_ignores", ".venv/"),
        ("workspace_hides", ".venv/"),
    ]
    assert filesystem.vcs_ignores == {"a", ".venv/"}
    assert filesystem.workspace_hides == {"b", ".venv/"}


def test_the_filesystem_serializes_sorted_and_seeded() -> None:
    filesystem, _ = _filesystem()
    filesystem.add_directory("z")
    filesystem.add_directory("a")
    filesystem.add_file_injection("f.txt", "body")
    filesystem.add_structured("b.toml", "x = 1", producer="p")
    filesystem.add_structured("a.toml", "y = 1", producer="q")
    filesystem.add_region("r2.txt", "two", identity="b")
    filesystem.add_region("r1.txt", "one", identity="a")
    filesystem.add_vcs_ignore("v2")
    filesystem.add_vcs_ignore("v1")
    filesystem.add_workspace_hide("h2")
    filesystem.add_workspace_hide("h1")

    record = filesystem.to_dict()

    assert record == {
        "directories": ["a", "z"],
        "file_injections": {"f.txt": "body"},
        "structured": {
            "a.toml": [StructuredContribution("q", "y = 1").to_dict()],
            "b.toml": [StructuredContribution("p", "x = 1").to_dict()],
        },
        "regions": {
            "r1.txt": [AppendContribution("a", "one").to_dict()],
            "r2.txt": [AppendContribution("b", "two").to_dict()],
        },
        "file_policy": "seed-only",
        "vcs_ignores": ["v1", "v2"],
        "workspace_hides": ["h1", "h2"],
    }
    assert list(record["structured"]) == ["a.toml", "b.toml"]
    assert list(record["regions"]) == ["r1.txt", "r2.txt"]


# ---- tooling ----


def _tooling() -> tuple[ToolingManifest, list[tuple[str, ...]]]:
    calls: list[tuple[str, ...]] = []
    return ToolingManifest(observe=calls.append), calls


def test_tooling_starts_empty() -> None:
    tooling, _ = _tooling()

    assert tooling.hook_runner is HookRunner.NONE
    assert not tooling.wants_hooks
    assert (
        tooling.wants_ci,
        tooling.wants_release,
        tooling.wants_docker,
        tooling.wants_just,
        tooling.wants_agents,
        tooling.wants_community,
        tooling.conventional_commits,
    ) == (False,) * 7
    assert tooling.to_dict() == {
        "hook_runner": "none",
        "pre_commit_hooks": [],
        "pre_commit_local_hooks": [],
        "wants_ci": False,
        "wants_release": False,
        "wants_docker": False,
        "ci_flags": [],
        "ci_steps": [],
        "wants_just": False,
        "just_format_commands": [],
        "just_lint_commands": [],
        "just_typecheck_commands": [],
        "just_clean_paths": [],
        "wants_agents": False,
        "wants_community": False,
        "conventional_commits": False,
        "ide_extensions": [],
    }


def test_a_hook_runner_is_observed_even_when_it_conflicts() -> None:
    tooling, calls = _tooling()

    tooling.set_hook_runner(HookRunner.PREK)
    with pytest.raises(ConfigurationError) as raised:
        tooling.set_hook_runner(HookRunner.PRE_COMMIT)

    assert calls == [("hook_runner", "prek"), ("hook_runner", "pre-commit")]
    assert str(raised.value) == (
        "Cannot configure 'pre-commit' when 'prek' is already active."
    )
    assert (
        raised.value.hint
        == "Choose either pre-commit or prek as your git hook manager."
    )
    assert tooling.hook_runner is HookRunner.PREK


def test_adopting_conventional_commits_is_observed() -> None:
    tooling, calls = _tooling()

    tooling.adopt_conventional_commits()

    assert tooling.conventional_commits is True
    assert calls == [("conventional_commits",)]


def test_hooks_ci_steps_and_types_are_observed_by_content_and_deduplicated() -> None:
    tooling, calls = _tooling()

    for payload in ("- id: a", "- id: a", "- id: b"):
        tooling.add_pre_commit_hook(payload)
    for payload in ("- id: l", "- id: l"):
        tooling.add_pre_commit_local_hook(payload)
    for payload in ("- run: x", "- run: x", "- run: y"):
        tooling.add_ci_step(payload)
    tooling.add_pre_commit_hook_type("commit-msg")
    tooling.add_ci_flag(CIFlag.PYTEST)
    tooling.add_ide_extension("a.b")
    tooling.add_ide_extension(("a.b", "c.d"))

    assert tooling.pre_commit_hooks == ["- id: a", "- id: b"]
    assert tooling.pre_commit_local_hooks == ["- id: l"]
    assert tooling.ci_steps == ["- run: x", "- run: y"]
    assert tooling.pre_commit_install_hook_types == {"commit-msg"}
    assert tooling.ci_flags == {CIFlag.PYTEST}
    assert calls == [
        ("pre_commit_hooks", _sha("- id: a")),
        ("pre_commit_hooks", _sha("- id: a")),
        ("pre_commit_hooks", _sha("- id: b")),
        ("pre_commit_local_hooks", _sha("- id: l")),
        ("pre_commit_local_hooks", _sha("- id: l")),
        ("ci_steps", _sha("- run: x")),
        ("ci_steps", _sha("- run: x")),
        ("ci_steps", _sha("- run: y")),
        ("pre_commit_install_hook_types", "commit-msg"),
        ("ci_flags", "pytest"),
        ("ide_extensions", "a.b"),
        ("ide_extensions", "('a.b', 'c.d')"),
    ]


def test_tooling_serializes_everything_it_holds() -> None:
    tooling, _ = _tooling()
    tooling.set_hook_runner(HookRunner.PREK)
    tooling.add_pre_commit_hook("- id: a")
    tooling.add_pre_commit_local_hook("- id: l")
    tooling.wants_ci = tooling.wants_release = tooling.wants_docker = True
    tooling.wants_just = tooling.wants_agents = tooling.wants_community = True
    tooling.conventional_commits = True
    tooling.add_ci_flag(CIFlag.ZENSICAL)
    tooling.add_ci_flag(CIFlag.CODECOV)
    tooling.add_ci_step("- run: x")
    tooling.just_format_commands.append("fmt")
    tooling.just_lint_commands.append("lint")
    tooling.just_typecheck_commands.append("types")
    tooling.just_clean_paths.append(".cache")
    for extension in ("c.d", ("b.e", "a.f"), "a.b", ("a.a", "z.z")):
        tooling.add_ide_extension(extension)

    assert tooling.to_dict() == {
        "hook_runner": "prek",
        "pre_commit_hooks": ["- id: a"],
        "pre_commit_local_hooks": ["- id: l"],
        "wants_ci": True,
        "wants_release": True,
        "wants_docker": True,
        "ci_flags": ["codecov", "zensical"],
        "ci_steps": ["- run: x"],
        "wants_just": True,
        "just_format_commands": ["fmt"],
        "just_lint_commands": ["lint"],
        "just_typecheck_commands": ["types"],
        "just_clean_paths": [".cache"],
        "wants_agents": True,
        "wants_community": True,
        "conventional_commits": True,
        "ide_extensions": [["a.a", "z.z"], "a.b", ["b.e", "a.f"], "c.d"],
    }


# ---- tasks ----


def test_a_task_is_observed_by_its_command_and_kept_once() -> None:
    calls: list[tuple[str, ...]] = []
    tasks = TaskManifest(observe=calls.append)

    tasks.add_system_task(["uv", "sync"], timeout=5, description="first")
    tasks.add_system_task(["uv", "sync"], timeout=99, description="second")
    tasks.add_post_install_task(["uv", "sync"])
    tasks.add_post_install_task(["a", "b"], owned_files=["f"], owned_trees=["t"])

    assert calls == [
        ("system_tasks", _sha("uv\0sync")),
        ("system_tasks", _sha("uv\0sync")),
        ("post_install_tasks", _sha("uv\0sync")),
        ("post_install_tasks", _sha("a\0b")),
    ]
    assert [(t.command, t.timeout, t.description) for t in tasks.system_tasks] == [
        (["uv", "sync"], 5, "first")
    ]
    assert [t.command for t in tasks.post_install_tasks] == [["uv", "sync"], ["a", "b"]]
    assert tasks.post_install_tasks[1].owned_files == ["f"]
    assert tasks.post_install_tasks[1].owned_trees == ["t"]
    assert tasks.post_install_tasks[0].timeout == 30


def test_a_system_task_declares_its_outputs_too() -> None:
    tasks = TaskManifest()

    tasks.add_system_task(["x"], owned_files=["f"], owned_trees=["t"])

    assert tasks.to_dict() == {
        "system_tasks": [
            {
                "command": ["x"],
                "description": None,
                "timeout": 30,
                "owned_files": ["f"],
                "owned_trees": ["t"],
            }
        ],
        "post_install_tasks": [],
    }


# ---- the environment ----


def _recipe(**context: str) -> ProjectRecipe:
    names = {"PROJECT_NAME": "demo-app", "PACKAGE_NAME": "demo_app", **context}
    return ProjectRecipe(
        None,
        "3.13",
        IDEType.NONE,
        (),
        (),
        tuple(sorted(names.items())),
        (),
    )


def test_a_new_manifest_is_empty_and_shares_nothing() -> None:
    first, second = EnvironmentManifest(), EnvironmentManifest()

    assert first.producer_contributions == ()
    assert first.selections == ()
    assert first.recipe is None
    assert first.one_shot is False
    assert first.template_reference is None
    assert first.migrations == ()
    assert first.collision_strategy is CollisionStrategy.MERGE
    assert first.collisions == frozenset()
    assert first.missing_tools == frozenset()
    assert first.diagnostics == []
    assert first.metadata == {}
    assert first.ide_settings == {}
    first.diagnostics.append(DiagnosticEvent(DiagnosticPhase.CI, "x", Severity.INFO))
    first.metadata["description"] = "d"
    first.add_ide_setting("python.terminal.activateEnvironment", True)
    assert second.diagnostics == []
    assert second.metadata == {}
    assert second.ide_settings == {}


def test_a_missing_tool_is_found_by_its_executable() -> None:
    manifest = EnvironmentManifest(
        missing_tools=frozenset({MissingTool(GlobalExecutable.JUST, Tool.RUFF)})
    )

    assert manifest.is_missing(GlobalExecutable.JUST) is True
    assert manifest.is_missing(GlobalExecutable.DIRENV) is False


def test_the_guide_needs_a_recipe() -> None:
    with pytest.raises(ConfigurationError) as raised:
        EnvironmentManifest().guide_spec()

    assert str(raised.value) == "The guide needs a planned recipe."


def test_the_guide_states_the_tooling_the_manifest_holds() -> None:
    manifest = EnvironmentManifest(recipe=_recipe(), one_shot=True)
    tooling = manifest.tooling
    tooling.set_hook_runner(HookRunner.PREK)
    tooling.wants_just = tooling.wants_ci = tooling.conventional_commits = True
    tooling.add_ci_flag(CIFlag.PYTEST)
    tooling.just_format_commands.append("fmt")
    tooling.just_lint_commands.append("lint")
    tooling.just_typecheck_commands.append("types")

    spec = manifest.guide_spec()

    assert (
        spec.python_version,
        spec.hook_runner,
        spec.wants_just,
        spec.format_commands,
        spec.lint_commands,
        spec.typecheck_commands,
        spec.ci_flags,
        spec.conventional_commits,
        spec.wants_ci,
        spec.one_shot,
    ) == (
        "3.13",
        HookRunner.PREK,
        True,
        ["fmt"],
        ["lint"],
        ["types"],
        {CIFlag.PYTEST},
        True,
        True,
        True,
    )
    assert EnvironmentManifest(recipe=_recipe()).guide_spec().one_shot is False


def test_a_documents_locations_depend_on_the_hook_runner() -> None:
    manifest = EnvironmentManifest()
    manifest.tooling.set_hook_runner(HookRunner.PREK)

    locations = manifest.document_locations(".pre-commit-config.yaml")

    assert locations.editable == (".pre-commit-config.yaml", ".pre-commit-config.yml")
    assert locations.competitors == ("prek.toml",)
    assert manifest.document_locations("notes.txt").paths == ("notes.txt",)


def test_declared_documents_always_include_pyproject_and_its_aliases() -> None:
    assert EnvironmentManifest().declared_documents() == {"pyproject.toml"}


def test_declared_documents_follow_what_the_manifest_declares() -> None:
    manifest = EnvironmentManifest(recipe=_recipe())
    manifest.filesystem.add_structured(
        "config/<% PACKAGE_NAME %>.toml", "x = 1", producer="m"
    )
    manifest.filesystem.add_file_injection(".github/renovate.json", "{}")
    manifest.filesystem.add_file_injection("README.md", "# x\n")
    manifest.tooling.set_hook_runner(HookRunner.PREK)
    manifest.tooling.wants_ci = manifest.tooling.wants_release = True
    manifest.add_ide_setting("python.terminal.activateEnvironment", True)

    assert manifest.declared_documents() == {
        "pyproject.toml",
        "config/demo_app.toml",
        ".github/renovate.json",
        "renovate.json",
        "renovate.jsonc",
        ".github/renovate.jsonc",
        ".renovaterc",
        ".renovaterc.json",
        ".renovaterc.jsonc",
        "renovate.json5",
        ".github/renovate.json5",
        ".renovaterc.json5",
        ".pre-commit-config.yaml",
        ".pre-commit-config.yml",
        "prek.toml",
        ".github/workflows/ci.yml",
        ".github/workflows/ci.yaml",
        ".github/workflows/release.yml",
        ".github/workflows/release.yaml",
        ".vscode/settings.json",
    }


def test_each_declared_document_needs_its_own_declaration() -> None:
    def declared(**wants: bool) -> set[str]:
        manifest = EnvironmentManifest()
        for name, value in wants.items():
            setattr(manifest.tooling, name, value)
        return manifest.declared_documents()

    assert declared(wants_ci=True) == {
        "pyproject.toml",
        ".github/workflows/ci.yml",
        ".github/workflows/ci.yaml",
    }
    assert declared(wants_release=True) == {
        "pyproject.toml",
        ".github/workflows/release.yml",
        ".github/workflows/release.yaml",
    }
    manifest = EnvironmentManifest()
    manifest.tooling.set_hook_runner(HookRunner.PRE_COMMIT)
    assert manifest.declared_documents() == {
        "pyproject.toml",
        ".pre-commit-config.yaml",
        ".pre-commit-config.yml",
    }


def test_a_tool_generates_a_file_whole_only_while_it_is_wanted() -> None:
    manifest = EnvironmentManifest()
    assert manifest.generated_files() == set()

    manifest.tooling.wants_just = True
    assert manifest.generated_files() == {"justfile"}
    manifest.tooling.wants_docker = True
    assert manifest.generated_files() == {"justfile", "Dockerfile"}


def test_each_wanted_tool_adds_its_own_target_file() -> None:
    manifest = EnvironmentManifest()
    assert manifest.target_files() == set()

    manifest.dependencies.includes.append(
        DependencyInclude(DependencyGroup.DEV, DependencyGroup.DOCS)
    )
    assert manifest.target_files() == {Path("pyproject.toml")}
    manifest.tooling.set_hook_runner(HookRunner.PRE_COMMIT)
    manifest.tooling.wants_ci = True
    assert manifest.target_files() == {
        Path("pyproject.toml"),
        Path(".pre-commit-config.yaml"),
        Path(".github/workflows/ci.yml"),
    }
    manifest.tooling.wants_release = True
    manifest.tooling.wants_docker = True
    assert manifest.target_files() == {
        Path("pyproject.toml"),
        Path(".pre-commit-config.yaml"),
        Path(".github/workflows/ci.yml"),
        Path(".github/workflows/release.yml"),
        Path("Dockerfile"),
        Path(".dockerignore"),
    }


def test_target_paths_render_from_the_recipe_when_there_is_one() -> None:
    manifest = EnvironmentManifest(recipe=_recipe(PACKAGE_NAME="from_recipe"))
    manifest.metadata.update(cast(ProjectMetadata, {"package_name": "from_meta"}))
    manifest.filesystem.add_file_injection("<% PACKAGE_NAME %>/a.txt", "x")
    manifest.filesystem.add_structured("<% PACKAGE_NAME %>.toml", "x = 1", producer="m")
    manifest.filesystem.add_region("<% PACKAGE_NAME %>/r.txt", "x", identity="r")
    manifest.filesystem.add_directory("<% PROJECT_NAME %>")

    assert manifest.target_files() == {
        Path("from_recipe/a.txt"),
        Path("from_recipe.toml"),
        Path("from_recipe/r.txt"),
    }
    assert manifest.target_directories() == {Path("demo-app")}


def test_target_paths_render_from_the_metadata_without_a_recipe() -> None:
    manifest = EnvironmentManifest()
    manifest.metadata.update(
        cast(ProjectMetadata, {"project_name": "my-proj", "package_name": "my_pkg"})
    )
    manifest.filesystem.add_directory("<% PROJECT_NAME %>/<% PACKAGE_NAME %>")

    assert manifest.target_directories() == {Path("my-proj/my_pkg")}


def test_previews_list_what_a_run_writes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = EnvironmentManifest()
    assert manifest.written_files() == set()

    manifest.filesystem.add_vcs_ignore(".venv/")
    assert manifest.written_files() == {Path(".gitignore")}
    manifest.add_ide_setting("python.terminal.activateEnvironment", True)
    assert manifest.written_files() == {
        Path(".gitignore"),
        Path(".vscode/settings.json"),
    }


def test_a_document_found_under_another_name_is_listed_there(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pre-commit-config.yml").write_text("repos: []\n", encoding="utf-8")
    manifest = EnvironmentManifest()
    manifest.tooling.set_hook_runner(HookRunner.PREK)

    assert manifest.written_files() == {Path(".pre-commit-config.yml")}
    assert manifest.colliding_files() == {Path(".pre-commit-config.yml")}


def test_a_document_that_cannot_be_chosen_is_listed_under_its_own_name(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for name in (".pre-commit-config.yaml", ".pre-commit-config.yml"):
        (tmp_path / name).write_text("repos: []\n", encoding="utf-8")
    manifest = EnvironmentManifest()
    manifest.tooling.set_hook_runner(HookRunner.PRE_COMMIT)

    assert manifest.written_files() == {Path(".pre-commit-config.yaml")}


def test_colliding_files_are_the_existing_ones_a_run_would_edit(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    (tmp_path / "prek.toml").write_text("", encoding="utf-8")
    manifest = EnvironmentManifest()
    manifest.filesystem.add_file_injection("README.md", "# y\n")
    manifest.filesystem.add_file_injection("NEW.md", "# z\n")
    manifest.tooling.set_hook_runner(HookRunner.PREK)

    assert manifest.colliding_files() == {Path("README.md")}


def test_the_files_commands_create_leave_out_clone_local_git_state() -> None:
    manifest = EnvironmentManifest()
    manifest.tasks.add_system_task(["a"], owned_files=["x.txt", ".git/config"])
    manifest.tasks.add_post_install_task(
        ["b"], owned_files=[".github/y.yml", ".git/hooks/pre-commit", "git/z", "w.txt"]
    )

    assert manifest.command_files() == {
        Path("x.txt"),
        Path(".github/y.yml"),
        Path("git/z"),
        Path("w.txt"),
    }


def test_the_resolver_footprint_is_planned_for_any_installed_group() -> None:
    footprint = ResolverFootprint(("pyproject.toml", "uv.lock", "extra.lock"))
    for install in ("add", "add_dev", "add_docs"):
        manifest = EnvironmentManifest(one_shot=True)
        manifest.dependencies.resolver_footprint = footprint
        assert manifest.planned_files() == set()
        getattr(manifest.dependencies, install)("requests")
        assert manifest.planned_files() == {
            Path("pyproject.toml"),
            Path("uv.lock"),
            Path("extra.lock"),
        }


def test_planned_files_add_the_reconciliation_state_unless_one_shot() -> None:
    assert Path("protostar.lock") in EnvironmentManifest().planned_files()
    assert (
        Path("protostar.lock") not in EnvironmentManifest(one_shot=True).planned_files()
    )


def test_the_manifest_serializes_its_state_for_machines() -> None:
    reference = TemplateReference(TemplateOrigin.LOCAL, "/t", "abc")
    manifest = EnvironmentManifest(
        one_shot=True,
        template_reference=reference,
        migrations=(Migration("1.0.0", remove=("old.txt",)),),
        collisions=frozenset({Path("b/x.txt"), Path("a.txt")}),
        missing_tools=frozenset({MissingTool(GlobalExecutable.JUST, Tool.RUFF)}),
    )
    manifest.metadata.update(cast(ProjectMetadata, {"description": "d"}))
    manifest.add_ide_setting("python.terminal.activateEnvironment", True)
    manifest.dependencies.add("requests")
    manifest.filesystem.add_directory("src")
    manifest.tooling.wants_just = True
    manifest.tasks.add_system_task(["uv", "sync"])

    assert manifest.to_dict() == {
        "one_shot": True,
        "template_reference": reference.to_dict(),
        "migrations": [Migration("1.0.0", remove=("old.txt",)).to_dict()],
        "collision_strategy": "merge",
        "collisions": ["a.txt", "b/x.txt"],
        "missing_tools": [{"executable": "just", "tool": "ruff"}],
        "metadata": {"description": "d"},
        "ide_settings": {"python.terminal.activateEnvironment": True},
        "dependencies": manifest.dependencies.to_dict(),
        "filesystem": manifest.filesystem.to_dict(),
        "tooling": manifest.tooling.to_dict(),
        "tasks": manifest.tasks.to_dict(),
    }


def test_an_empty_manifest_serializes_without_a_reference_or_strategy() -> None:
    record = EnvironmentManifest(collision_strategy=None).to_dict()

    assert record["template_reference"] is None
    assert record["collision_strategy"] is None
    assert record["migrations"] == []
    assert record["collisions"] == []
    assert record["missing_tools"] == []
    assert (
        EnvironmentManifest(collision_strategy=CollisionStrategy.OVERWRITE).to_dict()[
            "collision_strategy"
        ]
        == "overwrite"
    )


def test_a_declared_path_is_rendered_as_a_path_not_as_toml() -> None:
    """A name with a quote stays as written: nothing here is TOML to escape."""
    manifest = EnvironmentManifest(recipe=_recipe(PROJECT_NAME='a"b', PACKAGE_NAME="p"))
    manifest.filesystem.add_directory("<% PROJECT_NAME %>/d")
    manifest.filesystem.add_file_injection("<% PROJECT_NAME %>/f.txt", "x")
    manifest.filesystem.add_structured("<% PROJECT_NAME %>.toml", "x = 1", producer="m")
    manifest.filesystem.add_region("<% PROJECT_NAME %>/r.txt", "x", identity="r")

    assert manifest.target_directories() == {Path('a"b/d')}
    assert manifest.target_files() == {
        Path('a"b/f.txt'),
        Path('a"b.toml'),
        Path('a"b/r.txt'),
    }
    assert 'a"b.toml' in manifest.declared_documents()


def test_a_template_path_that_renders_to_renovates_file_declares_renovate() -> None:
    manifest = EnvironmentManifest(recipe=_recipe(PROJECT_NAME="renovate"))
    manifest.filesystem.add_file_injection(".github/<% PROJECT_NAME %>.json", "{}")

    assert ".github/renovate.json" in manifest.declared_documents()


def test_setting_requires_python_in_pyproject_moves_the_resolver() -> None:
    filesystem, _ = _filesystem()

    filesystem.add_structured(
        "pyproject.toml", '[project]\nrequires-python = ">=3.12"\n', producer="m"
    )
    filesystem.add_structured(
        "other.toml", '[project]\nrequires-python = ">=3.12"\n', producer="m"
    )
    filesystem.add_structured("pyproject.toml", "[tool.x]\na = 1\n", producer="n")

    footprints = [c.resolver_footprint for c in filesystem.structured["pyproject.toml"]]
    assert footprints == [ResolverFootprint(), None]
    assert filesystem.structured["other.toml"][0].resolver_footprint is None
