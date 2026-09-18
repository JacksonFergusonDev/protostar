"""Lossless JSONC codec and byte-splice editor for workspace configuration files.

The parser records source spans only. Edits are computed as replacements over those
spans, so every byte outside an accepted edit is identical to the original document.
The module is pure Python, uses only the standard library, and performs no I/O.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from .errors import ConfigurationError
from .merge import MISSING, Value, semantic_equal, validate_value

type Path = tuple[str | int, ...]

_MAX_BYTES = 1_000_000
_MAX_DEPTH = 100
_MAX_NODES = 10_000
_HINT = (
    "Use one JSON object with unique string keys; comments and trailing commas are "
    "allowed, and the document is limited to 100 levels, 10000 nodes, and 1 MB."
)
_ESCAPES = frozenset('"\\/bfnrtu')
_HEX = frozenset("0123456789abcdefABCDEF")


class NodeKind(StrEnum):
    """Syntactic kind of a parsed JSON value."""

    OBJECT = "object"
    ARRAY = "array"
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"


@dataclass(frozen=True)
class Node:
    """A parsed value spanning ``text[start:end]``, excluding surrounding trivia."""

    kind: NodeKind
    start: int
    end: int
    items: tuple[Item, ...] = ()
    scalar: Value = None


@dataclass(frozen=True)
class Item:
    """One object member or array element, with its trailing comma position."""

    start: int
    end: int
    node: Node
    key: str | None = None
    comma: int | None = None


@dataclass(frozen=True)
class TextEdit:
    """Replacement of ``text[start:end]`` with ``text``."""

    start: int
    end: int
    text: str


def _limits() -> ConfigurationError:
    return ConfigurationError(
        "JSONC configuration exceeds supported limits or is unsupported.",
        hint=_HINT,
    )


class _Parser:
    """Recursive-descent scanner that records spans instead of building text."""

    def __init__(self, text: str, *, strict: bool) -> None:
        self.text = text
        self.strict = strict
        self.pos = 0
        self.nodes = 0

    def fail(self, reason: str, at: int | None = None) -> ConfigurationError:
        pos = self.pos if at is None else at
        line = self.text.count("\n", 0, pos) + 1
        column = pos - (self.text.rfind("\n", 0, pos) + 1) + 1
        return ConfigurationError(
            f"Invalid JSONC at line {line}, column {column}: {reason}.", hint=_HINT
        )

    def count(self) -> None:
        self.nodes += 1
        if self.nodes > _MAX_NODES:
            raise _limits()

    def skip_trivia(self) -> None:
        text = self.text
        size = len(text)
        pos = self.pos
        while pos < size:
            char = text[pos]
            if char in " \t\r\n" or (char == "\ufeff" and pos == 0):
                pos += 1
            elif text.startswith("//", pos):
                if self.strict:
                    raise self.fail("comments are not allowed", pos)
                while pos < size and text[pos] not in "\r\n":
                    pos += 1
            elif text.startswith("/*", pos):
                if self.strict:
                    raise self.fail("comments are not allowed", pos)
                end = text.find("*/", pos + 2)
                if end < 0:
                    raise self.fail("unterminated block comment", pos)
                pos = end + 2
            else:
                break
        self.pos = pos

    def value(self, depth: int) -> Node:
        if depth > _MAX_DEPTH:
            raise _limits()
        self.count()
        text = self.text
        if self.pos >= len(text):
            raise self.fail("unexpected end of input")
        start = self.pos
        char = text[start]
        if char == "{":
            return self.container(depth, NodeKind.OBJECT)
        if char == "[":
            return self.container(depth, NodeKind.ARRAY)
        if char == '"':
            text_value = self.string()
            return Node(NodeKind.STRING, start, self.pos, scalar=text_value)
        for literal, kind, scalar in (
            ("true", NodeKind.BOOLEAN, True),
            ("false", NodeKind.BOOLEAN, False),
            ("null", NodeKind.NULL, None),
        ):
            if text.startswith(literal, start):
                self.pos = start + len(literal)
                return Node(kind, start, self.pos, scalar=scalar)
        if char == "-" or char.isdigit():
            return self.number()
        raise self.fail(f"unexpected character {char!r}")

    def container(self, depth: int, kind: NodeKind) -> Node:
        text = self.text
        size = len(text)
        is_object = kind is NodeKind.OBJECT
        close = "}" if is_object else "]"
        start = self.pos
        self.pos += 1
        items: list[Item] = []
        keys: set[str] = set()
        while True:
            self.skip_trivia()
            if self.pos >= size:
                raise self.fail(f"unterminated {kind.value}", start)
            if text[self.pos] == close:
                break
            item_start = self.pos
            key: str | None = None
            if is_object:
                if text[self.pos] != '"':
                    raise self.fail("expected a string key")
                self.count()
                key = self.string()
                if key in keys:
                    raise self.fail(f"duplicate key {key!r}", item_start)
                keys.add(key)
                self.skip_trivia()
                if self.pos >= size or text[self.pos] != ":":
                    raise self.fail("expected ':' after key")
                self.pos += 1
                self.skip_trivia()
            node = self.value(depth + 1)
            self.skip_trivia()
            comma: int | None = None
            if self.pos < size and text[self.pos] == ",":
                comma = self.pos
                self.pos += 1
            elif self.pos >= size or text[self.pos] != close:
                raise self.fail(f"expected ',' or '{close}'")
            items.append(Item(item_start, node.end, node, key, comma))
        if self.strict and items and items[-1].comma is not None:
            raise self.fail("trailing commas are not allowed", items[-1].comma)
        self.pos += 1
        return Node(kind, start, self.pos, tuple(items))

    def string(self) -> str:
        text = self.text
        size = len(text)
        start = self.pos
        pos = start + 1
        escaped = False
        while True:
            if pos >= size:
                raise self.fail("unterminated string", start)
            char = text[pos]
            if char == '"':
                break
            if char < " ":
                raise self.fail("control character in string", pos)
            if char == "\\":
                escaped = True
                if pos + 1 >= size or text[pos + 1] not in _ESCAPES:
                    raise self.fail("invalid escape sequence", pos)
                if text[pos + 1] == "u":
                    digits = text[pos + 2 : pos + 6]
                    if len(digits) != 4 or not all(c in _HEX for c in digits):
                        raise self.fail("invalid unicode escape", pos)
                    pos += 4
                pos += 1
            pos += 1
        self.pos = pos + 1
        if not escaped:
            return text[start + 1 : pos]
        try:
            decoded = cast(str, json.loads(text[start : pos + 1]))
            decoded.encode("utf-8")
        except (ValueError, UnicodeEncodeError) as error:
            raise self.fail("invalid string escape", start) from error
        return decoded

    def number(self) -> Node:
        text = self.text
        size = len(text)
        start = self.pos
        pos = start + 1 if text[start] == "-" else start
        if pos < size and text[pos] == "0":
            pos += 1
        elif pos < size and "1" <= text[pos] <= "9":
            while pos < size and text[pos].isascii() and text[pos].isdigit():
                pos += 1
        else:
            raise self.fail("invalid number", start)
        floating = False
        if pos < size and text[pos] == ".":
            pos += 1
            digits = pos
            while pos < size and text[pos].isascii() and text[pos].isdigit():
                pos += 1
            if pos == digits:
                raise self.fail("invalid number", start)
            floating = True
        if pos < size and text[pos] in "eE":
            pos += 1
            if pos < size and text[pos] in "+-":
                pos += 1
            digits = pos
            while pos < size and text[pos].isascii() and text[pos].isdigit():
                pos += 1
            if pos == digits:
                raise self.fail("invalid number", start)
            floating = True
        token = text[start:pos]
        try:
            scalar: Value = float(token) if floating else int(token)
        except ValueError as error:
            raise self.fail("number out of range", start) from error
        if isinstance(scalar, float) and not math.isfinite(scalar):
            raise self.fail("number out of range", start)
        self.pos = pos
        return Node(NodeKind.NUMBER, start, pos, scalar=scalar)


def _node_value(node: Node) -> Value:
    if node.kind is NodeKind.OBJECT:
        return {cast(str, item.key): _node_value(item.node) for item in node.items}
    if node.kind is NodeKind.ARRAY:
        return [_node_value(item.node) for item in node.items]
    return node.scalar


def _leading_ws(text: str, pos: int) -> str:
    """Returns the leading whitespace of the line containing ``pos``."""
    start = text.rfind("\n", 0, pos) + 1
    end = start
    while end < len(text) and text[end] in " \t":
        end += 1
    return text[start:end]


def _line_end(text: str, pos: int) -> int:
    """Skips same-line trivia after ``pos`` and returns the offset before the break."""
    size = len(text)
    while pos < size:
        if text[pos] in " \t":
            pos += 1
        elif text.startswith("//", pos):
            while pos < size and text[pos] not in "\r\n":
                pos += 1
        elif text.startswith("/*", pos):
            pos = text.find("*/", pos + 2) + 2
        else:
            break
    return pos


def _check_json(value: Value) -> None:
    validate_value(value)

    def visit(node: Value) -> None:
        if isinstance(node, dict):
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
        elif node is MISSING or type(node) not in (str, bool, int, float, type(None)):
            raise ConfigurationError(
                "Unsupported JSON value.",
                hint="Use strings, numbers, booleans, null, arrays, and objects.",
            )
        elif isinstance(node, float) and not math.isfinite(node):
            raise ConfigurationError(
                "Unsupported JSON number.",
                hint="Use finite numbers; NaN and infinity are not valid JSON.",
            )
        elif isinstance(node, str):
            try:
                node.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ConfigurationError(
                    "Unsupported JSON string.",
                    hint="Remove lone UTF-16 surrogate characters.",
                ) from error

    visit(value)


def _compact(value: Value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _pretty(value: Value, unit: str, newline: str, base: str) -> str:
    """Renders a value with one child per line; ``base`` indents the closing bracket."""
    inner = base + unit
    if isinstance(value, dict) and value:
        members = [
            f"{inner}{json.dumps(key, ensure_ascii=False)}: "
            f"{_pretty(child, unit, newline, inner)}"
            for key, child in value.items()
        ]
        return f"{{{newline}{f',{newline}'.join(members)}{newline}{base}}}"
    if isinstance(value, list) and value:
        elements = [f"{inner}{_pretty(c, unit, newline, inner)}" for c in value]
        return f"[{newline}{f',{newline}'.join(elements)}{newline}{base}]"
    return _compact(value)


def _render(
    value: Value, unit: str, newline: str, base: str, *, multiline: bool
) -> str:
    if multiline and isinstance(value, (dict, list)) and value:
        return _pretty(value, unit, newline, base)
    return _compact(value)


def _newline(text: str) -> str:
    index = text.find("\n")
    return "\r\n" if index > 0 and text[index - 1] == "\r" else "\n"


def _infer_indent(text: str, root: Node | None, default: str) -> str:
    if root is not None:
        for item in root.items:
            prefix = text[text.rfind("\n", 0, item.start) + 1 : item.start]
            if prefix and not prefix.strip():
                return prefix
    return default


def _apply(text: str, edits: list[TextEdit]) -> str:
    out: list[str] = []
    cursor = 0
    for edit in sorted(edits, key=lambda e: (e.start, e.end)):
        out.append(text[cursor : edit.start])
        out.append(edit.text)
        cursor = edit.end
    out.append(text[cursor:])
    return "".join(out)


@dataclass(frozen=True)
class JsoncDocument:
    """A parsed document; editing methods return new documents.

    Attributes:
        text: Exact source text, including comments and any leading BOM.
        root: Root object, or ``None`` for blank or comment-only text.
        newline: Line break used for inserted lines.
        indent_unit: Indentation unit inferred from the document.
    """

    text: str
    root: Node | None
    newline: str
    indent_unit: str

    def value(self) -> dict[str, Value]:
        """Decodes the document into detached semantic values."""
        if self.root is None:
            return {}
        return cast(dict[str, Value], _node_value(self.root))

    def get(self, path: Path) -> Value:
        """Returns the decoded value at ``path``, or ``MISSING`` when absent."""
        if not path:
            return self.value()
        _, item, matched = self._lookup(path)
        if item is None or matched != len(path):
            return MISSING
        return _node_value(item.node)

    def set(self, path: Path, value: Value) -> JsoncDocument:
        """Sets ``path``, creating missing intermediate objects.

        Arrays replaced by arrays are edited by position, so unchanged leading
        elements keep their comments and formatting.

        Args:
            path: Object keys and array indexes leading to the value.
            value: JSON-compatible replacement value.

        Returns:
            The edited document.

        Raises:
            ConfigurationError: If the path cannot be created or the value is not JSON.
        """
        _check_json(value)
        parents, item, matched = self._lookup(path)
        if item is not None and matched == len(path):
            if item.node.kind is NodeKind.ARRAY and isinstance(value, list):
                return self._set_array(path, item.node, value)
            return self._replace(parents, item, value)
        return self._create(path, parents, matched, value)

    def append(self, path: Path, value: Value) -> JsoncDocument:
        """Appends ``value`` to the array at ``path``."""
        _check_json(value)
        _, item, matched = self._lookup(path)
        if not path:
            raise self._bad_path(path)
        if item is None or matched != len(path) or item.node.kind is not NodeKind.ARRAY:
            raise self._bad_path(path)
        return self._insert(item.node, None, value)

    def delete(self, path: Path) -> JsoncDocument:
        """Removes the member or element at ``path``.

        Comments on their own lines above the removed item are retained.

        Raises:
            ConfigurationError: If ``path`` does not exist.
        """
        parents, item, matched = self._lookup(path)
        if item is None or matched != len(path) or not path:
            raise self._bad_path(path)
        return self._delete(parents[-1], item)

    def _bad_path(self, path: Path) -> ConfigurationError:
        return ConfigurationError(
            f"Cannot edit JSONC path {'/'.join(map(str, path)) or '<root>'}.",
            hint="Use existing object keys and array indexes; objects can be created.",
        )

    def _lookup(self, path: Path) -> tuple[list[Node], Item | None, int]:
        """Resolves as much of ``path`` as exists.

        Returns the traversed containers (root first), the last item reached, and how
        many path elements resolved. When resolution stops early, the final entry is
        the deepest node reached, where creation would occur.
        """
        parents: list[Node] = []
        item: Item | None = None
        node = self.root
        matched = 0
        for step in path:
            if node is None:
                break
            found: Item | None = None
            if node.kind is NodeKind.OBJECT and isinstance(step, str):
                found = next((i for i in node.items if i.key == step), None)
            elif (
                node.kind is NodeKind.ARRAY
                and isinstance(step, int)
                and 0 <= step < len(node.items)
            ):
                found = node.items[step]
            if found is None:
                break
            parents.append(node)
            item = found
            node = found.node
            matched += 1
        if matched < len(path) and node is not None:
            parents.append(node)
        return parents, item, matched

    def _reparse(self, text: str) -> JsoncDocument:
        return parse_jsonc(text, allow_empty=True, default_indent=self.indent_unit)

    def _replace(self, parents: list[Node], item: Item, value: Value) -> JsoncDocument:
        node = item.node
        base = _leading_ws(self.text, item.start)
        parent = parents[-1]
        multiline = "\n" in self.text[node.start : node.end] or (
            "\n" in self.text[parent.start : item.start]
        )
        rendered = _render(
            value, self.indent_unit, self.newline, base, multiline=multiline
        )
        return self._reparse(
            _apply(self.text, [TextEdit(node.start, node.end, rendered)])
        )

    def _set_array(self, path: Path, node: Node, values: list[Value]) -> JsoncDocument:
        doc: JsoncDocument = self
        current = [_node_value(item.node) for item in node.items]
        common = 0
        while common < min(len(current), len(values)) and semantic_equal(
            current[common], values[common]
        ):
            common += 1
        for index in range(common, min(len(current), len(values))):
            doc = doc.set((*path, index), values[index])
        for extra in values[len(current) :]:
            doc = doc.append(path, extra)
        for index in range(len(current) - 1, len(values) - 1, -1):
            doc = doc.delete((*path, index))
        return doc

    def _create(
        self, path: Path, parents: list[Node], matched: int, value: Value
    ) -> JsoncDocument:
        remaining = path[matched:]
        if not remaining or not all(isinstance(step, str) for step in remaining):
            raise self._bad_path(path)
        keys = cast(tuple[str, ...], remaining)
        nested: Value = value
        for key in reversed(keys[1:]):
            nested = {key: nested}
        if self.root is None:
            return self._create_root({keys[0]: nested})
        container = parents[-1]
        if container.kind is not NodeKind.OBJECT:
            raise self._bad_path(path)
        return self._insert(container, keys[0], nested)

    def _create_root(self, member: dict[str, Value]) -> JsoncDocument:
        text = self.text
        body = _pretty(member, self.indent_unit, self.newline, "")
        lead = "" if not text or text.endswith("\n") else self.newline
        return self._reparse(f"{text}{lead}{body}{self.newline}")

    def _insert(self, container: Node, key: str | None, value: Value) -> JsoncDocument:
        """Inserts one member or element after the container's last item."""
        text = self.text
        unit = self.indent_unit
        nl = self.newline
        items = container.items
        close = container.end - 1
        is_object = container.kind is NodeKind.OBJECT

        def member(indent: str, *, multiline: bool) -> str:
            rendered = _render(value, unit, nl, indent, multiline=multiline)
            if key is None:
                return rendered
            separator = ": "
            if items and items[-1].key is not None:
                last = items[-1]
                gap = text[last.start : last.node.start]
                colon = gap[gap.rfind('"') + 1 :]
                if colon.strip() == ":" and "\n" not in colon:
                    separator = colon
            return f"{json.dumps(key, ensure_ascii=False)}{separator}{rendered}"

        if not items:
            body = text[container.start + 1 : close]
            open_indent = _leading_ws(text, container.start)
            inner = open_indent + unit
            expanded = f"{nl}{inner}{member(inner, multiline=True)}{nl}{open_indent}"
            line_start = text.rfind("\n", 0, close) + 1
            if not body.strip() and "\n" not in body:
                if not is_object and not isinstance(value, (dict, list)):
                    edit = TextEdit(
                        container.start + 1, close, member(inner, multiline=False)
                    )
                else:
                    edit = TextEdit(container.start + 1, close, expanded)
            elif not text[line_start:close].strip():
                edit = TextEdit(
                    line_start,
                    line_start,
                    f"{inner}{member(inner, multiline=True)}{nl}",
                )
            else:
                edit = TextEdit(close, close, expanded)
            return self._reparse(_apply(text, [edit]))

        last = items[-1]
        anchor = last.comma + 1 if last.comma is not None else last.end
        multiline = "\n" in text[container.start : items[0].start] and (
            "\n" in text[anchor:close]
        )
        if not multiline:
            if last.comma is None:
                edit = TextEdit(last.end, last.end, f", {member('', multiline=False)}")
            else:
                edit = TextEdit(anchor, anchor, f" {member('', multiline=False)},")
            return self._reparse(_apply(text, [edit]))

        indent = _leading_ws(text, last.start)
        eol = _line_end(text, anchor)
        line = f"{nl}{indent}{member(indent, multiline=True)}"
        edits: list[TextEdit] = []
        if last.comma is None:
            edits.append(TextEdit(last.end, last.end, ","))
        else:
            line += ","
        edits.append(TextEdit(eol, eol, line))
        return self._reparse(_apply(text, edits))

    def _delete(self, container: Node, item: Item) -> JsoncDocument:
        text = self.text
        items = container.items
        index = items.index(item)
        anchor = item.comma + 1 if item.comma is not None else item.end
        eol = _line_end(text, anchor)
        line_start = text.rfind("\n", 0, item.start) + 1
        own_line = (
            not text[line_start : item.start].strip()
            and eol < len(text)
            and text[eol] in "\r\n"
        )
        edits: list[TextEdit] = []
        if own_line:
            end = eol + 2 if text.startswith("\r\n", eol) else eol + 1
            edits.append(TextEdit(line_start, end, ""))
            if item.comma is None and index > 0 and items[index - 1].comma is not None:
                comma = cast(int, items[index - 1].comma)
                edits.append(TextEdit(comma, comma + 1, ""))
        elif item.comma is not None:
            end = anchor
            while end < len(text) and text[end] in " \t":
                end += 1
            edits.append(TextEdit(item.start, end, ""))
        elif index > 0:
            previous = cast(int, items[index - 1].comma)
            edits.append(TextEdit(previous, item.end, ""))
        else:
            edits.append(TextEdit(item.start, item.end, ""))
        return self._reparse(_apply(text, edits))


