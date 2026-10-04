"""Only complete mutation runs become public history and badge data."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.mutation_report import (
    changed_since_last_run,
    load_module_results,
    record_run,
)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def run_data(tmp_path):
    config = tmp_path / "pyproject.toml"
    config.write_text(
        '[tool.mutmut]\nsource_paths = ["src/protostar/merge.py", '
        '"src/protostar/documents/pyproject_layout.py"]\n',
        encoding="utf-8",
    )
    rows = {
        "merge-head": [{"module": "merge", "killed": 2, "survived": 1}],
        "merge-tail": [{"module": "merge", "killed": 5, "timeout": 1}],
        "documents.pyproject_layout": [
            {
                "module": "documents.pyproject_layout",
                "killed": 1,
                "suspicious": 1,
                "no_tests": 3,
            }
        ],
    }
    for artifact, values in rows.items():
        write_json(tmp_path / "results" / artifact / "summary.json", values)
    return argparse.Namespace(
        config=config,
        results=tmp_path / "results",
        matrix=json.dumps({"include": [{"artifact": name} for name in rows]}),
        history=tmp_path / "pages/benchmarks/mutation-history.json",
        latest=tmp_path / "pages/benchmarks/mutation-latest.json",
        commit="a" * 40,
        date="2026-10-03T02:23:00+00:00",
    )


def test_history_preserves_raw_counts_and_badge_uses_weighted_score(run_data):
    record_run(run_data)
    entries = json.loads(run_data.history.read_text())
    assert entries == [
        {
            "commit": "a" * 40,
            "date": run_data.date,
            "modules": [
                {
                    "module": "documents.pyproject_layout",
                    "killed": 1,
                    "timeout": 0,
                    "survived": 0,
                    "suspicious": 1,
                    "no_tests": 3,
                },
                {
                    "module": "merge",
                    "killed": 7,
                    "timeout": 1,
                    "survived": 1,
                    "suspicious": 0,
                    "no_tests": 0,
                },
            ],
        }
    ]
    assert json.loads(run_data.latest.read_text()) == {
        "schemaVersion": 1,
        "label": "engine mutation score",
        "message": "81.8%",
        "color": "22d3ee",
        "labelColor": "0A0A0A",
    }
    original = run_data.history.read_bytes(), run_data.latest.read_bytes()
    run_data.date = "2026-10-04T02:23:00+00:00"
    record_run(run_data)
    assert (run_data.history.read_bytes(), run_data.latest.read_bytes()) == original
    run_data.commit = "b" * 40
    record_run(run_data)
    assert len(json.loads(run_data.history.read_text())) == 2


@pytest.mark.parametrize(
    "missing", ["directory", "summary", "empty", "module", "extra"]
)
def test_partial_or_unexpected_results_never_write_public_files(run_data, missing):
    path = run_data.results / "merge-tail/summary.json"
    if missing == "directory":
        path.unlink()
        path.parent.rmdir()
    elif missing == "summary":
        path.unlink()
    elif missing == "empty":
        write_json(path, [])
    elif missing == "module":
        write_json(
            run_data.results / "documents.pyproject_layout/summary.json",
            [{"module": "wrong", "killed": 2}],
        )
    else:
        write_json(run_data.results / "unexpected/summary.json", [])
    with pytest.raises(SystemExit):
        record_run(run_data)
    assert not run_data.history.exists()
    assert not run_data.latest.exists()


def test_an_older_run_cannot_replace_newer_public_counts(run_data):
    record_run(run_data)
    original = run_data.history.read_bytes(), run_data.latest.read_bytes()
    run_data.commit = "b" * 40
    run_data.date = "2026-10-02T02:23:00+00:00"
    with pytest.raises(SystemExit, match="older"):
        record_run(run_data)
    assert (run_data.history.read_bytes(), run_data.latest.read_bytes()) == original


def test_nested_module_identity_and_unselected_shard_mutants(tmp_path):
    write_json(
        tmp_path / "src/protostar/documents/layout.py.meta",
        {
            "exit_code_by_key": {
                "killed": 1,
                "timeout": 36,
                "survived": 0,
                "no_tests": 5,
                "suspicious": 7,
                "unselected": None,
                "skipped": 34,
            }
        },
    )
    results, survivors = load_module_results(tmp_path)
    assert results[0].module == "documents.layout"
    assert results[0].caught == 2
    assert results[0].decided == 4
    assert results[0].no_tests == 1
    assert survivors == {"documents.layout": ["survived"]}


@pytest.mark.integration
@pytest.mark.parametrize(
    "changed",
    [
        "README.md",
        "src/protostar/merge.py",
        "tests/new_test.py",
        "pyproject.toml",
        "uv.lock",
        "scripts/mutation_report.py",
        ".github/workflows/mutation.yml",
        "src/protostar/unselected.py",
    ],
)
def test_gate_compares_real_git_inputs_with_last_recorded_commit(
    tmp_path, monkeypatch, changed
):
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.mutmut]\nsource_paths = ["src/protostar/merge.py"]\n')
    git("add", ".")
    git("commit", "-m", "Initial")
    base = git("rev-parse", "HEAD")
    history = tmp_path / "history.json"
    assert changed_since_last_run(history, config)
    write_json(history, [{"commit": base}])
    assert not changed_since_last_run(history, config)
    path = tmp_path / changed
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write("\n# Change\n")
    git("add", changed)
    git("commit", "-m", "Change")
    assert changed_since_last_run(history, config) == (
        changed not in {"README.md", "src/protostar/unselected.py"}
    )
    write_json(history, [{"commit": "f" * 40}])
    assert changed_since_last_run(history, config)


@pytest.mark.integration
@pytest.mark.skipif(sys.platform == "win32", reason="Workflow runs in Ubuntu Bash")
@pytest.mark.parametrize("history_conflict", [False, True])
def test_publication_retries_concurrent_pages_push_without_losing_data(
    tmp_path, monkeypatch, history_conflict
):
    """Execute the workflow's publisher against a local remote that races its push."""
    import os
    import shutil

    from ruamel.yaml import YAML

    repo = Path(__file__).resolve().parent.parent
    workflow = YAML(typ="safe").load(
        (repo / ".github/workflows/mutation.yml").read_text()
    )
    script = next(
        step["run"]
        for step in workflow["jobs"]["publish"]["steps"]
        if step.get("name") == "Append history and latest score"
    )
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True
        )

    git("init", "--bare", "remote.git")
    git("clone", "remote.git", "rival")
    git("-C", "rival", "config", "user.email", "test@example.invalid")
    git("-C", "rival", "config", "user.name", "Test")
    git("-C", "rival", "checkout", "-b", "gh-pages")
    (tmp_path / "rival/benchmarks").mkdir()
    (tmp_path / "rival/benchmarks/data.js").write_text("original benchmarks")
    git("-C", "rival", "add", ".")
    git("-C", "rival", "commit", "-m", "Initial")
    git("-C", "rival", "push", "origin", "gh-pages")
    git("clone", "--branch", "gh-pages", "remote.git", "pages-data")
    (tmp_path / "scripts").mkdir()
    shutil.copyfile(
        repo / "scripts/mutation_report.py", tmp_path / "scripts/mutation_report.py"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mutmut]\nsource_paths = ["src/protostar/merge.py"]\n'
    )
    write_json(
        tmp_path / "results/mutation-merge/summary.json",
        [{"module": "merge", "killed": 5}],
    )
    hook = tmp_path / "pages-data/.git/hooks/pre-push"
    # The first push races a benchmark update (and optionally another history point).
    # Git itself rejects the stale push; the workflow must fetch/rebase and retry.
    hook.write_text(
        '#!/bin/sh\nset -eu\nrm "$0"\n'
        f'cd "{tmp_path.as_posix()}/rival"\n'
        "echo updated > benchmarks/data.js\n"
        + (
            "cat > benchmarks/mutation-history.json <<'EOF'\n"
            + json.dumps(
                [
                    {
                        "commit": "b" * 40,
                        "date": "2020-01-01T00:00:00+00:00",
                        "modules": [],
                    }
                ]
            )
            + "\nEOF\n"
            if history_conflict
            else ""
        )
        + "git add benchmarks\ngit commit -m Concurrent\ngit push origin gh-pages\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", script],
        env={
            **os.environ,
            "MATRIX": json.dumps({"include": [{"artifact": "merge"}]}),
            "COMMIT": "a" * 40,
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    history = json.loads(
        git(
            "--git-dir",
            "remote.git",
            "show",
            "gh-pages:benchmarks/mutation-history.json",
        ).stdout
    )
    assert [entry["commit"] for entry in history] == (
        ["b" * 40, "a" * 40] if history_conflict else ["a" * 40]
    )
    assert (
        git("--git-dir", "remote.git", "show", "gh-pages:benchmarks/data.js").stdout
        == "updated\n"
    )
    badge = json.loads(
        git(
            "--git-dir",
            "remote.git",
            "show",
            "gh-pages:benchmarks/mutation-latest.json",
        ).stdout
    )
    assert badge["message"] == "100.0%"
