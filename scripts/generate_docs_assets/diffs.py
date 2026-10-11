"""Unified diff generator comparing scenario snapshots for documentation."""

from __future__ import annotations

import difflib

from scripts.generate_docs_assets.common import (
    DOCS_GENERATED_DIR,
    SNAPSHOTS_DIR,
    _write_generated_doc,
)

# Each page diff: the base scenario, the scenario it changes into, and the file.
DIFF_TARGETS = (
    ("ml", "ml_merged", "pyproject.toml"),
    ("ml", "ml_merged", ".gitignore"),
)


def generate_diff_fixtures() -> None:
    """Generates unified diffs between base and merged scenario snapshots for documentation.

    A pair whose files no longer differ removes its fixture, so a page can't
    keep showing a change that is gone.
    """
    for base, merged, filename in DIFF_TARGETS:
        output_name = f"diff_{base}_{merged}_{filename.replace('.', '_')}.diff"
        before = (SNAPSHOTS_DIR / base / filename).read_text(encoding="utf-8")
        after = (SNAPSHOTS_DIR / merged / filename).read_text(encoding="utf-8")
        diff = list(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                f"a/{filename}",
                f"b/{filename}",
                lineterm="",
            )
        )
        if diff:
            _write_generated_doc(output_name, "\n".join(line.rstrip() for line in diff))
        else:
            (DOCS_GENERATED_DIR / output_name).unlink(missing_ok=True)
