"""Probes whether Windows executable lookup prefers files in the working directory.

Temporary: run by `.github/workflows/windows-exe-probe.yml` from an empty
directory. Plants `git.bat` and `prek.cmd` there, as a template could, and
reports what `shutil.which` and Protostar's `ProcessRunner` do with them.
Exits 1 when a planted file runs in place of the real executable.
"""

import os
import shutil
import sys
from pathlib import Path

from protostar.errors import ProtostarError
from protostar.system import ProcessRunner

MARKER = Path("hijacked.txt")
GUARD = "NoDefaultCurrentDirectoryInExePath"


def main() -> int:
    """Runs the probe and prints a report."""
    cwd = Path.cwd()
    print(f"Python {sys.version.split()[0]} on {sys.platform}; cwd={cwd}")
    print(f"{GUARD}={os.environ.get(GUARD)!r}")
    print(f"Real git before planting: {shutil.which('git')}")

    for name in ("git.bat", "prek.cmd"):
        Path(name).write_text(f'@echo {name}> "%~dp0{MARKER}"\r\n')

    print("\n-- Lookup with planted files --")
    for command in ("git", "prek"):
        print(f"shutil.which({command!r}) -> {shutil.which(command)}")

    print("\n-- ProcessRunner().run(['git', '--version']) --")
    try:
        ProcessRunner().run(["git", "--version"], timeout=30)
        print("Command succeeded.")
    except ProtostarError as error:
        print(f"Command failed: {type(error).__name__}: {error}")
    hijacked = MARKER.exists()
    if hijacked:
        print(f"HIJACKED: planted file ran; marker says {MARKER.read_text().strip()!r}")
        MARKER.unlink()
    else:
        print("Not hijacked: the real git ran.")

    print(f"\n-- Lookup with {GUARD}=1 (candidate fix) --")
    os.environ[GUARD] = "1"
    for command in ("git", "prek"):
        print(f"shutil.which({command!r}) -> {shutil.which(command)}")

    print("\nRESULT:", "VULNERABLE" if hijacked else "NOT VULNERABLE")
    return 1 if hijacked else 0


if __name__ == "__main__":
    sys.exit(main())
