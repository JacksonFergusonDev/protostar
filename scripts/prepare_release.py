"""Refresh generated release inputs and stop until their changes are committed."""

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import SCRIPTS_DIR, run_repo_cmd

RELEASE_INPUTS = (
    "src/protostar/_fallbacks.py",
    "src/protostar/_secret_rules.py",
)


def main() -> None:
    """Regenerate both inputs before checking for changes awaiting review."""
    for script in ("sync_registry_fallbacks.py", "sync_secret_rules.py"):
        # Separate processes let the rules generator import the refreshed pins.
        result = run_repo_cmd([sys.executable, str(SCRIPTS_DIR / script)])
        if result.returncode:
            sys.exit(result.returncode)

    status = run_repo_cmd(
        ["git", "status", "--porcelain", "--", *RELEASE_INPUTS],
        capture_output=True,
    )
    if status.returncode:
        print(status.stderr, file=sys.stderr, end="")
        sys.exit(status.returncode)
    if status.stdout.strip():
        print("Release inputs have uncommitted changes. Version bump stopped.")
        print(status.stdout, end="")
        print("Review them with:")
        print(f"  git diff HEAD -- {' '.join(RELEASE_INPUTS)}")
        print(
            "If everything checks out, commit the changes and rerun `just bump <part>`."
        )
        sys.exit(1)
    print("Release inputs are current and committed.")


if __name__ == "__main__":
    main()
