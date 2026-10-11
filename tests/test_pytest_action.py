"""Exercise the retry action's shell with controlled pytest outcomes."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

ACTION = Path(__file__).resolve().parent.parent / ".github/actions/pytest/action.yml"


@pytest.mark.skipif(sys.platform == "win32", reason="The action runs in a bash shell")
@pytest.mark.parametrize(
    "remaining", [[], ["test::broken"], ["test::flaky", "test::broken"]]
)
def test_retry_reports_only_tests_that_passed_and_preserves_failure(
    tmp_path, remaining
):
    action = YAML(typ="safe").load(ACTION.read_text())
    step = action["runs"]["steps"][0]
    assert action["runs"]["steps"][1]["with"]["name"] == (
        "test-results-${{ inputs.artifact }}"
    )
    tools = tmp_path / "bin"
    tools.mkdir()
    uv = tools / "uv"
    uv.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "if args[:3] == ['run', '--no-sync', 'python']:\n"
        "    os.execv(sys.executable, [sys.executable, *args[3:]])\n"
        "assert args[:2] == ['run', 'pytest'], args\n"
        "assert args[args.index('-n') + 1] == '1', args\n"
        "retry = '--last-failed' in args\n"
        "tests = json.loads(os.environ['REMAINING']) if retry else ['test::flaky', 'test::broken']\n"
        "cache = Path('.pytest_cache/v/cache/lastfailed')\n"
        "cache.parent.mkdir(parents=True, exist_ok=True)\n"
        "cache.write_text(json.dumps(dict.fromkeys(tests, True)))\n"
        "sys.exit(1 if tests else 0)\n"
    )
    uv.chmod(0o755)
    summary = tmp_path / "summary"
    summary.touch()
    env = {
        **os.environ,
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "ARGS": "tests/test_rollback.py",
        "RETRY": "true",
        "WORKERS": "1",
        "FLAKY_LIST": "flaky-tests.txt",
        "GITHUB_STEP_SUMMARY": str(summary),
        "REMAINING": json.dumps(remaining),
    }
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(
        [bash, "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == (1 if remaining else 0), result.stderr
    expected = sorted({"test::flaky", "test::broken"} - set(remaining))
    assert (tmp_path / "flaky-tests.txt").read_text().splitlines() == expected
    for test in remaining:
        assert f"- `{test}`" not in summary.read_text()
    for test in expected:
        assert f"- `{test}`" in summary.read_text()