def parse_jsonc(
    text: str,
    *,
    strict: bool = False,
    allow_empty: bool = False,
    default_indent: str = "  ",
) -> JsoncDocument:
    """Parses one JSONC object into a lossless, span-based document.

    Args:
        text: Document text; a leading BOM, comments, and trailing commas are retained.
        strict: Reject comments and trailing commas (plain JSON).
        allow_empty: Accept blank or comment-only text as a document with no root.
        default_indent: Indentation unit used when none can be inferred.

    Returns:
        The parsed document.

    Raises:
        ConfigurationError: On syntax errors, duplicate keys, a non-object root, or
            documents beyond 1 MB, 100 levels, or 10000 nodes.
    """
    if len(text.encode("utf-8", errors="surrogatepass")) > _MAX_BYTES:
        raise _limits()
    parser = _Parser(text, strict=strict)
    parser.skip_trivia()
    root: Node | None = None
    if parser.pos >= len(text):
        if not allow_empty:
            raise parser.fail("expected a JSON object")
    else:
        if text[parser.pos] != "{":
            raise parser.fail("the document root must be an object")
        root = parser.value(0)
        parser.skip_trivia()
        if parser.pos < len(text):
            raise parser.fail("unexpected content after the root object")
    return JsoncDocument(
        text, root, _newline(text), _infer_indent(text, root, default_indent)
    )


def decode_jsonc(text: str) -> dict[str, Value]:
    """Decodes a JSONC object into detached, type-aware semantic values."""
    return parse_jsonc(text).value()


def decode_jsonc_baseline(text: str) -> dict[str, Value]:
    """Decodes a strict JSON owned-baseline document and validates its values."""
    value = parse_jsonc(text, strict=True).value()
    validate_value(value)
    return value


def dumps_jsonc(value: dict[str, Value], indent: str = "  ") -> str:
    """Renders a new document with one entry per line and a final newline.

    Args:
        value: JSON-compatible mapping.
        indent: Indentation unit.

    Returns:
        Document text.
    """
    _check_json(value)
    return f"{_pretty(value, indent, chr(10), '')}\n"


def encode_jsonc_baseline(value: dict[str, Value]) -> str:
    """Encodes owned values deterministically, without local comments."""

    def ordered(node: Value) -> Value:
        if isinstance(node, dict):
            return {key: ordered(node[key]) for key in sorted(node)}
        if isinstance(node, list):
            return [ordered(child) for child in node]
        return node

    content = dumps_jsonc(cast(dict[str, Value], ordered(value)))
    decode_jsonc_baseline(content)
    return content
