"""Shared constants and filesystem helpers for documentation asset generation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from protostar.fs import atomic_write_text
from scripts._common import (
    DOCS_GENERATED_DIR as DOCS_GENERATED_DIR,
)
from scripts._common import (
    DOCS_TERMINALS_DIR as DOCS_TERMINALS_DIR,
)
from scripts._common import (
    REPO_ROOT as REPO_ROOT,
)
from scripts._common import (
    SNAPSHOTS_DIR as SNAPSHOTS_DIR,
)


def _write_generated_doc(filepath: str | Path, content: str) -> None:
    """Writes raw unformatted content to a generated documentation file.

    Args:
        filepath: Target filename or Path relative to DOCS_GENERATED_DIR or absolute.
        content: Raw string data to write to disk.
    """
    import scripts.generate_docs_assets as pkg

    docs_dir = getattr(pkg, "DOCS_GENERATED_DIR", DOCS_GENERATED_DIR)
    output_path = docs_dir / filepath if isinstance(filepath, str) else filepath
    content = content.rstrip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, content)


def _format_markdown_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]]
) -> str:
    """Constructs a Markdown-formatted table from headers and row values."""
    header_row = f"| {' | '.join(headers)} |"
    separator_row = f"| {' | '.join([':---'] * len(headers))} |"
    table = [header_row, separator_row]
    for row in rows:
        table.append(f"| {' | '.join(row)} |")
    return "\n".join(table)


class ManifestEncoder(json.JSONEncoder):
    """Custom JSON serialization encoder for the EnvironmentManifest datastructure."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (set, frozenset)):
            return sorted(obj)
        if isinstance(obj, Path):
            return obj.as_posix()
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj) and not isinstance(obj, type):
            return {
                f.name: getattr(obj, f.name)
                for f in fields(obj)
                if f.name
                not in {"observe", "producer_contributions", "selections", "recipe"}
            }
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)
