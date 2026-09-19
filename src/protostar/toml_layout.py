"""The layout of a pyproject.toml: one spec, a section model, and a formatter.

Protostar lays out the pyproject.toml it creates in a fixed order, with a banner and
a header above each tool's configuration:

    [project] ... [build-system] ... [dependency-groups] ... [tool.hatch...]

    # ==================================================
    # Tool Configuration
    # ==================================================

    # ---- Ruff ---- #
    [tool.ruff] ...
    # ---- Protostar ---- #
    [tool.protostar] ...

Everything that decides that order lives in ``TOOL_SECTIONS`` and ``ROOT_ORDER``.

The file is handled as a list of ``Section`` pieces: each root table, and each child
of ``[tool]``. A piece is rendered with tomlkit's public API, and joining the pieces
reproduces the original text exactly, so a caller can change one section without
touching any other byte. The managed banner and headers that trail a piece are kept
apart in ``Section.tail`` and are matched by exact line, never by pattern.
"""

import logging
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import tomlkit
from tomlkit.items import AoT, Table

logger = logging.getLogger("protostar")

BANNER_RULE = "# " + "=" * 50
BANNER = (BANNER_RULE, "# Tool Configuration", BANNER_RULE)


@dataclass(frozen=True)
class ToolSection:
    """Where one ``[tool.<key>]`` table sits, and the header above it.

    Attributes:
        key: The table name under ``[tool]``.
        rank: Sort position among tool tables; lower comes first.
        title: Text of the ``# ---- <title> ---- #`` header, or None for no header.
            Tables that share a title share one header, printed above the first.
    """

    key: str
    rank: int
    title: str | None = None


# Build-backend configuration is not tooling: it sorts above the banner.
PACKAGING_RANK = -1
# Tables no entry below names sit after the known tools and before Protostar.
UNKNOWN_TOOL_RANK = 100

TOOL_SECTIONS: tuple[ToolSection, ...] = (
    ToolSection("hatch", PACKAGING_RANK),
    ToolSection("ruff", 0, "Ruff"),
    ToolSection("mypy", 1, "Mypy"),
    ToolSection("ty", 2, "Ty"),
    ToolSection("pyrefly", 3, "Pyrefly"),
    ToolSection("pytest", 4, "Pytest"),
    ToolSection("coverage", 5, "Pytest"),
    ToolSection("commitizen", 6, "Commitizen"),
    ToolSection("rumdl", 7, "rumdl"),
    ToolSection("protostar", 200, "Protostar"),
)

# Root tables in the order they appear, ahead of any other root table.
ROOT_ORDER = ("project", "build-system", "dependency-groups")
_UNKNOWN_ROOT_RANK = 100
_TOOL_BASE = 500

_BY_KEY = {section.key: section for section in TOOL_SECTIONS}

TOOL_SECTION_NAMES: dict[str, str] = {
    section.key: section.title for section in TOOL_SECTIONS if section.title
}

_MANAGED_LINES = frozenset(
    {*BANNER, *(f"# ---- {title} ---- #" for title in TOOL_SECTION_NAMES.values())}
)

SectionPath = tuple[str, ...]


def section_rank(path: SectionPath) -> tuple[int, str]:
    """Sort key for a section: known position first, then name for a stable tiebreak."""
    if not path:
        return (0, "")  # keyless root comments and whitespace stay at the top
    if path[0] == "tool" and len(path) > 1:
        known = _BY_KEY.get(path[1])
        return (_TOOL_BASE + (known.rank if known else UNKNOWN_TOOL_RANK), path[1])
    if path[0] in ROOT_ORDER:
        return (1 + ROOT_ORDER.index(path[0]), path[0])
    return (_UNKNOWN_ROOT_RANK, path[0])


def section_title(path: SectionPath) -> str | None:
    """The header title above this section, if it has one."""
    if len(path) > 1 and path[0] == "tool":
        known = _BY_KEY.get(path[1])
        return known.title if known else None
    return None


@dataclass
class Section:
    """One piece of a pyproject.toml.

    Attributes:
        path: ``("project",)``, ``("tool", "ruff")``, and so on; empty for root
            comments and blank lines.
        body: The section's text, ending at its last line of content.
        tail: Managed banner and header lines, and the blank lines around them, that
            trailed the section. They introduce the next section, not this one.
    """

    path: SectionPath
    body: str
    tail: str = ""

    @property
    def text(self) -> str:
        """The section exactly as it appeared in the file."""
        return self.body + self.tail


def _is_managed(line: str) -> bool:
    return line.strip() in _MANAGED_LINES


def _split_tail(text: str) -> tuple[str, str]:
    """Separates trailing managed lines (and the blanks around them) from a section."""
    lines = text.split("\n")
    index = len(lines)
    found = False
    while index > 0 and (not lines[index - 1].strip() or _is_managed(lines[index - 1])):
        found = found or _is_managed(lines[index - 1])
        index -= 1
    if not found:
        return text, ""
    cut = sum(len(line) + 1 for line in lines[:index])
    return text[:cut], text[cut:]


def _render(key_path: list[Any], item: Any) -> str:
    """Renders one item on its own, using only tomlkit's public API."""
    document = tomlkit.document()
    if len(key_path) == 1:
        document.append(key_path[0], item)
    else:
        parent = tomlkit.table(is_super_table=True)
        parent.append(key_path[1], item)
        document.append(key_path[0], parent)
    return tomlkit.dumps(document)


