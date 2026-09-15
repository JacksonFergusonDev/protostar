"""AST-preserving TOML merging, manipulation, and formatting."""

import logging
import re
import tomllib
from collections.abc import Callable
from typing import Any

import tomlkit
import tomlkit.items
from tomlkit.items import AoT, Table

from .errors import ConfigurationError
from .intent import (
    ContributionPolicy,
    DependencyInclude,
    ResolverFootprint,
    StructuredContribution,
    validate_configuration,
)
from .interpolation import extract_variables, render_template
from .manifest import Severity

logger = logging.getLogger("protostar")

__all__ = ["deep_merge_tomlkit", "format_pyproject_toml", "merge_toml_payloads"]

_RAW_TOOL_HEADERS = [
    ("Ruff", r"\[+tool\.ruff(?:\.[^\]]+)?\]+"),
    ("Mypy", r"\[+tool\.mypy(?:\.[^\]]+)?\]+"),
    ("Ty", r"\[+tool\.ty(?:\.[^\]]+)?\]+"),
    ("Pyrefly", r"\[+tool\.pyrefly(?:\.[^\]]+)?\]+"),
    ("Pytest", r"\[+tool\.(?:pytest|coverage)(?:\.[^\]]+)?\]+"),
    ("Commitizen", r"\[+tool\.commitizen(?:\.[^\]]+)?\]+"),
    ("rumdl", r"\[+tool\.rumdl(?:\.[^\]]+)?\]+"),
]

_COMPILED_TOOL_HEADERS: list[tuple[re.Pattern[str], re.Pattern[str], str]] = [
    (
        re.compile(rf"^{re.escape(f'# ---- {title} ---- #')}", re.MULTILINE),
        re.compile(rf"^{table_regex}\s*$", re.MULTILINE),
        f"# ---- {title} ---- #",
    )
    for title, table_regex in _RAW_TOOL_HEADERS
]

_FIRST_TOOL_HEADER_RE: re.Pattern[str] = re.compile(
    r"^# ---- (?:Ruff|Mypy|Ty|Pyrefly|Pytest|Commitizen|rumdl) ---- #\s*$",
    re.MULTILINE,
)

_MULTI_NEWLINE_RE: re.Pattern[str] = re.compile(r"\n{3,}")

_TOOL_CONFIG_BANNER_RE: re.Pattern[str] = re.compile(
    r"^[ \t]*# =+\s*\n[ \t]*# Tool Configuration\s*\n[ \t]*# =+\s*\n*",
    re.MULTILINE,
)

_TOOL_SECTION_HEADER_RE: re.Pattern[str] = re.compile(
    r"^[ \t]*# ---- [A-Za-z0-9_-]+ ---- #[ \t]*\n*",
    re.MULTILINE,
)


def deep_merge_tomlkit(
    base: Any,
    payload: Any,
    overwrite: bool = False,
    path: tuple[str, ...] = (),
    on_conflict: Callable[[str, Severity], None] | None = None,
) -> None:
    """Recursively deep-merges a tomlkit payload into a base document.

    Args:
        base: The existing tomlkit document or table to mutate.
        payload: The incoming tomlkit table to merge into the base.
        overwrite: If True, unmatched scalar keys in the base will be purged,
            and array-of-tables will be completely replaced.
        path: The tuple of keys representing the current path in the document.
        on_conflict: Callback invoked with (message, severity) when a type collision occurs.
    """

    def reject_controls(value: Any) -> None:
        if hasattr(value, "items"):
            for key, child in value.items():
                if key in ("__replace__", "__remove__"):
                    raise ConfigurationError(
                        "Template control sentinels are unsupported.",
                        hint="Remove __replace__/__remove__ and declare configuration directly.",
                    )
                reject_controls(child)
        elif isinstance(value, (list, AoT)):
            for child in value:
                reject_controls(child)

    reject_controls(payload)
    # Purge scalar/array keys in base that are missing from the payload
    # to enforce strict AST overwriting, while preserving sibling tables.
    # We explicitly protect the root document and the [project] and [dependency-groups] tables from being purged.
    if overwrite and len(path) > 0 and path[0] not in ("project", "dependency-groups"):
        keys_to_remove = []
        for b_key, b_val in base.items():
            if b_key not in payload and not isinstance(
                b_val, (tomlkit.items.Table, tomlkit.items.AoT)
            ):
                keys_to_remove.append(b_key)
        for k in keys_to_remove:
            del base[k]

    for key, value in payload.items():
        if key in base:
            if isinstance(value, tomlkit.items.Table):
                # Type Parity Guard
                if not isinstance(base[key], tomlkit.items.Table):
                    if on_conflict:
                        on_conflict(
                            f"TOML Merge Collision: Expected a Table for key '{key}', but found {type(base[key]).__name__}. Skipping injection.",
                            Severity.WARNING,
                        )
                    continue

                has_sub_tables = any(
                    isinstance(v, (tomlkit.items.Table, tomlkit.items.AoT))
                    for v in value.values()
                )

                is_protected_table = (
                    key in ("project", "dependency-groups") and len(path) == 0
                ) or (len(path) > 0 and path[0] in ("project", "dependency-groups"))

                if overwrite and not has_sub_tables and not is_protected_table:
                    base[key] = value
                else:
                    deep_merge_tomlkit(
                        base[key], value, overwrite, (*path, key), on_conflict
                    )

            elif isinstance(value, tomlkit.items.AoT):
                # Type Parity Guard
                if not isinstance(base[key], tomlkit.items.AoT):
                    if on_conflict:
                        on_conflict(
                            f"TOML Merge Collision: Expected an Array of Tables for key '{key}', but found {type(base[key]).__name__}. Skipping injection.",
                            Severity.WARNING,
                        )
                    continue

                if overwrite:
                    base[key] = value
                else:
                    for item in value:
                        base[key].append(item)
            elif isinstance(value, tomlkit.items.Array):
                if not isinstance(base[key], tomlkit.items.Array):
                    if on_conflict:
                        on_conflict(
                            f"TOML Merge Collision: Expected an Array for key '{key}', but found {type(base[key]).__name__}. Skipping injection.",
                            Severity.WARNING,
                        )
                    continue

                if (
                    overwrite
                    and len(path) > 0
                    and path[0] not in ("project", "dependency-groups")
                ):
                    base[key] = value
                else:
                    for item in value:
                        if item not in base[key]:
                            base[key].append(item)
            else:
                base[key] = value
        else:
            if isinstance(value, tomlkit.items.Table):
                value.add(tomlkit.nl())
            elif isinstance(value, tomlkit.items.AoT) and len(value) > 0:
                value[-1].add(tomlkit.nl())

            base[key] = value


