"""The smoke script recognizes hook output without an early-exit pipe race."""

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
