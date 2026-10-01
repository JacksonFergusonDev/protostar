"""Disposable sandbox commands never target the caller's repository."""

import os
import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from scripts.prepare_sandbox import commit, existing_project, run


@pytest.mark.parametrize("explicit_config", [False, True])
def test_setup_commands_use_only_fixture_state(
    explicit_config: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "caller.git"))
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "caller-venv"))
    monkeypatch.setenv("PROTOSTAR_CONFIG", str(tmp_path / "caller.toml"))
    command = mocker.patch("scripts.prepare_sandbox.subprocess.run")
    config = tmp_path / "fixture.toml" if explicit_config else None

    run("protostar", "init", cwd=tmp_path, config=config)

    args, kwargs = command.call_args
    assert args == (("protostar", "init"),)
    assert kwargs["cwd"] == tmp_path
    assert kwargs["check"] is True
    assert "GIT_DIR" not in kwargs["env"]
    assert "VIRTUAL_ENV" not in kwargs["env"]
    assert kwargs["env"]["PROTOSTAR_CONFIG"] == (str(config) if config else "")


@pytest.mark.integration
def test_existing_project_leaves_an_inherited_git_repository_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_tool_env,
    mocker: MockerFixture,
) -> None:
    mocker.patch.dict(os.environ, real_tool_env(), clear=True)
    caller = tmp_path / "caller"
    workspace = tmp_path / "workspace"
    caller.mkdir()
    workspace.mkdir()
    subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=caller, check=True)
    subprocess.run(
        ["git", "config", "maintenance.auto", "false"], cwd=caller, check=True
    )
    (caller / "original.txt").write_text("original content\n", encoding="utf-8")
    commit(caller, "chore: original project")
    git_dir = caller / ".git"
    before = {
        path.relative_to(git_dir): path.read_bytes()
        for path in git_dir.rglob("*")
        if path.is_file()
    }
    monkeypatch.setenv("GIT_DIR", str(git_dir))

    existing_project(workspace)

    assert (workspace / ".git" / "refs" / "heads" / "main").is_file()
    assert before == {
        path.relative_to(git_dir): path.read_bytes()
        for path in git_dir.rglob("*")
        if path.is_file()
    }
