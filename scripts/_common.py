"""Shared constants, environment setup, and subprocess utilities for repository scripts."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