def _decomposable(tool: Any) -> bool:
    """Whether [tool] is a plain table of tables that can be split per tool."""
    return isinstance(tool, Table) and all(
        key is None or isinstance(child, (Table, AoT)) for key, child in tool.value.body
    )


def split_sections(document: Any) -> list[Section]:
    """Splits a parsed document into sections whose text joins back to the original."""
    sections: list[Section] = []

    def add(path: SectionPath, text: str) -> None:
        body, tail = _split_tail(text)
        sections.append(Section(path, body, tail))

    for key, item in document.body:
        if key is None:
            add((), _render([None], item))
        elif key.key == "tool" and _decomposable(item):
            for child_key, child in item.value.body:
                if child_key is None:
                    add(("tool", ""), _render([key, None], child))
                else:
                    add(("tool", child_key.key), _render([key, child_key], child))
        else:
            add((key.key,), _render([key], item))
    return sections


def join_sections(sections: list[Section]) -> str:
    """Joins sections; unchanged sections reproduce the original text exactly."""
    return "".join(section.text for section in sections)


def _trim(text: str) -> str:
    """Drops blank and managed lines from both ends of a section."""
    lines = text.split("\n")
    while lines and (not lines[-1].strip() or _is_managed(lines[-1])):
        lines.pop()
    while lines and (not lines[0].strip() or _is_managed(lines[0])):
        lines.pop(0)
    return "\n".join(lines)


def format_sections(sections: list[Section]) -> str:
    """Lays sections out in canonical order with a banner and one header per tool.

    Managed decoration is discarded and rebuilt, so the result never depends on
    where a previous layout left it.
    """
    kept = [
        (section.path, body) for section in sections if (body := _trim(section.body))
    ]
    kept.sort(key=lambda entry: section_rank(entry[0]))

    parts: list[str] = []
    titles: set[str] = set()
    for path, body in kept:
        title = section_title(path)
        if title is not None:
            if not titles:
                parts.append("\n".join(BANNER))
            if title not in titles:
                titles.add(title)
                parts.append(f"# ---- {title} ---- #")
        parts.append(body)
    return "\n\n".join(parts) + "\n"


def format_document(
    document: Any, on_fallback: Callable[[str], None] | None = None
) -> str:
    """Formats a parsed pyproject.toml, or returns it unchanged if that is unsafe.

    The result must parse to exactly the data the input holds. If it cannot be proven
    to, the input is returned as it was, so a layout problem can never change a
    project's configuration. That is logged and reported to ``on_fallback``, so it is
    never silent.
    """
    raw = tomlkit.dumps(document)

    def fall_back(reason: str) -> str:
        logger.warning(f"{reason}; falling back to direct AST dump.")
        if on_fallback is not None:
            on_fallback(reason)
        return raw.rstrip() + "\n"

    try:
        expected = tomllib.loads(raw)
        formatted = format_sections(split_sections(document))
        if tomllib.loads(formatted) != expected:
            return fall_back("AST Parity mismatch during pyproject.toml formatting")
    except Exception as e:
        return fall_back(f"Validation error during pyproject.toml formatting ({e})")
    return formatted


def _newline(sections: list[Section]) -> str:
    return "\r\n" if "\r\n" in join_sections(sections) else "\n"


def insert_section(sections: list[Section], new: Section, index: int) -> None:
    """Inserts a section at ``index``, separated from its neighbors by a blank line.

    Only the bytes at the two seams change; every other section is left as it was. The
    file's own newline style is used for anything written.
    """
    newline = _newline(sections)
    if newline != "\n":
        new.body = new.body.replace("\n", newline)
    if index > 0:
        previous = sections[index - 1]
        if previous.text and not previous.text.endswith("\n"):
            previous.tail += newline
        if not previous.text.endswith(newline * 2):
            previous.tail += newline
    if index < len(sections) and not new.body.endswith(newline * 2):
        new.tail += newline
    sections.insert(index, new)


def compose_children(document: Any, path: SectionPath, order: tuple[str, ...]) -> str:
    """Rebuilds one table's text: its own keys, then each child table in ``order``.

    Children are rendered separately and joined by exactly one blank line, so the
    result does not depend on where tomlkit decided to put whitespace. Children that
    ``order`` does not name follow, in their existing order. Comments inside a child
    stay with it. The document is consumed: its child tables are removed.
    """
    parent = document
    for key in path:
        parent = parent[key]
    children = {k: parent[k] for k in list(parent) if isinstance(parent[k], Table)}
    for key in children:
        parent.remove(key)
    parts = [_trim(tomlkit.dumps(document))]

    rank = {key: position for position, key in enumerate(order)}
    for key in sorted(children, key=lambda k: rank.get(k, len(order))):
        root = tomlkit.document()
        holder: Any = root
        for name in path[:-1]:
            table = tomlkit.table(is_super_table=True)
            holder.append(name, table)
            holder = table
        middle = tomlkit.table(is_super_table=True)
        middle.append(key, children[key])
        holder.append(path[-1], middle)
        parts.append(_trim(tomlkit.dumps(root)))
    return "\n\n".join(parts) + "\n"
