"""AST-preserving TOML merging, manipulation, and formatting."""

import logging
import re
import tomllib
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

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
from .merge import (
    MISSING,
    MergeConflict,
    MergeLocation,
    MergePolicy,
    Value,
    reconcile,
    semantic_equal,
)

logger = logging.getLogger("protostar")

TOOL_SECTION_NAMES = {
    "ruff": "Ruff",
    "mypy": "Mypy",
    "ty": "Ty",
    "pyrefly": "Pyrefly",
    "pytest": "Pytest",
    "coverage": "Pytest",
    "commitizen": "Commitizen",
    "rumdl": "rumdl",
}

SET_LIKE_TOML_PATHS = frozenset(
    {
        ("tool", "ruff", "lint", "select"),
        ("tool", "ruff", "lint", "extend-select"),
        ("tool", "ruff", "lint", "ignore"),
        ("tool", "ruff", "lint", "extend-ignore"),
        ("tool", "rumdl", "disable"),
        ("project", "classifiers"),
    }
)


@dataclass(frozen=True)
class AggregatedToml:
    """Semantic desired value paired with its comment-preserving TOML AST."""

    value: dict[str, Value]
    document: Any


@dataclass(frozen=True)
class TomlReconciliation:
    """AST output, owned composite baseline, and concrete conflicts."""

    content: str
    baseline: Value
    conflicts: tuple[MergeConflict, ...]


def aggregate_toml_document(
    contributions: list[StructuredContribution],
) -> AggregatedToml:
    """Aggregates semantic precedence and the corresponding desired TOML AST."""
    desired: dict[str, Value] = {}
    desired_doc = tomlkit.document()
    owners: dict[tuple[str, ...], str] = {}

    def add_semantic(
        target: dict[str, Value],
        incoming: dict[str, Value],
        producer: str,
        path: tuple[str, ...] = (),
    ) -> None:
        for key, value in incoming.items():
            keys = (*path, key)
            current = target.get(key, MISSING)
            if isinstance(value, dict) and isinstance(current, dict):
                add_semantic(current, value, producer, keys)
                continue
            old = owners.get(keys)
            if (
                current is not MISSING
                and not semantic_equal(current, value)
                and old != producer
                and not (
                    producer.startswith("template:")
                    or (
                        producer.startswith("module:")
                        and old is not None
                        and old.startswith("module:")
                    )
                )
            ):
                raise ConfigurationError(
                    f"Ambiguous TOML producers at {'.'.join(keys)}.",
                    hint="Use documented module sequence/template precedence or remove conflicting declarations.",
                )
            target[key] = deepcopy(value)
            owners[keys] = producer
            if isinstance(value, dict):
                target[key] = {}
                add_semantic(cast(dict[str, Value], target[key]), value, producer, keys)

    def overlay_ast(target: Any, incoming: Any) -> None:
        overlap_seen = False
        separator_added = False
        for key, value in incoming.items():
            existed = key in target
            if (
                existed
                and isinstance(target[key], tomlkit.items.AbstractTable)
                and isinstance(value, tomlkit.items.AbstractTable)
                and not isinstance(target[key], AoT)
                and not isinstance(value, AoT)
            ):
                overlay_ast(target[key], value)
            else:
                if (
                    not existed
                    and overlap_seen
                    and not separator_added
                    and isinstance(target, tomlkit.items.AbstractTable)
                    and not isinstance(value, tomlkit.items.AbstractTable)
                ):
                    target.add(tomlkit.nl())
                    separator_added = True
                target[key] = deepcopy(value)
            overlap_seen = overlap_seen or existed

    for contribution in sorted(
        contributions, key=lambda item: item.producer.startswith("template:")
    ):
        data = cast(dict[str, Value], validate_configuration(contribution.content))
        add_semantic(desired, data, contribution.producer)
        overlay_ast(desired_doc, tomlkit.parse(contribution.content))
    return AggregatedToml(desired, desired_doc)


def aggregate_toml(contributions: list[StructuredContribution]) -> dict[str, Value]:
    """Returns aggregated semantic intent for validation and pure callers."""
    return aggregate_toml_document(contributions).value


