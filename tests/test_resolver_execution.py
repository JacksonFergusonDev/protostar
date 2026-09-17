"""PR G resolver ordering, ownership, and rollback acceptance tests."""

import tomllib
from pathlib import Path

import pytest
import tomlkit

from protostar.config import UserConfig
from protostar.errors import (
    CommandExecutionError,
    CommandTimeoutError,
    ConfigurationError,
)
from protostar.executor import SystemExecutor
from protostar.intent import DependencyGroup
from protostar.manifest import CollisionStrategy, EnvironmentManifest, SystemTask
from protostar.sync_state import deserialize_state


def intent(*, requirement=None, python=">=3.12", include=True):
    manifest = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    manifest.filesystem.add_structured(
        "pyproject.toml",
        f'[project]\nrequires-python = "{python}"\n',
        producer="module:test",
    )
    if include:
        manifest.dependencies.add_include(DependencyGroup.DEV, DependencyGroup.DOCS)
    if requirement:
        manifest.dependencies.add(requirement)
    return manifest


def execute(manifest, mocker, *, failure=None):
    executor = SystemExecutor(manifest, UserConfig())

    def resolve(command, **kwargs):
        target = Path("pyproject.toml")
        if command[:2] == ["uv", "init"]:
            target.write_text('[project]\nname = "demo"\ndependencies = []\n')
            return
        data = tomllib.loads(target.read_text())
        assert data["project"]["requires-python"] == ">=3.13"
        assert {"include-group": "docs"} in data["dependency-groups"]["dev"]
        assert {"pyproject.toml", "uv.lock"} <= executor.journal.touched_paths
        if command[:2] == ["uv", "add"]:
            doc = tomlkit.parse(target.read_text())
            doc["project"]["dependencies"] = [
                "requests>=2" if command[2] == "requests" else command[2]
            ]
            target.write_text(tomlkit.dumps(doc))
        Path("uv.lock").write_bytes(target.read_bytes())
        if failure:
            raise failure

    process = mocker.patch.object(executor.process_runner, "run", side_effect=resolve)
    mocker.patch.object(executor, "_check_ide_extensions")
    executor.execute()
    return executor, process


@pytest.mark.parametrize("addition", [False, True])
def test_final_metadata_resolves_once_after_initializer(
    tmp_path, monkeypatch, mocker, addition
):
    monkeypatch.chdir(tmp_path)
    manifest = intent(requirement="requests" if addition else None, python=">=3.13")
    manifest.tasks.system_tasks.append(
        SystemTask(["uv", "init"], owned_files=["pyproject.toml"])
    )
    _, process = execute(manifest, mocker)
    assert [c.args[0] for c in process.call_args_list] == [
        ["uv", "init"],
        ["uv", "add", "requests"] if addition else ["uv", "lock"],
    ]
    assert Path("uv.lock").read_bytes() == Path("pyproject.toml").read_bytes()
    # The repeat has no initializer declaration, as the real module plans it conditionally.
    repeated, process = execute(
        intent(requirement="requests" if addition else None, python=">=3.13"), mocker
    )
    process.assert_not_called()
    assert not repeated.journal.touched_paths
    if addition:
        record = deserialize_state(
            Path(".protostar.lock.toml").read_text()
        ).dependencies[0]
        assert (record.declared, record.materialized) == ("requests", "requests>=2")


@pytest.mark.parametrize("requirement", [None, "requests"])
def test_metadata_change_locks_when_dependency_unchanged(
    tmp_path, monkeypatch, mocker, requirement
):
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "demo"\ndependencies = []\n')
    execute(intent(requirement=requirement, python=">=3.13"), mocker)
    # Establish an older Python baseline without invoking a live resolver.
    state = Path(".protostar.lock.toml")
    state.write_text(state.read_text().replace(">=3.13", ">=3.12"))
    project = Path("pyproject.toml")
    project.write_text(project.read_text().replace(">=3.13", ">=3.12"))
    _, process = execute(intent(requirement=requirement, python=">=3.13"), mocker)
    process.assert_called_once_with(["uv", "lock"], timeout=600)
    assert Path("uv.lock").read_bytes() == project.read_bytes()


@pytest.mark.parametrize("deletion", ["edge", "group", "included_group"])
def test_owned_include_deletions_stay_deleted(tmp_path, monkeypatch, mocker, deletion):
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "demo"\n')
    execute(intent(python=">=3.13"), mocker)
    target = Path("pyproject.toml")
    doc = tomlkit.parse(target.read_text())
    groups = doc["dependency-groups"]
    if deletion == "edge":
        groups["dev"] = ["pytest>=8"]
    else:
        del groups["dev" if deletion == "group" else "docs"]
    target.write_text(tomlkit.dumps(doc))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    for _ in range(2):
        executor, process = execute(intent(python=">=3.13"), mocker)
        process.assert_not_called()
        assert not executor.journal.touched_paths
        assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("action", ["add", "lock"])
