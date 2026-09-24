"""Source lines of TOML keys, for pointing a reader at the text a report means.

Neither ``tomllib`` nor ``tomlkit`` reports where a key sits in its source, so
this is a small lexer that reads only as much TOML as locating needs: table
headers, keys, and where each value starts and ends. It never validates;
locating in malformed TOML finds what it can and answers None for the rest.
"""

from __future__ import annotations

import bisect
import contextlib
import json
import re
from dataclasses import dataclass

__all__ = ["TomlLineIndex"]

_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")
_MULTILINE_QUOTES = ('"""', "'''")


@dataclass(frozen=True)
class _Entry:
    """Where one key and its value sit, as character offsets."""

    key_start: int
    value_start: int
    value_end: int
    # The body of a value that is one multi-line string, when it is.
    string_start: int | None = None
    string_end: int | None = None


class TomlLineIndex:
    """Maps TOML key paths to 1-based source lines.

    A path is the tuple of key segments, table headers included, as the
    parsed document would nest them: ``("dev", "pyproject", "lint")``. An
    array of tables maps to its first element.
    """

    def __init__(self, text: str) -> None:
        """Indexes every table header and key in ``text``.

        Args:
            text: The TOML source.
        """
        self._text = text
        self._line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
        self._entries: dict[tuple[str, ...], _Entry] = {}
        self._scan()

    def line_of(self, path: tuple[str, ...]) -> int | None:
        """Returns the line of a key or table header, or None when absent.

        A table only defined implicitly, such as ``tool`` under
        ``[tool.ruff]``, is at its first key or header.
        """
        entry = self._entries.get(path)
        if entry is not None:
            return self._line(entry.key_start)
        starts = [
            nested.key_start
            for key, nested in self._entries.items()
            if key[: len(path)] == path
        ]
        return self._line(min(starts)) if starts else None

    def line_in_value(self, path: tuple[str, ...], needle: str) -> int | None:
        """Returns the first line of a key's value containing ``needle``.

        Falls back to the key's own line when the value does not contain it.
        """
        entry = self._entries.get(path)
        if entry is None:
            return None
        found = self._text.find(needle, entry.value_start, entry.value_end)
        return self._line(found if found >= 0 else entry.key_start)

    def line_in_string(
        self, path: tuple[str, ...], inner: tuple[str, ...]
    ) -> int | None:
        """Locates a key inside TOML held in a multi-line string value.

        Template payloads are TOML inside a TOML string. This indexes the
        string's raw body, so its lines match the file's line for line.

        Args:
            path: The key whose value is the multi-line string.
            inner: The key path within the string's TOML.

        Returns:
            The file line of ``inner``, the value's line when ``inner`` is not
            found, or None when ``path`` is absent.
        """
        entry = self._entries.get(path)
        if entry is None:
            return None
        if entry.string_start is None or entry.string_end is None:
            return self._line(entry.key_start)
        body = self._text[entry.string_start : entry.string_end]
        inner_line = TomlLineIndex(body).line_of(inner)
        if inner_line is None:
            return self._line(entry.key_start)
        return self._line(entry.string_start) + inner_line - 1

    def _line(self, offset: int) -> int:
        return bisect.bisect_right(self._line_starts, offset)

    def _scan(self) -> None:
        text, pos = self._text, 0
        table: tuple[str, ...] = ()
        while (pos := _skip_blank(text, pos)) < len(text):
            if text[pos] == "[":
                opener = 2 if text.startswith("[[", pos) else 1
                parsed = _read_key(text, pos + opener)
                if parsed is not None and text.startswith("]", parsed[1]):
                    table = parsed[0]
                    self._entries.setdefault(table, _Entry(pos, pos, pos))
                pos = _line_end(text, pos)
                continue
            parsed = _read_key(text, pos)
            if parsed is None or not text.startswith("=", parsed[1]):
                pos = _line_end(text, pos)
                continue
            keys, after = parsed
            value_start = _skip_spaces(text, after + 1)
            value_end, string = _scan_value(text, value_start)
            path = (*table, *keys)
            for depth in range(len(keys) - 1):
                # A dotted key also defines its parent tables on this line.
                self._entries.setdefault(
                    (*table, *keys[: depth + 1]), _Entry(pos, pos, pos)
                )
            self._entries.setdefault(
                path,
                _Entry(
                    pos,
                    value_start,
                    value_end,
                    *(string if string else (None, None)),
                ),
            )
            pos = value_end


