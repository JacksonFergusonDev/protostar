"""Select commits whose workflow results qualify for a release.

CI must cover refreshed inputs. Nightly may precede one generated-input-only
refresh. A tagged release may additionally step over its version bump. Both
local preparation and the release workflow use these same bounded rules.
"""

import argparse
import json
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import OutputStyle, report, run_repo_cmd

RELEASE_INPUTS = (
    "src/protostar/_fallbacks.py",
    "src/protostar/_secret_rules.py",
)
VERSION_FILES = ("pyproject.toml", "uv.lock")


def _git(*arguments: str) -> str:
    result = run_repo_cmd(["git", *arguments], capture_output=True)
    if result.returncode:
        report(result.stderr.rstrip(), style=OutputStyle.ERROR, stderr=True)
        sys.exit(result.returncode)
    return result.stdout


def _parent_with_only_edits(sha: str, paths: tuple[str, ...]) -> str | None:
    """Cross one ordinary commit only when it modifies exclusively these files."""
    lineage = _git("rev-list", "--parents", "-n", "1", sha).split()
    if len(lineage) != 2:
        return None
    parent = lineage[1]
    fields = (
        _git("diff", "--name-status", "--no-renames", "-z", parent, sha, "--")
        .rstrip("\0")
        .split("\0")
    )
    if not fields or len(fields) % 2:
        return None
    edits = zip(fields[::2], fields[1::2], strict=True)
    if all(status == "M" and path in paths for status, path in edits):
        return parent
    return None


def workflow_commits(sha: str, *, tagged: bool = False) -> dict[str, list[str]]:
    """Return newest-first eligible SHAs, never skipping a substantive change."""
    ci = [sha]
    if tagged and (parent := _parent_with_only_edits(sha, VERSION_FILES)):
        ci.append(parent)
    nightly = ci.copy()
    if parent := _parent_with_only_edits(ci[-1], RELEASE_INPUTS):
        nightly.append(parent)
    return {"ci.yml": ci, "nightly.yml": nightly}


def main() -> None:
    """Print the eligible commits for the release workflow's gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sha")
    parser.add_argument("--tagged", action="store_true")
    args = parser.parse_args()
    print(json.dumps(workflow_commits(args.sha, tagged=args.tagged)))


if __name__ == "__main__":
    main()
