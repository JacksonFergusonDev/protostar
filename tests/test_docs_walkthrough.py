"""Documentation walkthroughs plan with built-in defaults."""

import json
import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from scripts.check_docs_drift import _walkthrough_steps


def test_walkthrough_ignores_explicit_host_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("PROTOSTAR_CONFIG", str(tmp_path / "host.toml"))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "host.git"))
    monkeypatch.setattr("scripts.check_docs_drift.tempfile.tempdir", str(tmp_path))
    manifest: dict[str, dict[str, list[object]]] = {
        "dependencies": {
            "dependencies": [],
            "dev_dependencies": [],
            "docs_dependencies": [],
        },
        "tasks": {"system_tasks": [], "post_install_tasks": []},
    }
    command = mocker.patch(
        "scripts.check_docs_drift.subprocess.run",
        return_value=subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({"manifest": manifest})
        ),
    )

    assert _walkthrough_steps() == ["Writing project files"]

    env = command.call_args.kwargs["env"]
    assert env["PROTOSTAR_CONFIG"] == ""
    assert "GIT_DIR" not in env
    assert Path(env["HOME"]).is_relative_to(tmp_path)
