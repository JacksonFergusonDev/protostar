"""Transactional PR C acceptance tests with in-process resolver doubles."""

import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from protostar.config import UserConfig
from protostar.errors import (
    CommandExecutionError,
    ConfigurationError,
    FileSystemError,
    UnsupportedFilesystemNodeError,
)
from protostar.executor import SystemExecutor
from protostar.intent import (
    DependencyGroup,
    StructuredContribution,
    TemplateOrigin,
    TemplateReference,
)
from protostar.manifest import CollisionStrategy, EnvironmentManifest, SystemTask
from protostar.merge import MISSING, MergeLocation, Value
from protostar.models import ExecutionResult
from protostar.sync_state import decode_toml_baseline, deserialize_state
from protostar.toml_ast import aggregate_toml, reconcile_toml


def manifest(value=88, *, template=None):
    result = EnvironmentManifest(template_reference=template)
    result.collision_strategy = CollisionStrategy.MERGE
    result.filesystem.add_structured(
        "pyproject.toml",
        f'[project]\nname = "seed"\nversion = "0.1.0"\n[tool.ruff]\nline-length = {value}\n[tool.ruff.lint]\nselect = ["E", "F"]\n',
        producer="module:test",
    )
    return result


def run(intent, mocker):
    executor = SystemExecutor(intent, UserConfig())
    mocker.patch.object(executor.process_runner, "run")
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    return executor


def owned():
    state = deserialize_state(Path(".protostar.lock.toml").read_text())
    baseline = state.files[0].baseline
    assert baseline is not None
    return decode_toml_baseline(baseline)


