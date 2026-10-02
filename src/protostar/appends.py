"""Generic marker-block file append engine."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from .errors import ConfigurationError
from .intent import AppendContribution, region_tag, validate_region_id
from .merge import (
    MISSING,
    NO_RESOLUTIONS,
    ConflictReason,
    ConflictSides,
    LineSpan,
    MergeConflict,
    MergeLocation,
    ResolutionChoice,
    Resolutions,
)
from .text_merge import is_edited, reconcile_text

__all__ = [
    "RegionResult",
    "append_marker_blocks",
    "attach_regions",
    "cut_regions",
    "detach_regions",
    "get_comment_markers",
]


def get_comment_markers(filepath: Path) -> tuple[str, str]:
    """Returns the comment syntax (start, end) for a file's extension.

    Anything unlisted, which includes Python, TOML, YAML, shell, and files like
    ``justfile``, takes ``#``.
    """
    ext = filepath.suffix.lower()

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

    return ("#", "")


@dataclass(frozen=True)
class RegionResult:
    """Exact file content, composite applied region texts, and refused regions.

    Attributes:
        content: The file with every accepted region update applied.
        baselines: Each owned region's last applied framed text, by identity.
        conflicts: Refused regions, one per overlapping edit or whole region,
            identified by region and numbered by line in ``content``.
        resolved: Region conflicts settled by a resolution, numbered likewise,
            and restored regions.
        preserved: Local edits and deletions of regions the update left as they
            were, by region.
    """

    content: str
    baselines: dict[str, str]
    conflicts: tuple[MergeConflict, ...]
    resolved: tuple[MergeConflict, ...] = ()
    preserved: tuple[MergeConflict, ...] = ()


def _marker(filepath: Path, tag: str, end: bool = False) -> str:
    """Returns a region's begin or end marker in the file's comment syntax."""
    c_start, c_end = get_comment_markers(filepath)
    prefix = "endregion" if end else "region"
    return f"{c_start} {prefix}: protostar {tag} {c_end}".strip()


def _span(text: str, begin: str, end: str) -> tuple[int, int] | None:
    """Returns where a region's framed text starts and stops, or None if absent."""
    # Each marker occurs once in well-formed text, so which end a search
    # comes from, and where it starts, can't change what it finds.
    start = text.find(begin)  # pragma: no mutate
    if start == -1:
        return None
    stop = text.index(end, start)  # pragma: no mutate
    return start, stop + len(end)


def cut_regions(text: str, identities: Iterable[str], filepath: Path) -> str:
    """Removes regions from a text whatever they hold, such as a recorded baseline.

    Args:
        text: Text whose regions are well formed.
        identities: The regions to remove; absent ones are skipped.
        filepath: The file, which selects the comment syntax of the markers.

    Returns:
        The text without those regions, spaced as appending left it.
    """
    for identity in identities:
        tag = region_tag(identity)
        span = _span(text, _marker(filepath, tag), _marker(filepath, tag, True))
        if span is not None:
            text = _cut(text, *span)
    return text


def detach_regions(
    text: str, identities: Iterable[str], filepath: Path
) -> tuple[str, tuple[str, ...]]:
    """Takes regions out of a text, to put back with ``attach_regions``.

    Args:
        text: Text whose regions are well formed.
        identities: The regions to take out; absent ones are skipped.
        filepath: The file, which selects the comment syntax of the markers.

    Returns:
        The text without those regions, and each region's framed text in order.
    """
    blocks: list[tuple[int, str]] = []
    for identity in identities:
        tag = region_tag(identity)
        span = _span(text, _marker(filepath, tag), _marker(filepath, tag, True))
        if span is not None:
            start, stop = span
            blocks.append((start, text[start:stop]))
    detached = cut_regions(text, identities, filepath)
    return detached, tuple(block for _, block in sorted(blocks))


def attach_regions(text: str, blocks: Iterable[str]) -> str:
    """Appends framed regions to a text the way a new region is appended.

    Args:
        text: The text to extend.
        blocks: Framed region texts, in order.

    Returns:
        The text with each region appended after a blank line.
    """
    for block in blocks:
        newline = "\r\n" if "\r\n" in text or "\r\n" in block else "\n"
        separator = (
            "" if not text else (newline if text.endswith("\n") else newline + newline)
        )
        text += separator + block + newline
    return text


def _cut(text: str, start: int, stop: int) -> str:
    """Removes a region and the line break after it, and the blank line it needed."""
    if text[stop : stop + 2] == "\r\n":
        stop += 2
    elif text[stop : stop + 1] == "\n":
        stop += 1
    head, tail = text[:start], text[stop:]
    # Appending put one blank line before the region; one is enough.
    if head.endswith("\n\r\n") and (not tail or tail.startswith(("\r\n", "\n"))):
        head = head[:-2]
    elif head.endswith("\n\n") and (not tail or tail.startswith(("\r\n", "\n"))):
        head = head[:-1]
    elif not head and tail.startswith("\r\n"):
        tail = tail[2:]
    elif not head and tail.startswith("\n"):
        tail = tail[1:]
    return head + tail


