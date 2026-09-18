"""Generic marker-block file append engine."""

import re
from dataclasses import dataclass
from pathlib import Path

from .checksum import checksum_gate
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


@dataclass(frozen=True)
class RegionResult:
    """Exact region content, composite applied digests, and conflicting identities."""

    content: str
    digests: dict[str, str]
    conflicts: tuple[str, ...]


def append_marker_blocks(
    original_content: str,
    payloads: list[AppendContribution],
    filepath: Path,
    overwrite: bool = False,
    *,
    baselines: dict[str, str] | None = None,
    missing_owned_file: bool = False,
) -> RegionResult:
    """Reconciles stable regions using exact-byte gates and preserves surrounding bytes."""
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
    digests = dict(baselines or {})
    conflicts: list[str] = []
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
        baseline = digests.get(contribution.id)
        if missing_owned_file and not overwrite:
            # An owned deleted file protects newly introduced regions too.
            if (
                baseline is None
                or checksum_gate(None, framed.encode("utf-8"), baseline).conflict
            ):
                conflicts.append(contribution.id)
            continue
        decision = checksum_gate(
            local, framed.encode("utf-8"), baseline, overwrite=overwrite
        )
        if decision.conflict:
            conflicts.append(contribution.id)
        if decision.digest is not None:
            digests[contribution.id] = decision.digest
        if not decision.write:
            continue
        if local is not None:
            result = result[:start] + framed + result[stop:]
        else:
            separator = (
                "" if not result else ("\n" if result.endswith("\n") else "\n\n")
            )
            result += separator + framed + "\n"
            seen.add(tag)
    if payloads:
        append_marker_blocks(result, [], filepath)
    return RegionResult(result, digests, tuple(conflicts))