def reconcile_toml(
    original: str,
    desired: dict[str, Value],
    base: Value,
    location: MergeLocation,
    *,
    overwrite: bool = False,
    initializing: bool = False,
    missing_file: bool = False,
    desired_ast: Any | None = None,
) -> TomlReconciliation:
    """Applies semantic decisions to the local AST without global formatting."""
    try:
        doc = tomlkit.parse(original)
    except tomlkit.exceptions.TOMLKitError as e:
        raise ConfigurationError(
            "Invalid structured TOML file.",
            hint="Correct the target TOML syntax before retrying.",
        ) from e
    local = cast(dict[str, Value], doc.unwrap())
    clean_managed_tools = isinstance(base, dict) and semantic_equal(
        local.get("tool", MISSING), base.get("tool", MISSING)
    )
    inserted_tool_section = False
    if overwrite or initializing:
        # Explicit target authorization owns declared leaves, never foreign siblings.
        baseline: Value = deepcopy(base) if isinstance(base, dict) else {}

        def overlay(target: dict[str, Value], incoming: dict[str, Value]) -> None:
            for key, value in incoming.items():
                if isinstance(value, dict) and isinstance(target.get(key), dict):
                    overlay(cast(dict[str, Value], target[key]), value)
                else:
                    target[key] = deepcopy(value)

        value = deepcopy(local)
        overlay(value, desired)
        overlay(cast(dict[str, Value], baseline), desired)
        conflicts: tuple[MergeConflict, ...] = ()
    else:
        result = reconcile(
            base,
            MISSING if missing_file else local,
            desired,
            location,
            MergePolicy(SET_LIKE_TOML_PATHS),
        )
        if result.value is MISSING:
            return TomlReconciliation(original, result.baseline, result.conflicts)
        value = cast(dict[str, Value], result.value)
        baseline = result.baseline
        conflicts = result.conflicts

    def desired_node(keys: tuple[str, ...]) -> Any | None:
        node = desired_ast
        if node is None:
            return None
        try:
            for key in keys:
                node = node[key]
        except (KeyError, TypeError):
            return None
        return node

    def patch(
        ast: Any,
        before: dict[str, Value],
        after: dict[str, Value],
        keys: tuple[str, ...] = (),
    ) -> None:
        nonlocal inserted_tool_section
        for key, value in after.items():
            previous = before.get(key, MISSING)
            if semantic_equal(previous, value):
                continue
            path = (*keys, key)
            styled = desired_node(path)
            styled_value: Value = MISSING
            if styled is not None and hasattr(styled, "unwrap"):
                styled_value = cast(Value, styled.unwrap())
            if isinstance(previous, dict) and isinstance(value, dict):
                patch(ast[key], previous, value, path)
            elif previous is MISSING and isinstance(value, dict) and path == ("tool",):
                styled_keys = (
                    list(styled.keys())
                    if styled is not None and hasattr(styled, "keys")
                    else []
                )
                first_section = (
                    TOOL_SECTION_NAMES.get(styled_keys[0]) if styled_keys else None
                )
                prior = next(
                    (
                        item
                        for _, item in reversed(ast.body)
                        if isinstance(item, tomlkit.items.AbstractTable)
                    ),
                    None,
                )
                if not initializing and prior is not None and first_section is not None:
                    prior.add(tomlkit.nl())
                    if "# Tool Configuration" not in original:
                        prior.add(tomlkit.comment("=" * 50))
                        prior.add(tomlkit.comment("Tool Configuration"))
                        prior.add(tomlkit.comment("=" * 50))
                        prior.add(tomlkit.nl())
                    prior.add(tomlkit.comment(f"---- {first_section} ---- #"))
                ast[key] = tomlkit.table(is_super_table=True)
                patch(ast[key], {}, value, path)
            elif styled is not None and semantic_equal(styled_value, value):
                if previous is MISSING:
                    section: str | None = None
                    banner = False
                    if len(path) == 2 and path[0] == "tool":
                        section = TOOL_SECTION_NAMES.get(key)
                        inserted_tool_section = (
                            inserted_tool_section or section is not None
                        )
                    elif path == ("tool",) and hasattr(styled, "keys"):
                        first_tool = cast(str | None, next(iter(styled.keys()), None))
                        if first_tool is not None:
                            section = TOOL_SECTION_NAMES.get(first_tool)
                        banner = True
                    if not initializing and section is not None:
                        marker = f"# ---- {section} ---- #"
                        body = ast.body if hasattr(ast, "body") else ast.value.body
                        prior = next(
                            (
                                item
                                for _, item in reversed(body)
                                if isinstance(item, tomlkit.items.AbstractTable)
                            ),
                            None,
                        )
                        if prior is not None:
                            prior.add(tomlkit.nl())
                            if banner and "# Tool Configuration" not in original:
                                prior.add(tomlkit.comment("=" * 50))
                                prior.add(tomlkit.comment("Tool Configuration"))
                                prior.add(tomlkit.comment("=" * 50))
                                prior.add(tomlkit.nl())
                            if marker not in original:
                                prior.add(tomlkit.comment(f"---- {section} ---- #"))
                ast[key] = deepcopy(styled)
            elif (
                isinstance(previous, list)
                and isinstance(value, list)
                and path in SET_LIKE_TOML_PATHS
                and value[: len(previous)] == previous
            ):
                for member in value[len(previous) :]:
                    ast[key].append(tomlkit.item(member))
            else:
                ast[key] = tomlkit.item(value)

    patch(doc, local, value)
    if semantic_equal(local, value):
        content = original
    elif location.file == "pyproject.toml" and (
        initializing or (clean_managed_tools and inserted_tool_section)
    ):
        content = format_pyproject_toml(doc)
    else:
        content = tomlkit.dumps(doc)
    return TomlReconciliation(content, baseline, conflicts)


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

    # 3. Rebuild managed visual separators after AST table ordering. Parsed
    # comments are attached to the preceding table, so retaining old markers
    # while moving tables can label the wrong section.
    new_content = _TOOL_CONFIG_BANNER_RE.sub("", new_content)
    for marker_re, _, _ in _COMPILED_TOOL_HEADERS:
        new_content = marker_re.sub("", new_content)

    # 4. Apply visual separators safely using anchored regex
    for marker_re, table_re, marker in _COMPILED_TOOL_HEADERS:
        if not marker_re.search(new_content):
            new_content = table_re.sub(
                rf"\n{marker}\n\n\g<0>",
                new_content,
                count=1,
            )

    # 5. Add main Tool Configuration banner before the first tool header if not exists
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

    # 6. Normalize spacing (no more than one consecutive blank line, ending with a single newline)
    new_content = _MULTI_NEWLINE_RE.sub("\n\n", new_content).rstrip() + "\n"
    new_content = re.sub(
        r"\n+[ \t]*\[dependency-groups\]",
        "\n\n[dependency-groups]",
        new_content,
        count=1,
    )

    # 7. Safety Parity Guard: Guarantee data integrity
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
        if doc:
            doc.add(tomlkit.nl())
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
            item = tomlkit.parse(
                f'entry = {{ include-group = "{edge.include.value}" }}\n'
            )["entry"]
            entries.append(item)
            changed = True
    return tomlkit.dumps(doc) if changed else original