def _skip_spaces(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] in " \t":
        pos += 1
    return pos


def _skip_blank(text: str, pos: int) -> int:
    """Skips whitespace, newlines, and comments."""
    while pos < len(text):
        if text[pos] in " \t\r\n":
            pos += 1
        elif text[pos] == "#":
            pos = _line_end(text, pos)
        else:
            break
    return pos


def _line_end(text: str, pos: int) -> int:
    end = text.find("\n", pos)
    return len(text) if end < 0 else end + 1


def _read_key(text: str, pos: int) -> tuple[tuple[str, ...], int] | None:
    """Reads a dotted key; returns its segments and the offset after it."""
    parts: list[str] = []
    while True:
        pos = _skip_spaces(text, pos)
        if pos >= len(text):
            return None
        if text[pos] in "\"'":
            end = _one_line_string_end(text, pos)
            if end is None:
                return None
            raw = text[pos + 1 : end]
            if text[pos] == '"':
                # TOML escapes are close to JSON's; an unusual one stays raw.
                with contextlib.suppress(ValueError):
                    raw = json.loads(f'"{raw}"')
            parts.append(raw)
            pos = end + 1
        elif match := _BARE_KEY.match(text, pos):
            parts.append(match.group())
            pos = match.end()
        else:
            return None
        pos = _skip_spaces(text, pos)
        if not text.startswith(".", pos):
            return tuple(parts), pos
        pos += 1


def _one_line_string_end(text: str, pos: int) -> int | None:
    """Returns the offset of the quote closing the string opened at ``pos``.

    Only a basic (double-quoted) string has escapes. None when the line ends
    first.
    """
    quote = text[pos]
    pos += 1
    while pos < len(text) and text[pos] != "\n":
        if quote == '"' and text[pos] == "\\":
            pos += 2
            continue
        if text[pos] == quote:
            return pos
        pos += 1
    return None


def _scan_value(text: str, pos: int) -> tuple[int, tuple[int, int] | None]:
    """Finds where a value ends: the newline after it, outside any bracket.

    Returns:
        The end offset, and the body span of a multi-line string when the
        value is one.
    """
    start, depth = pos, 0
    string: tuple[int, int] | None = None
    while pos < len(text):
        quotes = text[pos : pos + 3]
        if quotes in _MULTILINE_QUOTES:
            body = pos + 3
            if text.startswith("\r\n", body):
                body += 2
            elif text.startswith("\n", body):
                body += 1
            close = _multiline_end(text, pos + 3, quotes)
            if pos == start:
                string = (body, close)
            pos = min(len(text), close + 3)
            while pos < len(text) and text[pos] == quotes[0]:
                pos += 1
        elif text[pos] in "\"'":
            # An unterminated string ends with its line.
            end = _one_line_string_end(text, pos)
            pos = _line_end(text, pos) - 1 if end is None else end + 1
        elif text[pos] in "[{":
            depth += 1
            pos += 1
        elif text[pos] in "]}":
            depth -= 1
            pos += 1
        elif text[pos] == "#":
            end = text.find("\n", pos)
            pos = len(text) if end < 0 else end
        elif text[pos] == "\n" and depth <= 0:
            return pos, string
        else:
            pos += 1
    return pos, string


def _multiline_end(text: str, pos: int, quotes: str) -> int:
    """Returns the offset of the quotes closing a multi-line string."""
    while (found := text.find(quotes, pos)) >= 0:
        if quotes == '"""':
            backslashes = len(text[:found]) - len(text[:found].rstrip("\\"))
            if backslashes % 2:
                pos = found + 1
                continue
        return found
    return len(text)
