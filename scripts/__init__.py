"""Repository scripts, run from the repository root as ``python -m scripts.<name>``.

Importing the package makes this checkout's ``src/`` importable when nothing
else provides Protostar, as under the release workflow's bare interpreter. It
is appended, so an installed Protostar wins: a benchmark of another version
imports these scripts but must time that version's code.
"""

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent / "src")
if _SRC not in sys.path:
    sys.path.append(_SRC)