def format_pyproject_toml(doc: Any) -> str:
    """Deterministically sorts tables and applies structured visual headers to pyproject.toml."""
    # 1. Deterministically sort top-level tables (scalar keys must precede all tables)
    root_order = ["project", "build-system", "dependency-groups"]

    def root_sort_key(item: tuple[Any, Any]) -> tuple[int, str]:
        k, v = item
        if k is None:
            return (999, "")
        k_str = k.key if hasattr(k, "key") else str(k)
        # Scalar/array keys at root level must precede table headers in TOML
        if not isinstance(v, (Table, AoT)) and not (
            hasattr(v, "is_table") and v.is_table()
        ):
            return (0, k_str)
        if k_str in root_order:
            return (1 + root_order.index(k_str), k_str)
        if k_str == "tool":
            return (500, k_str)
        return (100, k_str)

    if hasattr(doc, "body") and isinstance(doc.body, list):
        doc.body.sort(key=root_sort_key)
        if hasattr(doc, "_map") and isinstance(doc._map, dict):
            doc._map = {k: idx for idx, (k, _) in enumerate(doc.body) if k is not None}

    # 2. Deterministically sort tools within [tool]
    if (
        "tool" in doc
        and hasattr(doc["tool"], "value")
        and hasattr(doc["tool"].value, "body")
    ):
        tool_order = [
            "ruff",
            "mypy",
            "ty",
            "pyrefly",
            "pytest",
            "coverage",
            "commitizen",
            "rumdl",
        ]

        def tool_sort_key(item: tuple[Any, Any]) -> tuple[int, str]:
            k, _ = item
            if k is None:
                return (999, "")
            k_str = k.key if hasattr(k, "key") else str(k)
            if k_str in tool_order:
                return (tool_order.index(k_str), k_str)
            return (100, k_str)

        doc["tool"].value.body.sort(key=tool_sort_key)
        if hasattr(doc["tool"].value, "_map") and isinstance(
            doc["tool"].value._map, dict
        ):
            doc["tool"].value._map = {
                k: idx
                for idx, (k, _) in enumerate(doc["tool"].value.body)
                if k is not None
            }

    new_content = tomlkit.dumps(doc)
    raw_dump = new_content

    # 3. Apply visual separators safely using anchored regex
    for marker_re, table_re, marker in _COMPILED_TOOL_HEADERS:
        if not marker_re.search(new_content):
            new_content = table_re.sub(
                rf"\n{marker}\n\n\g<0>",
                new_content,
                count=1,
            )

    # 4. Add main Tool Configuration banner before the first tool header if not exists
    if "# Tool Configuration" not in new_content:
        tool_match = _FIRST_TOOL_HEADER_RE.search(new_content)
        if tool_match:
            header = (
                "# ==================================================\n"
                "# Tool Configuration\n"
                "# ==================================================\n\n"
            )
            new_content = (
                new_content[: tool_match.start()].rstrip()
                + "\n\n"
                + header
                + new_content[tool_match.start() :]
            )

    # 5. Normalize spacing (no more than one consecutive blank line, ending with a single newline)
    new_content = _MULTI_NEWLINE_RE.sub("\n\n", new_content).rstrip() + "\n"

    # 6. Safety Parity Guard: Guarantee data integrity
    try:
        expected_data = tomllib.loads(raw_dump)
        parsed_check = tomllib.loads(new_content)
        if parsed_check != expected_data:
            logger.warning(
                "AST Parity mismatch during pyproject.toml formatting; falling back to direct AST dump."
            )
            return raw_dump.rstrip() + "\n"
    except Exception as e:
        logger.warning(
            f"Validation error during pyproject.toml formatting ({e}); falling back to direct AST dump."
        )
        return raw_dump.rstrip() + "\n"

    return new_content


