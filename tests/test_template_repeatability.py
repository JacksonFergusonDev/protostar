"""Tests validating multi-stage template idempotency and state convergence.

Verifies that re-running Protostar against an existing workspace in MERGE mode
converges without spurious mutations, preserving byte-exact file contents and
reconciliation lock state across consecutive runs.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import tomlkit
from pytest_mock import MockerFixture

from protostar.cli.main import handle_init
from protostar.config import UserConfig
from protostar.models import ExecutionResult
from protostar.orchestrator import Orchestrator
from protostar.sync_state import FilePolicy, deserialize_state
from protostar.system import ProcessRunner

BUILTIN_TEMPLATES = ("cli", "astro", "ml", "api", "lib")


@pytest.fixture(autouse=True)
def setup_repeatability_test_environment(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """Enforces offline operation, forbids network calls, and mocks executables."""
    # 1. Enforce offline registry mode
    monkeypatch.setenv("PROTOSTAR_OFFLINE_HOOK_REGISTRY", "1")

    # 2. Assert zero external network calls occur
    def forbid_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "Unexpected network access attempt during unit test via urllib.request.urlopen"
        )

    mocker.patch("urllib.request.urlopen", side_effect=forbid_network)

    # 3. Mock executable availability so tests do not depend on host installation
    real_which = shutil.which

    def mock_which(cmd: str, *args: Any, **kwargs: Any) -> str | None:
        if cmd in ("git", "uv", "direnv"):
            return f"/usr/local/bin/{cmd}"
        return real_which(cmd, *args, **kwargs)

    mocker.patch("shutil.which", side_effect=mock_which)


def _mock_process_runner(cmd: list[str], *args: Any, **kwargs: Any) -> None:
    """Mock process runner simulating uv and git side effects deterministically.

    Args:
        cmd: Command line argument list.
        *args: Variable positional arguments.
        **kwargs: Variable keyword arguments.
    """
    if len(cmd) >= 2 and cmd[0] == "uv" and cmd[1] == "init":
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            pkg_name = re.sub(r"[-_.]+", "-", Path.cwd().name).lower()
            pyproject_path.write_text(
                f'[project]\nname = "{pkg_name}"\nversion = "0.1.0"\n'
                'description = "Add your description here."\nreadme = "README.md"\n'
                'requires-python = ">=3.13"\ndependencies = []\n',
                encoding="utf-8",
            )
        Path(".python-version").write_text("3.13\n", encoding="utf-8")
    elif len(cmd) >= 2 and cmd[0] == "uv" and cmd[1] == "add":
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            doc = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))

            if "--dev" in cmd:
                packages = [arg for arg in cmd[2:] if not arg.startswith("-")]
                if "dependency-groups" not in doc:
                    doc["dependency-groups"] = tomlkit.table()
                dep_groups = doc["dependency-groups"]
                if not isinstance(dep_groups, dict):
                    dep_groups = tomlkit.table()
                    doc["dependency-groups"] = dep_groups
                if "dev" not in dep_groups:
                    dep_groups["dev"] = tomlkit.array()
                dev_list = dep_groups["dev"]
                for pkg in packages:
                    dev_list.append(f"{pkg}>=1.0.0")
            elif "--group" in cmd:
                idx = cmd.index("--group")
                group = cmd[idx + 1]
                packages = [
                    arg for arg in cmd[2:] if not arg.startswith("-") and arg != group
                ]
                if "dependency-groups" not in doc:
                    doc["dependency-groups"] = tomlkit.table()
                dep_groups = doc["dependency-groups"]
                if not isinstance(dep_groups, dict):
                    dep_groups = tomlkit.table()
                    doc["dependency-groups"] = dep_groups
                if group not in dep_groups:
                    dep_groups[group] = tomlkit.array()
                grp_list = dep_groups[group]
                for pkg in packages:
                    grp_list.append(f"{pkg}>=1.0.0")
            else:
                packages = [arg for arg in cmd[2:] if not arg.startswith("-")]
                if "project" not in doc:
                    doc["project"] = tomlkit.table()
                project = doc["project"]
                if not isinstance(project, dict):
                    project = tomlkit.table()
                    doc["project"] = project
                if "dependencies" not in project:
                    project["dependencies"] = tomlkit.array()
                main_list = project["dependencies"]
                for pkg in packages:
                    main_list.append(f"{pkg}>=1.0.0")

            pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")
        Path("uv.lock").write_text("resolved-lock\n", encoding="utf-8")
    elif len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "init":
        Path(".git").mkdir(exist_ok=True)
    elif "install" in cmd and any(tool in cmd for tool in ("pre-commit", "prek")):
        hook_path = Path(".git/hooks/pre-commit")
        hook_path.parent.mkdir(parents=True, exist_ok=True)
        hook_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")


@pytest.mark.parametrize("template_alias", BUILTIN_TEMPLATES)
def test_template_initial_and_repeat_merge_convergence(
    template_alias: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Verifies that repeat initializations in MERGE mode produce zero spurious mutations.

    Executes a three-phase lifecycle:
    1. Initial init: Populates workspace and records baseline sync state.
    2. Identical re-run in MERGE mode: Asserts zero created paths, empty managed
       mutations, and byte-for-byte disk & state identity.
    3. Second identical re-run in MERGE mode: Asserts continuous convergence.

    Args:
        template_alias: Name of the built-in template to test.
        tmp_path: Isolated pytest temporary path fixture.
        monkeypatch: Pytest monkeypatch fixture.
        mocker: Pytest mock fixture.
    """
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())
    mocker.patch.object(ProcessRunner, "run", side_effect=_mock_process_runner)
    mocker.patch("protostar.cli.ui.is_json_mode", True)
    mocker.patch("protostar.cli.ui.emit_json")

    results: list[ExecutionResult] = []
    original_execute = Orchestrator.execute

    def spy_execute(self: Orchestrator, manifest: Any) -> ExecutionResult:
        result = original_execute(self, manifest)
        results.append(result)
        return result

    mocker.patch.object(Orchestrator, "execute", spy_execute)

    # Phase 1: Initial workspace ignition
    init_args = argparse.Namespace(
        template_name=template_alias,
        from_path=None,
        template_context={},
        python_version="3.13",
        docker=False,
        force_merge=False,
        force_replace=False,
        list_templates=False,
        dry_run=False,
        crash_test=False,
    )
    handle_init(init_args)

    assert len(results) == 1
    phase1_result = results[0]
    assert len(phase1_result.created_paths) > 0
    assert "pyproject.toml" in phase1_result.created_paths
    assert ".protostar.lock.toml" in phase1_result.created_paths

    disk_phase1 = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    state_phase1 = (tmp_path / ".protostar.lock.toml").read_bytes()
    state = deserialize_state(state_phase1.decode("utf-8"))

    from protostar.lifecycle import inspect_project

    process_spy = mocker.patch.object(
        ProcessRunner, "run", side_effect=AssertionError("inspection process")
    )
    for _ in range(2):
        review = inspect_project()
        assert not review.pending, review.to_dict()
        assert {
            p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
        } == disk_phase1
    process_spy.assert_not_called()
    mocker.patch.object(ProcessRunner, "run", side_effect=_mock_process_runner)

    # Whole-file ownership must describe the exact generated bytes, rather than
    # a later user-visible representation. Check this at the complete built-in
    # template matrix boundary, not just in isolated checksum-gate tests.
    checksum_records = [
        record for record in state.files if record.policy is FilePolicy.CHECKSUM
    ]
    assert checksum_records
    for record in checksum_records:
        generated_path = tmp_path / record.path
        assert generated_path.is_file()
        assert record.digest == hashlib.sha256(generated_path.read_bytes()).hexdigest()

    # Phase 2: Identical re-run in MERGE mode
    merge_args = argparse.Namespace(
        template_name=template_alias,
        from_path=None,
        template_context={},
        python_version="3.13",
        docker=False,
        force_merge=True,
        force_replace=False,
        list_templates=False,
        dry_run=False,
        crash_test=False,
    )
    handle_init(merge_args)

    assert len(results) == 2
    phase2_result = results[1]
    assert phase2_result.created_paths == frozenset()
    # Any touched path on repeat must be restricted to external subprocess hook registration
    assert phase2_result.touched_paths <= {".git/hooks/pre-commit"}

    disk_phase2 = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert disk_phase1 == disk_phase2
    assert (tmp_path / ".protostar.lock.toml").read_bytes() == state_phase1

    # Phase 3: Second identical re-run in MERGE mode (continuous convergence)
    handle_init(merge_args)

    assert len(results) == 3
    phase3_result = results[2]
    assert phase3_result.created_paths == frozenset()
    assert phase3_result.touched_paths <= {".git/hooks/pre-commit"}

    disk_phase3 = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert disk_phase1 == disk_phase3
    assert (tmp_path / ".protostar.lock.toml").read_bytes() == state_phase1


