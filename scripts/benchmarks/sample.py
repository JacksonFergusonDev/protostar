"""Times one run of a command, in the interpreter of the version under test.

    python scripts/benchmarks/sample.py ARGV_JSON OUTPUT CHECKOUT

``scripts/benchmarks/__main__.py`` starts it with the Python of the version it
measures, in the project the command runs in. Only the probes come from
``CHECKOUT``, the checkout doing the measuring; Protostar comes from the
interpreter's own environment, so a comparison times each version's code. It
writes the command's exit code, this process's CPU time, and the time the main
thread spent waiting on managed commands to ``OUTPUT`` as JSON. The caller
measures the whole process's duration around it.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import time
from pathlib import Path


def main() -> None:
    """Runs the command named on the command line and writes what it took."""
    argv = json.loads(sys.argv[1])
    output = Path(sys.argv[2])
    # This file's directory would make its neighbours importable as top-level
    # modules; the checkout's root makes them importable as ``scripts``.
    sys.path[0] = sys.argv[3]
    from scripts.benchmarks.probes import time_commands

    code = 0
    with time_commands() as clock, contextlib.redirect_stdout(io.StringIO()):
        sys.argv = ["protostar", *argv]
        from protostar.cli import main as protostar

        try:
            protostar()
        except SystemExit as exit_:
            # A message instead of a number exits 1, as the interpreter does.
            code = (
                exit_.code
                if isinstance(exit_.code, int)
                else int(exit_.code is not None)
            )
    output.write_text(
        json.dumps(
            {"exit": code, "cpu": time.process_time(), "commands": clock.seconds}
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
