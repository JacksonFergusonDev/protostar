"""Shared script output is readable in terminals and dependency-free in CI."""

import io
import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from rich.console import Console
from rich.text import Text

from scripts._common import (
    SCRIPTS_DIR,
    CodeLanguage,
    OutputStyle,
    fetch_bytes,
    fixture_environment,
    report,
    report_code,
)


@pytest.mark.parametrize("explicit_config", [False, True])
def test_fixture_environment_drops_caller_state_and_selects_configuration(
    explicit_config: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from protostar.config import ConfigOrigin, active_config_source
    from protostar.system import GIT_REPOSITORY_VARIABLES

    for name in GIT_REPOSITORY_VARIABLES | {"VIRTUAL_ENV", "PYTHONHOME"}:
        monkeypatch.setenv(name, "caller-state")
    monkeypatch.setenv("PROTOSTAR_CONFIG", str(tmp_path / "host.toml"))
    monkeypatch.setenv("PATH", "fixture-tools")
    config = tmp_path / "fixture.toml" if explicit_config else None

    env = fixture_environment(config=config)

    assert not (GIT_REPOSITORY_VARIABLES | {"VIRTUAL_ENV", "PYTHONHOME"}) & env.keys()
    assert env["PATH"] == "fixture-tools"
    assert os.environ["GIT_DIR"] == "caller-state"
    assert os.environ["PROTOSTAR_CONFIG"] == str(tmp_path / "host.toml")
    monkeypatch.setenv("PROTOSTAR_CONFIG", env["PROTOSTAR_CONFIG"])
    source = active_config_source()
    assert source.origin is (
        ConfigOrigin.EXPLICIT if explicit_config else ConfigOrigin.DISABLED
    )
    assert source.path == config


@pytest.mark.parametrize("terminal", [False, True])
def test_output_is_literal_and_safe_on_strict_cp1252(
    terminal: bool, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    buffer = io.BytesIO()
    with io.TextIOWrapper(buffer, encoding="cp1252", errors="strict") as stream:
        monkeypatch.setattr(sys, "stdout", stream)
        mocker.patch.object(stream, "isatty", return_value=terminal)
        console = mocker.patch(
            "rich.console.Console",
            return_value=Console(
                file=stream,
                force_terminal=True,
                color_system="standard",
                no_color=False,
                highlight=False,
                markup=False,
            ),
        )

        report("Fetching [test]...", style=OutputStyle.DETAIL)
        report("Review required", style=OutputStyle.WARNING)
        report("  git diff HEAD", style=OutputStyle.COMMAND)
        report("A path containing \u2603", style=OutputStyle.DETAIL)
        stream.flush()
        output = buffer.getvalue().decode("cp1252")

    assert "[test]" in output
    assert "A path containing ?" in output
    if terminal:
        assert "\x1b[2mFetching [test]..." in output
        assert "\x1b[1;33mReview required" in output
        assert "\x1b[1;36m  git diff HEAD" in output
    else:
        console.assert_not_called()
        assert "\x1b" not in output


@pytest.mark.parametrize("language", [CodeLanguage.DIFF, CodeLanguage.JSON])
def test_code_output_highlights_without_losing_long_lines(
    language: CodeLanguage, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    mocker.patch(
        "rich.console.Console",
        return_value=Console(
            file=stream,
            force_terminal=True,
            color_system="standard",
            no_color=False,
            width=20,
        ),
    )
    long_line = "x" * 200
    source = (
        f"--- a/file\n+++ b/file\n@@ -1 +1 @@\n-before\n+{long_line}"
        if language == CodeLanguage.DIFF
        else json.dumps({"key": long_line})
    )

    report_code(source, language)

    output = stream.getvalue()
    assert "\x1b[" in output
    assert source in Text.from_ansi(output).plain


def test_ci_code_output_stays_plain_even_when_color_is_forced(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("FORCE_COLOR", "1")
    console = mocker.patch("rich.console.Console")
    source = '{"key": "value"}'

    report_code(source, CodeLanguage.JSON, stderr=True)

    console.assert_not_called()
    assert capsys.readouterr().err == source + "\n"


def test_fetch_is_bounded_and_closes_the_response(mocker: MockerFixture) -> None:
    response = mocker.MagicMock()
    response.__enter__.return_value.read.return_value = b"payload"
    open_url = mocker.patch(
        "scripts._common.urllib.request.urlopen", return_value=response
    )

    assert fetch_bytes("https://example.invalid/source", timeout=5) == b"payload"

    open_url.assert_called_once_with("https://example.invalid/source", timeout=5)
    response.__enter__.return_value.read.assert_called_once_with(10 * 1024 * 1024)
    response.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "error", [urllib.error.URLError("offline"), TimeoutError("slow")]
)
def test_fetch_failure_reports_to_stderr_and_exits(
    error: Exception, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch("scripts._common.urllib.request.urlopen", side_effect=error)

    with pytest.raises(SystemExit) as failure:
        fetch_bytes("https://example.invalid/source")

    assert failure.value.code == 1
    output = capsys.readouterr()
    assert not output.out
    assert "Failed to fetch https://example.invalid/source" in output.err


_CI_PROBE = """
import json, runpy, subprocess, sys

script, mode = sys.argv[1:]
namespace = runpy.run_path(script)
main = namespace['main']
state = main.__globals__
sys.argv = [script, mode] if mode else [script]
if script.endswith('sync_registry_fallbacks.py'):
    state['fetch_bytes'] = lambda *args, **kwargs: json.dumps({
        'schema_version': 1, 'hooks': state['DEFAULT_REVISIONS']
    }).encode()
elif script.endswith('sync_secret_rules.py') and mode == '--check':
    state['fetch_bytes'] = lambda *args, **kwargs: b'source'
    state['generate'] = lambda tag, source, license, current: current
elif script.endswith('prepare_release.py'):
    state['run_repo_cmd'] = lambda *args, **kwargs: subprocess.CompletedProcess(
        [], 0, stdout='', stderr=''
    )
    # This probe checks the stdlib-only output path; workflow and build behavior
    # is exercised in test_prepare_release.py with GitHub and command fixtures.
    state['check_checkout'] = lambda: ('example/project', 'a' * 40)
    state['check_workflows'] = lambda repo, sha: None
    state['check_local_builds'] = lambda: None
try:
    main()
except SystemExit as error:
    assert error.code == 0, error.code
assert 'rich' not in sys.modules
assert 'textual' not in sys.modules
"""


@pytest.mark.integration
@pytest.mark.parametrize(
    ("script", "mode"),
    [
        ("sync_registry_fallbacks.py", "--check"),
        ("sync_secret_rules.py", "--check"),
        ("sync_secret_rules.py", "--dump"),
        ("prepare_release.py", ""),
    ],
)
def test_release_scripts_run_in_ci_without_site_packages(
    script: str, mode: str, tmp_path: Path
) -> None:
    result = subprocess.run(
        [sys.executable, "-S", "-c", _CI_PROBE, str(SCRIPTS_DIR / script), mode],
        cwd=tmp_path,
        env={
            **{key: value for key, value in os.environ.items() if key != "NO_COLOR"},
            "HOME": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "XDG_CONFIG_HOME": str(tmp_path),
            "CI": "true",
            "FORCE_COLOR": "1",
        },
        capture_output=True,
        text=True,
        check=True,
    )

    assert not result.stderr
    assert "\x1b" not in result.stdout
    if mode == "--dump":
        assert isinstance(json.loads(result.stdout), dict)
    else:
        assert "match" in result.stdout or "current and committed" in result.stdout