def append_marker_blocks(
    original_content: str,
    payloads: list[AppendContribution],
    filepath: Path,
    overwrite: bool = False,
    *,
    baselines: dict[str, str] | None = None,
    missing_owned_file: bool = False,
    resolutions: Resolutions = NO_RESOLUTIONS,
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
        resolutions: Choices settling region conflicts, by conflict identity.

    Returns:
        The reconciled content, applied region texts, and refused regions.
    """

    def marker(tag: str, end: bool = False) -> str:
        return _marker(filepath, tag, end)

    active: str | None = None
    seen: set[str] = set()
    for line in original_content.splitlines():
        match = re.fullmatch(
            r".*?\b(end)?region:\s*protostar\s+([0-9a-f]{8}).*",
            line,
        )
        if not match:
            if "region: protostar" in line:
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
    # Each refused or settled conflict, with the tag of its region.
    refused: list[tuple[str, MergeConflict]] = []
    settled: list[tuple[str, MergeConflict]] = []
    preserved: list[MergeConflict] = []
    for contribution in payloads:
        tag = contribution.tag
        begin, end = marker(tag), marker(tag, True)
        framed = f"{begin}\n{contribution.content}"
        if not framed.endswith("\n"):
            framed += "\n"
        framed += end
        span = _span(result, begin, end)
        local = None if span is None else result[slice(*span)].encode()
        baseline = applied.get(contribution.id)
        location = MergeLocation(filepath.as_posix(), identity=contribution.id)
        if missing_owned_file and not overwrite:
            # An owned deleted file protects newly introduced regions too.
            if baseline != framed:
                refused.append(
                    (tag, MergeConflict(location, ConflictReason.DELETED_ANCESTOR))
                )
                continue
            deleted = MergeConflict(
                location,
                ConflictReason.PRESERVED,
                ConflictSides(framed, MISSING, framed, line=0),
            )
            choice = deleted.settle(resolutions)
            if choice is None:
                preserved.append(deleted)
                continue
            if choice.resolution is not ResolutionChoice.DESIRED:
                settled.append((tag, choice))
                continue
            # Restoring one region recreates the file; the merge below reports it.
        decision = reconcile_text(
            local,
            framed,
            baseline,
            location,
            overwrite=overwrite,
            resolutions=resolutions,
        )
        refused.extend((tag, conflict) for conflict in decision.conflicts)
        settled.extend((tag, conflict) for conflict in decision.resolved)
        preserved.extend(decision.preserved)
        if decision.baseline is not None:
            applied[contribution.id] = decision.baseline
        if decision.content is None:
            continue
        if span is not None:
            start, stop = span
            result = result[:start] + decision.content + result[stop:]
        else:
            separator = (
                "" if not result else ("\n" if result.endswith("\n") else "\n\n")
            )
            result += separator + framed + "\n"
    declared = set(identities)
    for identity in [i for i in applied if i not in declared]:
        # A region nothing declares any more is retracted: removed when
        # unedited, a decision when edited, and forgotten when already gone.
        tag = region_tag(identity)
        span = _span(result, marker(tag), marker(tag, True))
        if span is None:
            del applied[identity]
            continue
        start, stop = span
        local_text = result[start:stop]
        if is_edited(local_text.encode(), applied[identity]):
            found = MergeConflict(
                MergeLocation(filepath.as_posix(), identity=identity),
                ConflictReason.RETRACTED,
                ConflictSides(applied[identity], local_text, MISSING, line=0),
            )
            choice = found.settle(resolutions)
            if choice is None:
                refused.append((tag, found))
                continue
            settled.append((tag, choice))
            if choice.resolution is ResolutionChoice.LOCAL:
                del applied[identity]
                continue
        del applied[identity]
        result = _cut(result, start, stop)
    if payloads or baselines:
        append_marker_blocks(result, [], filepath)

    def numbered(found: list[tuple[str, MergeConflict]]) -> tuple[MergeConflict, ...]:
        # Number lines in the final file, after every accepted region moved them.
        conflicts: list[MergeConflict] = []
        for tag, conflict in found:
            lines = conflict.location.lines
            if lines is not None:
                # A conflict with lines is a hunk of a region the file still
                # holds, and its marker occurs once, so either end finds it.
                begin = marker(tag)
                start = result.find(begin)  # pragma: no mutate
                offset = result[:start].count("\n")
                lines = LineSpan(lines.start + offset, lines.count)
            conflicts.append(
                replace(conflict, location=replace(conflict.location, lines=lines))
            )
        return tuple(conflicts)

    return RegionResult(
        result, applied, numbered(refused), numbered(settled), tuple(preserved)
    )
