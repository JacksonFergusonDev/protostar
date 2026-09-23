"""Generic marker-block file append engine."""

import re
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigurationError
from .intent import AppendContribution, validate_region_id
from .merge import LineSpan
from .text_merge import TextConflict, reconcile_text

__all__ = [
    "RegionConflict",
    "RegionResult",
    "append_marker_blocks",
    "get_comment_markers",
]


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


@dataclass(frozen=True)
class RegionConflict:
    """A region whose desired change was refused.

    Attributes:
        identity: The region's stable logical identity.
        lines: File lines where local and desired edits overlap, or ``None``
            when the whole region was refused (unowned, deleted, or unreadable).
    """

    identity: str
    lines: LineSpan | None = None


@dataclass(frozen=True)
class RegionResult:
    """Exact file content, composite applied region texts, and refused regions.

    Attributes:
        content: The file with every accepted region update applied.
        baselines: Each owned region's last applied framed text, by identity.
        conflicts: Refused regions, one entry per overlapping edit.
    """

    content: str
    baselines: dict[str, str]
    conflicts: tuple[RegionConflict, ...]


def append_marker_blocks(
    original_content: str,
    payloads: list[AppendContribution],
    filepath: Path,
    overwrite: bool = False,
    *,
    baselines: dict[str, str] | None = None,
    missing_owned_file: bool = False,
) -> RegionResult:
    """Merges each stable region three ways and preserves surrounding bytes.

    A region spans its begin marker through its end marker. Each merges against
    the framed text last applied to it, so local edits inside a region survive
    desired updates to other lines; overlapping edits keep that region whole.

    Args:
        original_content: The file's current text.
        payloads: Desired region contents, in append order.
        filepath: The file, which selects the comment syntax of the markers.
        overwrite: Whether desired regions replace local edits.
        baselines: Each owned region's last applied framed text, by identity.
        missing_owned_file: Whether the file is owned but was deleted, which
            protects newly introduced regions too.

    Returns:
        The reconciled content, applied region texts, and refused regions.
    """
    c_start, c_end = get_comment_markers(filepath)

    def marker(tag: str, end: bool = False) -> str:
        prefix = "endregion" if end else "region"
        suffix = f" {c_end}" if c_end else ""
        return f"{c_start} {prefix}: protostar {tag}{suffix}".strip()

    active: str | None = None
    seen: set[str] = set()
    for line in original_content.splitlines():
        match = re.fullmatch(
            r".*?\b(end)?region:\s*protostar\s+([0-9a-f]{8}).*",
            line,
        )
        if not match:
            if "region: protostar" in line or "endregion: protostar" in line:
                raise ConfigurationError(
                    "Malformed append boundary.",
                    hint="Repair the region markers.",
                )
            continue
        ending, tag = match.groups()
        if (
            line != marker(tag, bool(ending))
            or (ending and active != tag)
            or (not ending and (active is not None or tag in seen))
        ):
            raise ConfigurationError(
                "Duplicate, nested, or mismatched append boundaries.",
                hint="Give each region one unique matching begin/end pair.",
            )
        if ending:
            active = None
        else:
            active = tag
            seen.add(tag)
    if active:
        raise ConfigurationError(
            "Unclosed append region.", hint="Restore the matching end marker."
        )
    identities = [c.id for c in payloads]
    if len(set(identities)) != len(identities):
        raise ConfigurationError(
            "Duplicate desired region identities.", hint="Use unique stable IDs."
        )
    tags = [c.tag for c in payloads]
    if len(set(tags)) != len(tags):
        raise ConfigurationError(
            "Duplicate desired region tags.", hint="Use unique stable IDs."
        )
    for identity in identities:
        validate_region_id(identity)
    result = original_content
    applied = dict(baselines or {})
    refused: list[tuple[AppendContribution, tuple[TextConflict, ...]]] = []
    for contribution in payloads:
        tag = contribution.tag
        begin, end = marker(tag), marker(tag, True)
        framed = f"{begin}\n{contribution.content}"
        if not framed.endswith("\n"):
            framed += "\n"
        framed += end
        local = None
        start = stop = 0
        if tag in seen:
            start = result.index(begin)
            stop = result.index(end, start) + len(end)
            local = result[start:stop].encode("utf-8")
        baseline = applied.get(contribution.id)
        if missing_owned_file and not overwrite:
            # An owned deleted file protects newly introduced regions too.
            if baseline != framed:
                refused.append((contribution, ()))
            continue
        decision = reconcile_text(local, framed, baseline, overwrite=overwrite)
        if decision.conflict:
            refused.append((contribution, decision.conflicts))
        if decision.baseline is not None:
            applied[contribution.id] = decision.baseline
        if decision.content is None:
            continue
        if local is not None:
            result = result[:start] + decision.content + result[stop:]
        else:
            separator = (
                "" if not result else ("\n" if result.endswith("\n") else "\n\n")
            )
            result += separator + framed + "\n"
            seen.add(tag)
    if payloads:
        append_marker_blocks(result, [], filepath)
    conflicts: list[RegionConflict] = []
    for contribution, overlaps in refused:
        if not overlaps:
            conflicts.append(RegionConflict(contribution.id))
            continue
        # Number lines in the final file, after every accepted region moved them.
        offset = result[: result.index(marker(contribution.tag))].count("\n")
        conflicts.extend(
            RegionConflict(
                contribution.id,
                LineSpan(overlap.lines.start + offset, overlap.lines.count),
            )
            for overlap in overlaps
        )
    return RegionResult(result, applied, tuple(conflicts))
