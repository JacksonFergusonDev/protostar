"""Refresh release inputs, review their diff, and commit accepted changes."""

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import (
    SCRIPTS_DIR,
    CodeLanguage,
    OutputStyle,
    report,
    report_code,
    run_repo_cmd,
)

RELEASE_INPUTS = (
    "src/protostar/_fallbacks.py",
    "src/protostar/_secret_rules.py",
)


def main() -> None:
    """Regenerate both inputs before checking for changes awaiting review."""
    report()
    report("Preparing release", style=OutputStyle.TITLE)
    report()
    for script in ("sync_registry_fallbacks.py", "sync_secret_rules.py"):
        # Separate processes let the rules generator import the refreshed pins.
        result = run_repo_cmd([sys.executable, str(SCRIPTS_DIR / script)])
        report()
        if result.returncode:
            report(
                "Version bump stopped: preparation failed.",
                style=OutputStyle.ERROR,
                stderr=True,
            )
            sys.exit(result.returncode)

    status = run_repo_cmd(
        ["git", "status", "--porcelain", "--", *RELEASE_INPUTS],
        capture_output=True,
    )
    if status.returncode:
        report(status.stderr.rstrip(), style=OutputStyle.ERROR, stderr=True)
        sys.exit(status.returncode)
    if status.stdout.strip():
        report("Review release inputs", style=OutputStyle.WARNING)
        diff = run_repo_cmd(
            [
                "git",
                "diff",
                "--no-ext-diff",
                "--no-color",
                "HEAD",
                "--",
                *RELEASE_INPUTS,
            ],
            capture_output=True,
        )
        if diff.returncode:
            report(diff.stderr.rstrip(), style=OutputStyle.ERROR, stderr=True)
            sys.exit(diff.returncode)
        if not diff.stdout.strip():
            report(
                "Version bump stopped: Git reports changes but no reviewable diff.",
                style=OutputStyle.ERROR,
                stderr=True,
            )
            sys.exit(1)
        report_code(diff.stdout.rstrip(), CodeLanguage.DIFF)
        report()
        if not sys.stdin.isatty():
            report(
                "Version bump stopped: release inputs need an interactive review.",
                style=OutputStyle.ERROR,
                stderr=True,
            )
            sys.exit(1)
        try:
            while True:
                report(
                    "Accept these changes, commit and push them, then continue? [y/N] ",
                    end="",
                )
                answer = input().strip().lower()
                if answer in {"", "n", "no"}:
                    report("Version bump stopped: release inputs were not accepted.")
                    sys.exit(1)
                if answer in {"y", "yes"}:
                    break
                report("Please answer y or n.")
        except (EOFError, KeyboardInterrupt):
            report()
            report("Version bump stopped: release input review was cancelled.")
            sys.exit(1)

        for command in (
            ["git", "add", "--", *RELEASE_INPUTS],
            [
                "git",
                "commit",
                "--only",
                "-m",
                "chore(release): refresh generated release inputs",
                "--",
                *RELEASE_INPUTS,
            ],
            ["git", "push"],
        ):
            result = run_repo_cmd(command)
            if result.returncode:
                report(
                    "Version bump stopped: release input commit or push failed.",
                    style=OutputStyle.ERROR,
                    stderr=True,
                )
                sys.exit(result.returncode)
        report(
            "Release inputs committed and pushed. Continuing release.",
            style=OutputStyle.SUCCESS,
        )
        report()
        return
    report("Release inputs are current and committed.", style=OutputStyle.SUCCESS)
    report()


if __name__ == "__main__":
    main()