def test_template_merge_preserves_foreign_content_and_local_modifications(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Verifies that MERGE mode retains unowned foreign dependencies and local edits."""
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())
    mocker.patch.object(ProcessRunner, "run", side_effect=_mock_process_runner)
    mocker.patch("protostar.cli.ui.is_json_mode", True)
    mocker.patch("protostar.cli.ui.emit_json")

    init_args = argparse.Namespace(
        template_name="cli",
        from_path=None,
        template_context={},
        python_version="3.13",
        docker=False,
        force_merge=False,
        force_replace=False,
        list_templates=False,
        dry_run=False,
        crash_test=False,
    )
    handle_init(init_args)

    # Simulate user adding foreign dependency and custom file
    pyproject_path = tmp_path / "pyproject.toml"
    doc = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))
    project_table = doc["project"]
    assert isinstance(project_table, dict)
    deps = project_table["dependencies"]
    assert isinstance(deps, list)
    deps.append("foreign-package>=2.0.0")
    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    foreign_file = tmp_path / "data" / "user_dataset.csv"
    foreign_file.parent.mkdir(parents=True, exist_ok=True)
    foreign_file.write_text("id,val\n1,100\n", encoding="utf-8")

    # Re-run template in MERGE mode
    merge_args = argparse.Namespace(
        template_name="cli",
        from_path=None,
        template_context={},
        python_version="3.13",
        docker=False,
        force_merge=True,
        force_replace=False,
        list_templates=False,
        dry_run=False,
        crash_test=False,
    )
    handle_init(merge_args)

    # Verify foreign content is completely preserved in pyproject.toml
    updated_doc = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))
    updated_deps = updated_doc["project"]["dependencies"]
    assert any("foreign-package>=2.0.0" in d for d in updated_deps)
    assert foreign_file.exists()
    assert foreign_file.read_text(encoding="utf-8") == "id,val\n1,100\n"

    # Verify foreign dependency was not adopted into Protostar state tracking
    lock_doc = tomlkit.parse(
        (tmp_path / ".protostar.lock.toml").read_text(encoding="utf-8")
    )
    owned_deps = lock_doc.get("dependencies", [])
    assert isinstance(owned_deps, list)
    owned_dep_names = {r["name"] for r in owned_deps if isinstance(r, dict)}
    assert "foreign-package" not in owned_dep_names


def test_stage_one_enrollment_preserves_applied_ownership(
    tmp_path, monkeypatch, mocker
):
    """Explicit enrollment writes intent without adopting equal foreign keys."""
    from protostar.recipe import read_recipe

    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())
    mocker.patch.object(ProcessRunner, "run", side_effect=_mock_process_runner)
    mocker.patch("protostar.cli.ui.is_json_mode", True)
    mocker.patch("protostar.cli.ui.emit_json")
    args = argparse.Namespace(
        template_name="cli", docker=None, python_version="3.13", force_merge=True
    )
    handle_init(args)
    project = tmp_path / "pyproject.toml"
    doc = tomlkit.parse(project.read_text())
    del doc["tool"]["protostar"]
    doc["tool"]["foreign"] = {"local-key": "retain"}
    project.write_text(tomlkit.dumps(doc))
    before = (tmp_path / ".protostar.lock.toml").read_bytes()
    handle_init(args)
    assert read_recipe(project) is not None
    assert (
        tomlkit.parse(project.read_text())["tool"]["foreign"]["local-key"] == "retain"
    )
    assert (tmp_path / ".protostar.lock.toml").read_bytes() == before
    assert "protostar" not in str(deserialize_state(before.decode()).files)


@pytest.mark.parametrize("template_alias", BUILTIN_TEMPLATES)
def test_builtin_complete_lifecycle_has_no_repeat_mutations(
    template_alias, tmp_path, monkeypatch, mocker, capsys
):
    """Every shipped template supports inspection and three no-op applications."""
    import json
    import stat

    from protostar.cli import main, ui

    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.cli.main.UserConfig.load", return_value=UserConfig())
    mocker.patch.object(ProcessRunner, "run", side_effect=_mock_process_runner)
    mocker.patch(
        "protostar.cli.main.resolve_auto_metadata",
        return_value={
            "description": "Lifecycle acceptance",
            "author_name": "Test Author",
            "author_email": "test@example.invalid",
            "license": "MIT",
        },
    )
    mocker.patch("subprocess.run", side_effect=AssertionError("subprocess"))
    mocker.patch("subprocess.Popen", side_effect=AssertionError("subprocess"))
    monkeypatch.setattr(ui, "is_json_mode", True)
    handle_init(
        argparse.Namespace(
            template_name=template_alias, python_version="3.13", docker=None
        )
    )
    capsys.readouterr()
    before = {
        p.relative_to(tmp_path): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    process = mocker.patch.object(
        ProcessRunner, "run", side_effect=AssertionError("process")
    )
    mocker.patch("subprocess.run", side_effect=AssertionError("subprocess"))
    mocker.patch("subprocess.Popen", side_effect=AssertionError("subprocess"))
    mocker.patch("questionary.confirm", side_effect=AssertionError("prompt"))
    mocker.patch(
        "protostar.config.UserConfig.load", side_effect=AssertionError("defaults")
    )
    for _ in range(3):
        for command in (
            ["status"],
            ["diff"],
            ["sync", "--dry-run"],
            ["sync", "--check"],
            ["sync"],
        ):
            monkeypatch.setattr(ui, "is_json_mode", False)
            monkeypatch.setattr("sys.argv", ["protostar", *command, "--json"])
            main()
            payload = json.loads(capsys.readouterr().out)
            if command == ["sync"]:
                assert payload["status"] == "success"
                assert payload["result"]["touched_paths"] == []
            else:
                assert payload["status"] == "reviewed"
                assert not payload["pending"]
                if "--check" in command:
                    assert payload["check_passed"]
            assert {
                p.relative_to(tmp_path): (
                    p.read_bytes(),
                    stat.S_IMODE(p.stat().st_mode),
                )
                for p in tmp_path.rglob("*")
                if p.is_file()
            } == before
    process.assert_not_called()
