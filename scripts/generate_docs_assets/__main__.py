"""CLI entrypoint for standalone documentation asset generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import OutputStyle, report
from scripts.generate_docs_assets import (
    generate_diff_fixtures,
    generate_docs_assets,
)


def main() -> None:
    """CLI entrypoint for standalone documentation asset generation."""
    parser = argparse.ArgumentParser(
        description="Generate documentation presentation assets."
    )
    parser.add_argument(
        "--diffs",
        action="store_true",
        help="Generate diff fixtures between scenario snapshots.",
    )
    args = parser.parse_args()

    # Isolate in-process configuration
    import protostar.config

    protostar.config.select_config_source(None, disabled=True)

    generate_docs_assets()
    if args.diffs:
        generate_diff_fixtures()
    report("Documentation assets updated successfully!", style=OutputStyle.SUCCESS)


if __name__ == "__main__":
    main()
