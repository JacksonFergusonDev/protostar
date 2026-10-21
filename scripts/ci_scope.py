"""Select conservative PR checks; every non-PR event runs the full suite."""

import os
import subprocess
from collections.abc import Iterable
from enum import StrEnum
from pathlib import PurePosixPath


class Scope(StrEnum):
    """The independent change categories eligible for reduced PR checks."""

    DOCS = "docs"
    DASHBOARD = "dashboard"
    FULL = "full"


def path_scope(path: str) -> Scope:
    """Classify only known prose, static assets, and dashboard source paths."""
    target = PurePosixPath(path)
    if path == "tests/metrics_dashboard.test.mjs" or (
        path.startswith("metrics/")
        and target.suffix in {".js", ".mjs", ".html", ".css"}
    ):
        return Scope.DASHBOARD
    if path in {"README.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md"}:
        return Scope.DOCS
    # Vendored files, generated references, and executable site assets are not
    # prose. Their contracts and behavior need the full suite.
    if path.startswith("docs/") and not path.startswith(
        ("docs/house/", "docs/generated/")
    ):
        if target.suffix == ".md" or (
            path.startswith("docs/assets/")
            and target.suffix
            in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".cast"}
        ):
            return Scope.DOCS
    return Scope.FULL


def select_scope(paths: Iterable[str]) -> Scope:
    """Reduce checks only for a nonempty diff in exactly one allowed category."""
    scopes = {path_scope(path) for path in paths}
    return scopes.pop() if len(scopes) == 1 else Scope.FULL


def main() -> None:
    """Write the selected scope to GitHub Actions' job output file."""
    scope = Scope.FULL
    if os.environ["EVENT"] == "pull_request":
        # Compare the PR head with its merge base, including on stacked PRs.
        # No rename detection: both an old and a new path must qualify. NUL
        # separators keep unusual filenames from disguising another path.
        changed = subprocess.check_output(
            [
                "git",
                "diff",
                "--name-only",
                "--no-renames",
                "-z",
                f"{os.environ['BASE_SHA']}...{os.environ['HEAD_SHA']}",
                "--",
            ]
        )
        scope = select_scope(os.fsdecode(path) for path in changed.split(b"\0") if path)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"scope={scope}\n")
    print(f"CI scope: {scope}")


if __name__ == "__main__":
    main()
