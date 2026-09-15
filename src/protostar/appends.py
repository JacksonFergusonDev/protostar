"""Generic marker-block file append engine."""

import re
from collections.abc import Callable
from pathlib import Path

from .errors import ConfigurationError
from .intent import AppendContribution, validate_region_id

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
    payloads: list[AppendContribution],
    filepath: Path,
    overwrite: bool = False,
    on_conflict: Callable[[str], None] | None = None,
) -> str | None:
    """Applies named regions conservatively until checksum state lands in PR F.

    Existing regions are preserved in merge mode. Explicit overwrite replaces
    only the declared region and retains surrounding bytes. Legacy or malformed
    markers fail rather than guessing ownership.
    """
    c_start, c_end = get_comment_markers(filepath)

    def marker(identity: str, end: bool = False) -> str:
        return f"{c_start} --- {'End ' if end else ''}Protostar Region: {identity} --- {c_end}".strip()

    if "Protostar Injection" in original_content:
        raise ConfigurationError(
            "Legacy anonymous append markers are unsupported.",
            hint="Remove the legacy block before applying a named region; automatic adoption is unavailable.",
        )
    active: str | None = None
    seen: set[str] = set()
    for line in original_content.splitlines():
        match = re.fullmatch(
            r".*--- (End )?Protostar Region: ([A-Za-z0-9_][A-Za-z0-9_.:/-]*) ---.*",
            line,
        )
        if not match:
            if "Protostar Region:" in line:
                raise ConfigurationError(
                    "Malformed append boundary.",
                    hint="Repair the named region markers.",
                )
            continue
        ending, identity = match.groups()
        if (
            line != marker(identity, bool(ending))
            or (ending and active != identity)
            or (not ending and (active is not None or identity in seen))
        ):
            raise ConfigurationError(
                "Duplicate, nested, or mismatched append boundaries.",
                hint="Give each region one unique matching begin/end pair.",
            )
        if ending:
            active = None
        else:
            active = identity
            seen.add(identity)
    if active:
        raise ConfigurationError(
            "Unclosed append region.", hint="Restore the matching end marker."
        )
    identities = [c.id for c in payloads]
    if len(set(identities)) != len(identities):
        raise ConfigurationError(
            "Duplicate desired region identities.", hint="Use unique stable IDs."
        )
    for identity in identities:
        validate_region_id(identity)
    result = original_content
    for contribution in payloads:
        begin, end = marker(contribution.id), marker(contribution.id, True)
        framed = f"{begin}\n{contribution.content}"
        if not framed.endswith("\n"):
            framed += "\n"
        framed += end
        if contribution.id in seen:
            start = result.index(begin)
            stop = result.index(end, start) + len(end)
            if not overwrite:
                if result[start:stop] != framed and on_conflict:
                    on_conflict(contribution.id)
                continue
            result = result[:start] + framed + result[stop:]
        else:
            separator = (
                "" if not result else ("\n" if result.endswith("\n") else "\n\n")
            )
            result += separator + framed + "\n"
            seen.add(contribution.id)
    return result if result != original_content else None
