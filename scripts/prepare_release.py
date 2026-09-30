"""Refresh generated release inputs and stop until their changes are committed."""

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import SCRIPTS_DIR, OutputStyle, report, run_repo_cmd

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
        report("Review required", style=OutputStyle.WARNING)
        report("Version bump stopped: release inputs have uncommitted changes.")
        report()
        report(status.stdout.rstrip(), style=OutputStyle.WARNING)
        report()
        report("Review the changes:")
        report(
            f"  git diff HEAD -- {' '.join(RELEASE_INPUTS)}",
            style=OutputStyle.COMMAND,
        )
        report()
        report("If everything checks out, commit the changes and rerun:")
        report("  just bump <part>", style=OutputStyle.COMMAND)
        report()
        sys.exit(1)
    report("Release inputs are current and committed.", style=OutputStyle.SUCCESS)
    report()


if __name__ == "__main__":
    main()