@pytest.mark.parametrize("error", ["failure", "timeout", "interrupt"])
def test_resolver_failure_restores_bytes_modes_and_state(
    tmp_path, monkeypatch, mocker, action, error
):
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "demo"\ndependencies = []\n')
    execute(intent(python=">=3.13"), mocker)
    state = Path(".protostar.lock.toml")
    state.write_text(state.read_text().replace(">=3.13", ">=3.12"))
    project = Path("pyproject.toml")
    project.write_text(project.read_text().replace(">=3.13", ">=3.12"))
    for path in (project, state, Path("uv.lock")):
        path.chmod(0o640)
    before = {p.name: (p.read_bytes(), p.stat().st_mode) for p in tmp_path.iterdir()}
    failure = {
        "failure": CommandExecutionError(
            command=["uv", action], returncode=1, stderr="failed"
        ),
        "timeout": CommandTimeoutError(command=["uv", action], timeout=600),
        "interrupt": KeyboardInterrupt(),
    }[error]
    cleanup = mocker.patch(
        "protostar.system.ProcessRunner.terminate_active_process_tree"
    )
    with pytest.raises(type(failure)):
        execute(
            intent(
                requirement="requests" if action == "add" else None, python=">=3.13"
            ),
            mocker,
            failure=failure,
        )
    cleanup.assert_called_once()
    assert {
        p.name: (p.read_bytes(), p.stat().st_mode) for p in tmp_path.iterdir()
    } == before


def test_missing_local_project_never_resolves_ancestor(tmp_path, monkeypatch, mocker):
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "pyproject.toml").write_text('[project]\nname = "ancestor"\n')
    child = parent / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    manifest = EnvironmentManifest()
    manifest.dependencies.add("requests")
    executor = SystemExecutor(manifest, UserConfig())
    process = mocker.patch.object(executor.process_runner, "run")
    with pytest.raises(ConfigurationError, match="No local resolver project"):
        executor.execute()
    process.assert_not_called()
    assert not list(child.iterdir())


def test_foreign_include_is_not_adopted(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    project = Path("pyproject.toml")
    project.write_text(
        '[project]\nrequires-python = ">=3.13"\n[dependency-groups]\ndev = [{ include-group = "docs" }, "pytest"]\ndocs = ["zensical"]\nother = ["custom"]\n'
    )
    original = project.read_bytes()
    _, process = execute(intent(python=">=3.13"), mocker)
    process.assert_not_called()
    assert project.read_bytes() == original
    state = deserialize_state(Path(".protostar.lock.toml").read_text())
    assert not state.files


@pytest.mark.parametrize(
    "group", [DependencyGroup.MAIN, DependencyGroup.DEV, DependencyGroup.DOCS]
)
def test_requirement_identity_tracks_only_accepted_group(
    tmp_path, monkeypatch, mocker, group
):
    monkeypatch.chdir(tmp_path)
    project = Path("pyproject.toml")
    project.write_text(
        '[project]\ndependencies = ["foreign>=5"]\n[dependency-groups]\ndev = []\ndocs = []\nother = ["custom"]\n'
    )
    manifest = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    requested = 'Foo_Bar[Some_Extra]>=2; python_version < "3.15"'
    getattr(
        manifest.dependencies,
        {
            DependencyGroup.MAIN: "add",
            DependencyGroup.DEV: "add_dev",
            DependencyGroup.DOCS: "add_docs",
        }[group],
    )(requested)
    executor = SystemExecutor(manifest, UserConfig())

    def resolve(command, **kwargs):
        assert command == ["uv", "add", *group.cli_args, requested]
        doc = tomlkit.parse(project.read_text())
        entries = (
            doc["project"]["dependencies"]
            if group is DependencyGroup.MAIN
            else doc["dependency-groups"][group.value]
        )
        entries.append('foo-bar[some-extra]>=2; python_version < "3.15"')
        project.write_text(tomlkit.dumps(doc))
        Path("uv.lock").write_text("resolved")

    process = mocker.patch.object(executor.process_runner, "run", side_effect=resolve)
    executor.execute()
    process.assert_called_once()
    state = deserialize_state(Path(".protostar.lock.toml").read_text())
    assert len(state.dependencies) == 1
    record = state.dependencies[0]
    assert (record.group, record.name, record.marker) == (
        group,
        "foo-bar",
        'python_version < "3.15"',
    )
    assert record.declared == requested
    assert tomllib.loads(project.read_text())["dependency-groups"]["other"] == [
        "custom"
    ]
    repeated = SystemExecutor(manifest, UserConfig())
    process = mocker.patch.object(repeated.process_runner, "run")
    repeated.execute()
    process.assert_not_called()
    assert not repeated.journal.touched_paths


def test_new_dependency_cannot_restore_include_owned_group(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "demo"\n')
    execute(intent(python=">=3.13"), mocker)
    project = Path("pyproject.toml")
    doc = tomlkit.parse(project.read_text())
    del doc["dependency-groups"]["docs"]
    project.write_text(tomlkit.dumps(doc))
    manifest = intent(python=">=3.13")
    manifest.dependencies.add_docs("new-package")
    executor, process = execute(manifest, mocker)
    process.assert_not_called()
    assert "docs" not in tomllib.loads(project.read_text())["dependency-groups"]
    assert executor.diagnostics
