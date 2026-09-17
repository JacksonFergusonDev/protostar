"""Read-only review/apply parity and captured-input acceptance for Stage 2 PR 2."""

import dataclasses
import stat
import sys
import tomllib
from pathlib import Path

import pytest
import tomlkit

from protostar.config import UserConfig
from protostar.errors import (
    CommandExecutionError,
    StaleReviewError,
    UnsupportedFilesystemNodeError,
)
from protostar.executor import SystemExecutor
from protostar.intent import DependencyGroup, StructuredFormat
from protostar.manifest import EnvironmentManifest, HookRunner
from protostar.preparation import prepare_review
from protostar.recipe import RecipeIntent, Tool, establish_recipe
from protostar.registry import PinProvenance, RemoteHook, ResolvedHookRevision
from protostar.sync_state import deserialize_state


def intent(value=88):
    result = EnvironmentManifest()
    result.filesystem.add_structured(
        "pyproject.toml", f"[tool.ruff]\nline-length = {value}\n", producer="ruff"
    )
    return result


def initialize(manifest, mocker):
    executor = SystemExecutor(manifest, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    mocker.patch.object(
        executor.process_runner, "run", side_effect=AssertionError("unexpected process")
    )
    executor.execute()
    return executor


def snapshot(root):
    return {
        path.relative_to(root).as_posix(): (
            path.read_bytes() if path.is_file() else None,
            stat.S_IMODE(path.stat().st_mode),
        )
        for path in root.rglob("*")
    }


def apply(manifest, review, mocker):
    executor = SystemExecutor(manifest, UserConfig(), review=review)
    process = mocker.patch.object(
        executor.process_runner, "run", side_effect=AssertionError("unexpected process")
    )
    mocker.patch.object(
        executor,
        "_check_ide_extensions",
        side_effect=AssertionError("unexpected IDE probe"),
    )
    executor.execute()
    process.assert_not_called()
    return executor


def test_preview_is_read_only_and_applies_exact_safe_sibling_bytes(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    initialize(intent(), mocker)
    target = Path("pyproject.toml")
    target.write_text(target.read_text().replace("88", "120 # local"))
    desired = intent(100)
    desired.filesystem.add_structured(
        "pyproject.toml", "[tool.ruff]\npreview = true\n", producer="template"
    )
    before = snapshot(tmp_path)
    mocker.patch("subprocess.run", side_effect=AssertionError("unexpected subprocess"))
    mocker.patch(
        "protostar.registry.resolve_hook_revisions",
        side_effect=AssertionError("unexpected registry acquisition"),
    )
    review = prepare_review(desired, UserConfig())
    assert snapshot(tmp_path) == before
    assert len(review.conflicts) == 1
    assert review.conflicts[0].location.keys == ("tool", "ruff", "line-length")
    assert len(review.edits) == 1
    assert b"120 # local" in review.edits[0].after
    assert b"preview = true" in review.edits[0].after
    apply(desired, review, mocker)
    assert target.read_bytes() == review.edits[0].after
    assert (
        deserialize_state(Path(".protostar.lock.toml").read_text())
        == review.candidate_state
    )


@pytest.mark.parametrize(
    "change", ["pyproject", "state", "uv-lock", "mode", "new-file", "ancestor"]
)
def test_stale_review_aborts_before_mutation(tmp_path, monkeypatch, mocker, change):
    monkeypatch.chdir(tmp_path)
    initialize(intent(), mocker)
    desired = intent(100)
    desired.filesystem.add_file_injection("new/seed.py", "seed")
    review = prepare_review(desired, UserConfig())
    if change == "pyproject":
        Path("pyproject.toml").write_text(
            "# concurrent\n" + Path("pyproject.toml").read_text()
        )
    elif change == "state":
        Path(".protostar.lock.toml").write_text(
            "# concurrent\n" + Path(".protostar.lock.toml").read_text()
        )
    elif change == "uv-lock":
        Path("uv.lock").write_text("new resolver state")
    elif change == "mode":
        if sys.platform == "win32":
            pytest.skip("Windows does not support POSIX permission modes")
        Path("pyproject.toml").chmod(0o744)
    elif change == "new-file":
        Path("new").mkdir()
        Path("new/seed.py").write_text("concurrent")
    else:
        Path("new").mkdir()
    before = snapshot(tmp_path)
    executor = SystemExecutor(desired, UserConfig(), review=review)
    writes = mocker.spy(executor.fs, "write_text")
    with pytest.raises(StaleReviewError):
        executor.execute()
    writes.assert_not_called()
    assert not executor.journal.touched_paths
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("node", ["input", "state", "lock", "ancestor"])
def test_unsupported_nodes_fail_during_preparation(tmp_path, monkeypatch, node):
    monkeypatch.chdir(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    path = {
        "input": "pyproject.toml",
        "state": ".protostar.lock.toml",
        "lock": "uv.lock",
        "ancestor": "generated",
    }[node]
    Path(path).symlink_to(outside)
    desired = intent()
    desired.filesystem.add_file_injection("generated/file.py", "seed")
    with pytest.raises(UnsupportedFilesystemNodeError):
        prepare_review(desired, UserConfig())
    assert outside.read_text() == "outside"


def test_state_only_convergence_and_preserved_local_deviation(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    initialize(intent(), mocker)
    target = Path("pyproject.toml")
    target.write_text(target.read_text().replace("88", "100"))
    desired = intent(100)
    review = prepare_review(desired, UserConfig())
    assert not review.edits
    assert review.state_changed
    assert review.pending
    executor = apply(desired, review, mocker)
    assert executor.journal.mutated_paths == {".protostar.lock.toml"}
    target.write_text(target.read_text().replace("100", "120"))
    review = prepare_review(desired, UserConfig())
    assert not review.pending
    assert review.preserved[0].location.keys == ("tool", "ruff", "line-length")
    assert not review.preserved[0].deleted
    assert not apply(desired, review, mocker).journal.touched_paths
    target.unlink()
    review = prepare_review(desired, UserConfig())
    assert not review.pending
    assert review.preserved[0].deleted
    assert not apply(desired, review, mocker).journal.touched_paths
    assert not target.exists()


def test_generated_regions_keyed_yaml_and_includes_share_prepared_bytes(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    first = intent()
    first.filesystem.add_file_injection(".github/renovate.json", '{"extends": []}\n')
    first.filesystem.add_region(".envrc", "first", identity="owned")
    first.filesystem.add_structured(
        ".github/codecov.yml",
        "coverage:\n  precision: 2\n",
        producer="codecov",
        document_format=StructuredFormat.YAML,
    )
    first.tooling.hook_runner = HookRunner.PRE_COMMIT
    pins = tuple(
        ResolvedHookRevision(hook, "v1.0.0", PinProvenance.REGISTRY)
        for hook in RemoteHook
    )
    mocker.patch("protostar.executor.resolve_hook_revisions", return_value=pins)
    initialize(first, mocker)
    desired = intent()
    desired.filesystem.add_file_injection(
        ".github/renovate.json", '{"extends": ["config:recommended"]}\n'
    )
    desired.filesystem.add_region(".envrc", "second", identity="owned")
    desired.filesystem.add_structured(
        ".github/codecov.yml",
        "coverage:\n  precision: 3\n",
        producer="codecov",
        document_format=StructuredFormat.YAML,
    )
    desired.tooling.hook_runner = HookRunner.PRE_COMMIT
    desired.tooling.add_pre_commit_local_hook(
        "      - id: new\n        entry: new\n        language: system"
    )
    review = prepare_review(desired, UserConfig(), hook_revisions=pins)
    before = snapshot(tmp_path)
    mocker.patch(
        "protostar.executor.resolve_hook_revisions",
        side_effect=AssertionError("registry refetch"),
    )
    assert snapshot(tmp_path) == before
    assert {edit.path for edit in review.edits} == {
        ".envrc",
        ".github/codecov.yml",
        ".github/renovate.json",
        ".pre-commit-config.yaml",
    }
    apply(desired, review, mocker)
    for edit in review.edits:
        assert Path(edit.path).read_bytes() == edit.after
    assert not prepare_review(desired, UserConfig(), hook_revisions=pins).pending


def test_lifecycle_excludes_every_declared_task_and_probe(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    initialize(intent(), mocker)
    desired = intent(100)
    desired.tasks.add_system_task(["uv", "init"], owned_files=["pyproject.toml"])
    desired.tasks.add_system_task(["git", "init"], owned_trees=[".git"])
    desired.tasks.add_post_install_task(["uv", "run", "arbitrary-template-task"])
    desired.tooling.add_ide_extension("extension")
    review = prepare_review(desired, UserConfig())
    assert len(review.initialization_only) == 3
    executor = apply(desired, review, mocker)
    assert executor.completed_tasks == []
    assert not Path(".git").exists()


def test_resolver_requests_unknown_output_and_declared_rollback(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    initialize(intent(), mocker)
    desired = intent(100)
    desired.dependencies.add_dev("example>=2")
    desired.dependencies.add_include(DependencyGroup.DEV, DependencyGroup.DOCS)
    review = prepare_review(desired, UserConfig())
    assert review.resolver.pending
    assert review.to_dict()["resolver"]["output"] == "unknown"
    assert "uv.lock" not in {edit.path for edit in review.edits}
    assert b"example" not in review.edits[0].after
    before = snapshot(tmp_path)
    executor = SystemExecutor(desired, UserConfig(), review=review)

    def fail(_command, *, timeout):
        Path("pyproject.toml").write_text("changed by resolver")
        Path("uv.lock").write_text("changed lock")
        raise CommandExecutionError(["uv", "add"], 1)

    mocker.patch.object(executor.process_runner, "run", side_effect=fail)
    with pytest.raises(CommandExecutionError):
        executor.execute()
    assert snapshot(tmp_path) == before


def test_dependency_convergence_advances_state_without_resolver(
    tmp_path, monkeypatch, mocker
):
    from protostar.sync_state import DependencyState, SyncState, serialize_state

    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text(
        '[project]\nname = "test"\ndependencies = ["example>=2"]\n'
    )
    state = SyncState(
        "test",
        dependencies=(
            DependencyState(
                "pyproject.toml",
                DependencyGroup.MAIN,
                "example",
                "",
                "example>=1",
                "example>=1",
            ),
        ),
    )
    Path(".protostar.lock.toml").write_text(serialize_state(state))
    desired = EnvironmentManifest()
    desired.dependencies.add("example>=2")
    review = prepare_review(desired, UserConfig())
    assert not review.edits
    assert not review.resolver.pending
    assert review.state_changed
    apply(desired, review, mocker)
    assert (
        deserialize_state(Path(".protostar.lock.toml").read_text())
        .dependencies[0]
        .declared
        == "example>=2"
    )


def test_recipe_opt_out_filters_producer_before_shared_target_build(
    tmp_path, monkeypatch, mocker
):
    from protostar.models import InitRequest
    from protostar.modules import BootstrapModule
    from protostar.orchestrator import Orchestrator

    monkeypatch.chdir(tmp_path)
    recipe = dataclasses.replace(
        establish_recipe(UserConfig(), RecipeIntent()),
        tools=((Tool.RUFF, False), (Tool.MYPY, True)),
    )

    class Ruff(BootstrapModule):
        config_key = "ruff"

        @property
        def name(self):
            return "Ruff"

        def pre_flight(self):
            raise AssertionError("opted-out producer preflight")

        def build(self, manifest):
            raise AssertionError("opted-out producer build")

    class Mypy(Ruff):
        config_key = "mypy"

        def pre_flight(self):
            pass

        def build(self, manifest):
            manifest.filesystem.add_structured(
                "pyproject.toml", "[tool.mypy]\nstrict = true\n", producer="mypy"
            )
            manifest.dependencies.add_dev("shared")

    manifest = Orchestrator(
        [Ruff(), Mypy()], UserConfig(), InitRequest(recipe=recipe)
    ).plan()
    assert manifest.dependencies.dev_dependencies == ["shared"]
    assert {item.tool for item in manifest.producer_contributions} == {Tool.MYPY}
    review = prepare_review(manifest, UserConfig())
    assert b"strict = true" in review.edits[0].after
    assert "ruff" not in tomllib.loads(review.edits[0].after.decode())["tool"]


def test_prepared_resolver_uses_only_accepted_requests_and_materialized_bounds(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    initialize(intent(), mocker)
    desired = intent(100)
    desired.dependencies.add_dev("example")
    review = prepare_review(desired, UserConfig())
    executor = SystemExecutor(desired, UserConfig(), review=review)

    def resolve(command, *, timeout):
        assert command == ["uv", "add", "--dev", "example"]
        assert {"pyproject.toml", "uv.lock"} <= executor.journal.touched_paths
        doc = tomlkit.parse(Path("pyproject.toml").read_text())
        doc["dependency-groups"] = {"dev": ["example>=3"]}
        Path("pyproject.toml").write_text(tomlkit.dumps(doc))
        Path("uv.lock").write_text("resolved")

    process = mocker.patch.object(executor.process_runner, "run", side_effect=resolve)
    executor.execute()
    process.assert_called_once()
    assert b"line-length = 100" in Path("pyproject.toml").read_bytes()
    state = deserialize_state(Path(".protostar.lock.toml").read_text())
    assert state.dependencies[0].declared == "example"
    assert state.dependencies[0].materialized == "example>=3"
    assert not prepare_review(desired, UserConfig()).pending


def test_keyed_hook_conflict_retains_local_entry_and_adds_safe_sibling(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)

    def hooks(entry, extra=False):
        manifest = EnvironmentManifest()
        manifest.tooling.hook_runner = HookRunner.PRE_COMMIT
        manifest.tooling.add_pre_commit_local_hook(
            f"      - id: owned\n        entry: {entry}\n        language: system"
        )
        if extra:
            manifest.tooling.add_pre_commit_local_hook(
                "      - id: sibling\n        entry: safe\n        language: system"
            )
        return manifest

    pins = tuple(
        ResolvedHookRevision(hook, "v1.0.0", PinProvenance.REGISTRY)
        for hook in RemoteHook
    )
    mocker.patch("protostar.executor.resolve_hook_revisions", return_value=pins)
    initialize(hooks("v1"), mocker)
    target = Path(".pre-commit-config.yaml")
    target.write_text(target.read_text().replace("entry: v1", "entry: local # intent"))
    desired = hooks("v2", extra=True)
    review = prepare_review(desired, UserConfig(), hook_revisions=pins)
    assert len(review.conflicts) == 1
    assert review.to_dict()["conflicts"][0]["reason"] == "diverged"
    assert b"entry: local # intent" in review.edits[0].after
    assert b"id: sibling" in review.edits[0].after
    apply(desired, review, mocker)
    assert target.read_bytes() == review.edits[0].after


def test_independent_region_update_beside_conflict(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    first = EnvironmentManifest()
    first.filesystem.add_region(".envrc", "v1", identity="conflicting")
    first.filesystem.add_region(".envrc", "safe-v1", identity="safe")
    initialize(first, mocker)
    target = Path(".envrc")
    target.write_bytes(target.read_bytes().replace(b"\nv1\n", b"\nlocal\n"))
    desired = EnvironmentManifest()
    desired.filesystem.add_region(".envrc", "v2", identity="conflicting")
    desired.filesystem.add_region(".envrc", "safe-v2", identity="safe")
    review = prepare_review(desired, UserConfig())
    assert review.conflicts[0].location.identity == "conflicting"
    assert b"\nlocal\n" in review.edits[0].after
    assert b"\nsafe-v2\n" in review.edits[0].after
    apply(desired, review, mocker)
    assert target.read_bytes() == review.edits[0].after


def test_deleted_ancestor_preserves_new_intent_and_accepts_other_target(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    initialize(intent(), mocker)
    target = Path("pyproject.toml")
    target.write_text("# user removed tool ancestor\n")
    desired = intent(100)
    desired.filesystem.add_region(".envrc", "safe", identity="safe")
    review = prepare_review(desired, UserConfig())
    assert review.conflicts
    assert {edit.path for edit in review.edits} == {".envrc"}
    apply(desired, review, mocker)
    assert target.read_text() == "# user removed tool ancestor\n"


def test_changed_desired_manifest_rejects_prepared_review(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.chdir(tmp_path)
    desired = intent()
    review = prepare_review(desired, UserConfig())
    desired.filesystem.add_file_injection("new.py", "unexpected")
    executor = SystemExecutor(desired, UserConfig(), review=review)
    before = snapshot(tmp_path)
    with pytest.raises(StaleReviewError):
        executor.execute()
    assert not executor.journal.touched_paths
    assert snapshot(tmp_path) == before
