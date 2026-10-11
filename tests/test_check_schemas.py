"""Schema validation checks configurations without managing dependencies."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from scripts import check_schemas


@pytest.mark.parametrize(
    "failed_program", [None, "prek", "actionlint", "check-jsonschema"]
)
def test_schema_validation_runs_every_validator_without_syncing_dependencies(
    tmp_path, monkeypatch, mocker, capsys, failed_program
):
    files = {
        "pyproject.toml": b'[project]\nname = "fixture"\n',
        "uv.lock": b"committed lock\n",
        ".pre-commit-config.yaml": b"repos: []\n",
        ".github/workflows/check.yml": b"name: Check\n",
        ".github/actions/example/action.yml": b"name: Example\n",
        ".github/renovate.json": b"{}\n",
        "src/protostar/templates/example.toml": b'name = "Example"\n',
    }
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    monkeypatch.setattr(check_schemas, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_schemas, "SRC_DIR", tmp_path / "src")
    monkeypatch.setattr(check_schemas, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr("scripts.check_schemas.tempfile.tempdir", str(tmp_path))
    commands = []

    def run(cmd, **kwargs):
        commands.append(cmd)
        # A dependency-management command must fail this test immediately.
        assert cmd[0] in {"prek", "actionlint", "check-jsonschema", "protostar"}
        return subprocess.CompletedProcess(
            cmd, int(cmd[0] == failed_program), stdout="{}", stderr=""
        )

    mocker.patch.object(check_schemas, "run_repo_cmd", side_effect=run)
    if failed_program:
        with pytest.raises(SystemExit) as failure:
            check_schemas.main()
        assert failure.value.code == 1
        assert "Schema validation failed" in capsys.readouterr().err
    else:
        check_schemas.main()
        assert "All schema checks passed" in capsys.readouterr().out
    assert {cmd[0] for cmd in commands} == {
        "prek",
        "actionlint",
        "check-jsonschema",
        "protostar",
    }
    metaschema = next(cmd for cmd in commands if "--check-metaschema" in cmd)
    assert sorted(Path(arg).name for arg in metaschema[2:]) == [
        "application_schema.json",
        "review_schema.json",
        "template_schema.json",
    ]
    assert {name: (tmp_path / name).read_bytes() for name in files} == files
    assert not list(tmp_path.glob("tmp*"))


def test_schema_callers_require_the_committed_lock():
    root = Path(__file__).resolve().parent.parent
    yaml = YAML(typ="safe")
    hooks = yaml.load((root / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hook = next(
        hook
        for repo in hooks["repos"]
        for hook in repo["hooks"]
        if hook["id"] == "check-schemas"
    )
    command = "uv run --locked python -m scripts.check_schemas"
    assert hook["entry"] == command
    workflow = yaml.load(
        (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["checks"]["steps"]
    assert (
        next(step for step in steps if step.get("name") == "Validate schemas")["run"]
        == command
    )
    assert (
        "--locked"
        in next(step for step in steps if step.get("name") == "Install dependencies")[
            "run"
        ]
    )
    justfile = (root / "justfile").read_text(encoding="utf-8")
    assert "sync:\n    uv sync --locked --quiet" in justfile
    assert "check-schemas: sync\n" in justfile
    assert f"    {command}\n" in justfile