def merge_toml_payloads(
    original_content: str,
    payloads: list[str],
    is_pyproject: bool = False,
    overwrite: bool = False,
    on_conflict: Callable[[str, Severity], None] | None = None,
) -> str:
    """Merges multiple TOML payload strings into an existing TOML document string.

    Args:
        original_content: The existing TOML file contents.
        payloads: Raw TOML strings to merge.
        is_pyproject: If True, strips existing tool headers and formats with format_pyproject_toml.
        overwrite: If True, enables overwrite merging semantics.
        on_conflict: Callback invoked with (message, severity) on AST collisions.

    Returns:
        The resulting serialized TOML string.
    """
    clean_content = original_content
    if is_pyproject and clean_content:
        clean_content = _TOOL_CONFIG_BANNER_RE.sub("", clean_content)
        clean_content = _TOOL_SECTION_HEADER_RE.sub("", clean_content)

    doc = tomlkit.parse(clean_content) if clean_content else tomlkit.document()

    for payload in payloads:
        payload_doc = tomlkit.parse(payload)
        deep_merge_tomlkit(
            doc, payload_doc, overwrite=overwrite, on_conflict=on_conflict
        )

    if is_pyproject:
        return format_pyproject_toml(doc)
    return tomlkit.dumps(doc)


def declare_structured_contributions(
    path: str, content: str, producer: str, policy: ContributionPolicy
) -> tuple[StructuredContribution, ...]:
    """Separates personal pyproject seeds from managed tooling/build intent.

    Placeholder substitution is temporary and reversible: declaration must retain
    late-bound values for execution, rather than persisting dummy interpolation.
    """
    variables = {v: f"PROTOSTAR_LATE_{v}" for v in extract_variables(content)}
    data = validate_configuration(render_template(content, variables))
    project_data = data.get("project")
    footprint = (
        ResolverFootprint()
        if path == "pyproject.toml"
        and isinstance(project_data, dict)
        and "requires-python" in project_data
        else None
    )
    personal = {
        "name",
        "version",
        "description",
        "authors",
        "maintainers",
        "license",
        "license-files",
        "readme",
        "urls",
        "classifiers",
        "keywords",
    }
    if (
        path != "pyproject.toml"
        or policy != ContributionPolicy.MANAGED
        or not isinstance(project_data, dict)
        or not personal.intersection(project_data)
    ):
        return (StructuredContribution(producer, content, policy, footprint),)
    doc = tomlkit.parse(render_template(content, variables))
    project = doc["project"]
    seed = tomlkit.document()
    seed_project = tomlkit.table()
    for key in list(project):
        if key in personal:
            seed_project[key] = project.pop(key)
    seed["project"] = seed_project
    if not project:
        del doc["project"]

    def restore(text: str) -> str:
        for variable, token in variables.items():
            text = text.replace(token, f"<% {variable} %>")
        return text

    result = [
        StructuredContribution(
            producer, restore(tomlkit.dumps(seed)), ContributionPolicy.SEED_ONLY
        )
    ]
    if doc:
        result.append(
            StructuredContribution(
                producer, restore(tomlkit.dumps(doc)), policy, footprint
            )
        )
    return tuple(result)


def apply_dependency_includes(original: str, edges: list[DependencyInclude]) -> str:
    """Returns an AST-preserving additive application of typed group includes."""
    try:
        doc = tomlkit.parse(original)
    except tomlkit.exceptions.ParseError as e:
        raise ConfigurationError(
            "Invalid dependency configuration.",
            hint="Correct pyproject.toml before applying dependency includes.",
        ) from e
    groups = doc.get("dependency-groups")
    if groups is not None and not isinstance(groups, tomlkit.items.AbstractTable):
        raise ConfigurationError(
            "dependency-groups must be a TOML table.",
            hint="Correct the dependency-groups table.",
        )
    if groups is None:
        groups = tomlkit.table()
        doc["dependency-groups"] = groups
    changed = False
    for edge in edges:
        if edge.group not in groups:
            groups[edge.group] = tomlkit.array()
            changed = True
        if edge.include not in groups:
            groups[edge.include] = tomlkit.array()
            changed = True
        entries = groups[edge.group]
        if not isinstance(entries, tomlkit.items.Array) or not isinstance(
            groups[edge.include], tomlkit.items.Array
        ):
            raise ConfigurationError(
                "Dependency-group entries must be arrays.",
                hint="Use requirement strings and include-group records inside each group array.",
            )
        if not any(
            isinstance(e, dict) and e.get("include-group") == edge.include
            for e in entries
        ):
            item = tomlkit.inline_table()
            item["include-group"] = edge.include.value
            entries.append(item)
            changed = True
    return tomlkit.dumps(doc) if changed else original
