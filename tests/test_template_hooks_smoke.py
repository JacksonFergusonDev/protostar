"""The smoke script recognizes hook output without an early-exit pipe race."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform == "win32", reason="Exercises a POSIX shell script")
@pytest.mark.parametrize("hooks_ran", [False, True])
def test_large_commit_output_only_passes_when_hooks_ran(
    tmp_path: Path, hooks_ran: bool
):
    bash = shutil.which("bash")
    assert bash is not None
    tools = tmp_path / "tools"
    tools.mkdir()
    protostar = tools / "protostar"
    protostar.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "hooks = Path('.git/hooks')\n"
        "hooks.mkdir(parents=True)\n"
        "(hooks / 'pre-commit').write_text('installed')\n",
        encoding="utf-8",
    )
    git = tools / "git"
    git.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "if sys.argv[1] == 'commit':\n"
        "    if os.environ['HOOKS_RAN'] == '1':\n"
        "        print('ruff check................................Passed')\n"
        "    print(' create mode 100644 scaffold-file.txt\\n' * 100000)\n",
        encoding="utf-8",
    )
    for program in (protostar, git):
        program.chmod(0o755)
    script = (
        Path(__file__).resolve().parent.parent
        / ".github/scripts/template-hooks-smoke.sh"
    )
    result = subprocess.run(
        [bash, str(script), "cli", "3.14"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
            "RUNNER_TEMP": str(tmp_path),
            "HOOKS_RAN": str(int(hooks_ran)),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == (0 if hooks_ran else 1)
    assert "Broken pipe" not in result.stderr
    assert ("Prek hook execution not detected" in result.stdout) is not hooks_ran


@pytest.mark.integration
@pytest.mark.skipif(sys.platform == "win32", reason="Exercises a POSIX shell script")
def test_a_package_init_built_from_source_is_recorded_without_failing(
    tmp_path: Path,
):
    bash = shutil.which("bash")
    assert bash is not None
    tools = tmp_path / "tools"
    tools.mkdir()
    protostar = tools / "protostar"
    protostar.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "Path('.git/hooks').mkdir(parents=True)\n"
        "Path('.git/hooks/pre-commit').write_text('installed')\n"
        "Path('uv.lock').write_text(\n"
        '    \'[[package]]\\nname = "slow"\\nversion = "1.0"\\n\'\n'
        "    'source = { registry = \"https://pypi.org/simple\" }\\n'\n"
        "    'sdist = { url = \"https://files.example/slow-1.0.tar.gz\" }\\n'\n"
        ")\n"
        "venv = Path('.venv')\n"
        "venv.mkdir()\n"
        "(venv / 'pyvenv.cfg').write_text('version_info = 3.14.0\\n')\n"
        "wheel = venv / 'lib/python3.14/site-packages/slow-1.0.dist-info/WHEEL'\n"
        "wheel.parent.mkdir(parents=True)\n"
        "wheel.write_text('Tag: py3-none-any\\n')\n",
        encoding="utf-8",
    )
    git = tools / "git"
    git.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "if sys.argv[1] == 'commit':\n"
        "    print('ruff check................................Passed')\n",
        encoding="utf-8",
    )
    for program in (protostar, git):
        program.chmod(0o755)
    script = (
        Path(__file__).resolve().parent.parent
        / ".github/scripts/template-hooks-smoke.sh"
    )
    record = tmp_path / "builds.jsonl"
    result = subprocess.run(
        [bash, str(script), "ml", "3.14"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
            "RUNNER_TEMP": str(tmp_path),
            "SOURCE_BUILDS": str(record),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    [line] = record.read_text().splitlines()
    assert json.loads(line)["packages"] == ["slow==1.0"]
