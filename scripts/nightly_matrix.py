"""The rollback jobs Nightly runs, optionally narrowed to one OS and template.

Every template runs on every OS; Windows, where each run is slowest, splits
each template into slices so no job runs for hours. A manual run can narrow
the matrix to reproduce one failure without starting every job.

Usage: ``python -m scripts.nightly_matrix [--os OS] [--template TEMPLATE]``
prints the matrix as JSON for ``strategy.matrix``.
"""

import argparse
import json
from typing import Any

OPERATING_SYSTEMS = ("ubuntu-latest", "macos-latest", "windows-latest")
# Every built-in template. This module runs under a bare interpreter, so it
# can't ask Protostar; tests/test_nightly.py checks the list against what ships,
# and the benchmarks and rollback harness read it from here.
TEMPLATES = ("api", "astro", "cli", "lib", "ml")
WINDOWS_SLICES = 6


def rollback_matrix(os: str = "all", template: str = "all") -> dict[str, Any]:
    """Returns the rollback jobs, each with its OS, template, slice, and artifact.

    The artifact names the job's fault report, so the publisher can tell which
    jobs reported.

    Args:
        os: One operating system, or ``all``.
        template: One built-in template, or ``all``.

    Returns:
        A ``strategy.matrix`` holding one ``include`` entry per job.
    """
    jobs = [
        {
            "os": system,
            "template": name,
            "slice": f"{part}/{slices}",
            "artifact": f"rollback-{system}-{name}-{part}of{slices}",
        }
        for system in OPERATING_SYSTEMS
        if os in ("all", system)
        for name in TEMPLATES
        if template in ("all", name)
        for slices in [WINDOWS_SLICES if system == "windows-latest" else 1]
        for part in range(1, slices + 1)
    ]
    return {"include": jobs}


def main() -> None:
    """Prints the matrix for the given filters."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--os", default="all", choices=("all", *OPERATING_SYSTEMS))
    parser.add_argument("--template", default="all", choices=("all", *TEMPLATES))
    args = parser.parse_args()
    print(json.dumps(rollback_matrix(args.os, args.template)))


if __name__ == "__main__":
    main()
