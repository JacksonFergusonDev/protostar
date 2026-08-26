"""Generic marker-block file append engine."""

import hashlib
from pathlib import Path

__all__ = ["append_marker_blocks", "get_comment_markers"]


def get_comment_markers(filepath: Path) -> tuple[str, str]:
    """Returns the appropriate comment syntax (start, end) for a given file extension."""
    ext = filepath.suffix.lower()
    name = filepath.name.lower()

    # Files that use '#' comments
    if ext in (
        ".py",
        ".toml",
        ".yaml",
        ".yml",
        ".sh",
        ".bash",
        ".zsh",
        ".rb",
        ".pl",
        ".gitignore",
        ".dockerignore",
    ) or name in ("justfile", "makefile", "dockerfile"):
        return ("#", "")

    # Files that use '//' comments
    if ext in (
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".java",
        ".go",
        ".rs",
        ".cs",
        ".swift",
        ".kt",
        ".scala",
    ):
        return ("//", "")

    # HTML/XML/Markdown
    if ext in (".html", ".htm", ".xml", ".svg", ".md"):
        return ("<!--", "-->")

    # CSS
    if ext in (".css", ".scss", ".sass", ".less"):
        return ("/*", "*/")

    # SQL, Haskell, Lua
    if ext in (".sql", ".hs", ".lua"):
        return ("--", "")

    # Fallback to standard hash
    return ("#", "")


def append_marker_blocks(
    original_content: str,
    payloads: list[str],
    filepath: Path,
    overwrite: bool = False,
) -> str | None:
    """Appends configuration payloads wrapped in hash-delimited marker blocks.

    Args:
        original_content: Existing file contents.
        payloads: Raw string payloads to append.
        filepath: Target filepath used to determine comment syntax.
        overwrite: If True, appends payloads even if their boundary markers exist.

    Returns:
        The updated file content string, or None if all payloads are already present.
    """
    c_start, c_end = get_comment_markers(filepath)

    existing_clean = original_content.rstrip()
    missing_payloads = []

    for payload in payloads:
        # Generate a deterministic boundary marker based on the payload content
        payload_hash = hashlib.md5(
            payload.encode("utf-8"), usedforsecurity=False
        ).hexdigest()[:8]
        marker_begin = (
            f"{c_start} --- Protostar Injection: {payload_hash} --- {c_end}".strip()
        )
        marker_end = f"{c_start} --- End Protostar Injection --- {c_end}".strip()

        if marker_begin in original_content and not overwrite:
            continue

        framed_payload = f"{marker_begin}\n{payload.strip()}\n{marker_end}"
        missing_payloads.append(framed_payload)

    if not missing_payloads:
        return None

    combined_content = "\n\n".join(missing_payloads)
    prefix = "\n\n" if existing_clean and combined_content else ""
    return existing_clean + prefix + combined_content + "\n"
