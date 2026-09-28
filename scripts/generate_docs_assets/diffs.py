"""Unified diff generator comparing scenario snapshots for documentation."""

from __future__ import annotations

import subprocess

from scripts.generate_docs_assets.common import (
    SNAPSHOTS_DIR,
    _write_generated_doc,
)


def generate_diff_fixtures() -> None:
    """Generates unified diffs between base and merged scenario snapshots for documentation."""
    diff_targets = [
        ("ml", "ml_merged", "pyproject.toml"),
        ("ml", "ml_merged", ".gitignore"),
    ]

    for base, merged, filename in diff_targets:
        base_path = SNAPSHOTS_DIR / base / filename
        merged_path = SNAPSHOTS_DIR / merged / filename

        if base_path.exists() and merged_path.exists():
            result = subprocess.run(
                ["diff", "-u", str(base_path), str(merged_path)],
                capture_output=True,
                text=True,
            )
            diff_lines = result.stdout.splitlines()
            if len(diff_lines) >= 2:
                diff_lines[0] = f"--- a/{filename}"
                diff_lines[1] = f"+++ b/{filename}"
                clean_diff = "\n".join(line.rstrip() for line in diff_lines)

                safe_name = filename.replace(".", "_")
                output_name = f"diff_{base}_{merged}_{safe_name}.diff"
                _write_generated_doc(output_name, clean_diff)
