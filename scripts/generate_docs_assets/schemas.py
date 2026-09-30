"""Field tables for the machine interface, rendered from the published JSON Schemas."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from protostar.cli.schema import application_schema, review_schema
from scripts.generate_docs_assets.common import (
    _format_markdown_table,
    _write_generated_doc,
)

Schema = dict[str, Any]

HEADERS = ("Key", "Type", "Meaning")


def _record(schema: Schema) -> Schema:
    """Returns the object schema inside an array, a nullable, or the schema itself."""
    if "items" in schema:
        return _record(schema["items"])
    for option in schema.get("oneOf", ()):
        if option.get("type") != "null":
            return _record(option)
    return schema


def _values(values: Sequence[object]) -> str:
    return ", ".join("`null`" if value is None else f"`{value}`" for value in values)


def _type(schema: Schema) -> str:
    """Names a schema's type in the words the tables use."""
    if "const" in schema:
        return _values([schema["const"]])
    if "enum" in schema:
        return _values(schema["enum"])
    options = schema.get("oneOf")
    if options:
        if all("const" in option for option in options):
            return "one of the values below"
        return " or ".join(_type(option) for option in options)
    kind = schema.get("type")
    if isinstance(kind, list):
        return " or ".join(f"`{name}`" for name in kind)
    if kind == "array":
        return f"array of {_type(schema['items'])}"
    if kind is None:
        return "any"
    return f"`{kind}`"


def _rows(record: Schema, *, prefix: str = "") -> list[list[str]]:
    """Returns one row per property of a record: its key, type, and meaning."""
    return [
        [f"`{prefix}{key}`", _type(prop), prop["description"]]
        for key, prop in record["properties"].items()
    ]


def _write(name: str, rows: list[list[str]], headers: Sequence[str] = HEADERS) -> None:
    _write_generated_doc(
        f"table_schema_{name}.md", _format_markdown_table(headers, rows)
    )


def generate_schema_tables() -> None:
    """Writes the field tables of the review and application envelopes."""
    review = review_schema()
    application = application_schema()
    body = review["properties"]["review"]["properties"]
    conflict = _record(body["conflicts"])

    _write("review_envelope", _rows(review))
    _write("application_envelope", _rows(application))
    _write("template", _rows(_record(review["properties"]["template"])))
    _write("review", _rows(_record(review["properties"]["review"])))
    _write("result", _rows(_record(application["properties"]["result"])))

    # The three decision lists share one record and each adds a key.
    shared = [["all four", *row] for row in _rows(conflict)]
    added = [
        [f"`{name}`", *row]
        for name, extra in (
            ("resolved", "resolution"),
            ("proposals", "resolution"),
            ("preserved", "deleted"),
        )
        for row in _rows(
            {"properties": {extra: _record(body[name])["properties"][extra]}}
        )
    ]
    _write(
        "decision",
        [*shared, *added],
        ("Present in", *HEADERS),
    )
    reasons = conflict["properties"]["reason"]["oneOf"]
    _write(
        "reasons",
        [[f"`{option['const']}`", option["description"]] for option in reasons],
        ("Reason", "Meaning"),
    )
