"""Validates that all documentation paths in DocsPage resolve to real files and anchors.

Applies MkDocs URL routing convention:
    /en/stable/usage/init/  ->  docs/usage/init.md
    /en/stable/getting-started/  ->  docs/getting-started.md

Run:
    uv run python scripts/check_doc_links.py
"""

import re
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import DOCS_DIR, REPO_ROOT


def slugify(text: str) -> str:
    """Generates a Markdown header slug matching Python-Markdown/MkDocs conventions."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def extract_anchors(file_path: Path) -> set[str]:
    """Extracts all header slugs and HTML anchor IDs from a markdown file."""
    if not file_path.is_file():
        return set()

    content = file_path.read_text(encoding="utf-8")
    anchors: set[str] = set()

    for match in re.finditer(r"^#{1,6}\s+(.+)$", content, re.MULTILINE):
        heading_text = match.group(1).strip()
        heading_clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", heading_text)
        heading_clean = re.sub(r"[`*_~]", "", heading_clean)
        anchors.add(slugify(heading_clean))

    for match in re.finditer(r"""(?:id|name)=["']([^"']+)["']""", content):
        anchors.add(match.group(1))

    return anchors


def docs_path_to_file(docs_path: str) -> tuple[Path, str | None]:
    """Converts a MkDocs-style URL path segment to its Markdown source file and anchor."""
    path_part, _, anchor = docs_path.partition("#")
    normalized = path_part.strip("/").removesuffix(".html")

    file_path = (
        (DOCS_DIR / "index.md") if not normalized else (DOCS_DIR / f"{normalized}.md")
    )
    return file_path, (anchor if anchor else None)


def main() -> None:
    from protostar.docs_registry import DocsPage

    print("Validating DocsPage enum paths...\n")

    broken: list[tuple[str, str, Path, str]] = []
    valid: list[tuple[str, str, Path]] = []

    for page in DocsPage:
        label = page.name
        docs_path = page.path

        resolved_file, anchor = docs_path_to_file(docs_path)
        if not resolved_file.exists():
            broken.append((label, docs_path, resolved_file, "FILE NOT FOUND"))
        elif anchor:
            anchors = extract_anchors(resolved_file)
            if anchor not in anchors:
                broken.append(
                    (label, docs_path, resolved_file, f"ANCHOR '#{anchor}' NOT FOUND")
                )
            else:
                valid.append((label, docs_path, resolved_file))
        else:
            valid.append((label, docs_path, resolved_file))

    for label, docs_path, resolved in valid:
        rel = resolved.relative_to(REPO_ROOT)
        print(f"  \u2713  {label:35s}  {docs_path!r:35s}  \u2192  {rel}")

    if broken:
        print(f"\n{'─' * 80}")
        print(f"BROKEN DOCUMENTATION REFERENCES ({len(broken)}):\n")
        for label, docs_path, resolved, reason in broken:
            rel = resolved.relative_to(REPO_ROOT)
            print(
                f"  \u2717  {label:35s}  {docs_path!r:35s}  \u2192  {rel}  [{reason}]"
            )
        print(
            f"\n{'─' * 80}\n"
            f"{len(broken)} broken reference(s) detected.\n"
            "Update the docs_path value in DocsPage, or create the missing file/anchor."
        )
        sys.exit(1)

    print(f"\nAll {len(valid)} documentation reference(s) are valid.")
    sys.exit(0)


if __name__ == "__main__":
    main()