def test_initial_repeat_and_clean_update(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    first = run(manifest(), mocker)
    assert first.journal.created_paths == {"pyproject.toml", ".protostar.lock.toml"}
    initial = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    for _ in range(2):
        repeated = run(manifest(), mocker)
        assert repeated.journal.touched_paths == frozenset()
        assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == initial
    changed = run(manifest(100), mocker)
    assert changed.journal.mutated_paths == {"pyproject.toml", ".protostar.lock.toml"}
    assert owned()["tool"]["ruff"]["line-length"] == 100


def test_partial_conflict_and_foreign_trivia(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(manifest(), mocker)
    target = Path("pyproject.toml")
    target.write_text(
        target.read_text()
        .replace("line-length = 88", "line-length = 120 # local choice")
        .replace('select = ["E", "F"]', 'select = ["E"] # user deleted F')
        + "\n[tool.foreign]\nanswer = 42 # foreign\n"
    )
    changed = manifest(100)
    changed.filesystem.add_structured(
        "pyproject.toml",
        '[tool.ruff]\npreview = true\n[tool.ruff.lint]\nselect = ["E", "F", "I"]\n',
        producer="template:example:config",
    )
    executor = run(changed, mocker)
    content = target.read_text()
    assert "line-length = 120 # local choice" in content
    assert "# user deleted F" in content
    assert "answer = 42 # foreign" in content
    data = tomllib.loads(content)
    assert data["tool"]["ruff"]["preview"] is True
    assert data["tool"]["ruff"]["lint"]["select"] == ["E", "I"]
    baseline = owned()
    assert baseline["tool"]["ruff"]["line-length"] == 88
    assert "foreign" not in baseline["tool"]
    payload = ExecutionResult(
        executor.journal.created_paths,
        executor.journal.mutated_paths,
        tuple(executor.diagnostics),
    ).to_dict()
    assert payload["diagnostics"][0]["conflict"] == {
        "file": "pyproject.toml",
        "keys": ["tool", "ruff", "line-length"],
        "identity": None,
        "reason": "diverged",
    }


def test_missing_state_no_adoption_and_seed_metadata(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    original = '[project]\nname = "personal"\nversion = "9.0"\n[tool.ruff]\nline-length = 88 # equal foreign\n'
    Path("pyproject.toml").write_text(original)
    run(manifest(), mocker)
    assert 'name = "personal"' in Path("pyproject.toml").read_text()
    assert "line-length" not in owned()["tool"]["ruff"]
    assert "project" not in owned()
    later = run(manifest(100), mocker)
    assert (
        tomllib.loads(Path("pyproject.toml").read_text())["tool"]["ruff"]["line-length"]
        == 88
    )
    assert later.diagnostics[0].conflict.reason.value == "unowned"


@pytest.mark.parametrize("delete", ["file", "table", "scalar"])
def test_owned_deletion_protects_new_intent(tmp_path, monkeypatch, mocker, delete):
    monkeypatch.chdir(tmp_path)
    run(manifest(), mocker)
    target = Path("pyproject.toml")
    if delete == "file":
        target.unlink()
    elif delete == "table":
        target.write_text('[project]\nname = "seed"\nversion = "0.1.0"\n')
    else:
        target.write_text(target.read_text().replace("line-length = 88\n", ""))
    local = target.read_bytes() if target.exists() else None
    executor = run(manifest(100), mocker)
    assert (target.read_bytes() if target.exists() else None) == local
    assert executor.diagnostics
    assert owned()["tool"]["ruff"]["line-length"] == 88


@pytest.mark.parametrize("phase", ["post", "resolver", "state"])
def test_failures_restore_exact_bytes_modes_and_state(
    tmp_path, monkeypatch, mocker, phase
):
    monkeypatch.chdir(tmp_path)
    run(manifest(), mocker)
    paths = [Path("pyproject.toml"), Path(".protostar.lock.toml"), Path("uv.lock")]
    paths[-1].write_bytes(b"original lock\r\n")
    for path in paths:
        path.chmod(0o640)
    originals = {p: (p.read_bytes(), p.stat().st_mode) for p in paths}
    intent = manifest(100)
    executor = SystemExecutor(intent, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    if phase == "post":
        intent.tasks.post_install_tasks.append(SystemTask(["git", "status"]))
        mocker.patch.object(
            executor.process_runner,
            "run",
            side_effect=CommandExecutionError(["git"], 1),
        )
    elif phase == "resolver":
        intent.dependencies.add("new-package")

        def fail(*args, **kwargs):
            Path("pyproject.toml").write_bytes(b"resolver edit")
            Path("uv.lock").write_bytes(b"resolver lock")
            raise CommandExecutionError(["uv", "add"], 1)

        mocker.patch.object(executor.process_runner, "run", side_effect=fail)
    else:
        original_write = executor.fs.write_text

        def fail_state(path, content, **kwargs):
            original_write(path, content, **kwargs)
            if path.name == ".protostar.lock.toml":
                raise OSError("state write failure")

        mocker.patch.object(executor.fs, "write_text", side_effect=fail_state)
    with pytest.raises((CommandExecutionError, FileSystemError)):
        executor.execute()
    assert {p: (p.read_bytes(), p.stat().st_mode) for p in paths} == originals


@pytest.mark.parametrize(
    "bad", ["malformed", "version", "identity", "symlink", "target_symlink"]
)
def test_invalid_state_and_nodes_abort_before_mutation(
    tmp_path, monkeypatch, mocker, bad
):
    monkeypatch.chdir(tmp_path)
    ref = TemplateReference(TemplateOrigin.BUILT_IN, "cli", "a" * 64)
    run(manifest(template=ref), mocker)
    state = Path(".protostar.lock.toml")
    if bad == "malformed":
        state.write_text("[broken")
    elif bad == "version":
        state.write_text(
            state.read_text().replace("schema_version = 1", "schema_version = 2")
        )
    elif bad == "identity":
        ref = replace(ref, locator="other")
    elif bad == "symlink":
        state.rename("actual-state")
        state.symlink_to("actual-state")
    else:
        Path("pyproject.toml").rename("actual-project")
        Path("pyproject.toml").symlink_to("actual-project")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises((ConfigurationError, UnsupportedFilesystemNodeError)):
        run(manifest(100, template=ref), mocker)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_initializer_output_is_owned_but_preexisting_metadata_is_not(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    intent = manifest()
    intent.tasks.system_tasks.append(
        SystemTask(["uv", "init"], owned_files=["pyproject.toml"])
    )
    executor = SystemExecutor(intent, UserConfig())

    def initialize(*args, **kwargs):
        Path("pyproject.toml").write_text(
            '[project]\nname = "uv-default"\nversion = "0.1.0"\n'
        )

    mocker.patch.object(executor.process_runner, "run", side_effect=initialize)
    executor.execute()
    assert owned()["project"]["name"] == "seed"


def test_aggregation_precedence_and_ambiguity():
    contributions = [
        StructuredContribution("template:x:config", "[tool.ruff]\nline-length = 100\n"),
        StructuredContribution("module:Ruff", "[tool.ruff]\nline-length = 88\n"),
    ]
    assert aggregate_toml(contributions) == {"tool": {"ruff": {"line-length": 100}}}
    with pytest.raises(ConfigurationError, match="Ambiguous"):
        aggregate_toml(
            [
                StructuredContribution("one", "key = 1"),
                StructuredContribution("two", "key = 2"),
            ]
        )


def test_atomic_arrays_and_noop_representation():
    original = '# custom header\r\n[tool.custom]\r\norder = ["a", "b"] # ordered\r\n'
    desired: dict[str, Value] = {"tool": {"custom": {"order": ["a", "b"]}}}
    result = reconcile_toml(original, desired, MISSING, MergeLocation("custom.toml"))
    assert result.content == original
    assert result.baseline is MISSING
    changed = reconcile_toml(
        original,
        {"tool": {"custom": {"order": ["b", "a"]}}},
        MISSING,
        MergeLocation("custom.toml"),
    )
    assert changed.content == original
    assert changed.conflicts


def test_dependency_materialized_bounds_repeat_edit_and_update(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text(
        '[project]\nname = "personal"\ndependencies = []\n'
    )

    def execute_requirement(requirement, materialized=None):
        intent = EnvironmentManifest()
        intent.collision_strategy = CollisionStrategy.MERGE
        intent.dependencies.add(requirement)
        executor = SystemExecutor(intent, UserConfig())

        def resolve(command, **kwargs):
            assert command == ["uv", "add", requirement]
            import tomlkit

            doc = tomlkit.parse(Path("pyproject.toml").read_text())
            doc["project"]["dependencies"] = [materialized or requirement]
            Path("pyproject.toml").write_text(tomlkit.dumps(doc))
            Path("uv.lock").write_text("resolved")

        runner = mocker.patch.object(
            executor.process_runner, "run", side_effect=resolve
        )
        executor.execute()
        return executor, runner

    _first, runner = execute_requirement("Requests", "requests>=2.0")
    runner.assert_called_once()
    record = deserialize_state(Path(".protostar.lock.toml").read_text()).dependencies[0]
    assert record.declared == "Requests"
    assert record.materialized == "requests>=2.0"
    repeated, runner = execute_requirement("requests")
    runner.assert_not_called()
    assert repeated.journal.touched_paths == frozenset()
    Path("pyproject.toml").write_text(
        Path("pyproject.toml").read_text().replace("requests>=2.0", "requests>=5.0")
    )
    edited, runner = execute_requirement("requests>=3.0")
    runner.assert_not_called()
    assert edited.diagnostics[0].conflict.reason.value == "diverged"
    Path("pyproject.toml").write_text(
        Path("pyproject.toml").read_text().replace("requests>=5.0", "requests>=2.0")
    )
    _accepted, runner = execute_requirement("requests>=3.0")
    runner.assert_called_once()
    assert (
        deserialize_state(Path(".protostar.lock.toml").read_text())
        .dependencies[0]
        .materialized
        == "requests>=3.0"
    )


@pytest.mark.parametrize(
    ("local", "desired"),
    [
        (["requests>=5"], ["requests"]),
        (["requests>=2", "Requests<4"], ["requests>=3"]),
        ([], ["Requests>=2", "requests>=3"]),
        (["requests[security]>=2"], ["requests>=2"]),
        (["requests @ https://example.com/a.whl"], ["requests"]),
        (
            ["requests>=2; python_version < '3.14'"],
            ["requests>=3; python_version < '3.14'"],
        ),
    ],
)
def test_unowned_dependency_constraints_and_duplicate_identities(local, desired):
    from protostar.dependencies import select_dependencies

    result = select_dependencies(desired, local, (), DependencyGroup.MAIN)
    assert not result.packages
    assert result.conflicts


def test_owned_dependency_deletion_and_regression():
    from protostar.dependencies import select_dependencies
    from protostar.sync_state import DependencyState

    record = DependencyState(
        "pyproject.toml",
        DependencyGroup.MAIN,
        "requests",
        "",
        "requests",
        "requests>=3",
    )
    for local, desired in [
        ([], "requests>=4"),
        (["requests>=3"], "requests==2"),
        (["requests>=3"], "requests<5"),
    ]:
        result = select_dependencies([desired], local, (record,), DependencyGroup.MAIN)
        assert not result.packages
        assert result.conflicts


def test_toml_execution_noop_preserves_crlf_bytes(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    original = b'[project]\r\nname = "mine"\r\n[tool.ruff]\r\nline-length = 88 # foreign\r\n[tool.ruff.lint]\r\nselect = ["E", "F"]\r\n'
    Path("pyproject.toml").write_bytes(original)
    executor = run(manifest(), mocker)
    assert Path("pyproject.toml").read_bytes() == original
    assert "pyproject.toml" not in executor.journal.touched_paths


def test_existing_directories_are_valid_on_repeat(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    intent = manifest()
    intent.filesystem.add_directory(".github")
    run(intent, mocker)
    repeated = run(intent, mocker)
    assert repeated.journal.touched_paths == frozenset()


def test_new_dependency_does_not_resurrect_owned_file(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(manifest(), mocker)
    Path("pyproject.toml").unlink()
    intent = manifest()
    intent.dependencies.add("new-package")
    executor = run(intent, mocker)
    executor.process_runner.run.assert_not_called()
    assert not Path("pyproject.toml").exists()


@pytest.mark.parametrize(
    ("before", "after"),
    [("foo<2", "foo<1"), ("foo~=2.0", "foo~=1.0"), ("foo>=2", "foo>=2,<2.1")],
)
def test_ambiguous_owned_dependency_constraints_preserved(before, after):
    from protostar.dependencies import select_dependencies
    from protostar.sync_state import DependencyState

    record = DependencyState(
        "pyproject.toml", DependencyGroup.MAIN, "foo", "", before, before
    )
    assert select_dependencies(
        [after], [before], (record,), DependencyGroup.MAIN
    ).conflicts


def test_includes_cannot_bypass_deleted_file_guard(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    run(manifest(), mocker)
    Path("pyproject.toml").unlink()
    intent = manifest()
    intent.dependencies.add_include(DependencyGroup.DEV, DependencyGroup.DOCS)
    intent.dependencies.add_dev("new-package")
    executor = run(intent, mocker)
    executor.process_runner.run.assert_not_called()
    assert not Path("pyproject.toml").exists()


def test_dependency_only_malformed_toml_is_fatal_before_writes(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_bytes(b"[broken")
    intent = EnvironmentManifest()
    intent.dependencies.add("requests")
    with pytest.raises(ConfigurationError):
        run(intent, mocker)
    assert not Path(".protostar.lock.toml").exists()
    assert Path("pyproject.toml").read_bytes() == b"[broken"


def test_owned_convergence_advances_only_accepted_dependency(
    tmp_path, monkeypatch, mocker
):
    from protostar.sync_state import DependencyState, SyncState, serialize_state

    monkeypatch.chdir(tmp_path)
    record = DependencyState(
        "pyproject.toml",
        DependencyGroup.MAIN,
        "requests",
        "",
        "requests>=2",
        "requests>=2",
    )
    Path(".protostar.lock.toml").write_text(
        serialize_state(SyncState("old", dependencies=(record,)))
    )
    Path("pyproject.toml").write_text('[project]\ndependencies = ["requests>=3"]\n')
    intent = EnvironmentManifest()
    intent.dependencies.add("requests>=3")
    executor = run(intent, mocker)
    executor.process_runner.run.assert_not_called()
    assert (
        deserialize_state(Path(".protostar.lock.toml").read_text())
        .dependencies[0]
        .declared
        == "requests>=3"
    )


def test_new_dependency_cannot_resurrect_owned_project_table(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(manifest(), mocker)
    Path("pyproject.toml").write_text(
        '[tool.ruff]\nline-length = 88\n[tool.ruff.lint]\nselect = ["E", "F"]\n'
    )
    intent = manifest()
    intent.dependencies.add("new-package")
    executor = run(intent, mocker)
    executor.process_runner.run.assert_not_called()
    assert "project" not in tomllib.loads(Path("pyproject.toml").read_text())


def test_unchanged_dependency_under_deleted_file_is_silent(
    tmp_path, monkeypatch, mocker
):
    from protostar.sync_state import DependencyState, SyncState, serialize_state

    monkeypatch.chdir(tmp_path)
    record = DependencyState(
        "pyproject.toml",
        DependencyGroup.MAIN,
        "requests",
        "",
        "requests",
        "requests>=2",
    )
    Path(".protostar.lock.toml").write_text(
        serialize_state(SyncState("old", dependencies=(record,)))
    )
    intent = EnvironmentManifest()
    intent.dependencies.add("requests")
    executor = run(intent, mocker)
    executor.process_runner.run.assert_not_called()
    assert not executor.diagnostics
    assert not Path("pyproject.toml").exists()


def test_owned_incompatible_project_table_preserved_with_warning(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    run(manifest(), mocker)
    Path("pyproject.toml").write_text(
        'project = "local"\n[tool.ruff]\nline-length = 88\n'
    )
    intent = manifest()
    intent.dependencies.add("new-package")
    intent.filesystem.add_structured(
        "pyproject.toml",
        '[project]\nrequires-python = ">=3.13"\n[tool.ruff]\npreview = true\n',
        producer="module:extra",
    )
    executor = run(intent, mocker)
    executor.process_runner.run.assert_not_called()
    assert tomllib.loads(Path("pyproject.toml").read_text())["project"] == "local"
    assert executor.diagnostics
