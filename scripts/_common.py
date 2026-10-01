"""Shared paths, output, downloads, and subprocess helpers for repository scripts."""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, TextIO

# Canonical repository root and directory anchors
REPO_ROOT: Path = Path(__file__).resolve().parent.parent
SRC_DIR: Path = REPO_ROOT / "src"
SCRIPTS_DIR: Path = REPO_ROOT / "scripts"
DOCS_DIR: Path = REPO_ROOT / "docs"
DOCS_GENERATED_DIR: Path = (DOCS_DIR / "generated").resolve()
DOCS_TERMINALS_DIR: Path = (DOCS_DIR / "assets" / "terminals").resolve()
SNAPSHOTS_DIR: Path = (REPO_ROOT / "tests" / "snapshots").resolve()
CONSTRAINTS_FILE: Path = SNAPSHOTS_DIR / "constraints.txt"
VENV_DIR: Path = REPO_ROOT / ".venv"
VENV_BIN: Path = VENV_DIR / ("Scripts" if sys.platform == "win32" else "bin")

# Ensure REPO_ROOT, SCRIPTS_DIR, and SRC_DIR are available on sys.path
for _path in (str(REPO_ROOT), str(SCRIPTS_DIR), str(SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)


class OutputStyle(StrEnum):
    """Shared emphasis for human-facing repository script output."""

    PLAIN = ""
    TITLE = "bold blue"
    DETAIL = "dim"
    SUCCESS = "bold green"
    WARNING = "bold yellow"
    ERROR = "bold red"
    COMMAND = "bold cyan"


class CodeLanguage(StrEnum):
    """Languages used by structured script output."""

    DIFF = "diff"
    JSON = "json"


def _styled_output(stream: TextIO) -> bool:
    """Keeps CI plain and honors explicit color choices for captured output."""
    if os.environ.get("CI") or "NO_COLOR" in os.environ:
        return False
    return stream.isatty() or os.environ.get("FORCE_COLOR", "") not in {"", "0"}


def report(
    message: str = "",
    *,
    style: OutputStyle = OutputStyle.PLAIN,
    stderr: bool = False,
    end: str = "\n",
) -> None:
    """Prints literal text, styled on terminals and plain when redirected.

    CI and ordinary redirected output need only the standard library. Set
    FORCE_COLOR=1 to keep terminal formatting through a local output capture.
    Text is never parsed as markup, and unsupported stream characters are
    replaced so redirected Windows output cannot fail on an encoding error.
    """
    stream = sys.stderr if stderr else sys.stdout
    encoding = stream.encoding or "utf-8"
    message = message.encode(encoding, errors="replace").decode(encoding)
    if not _styled_output(stream):
        print(message, file=stream, end=end, flush=True)
        return

    from rich.console import Console

    Console(file=stream, force_terminal=True, highlight=False, markup=False).print(
        message, style=style.value, end=end, soft_wrap=True
    )


def report_code(source: str, language: CodeLanguage, *, stderr: bool = False) -> None:
    """Highlights code on terminals; redirected CI output keeps its raw text."""
    stream = sys.stderr if stderr else sys.stdout
    if not _styled_output(stream):
        report(source, stderr=stderr)
        return

    from rich.console import Console
    from rich.syntax import Syntax

    encoding = stream.encoding or "utf-8"
    source = source.encode(encoding, errors="replace").decode(encoding)
    console = Console(file=stream, force_terminal=True, highlight=False, markup=False)
    console.print(
        Syntax(source, language.value, theme="ansi_dark", background_color="default"),
        soft_wrap=True,
    )


def fetch_bytes(url: str, *, timeout: float = 10) -> bytes:
    """Downloads at most 10 MiB, reporting a fetch failure before exiting."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return bytes(response.read(10 * 1024 * 1024))
    except (urllib.error.URLError, TimeoutError) as error:
        report(f"Failed to fetch {url}: {error}", style=OutputStyle.ERROR, stderr=True)
        sys.exit(1)


def get_repo_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Builds an environment dictionary ensuring virtualenv binaries are on PATH.

    Args:
        extra: Optional additional environment variables to set or override.

    Returns:
        Environment dictionary with VENV_BIN prepended to PATH if it exists.
    """
    env = os.environ.copy()
    if VENV_BIN.is_dir():
        current_path = env.get("PATH", "")
        if str(VENV_BIN) not in current_path.split(os.pathsep):
            env["PATH"] = (
                f"{VENV_BIN}{os.pathsep}{current_path}"
                if current_path
                else str(VENV_BIN)
            )
    if extra:
        env.update(extra)
    return env


def fixture_environment(*, config: Path | None = None) -> dict[str, str]:
    """Builds a fixture environment with only its explicitly chosen configuration.

    Drops the caller's Python environment and repository-local Git variables.
    Callers that need a disposable home directory set it separately.

    Args:
        config: The fixture's configuration file; None disables configuration.

    Returns:
        A fresh environment for commands operating on disposable projects.
    """
    from protostar.system import subprocess_environment

    env = subprocess_environment()
    env["PROTOSTAR_CONFIG"] = str(config) if config is not None else ""
    return env


def run_repo_cmd(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = False,
    capture_output: bool = False,
    text: bool = True,
    env: dict[str, str] | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Executes a command anchored at the repository root by default.

    Args:
        cmd: Command and arguments to execute.
        cwd: Execution directory. Defaults to REPO_ROOT.
        check: If True, raises CalledProcessError on non-zero exit.
        capture_output: If True, captures stdout and stderr.
        text: If True, decodes stdout/stderr as text.
        env: Optional environment overrides merged into get_repo_env().
        **kwargs: Additional arguments forwarded to subprocess.run.

    Returns:
        CompletedProcess instance representing the finished execution.
    """
    execution_dir = cwd if cwd is not None else REPO_ROOT
    execution_env = get_repo_env(env)
    return subprocess.run(
        cmd,
        cwd=execution_dir,
        check=check,
        capture_output=capture_output,
        text=text,
        env=execution_env,
        **kwargs,
    )
