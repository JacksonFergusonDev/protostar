"""Exercise the workflow's actual planner against configurable source paths."""

import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def planner(tmp_path, monkeypatch):
    workflow = YAML(typ="safe").load(
        (REPO_ROOT / ".github/workflows/mutation.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["plan"]["steps"]
    assert steps[0]["uses"].startswith("actions/checkout@")
    script = next(step["run"] for step in steps if step.get("id") == "matrix")
    code = compile(
        script.split("<<'EOF'\n", 1)[1].rsplit("EOF", 1)[0], "mutation.yml", "exec"
    )
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    def run(requested, source_paths):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mutmut]\nsource_paths = " + json.dumps(source_paths) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("REQUESTED", requested)
        exec(code, {})
        return json.loads(output.read_text(encoding="utf-8").removeprefix("matrix="))

    return run


def test_all_uses_configured_sources_including_nested_modules(planner):
    assert planner(
        "all",
        [
            "src/protostar/reconciliation.py",
            "src/protostar/documents/pyproject_layout.py",
        ],
    ) == {"module": ["reconciliation", "documents.pyproject_layout"]}


def test_subset_preserves_requested_order_and_accepts_spaces(planner):
    assert planner(
        " documents.pyproject_layout, journal ",
        ["src/protostar/journal.py", "src/protostar/documents/pyproject_layout.py"],
    ) == {"module": ["documents.pyproject_layout", "journal"]}


@pytest.mark.parametrize("requested", ["merge", "journal,merge", "", "journal,"])
def test_unknown_or_empty_module_fails_without_writing_matrix(
    planner, tmp_path, requested
):
    with pytest.raises(SystemExit, match=r"Unknown modules.*choose from.*journal"):
        planner(requested, ["src/protostar/journal.py"])
    assert not (tmp_path / "output").exists()
