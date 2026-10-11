"""Documentation walkthroughs plan with built-in defaults."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from scripts import check_docs_drift
from scripts.check_docs_drift import WalkthroughRunError, _walkthrough_steps


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


def test_a_failed_walkthrough_run_names_its_error(mocker: MockerFixture) -> None:
    mocker.patch(
        "scripts.check_docs_drift.subprocess.run",
        return_value=subprocess.CompletedProcess(
            [], 1, stdout="", stderr="Error: no such template\n"
        ),
    )

    with pytest.raises(WalkthroughRunError, match="exited 1:\nError: no such template"):
        _walkthrough_steps()


def test_a_crashing_check_is_reported_and_the_rest_still_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ran = []

    def crashes() -> list[str]:
        """A check that raises."""
        raise KeyError("nav")

    def passes() -> list[str]:
        """A check that runs after it."""
        ran.append(True)
        return []

    monkeypatch.setattr(check_docs_drift, "CHECKS", (crashes, passes))

    assert check_docs_drift.main() == 1
    assert ran == [True]
    output = capsys.readouterr().out
    assert "FAIL  A check that raises." in output
    assert "KeyError: 'nav'" in output


FIRST_PROJECT = Path("docs/first-project.md")


def _brightness_blocks(text: str) -> tuple[str, str]:
    """Returns the page's ``brightness.py`` and the top it tells you to give it."""
    blocks = [
        b
        for b in re.findall(r"```python\n(.*?)```", text, re.DOTALL)
        if b.startswith('"""Compare the brightness')
    ]
    script = next(b for b in blocks if "print(" in b)
    top = next(b for b in blocks if "print(" not in b)
    return script, top


def _ruff(project: Path) -> list[tuple[str, int, int]]:
    """Runs Ruff in ``project`` and returns each finding's code and location."""
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--output-format", "json", "."],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    return [
        (f["code"], f["location"]["row"], f["location"]["column"])
        for f in json.loads(result.stdout)
    ]


@pytest.mark.integration
def test_the_lint_example_fails_the_way_the_walkthrough_shows(tmp_path: Path) -> None:
    """Ruff, with the astro template's settings, reports what first-project.md shows."""
    text = FIRST_PROJECT.read_text(encoding="utf-8")
    script, top = _brightness_blocks(text)
    shown = re.search(
        r"^(\w+) \[\*\].*\n --> src/brightness\.py:(\d+):(\d+)", text, re.M
    )
    assert shown is not None
    (tmp_path / "src").mkdir()
    snapshot = Path("tests/snapshots/astro/pyproject.toml").read_text(encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(snapshot, encoding="utf-8")
    brightness = tmp_path / "src" / "brightness.py"

    rest = script.split("import numpy as np\n", 1)[1]
    brightness.write_text(top + rest, encoding="utf-8")
    assert _ruff(tmp_path) == [
        (shown.group(1), int(shown.group(2)), int(shown.group(3)))
    ]

    brightness.write_text(script, encoding="utf-8")
    assert _ruff(tmp_path) == []
