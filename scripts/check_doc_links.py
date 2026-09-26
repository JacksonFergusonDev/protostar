"""Validates Protostar's documentation links.

Every DocsPage path must resolve to a real file and anchor, following the
documentation URL routing convention:
    usage/init/  ->  docs/usage/init.md
    getting-started/  ->  docs/getting-started.md

Every tooling module's ``ToolInfo.docs_url`` must answer without an HTTP
error, so a dead link to a tool's documentation fails the pre-push hook.

Run:
    uv run python scripts/check_doc_links.py
"""

import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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


_USER_AGENT = "protostar-check-doc-links"
_TIMEOUT_SECONDS = 20


def check_url(url: str) -> str | None:
    """Returns why the URL is dead, or ``None`` when it answers.

    Some sites refuse ``HEAD``, so a refused ``HEAD`` is retried as ``GET``.
    """
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(
            url, method=method, headers={"User-Agent": _USER_AGENT}
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS):
                return None
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in {403, 405}:
                continue
            return f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError) as exc:
            return str(getattr(exc, "reason", exc))
    return None


def check_tool_urls() -> list[tuple[str, str, str]]:
    """Returns each tooling module's dead documentation link and why."""
    from protostar.modules import TOOLING_MODULES

    urls = {module.name: module.info.docs_url for module in TOOLING_MODULES}
    with ThreadPoolExecutor(max_workers=8) as pool:
        reasons = dict(zip(urls, pool.map(check_url, urls.values()), strict=True))
    for name, url in urls.items():
        if reasons[name] is None:
            print(f"  \u2713  {name:35s}  {url}")
    return [
        (name, urls[name], reason)
        for name, reason in reasons.items()
        if reason is not None
    ]


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

    print("\nValidating tool documentation links...\n")
    dead = check_tool_urls()

    if dead:
        print(f"\n{'─' * 80}")
        print(f"DEAD TOOL DOCUMENTATION LINKS ({len(dead)}):\n")
        for name, url, reason in dead:
            print(f"  \u2717  {name:35s}  {url}  [{reason}]")
        print("\nUpdate the module's ToolInfo.docs_url.")

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
    if broken or dead:
        sys.exit(1)

    print(f"\nAll {len(valid)} documentation reference(s) are valid.")
    sys.exit(0)


if __name__ == "__main__":
    main()
