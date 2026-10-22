"""Conservative change routing and the required CI gate's actual shell program."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from scripts.ci_scope import Scope, select_scope

ROOT = Path(__file__).resolve().parent.parent
CI = YAML(typ="safe").load((ROOT / ".github/workflows/ci.yml").read_text())


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["README.md", "docs/usage/init.md"], Scope.DOCS),
        (["docs/assets/example.png", "docs/assets/demo.cast"], Scope.DOCS),
        (["metrics/index.html", "metrics/charts.mjs"], Scope.DASHBOARD),
        (["tests/metrics_dashboard.test.mjs"], Scope.DASHBOARD),
        (["metrics/style.css", "docs/developer/ci.md"], Scope.FULL),
        (["README.md", "src/protostar/cli/main.py"], Scope.FULL),
        (["src/protostar/templates/lib.toml"], Scope.FULL),
        (["docs/javascripts/casts.js"], Scope.FULL),
        (["docs/stylesheets/extra.css"], Scope.FULL),
        (["docs/house/GUIDELINES.txt"], Scope.FULL),
        (["docs/house/README.md"], Scope.FULL),
        (["docs/generated/commands.md"], Scope.FULL),
        (["overrides/main.html"], Scope.FULL),
        (["zensical.toml"], Scope.FULL),
        (["uv.lock"], Scope.FULL),
        (["pyproject.toml"], Scope.FULL),
        ([".github/workflows/ci.yml"], Scope.FULL),
        (["scripts/ci_scope.py"], Scope.FULL),
        (["scripts/prepare_pages.py"], Scope.FULL),
        (["scripts/benchmarks/report.py"], Scope.FULL),
        (["metrics/unknown.py"], Scope.FULL),
        (["AGENTS.md"], Scope.FULL),
        (["unknown.md"], Scope.FULL),
        ([], Scope.FULL),
    ],
)
def test_only_one_known_change_category_reduces_checks(paths, expected):
    assert select_scope(paths) is expected


def run_selector(tmp_path, monkeypatch, event, base="", head=""):
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("EVENT", event)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", head)
    from scripts.ci_scope import main

    main()
    return output.read_text()


@pytest.mark.parametrize("event", ["push", "workflow_dispatch"])
def test_non_pr_events_always_run_everything(tmp_path, monkeypatch, event):
    monkeypatch.chdir(tmp_path)
    assert run_selector(tmp_path, monkeypatch, event) == "scope=full\n"


def test_git_failure_cannot_publish_a_reduced_scope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(subprocess.CalledProcessError):
        run_selector(tmp_path, monkeypatch, "pull_request", "bad", "missing")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("rename", [False, True])
def test_diff_uses_the_merge_base_and_both_sides_of_a_rename(
    tmp_path, monkeypatch, rename
):
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.check_output(["git", *args], text=True).strip()

    git("init", "-b", "main")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    git("config", "commit.gpgsign", "false")
    (tmp_path / "code.py").write_text("original\n")
    git("add", ".")
    git("commit", "-m", "initial")
    git("branch", "pr")
    (tmp_path / "unrelated.py").write_text("base branch advanced\n")
    git("add", ".")
    git("commit", "-m", "advance base")
    base = git("rev-parse", "HEAD")
    git("switch", "pr")
    if rename:
        git("mv", "code.py", "README.md")
    else:
        (tmp_path / "README.md").write_text("docs\n")
    git("add", ".")
    git("commit", "-m", "PR change")
    head = git("rev-parse", "HEAD")
    expected = "full" if rename else "docs"
    assert run_selector(tmp_path, monkeypatch, "pull_request", base, head) == (
        f"scope={expected}\n"
    )


def test_nul_separated_names_cannot_hide_a_code_change(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess, "check_output", lambda _: b"docs/page.md\0unknown\nREADME.md\0"
    )
    assert run_selector(tmp_path, monkeypatch, "pull_request") == "scope=full\n"


@pytest.mark.skipif(sys.platform == "win32", reason="CI gate runs in bash")
@pytest.mark.parametrize("scope", ["docs", "dashboard", "full", "", "unknown"])
@pytest.mark.parametrize(
    "broken", [None, "select", "checks", "platforms", "images-and-dashboard"]
)
@pytest.mark.parametrize("outcome", ["failure", "cancelled", "skipped", "success"])
def test_gate_accepts_only_the_selected_jobs_with_the_expected_results(
    scope, broken, outcome
):
    bash = shutil.which("bash")
    if not bash or not shutil.which("jq"):
        pytest.skip("The CI gate needs bash and jq")
    results: dict[str, dict[str, object]] = {
        "select": {"result": "success", "outputs": {"scope": scope}},
        "checks": {"result": "success"},
        "platforms": {"result": "success" if scope == "full" else "skipped"},
        "images-and-dashboard": {
            "result": "success" if scope in {"full", "dashboard"} else "skipped"
        },
    }
    expected = scope in {"docs", "dashboard", "full"}
    if broken:
        expected = expected and results[broken]["result"] == outcome
        results[broken]["result"] = outcome
    step = CI["jobs"]["ci-passed"]["steps"][0]
    run = subprocess.run(
        [bash, "-e", "-o", "pipefail", "-c", step["run"]],
        env={**os.environ, "RESULTS": json.dumps(results)},
        capture_output=True,
        text=True,
    )
    assert (run.returncode == 0) is expected, run.stdout + run.stderr


def test_the_workflow_wires_selection_and_does_not_filter_out_required_checks():
    jobs = CI["jobs"]
    assert CI["on"]["pull_request"] is None
    assert jobs["select"]["steps"][0]["with"]["fetch-depth"] == 0
    assert jobs["select"]["steps"][1]["run"] == "python3 -m scripts.ci_scope"
    for name in ("checks", "platforms", "images-and-dashboard"):
        assert jobs[name]["needs"] == "select"
    assert jobs["platforms"]["if"] == "needs.select.outputs.scope == 'full'"
    assert jobs["images-and-dashboard"]["if"] == (
        "needs.select.outputs.scope == 'full' || needs.select.outputs.scope == 'dashboard'"
    )
    for step in jobs["images-and-dashboard"]["steps"]:
        if step.get("name") in {None, "Test metrics dashboard data handling"}:
            continue
        # Steps following a successful install cannot execute on the
        # dashboard path, where installation is skipped.
        assert "needs.select.outputs.scope == 'full'" in step.get(
            "if", ""
        ) or "steps.protostar.outcome == 'success'" in step.get("if", "")
