"""Exercise the workflow's actual planner against configurable source paths."""

import ast
import fnmatch
import json
import tomllib
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from scripts.mutation_report import ModuleResult, combine_results

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

    def run(requested, source_paths, shards=None):
        config = "[tool.mutmut]\nsource_paths = " + json.dumps(source_paths) + "\n"
        for module, by_shard in (shards or {}).items():
            config += f'[tool.mutmut-shards."{module}"]\n'
            config += "".join(
                f"{shard} = {json.dumps(functions)}\n"
                for shard, functions in by_shard.items()
            )
        (tmp_path / "pyproject.toml").write_text(config, encoding="utf-8")
        monkeypatch.setenv("REQUESTED", requested)
        exec(code, {})
        text = output.read_text(encoding="utf-8").removeprefix("matrix=")
        return json.loads(text)

    return run


def names(matrix):
    return [entry["name"] for entry in matrix["include"]]


def test_all_uses_configured_sources_including_nested_modules(planner):
    assert planner(
        "all",
        [
            "src/protostar/reconciliation.py",
            "src/protostar/documents/pyproject_layout.py",
        ],
    ) == {
        "include": [
            {
                "name": "reconciliation",
                "artifact": "reconciliation",
                "patterns": "protostar.reconciliation.*",
            },
            {
                "name": "documents.pyproject_layout",
                "artifact": "documents.pyproject_layout",
                "patterns": "protostar.documents.pyproject_layout.*",
            },
        ]
    }


def test_subset_preserves_requested_order_and_accepts_spaces(planner):
    matrix = planner(
        " documents.pyproject_layout, journal ",
        ["src/protostar/journal.py", "src/protostar/documents/pyproject_layout.py"],
    )
    assert names(matrix) == ["documents.pyproject_layout", "journal"]


@pytest.mark.parametrize("requested", ["merge", "journal,merge", "", "journal,"])
def test_unknown_or_empty_module_fails_without_writing_matrix(
    planner, tmp_path, requested
):
    with pytest.raises(SystemExit, match=r"Unknown modules.*choose from.*journal"):
        planner(requested, ["src/protostar/journal.py"])
    assert not (tmp_path / "output").exists()


def test_a_sharded_module_gets_one_runner_per_shard(planner):
    matrix = planner(
        "all",
        ["src/protostar/journal.py", "src/protostar/merge.py"],
        shards={"merge": {"head": ["Joiner.add", "hold"], "tail": ["Joiner._seal"]}},
    )
    assert matrix["include"][1:] == [
        {
            "name": "merge (head)",
            "artifact": "merge-head",
            "patterns": (
                "protostar.merge.xǁJoinerǁadd__mutmut_* protostar.merge.x_hold__mutmut_*"
            ),
        },
        {
            "name": "merge (tail)",
            "artifact": "merge-tail",
            "patterns": "protostar.merge.xǁJoinerǁ_seal__mutmut_*",
        },
    ]
    assert names(matrix)[0] == "journal"


def test_a_subset_that_leaves_out_a_sharded_module_runs_no_shard_of_it(planner):
    matrix = planner(
        "journal",
        ["src/protostar/journal.py", "src/protostar/merge.py"],
        shards={"merge": {"only": ["hold"]}},
    )
    assert names(matrix) == ["journal"]


def test_shards_for_a_module_outside_source_paths_fail(planner, tmp_path):
    with pytest.raises(SystemExit, match=r"Shards for \['merge'\]"):
        planner("all", ["src/protostar/journal.py"], shards={"merge": {"a": ["f"]}})
    assert not (tmp_path / "output").exists()


def defined_functions(module):
    """Names every function mutmut mutates in a module, as the planner writes them."""
    path = REPO_ROOT / "src/protostar" / (module.replace(".", "/") + ".py")
    found = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            found.append(node.name)
        elif isinstance(node, ast.ClassDef):
            found += [
                f"{node.name}.{member.name}"
                for member in node.body
                if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef)
            ]
    return found


def mutant_name(module, function):
    cls, _, name = function.rpartition(".")
    body = f"xǁ{cls}ǁ{name}" if cls else f"x_{name}"
    return f"protostar.{module}.{body}__mutmut_1"


def test_the_configured_shards_cover_every_function_exactly_once(planner):
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    shards = config["tool"]["mutmut-shards"]
    assert shards, "delete this test along with the last shard"
    matrix = planner("all", config["tool"]["mutmut"]["source_paths"], shards)
    for module in shards:
        runs = [e["patterns"].split() for e in matrix["include"] if module in e["name"]]
        for function in defined_functions(module):
            name = mutant_name(module, function)
            hits = [
                i
                for i, patterns in enumerate(runs)
                if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
            ]
            assert len(hits) == 1, f"{function} runs in shards {hits}"
        for patterns in runs:
            for pattern in patterns:
                assert any(
                    fnmatch.fnmatchcase(mutant_name(module, function), pattern)
                    for function in defined_functions(module)
                ), f"{pattern} matches no function"


def test_combine_adds_the_shards_of_a_module(tmp_path):
    paths = []
    for index, row in enumerate(
        [
            {"module": "merge", "killed": 3, "survived": 1},
            {"module": "merge", "killed": 4, "timeout": 2, "no_tests": 1},
            {"module": "journal", "killed": 5},
        ]
    ):
        path = tmp_path / f"{index}.json"
        path.write_text(json.dumps([row]), encoding="utf-8")
        paths.append(path)
    assert combine_results(paths) == [
        ModuleResult(module="journal", killed=5),
        ModuleResult(module="merge", killed=7, timeout=2, survived=1, no_tests=1),
    ]
