"""The pyproject.toml layout model: exactness, canonical order, and its guards."""

import importlib.resources
import itertools
import logging
import re
import tomllib
from pathlib import Path

import pytest
import tomlkit

from protostar.documents.pyproject_layout import (
    BANNER,
    TOOL_SECTION_NAMES,
    TOOL_SECTIONS,
    Section,
    _announced,
    _take_leading_comments,
    compose_children,
    format_document,
    insert_section,
    join_sections,
    place_new_sections,
    section_rank,
    section_title,
    split_sections,
)
from protostar.manifest import EnvironmentManifest
from protostar.modules import TOOLING_MODULES

SNAPSHOTS = Path(__file__).parent / "snapshots"
# ml_merged is the product of a merge, which never reformats; it is not a fresh layout.
FRESH_SNAPSHOTS = ["api", "astro", "cli", "lib", "ml"]

# Files a user might already have. Their bytes must survive a split and a join.
FOREIGN_FILES = {
    "irregular spacing and a top comment": (
        '# my project\n\n\n[project]\nname="x"   # inline\nversion = "1"\n\n\n\n'
        "# about ruff\n[tool.ruff]\nline-length=99\n\n[tool.black]\nx = 1\n"
    ),
    "no trailing newline": (
        '[project]\nname = "x"\nversion = "1"\n\n[tool.ruff]\nline-length = 99'
    ),
    "out of order tables": (
        '[project]\nname="x"\n\n[tool.ruff]\na=1\n\n[project.scripts]\n'
        'x="y"\n\n[tool.ruff.lint]\nselect=["E"]\n'
    ),
    "arrays of tables": (
        '[project]\nname="x"\n\n[[tool.mypy.overrides]]\nmodule=["a"]\n\n'
        '[[tool.mypy.overrides]]\nmodule=["b"]\n\n[tool.mypy]\nstrict=true\n'
    ),
    "crlf line endings": '[project]\r\nname = "x"\r\n\r\n[tool.ruff]\r\nline-length = 99\r\n',
    "dotted keys": '[project]\nname = "x"\n\n[tool]\nruff.line-length = 99\n',
    "inline tool table": '[project]\nname = "x"\n\n[tool]\nruff = { line-length = 99 }\n',
    "root scalars": 'title = "x"\n\n[project]\nname = "x"\n',
    "user-written managed headers": (
        "# ---- Ruff ---- #\n\n[tool.ruff]\nline-length = 88\n\n"
        "# ---- Mypy ---- #\n\n[tool.mypy]\nstrict = true\n"
    ),
    "unicode": '[project]\nname = "café"\ndescription = "日本語"\n',
    "comments only": "# nothing here\n",
    "empty": "",
}


@pytest.mark.parametrize("name", FOREIGN_FILES)
def test_splitting_and_joining_reproduces_every_byte(name: str) -> None:
    text = FOREIGN_FILES[name]

    assert join_sections(split_sections(tomlkit.parse(text))) == text


@pytest.mark.parametrize("name", FRESH_SNAPSHOTS)
def test_formatting_reproduces_a_freshly_generated_pyproject(name: str) -> None:
    text = (SNAPSHOTS / name / "pyproject.toml").read_text(encoding="utf-8")

    assert format_document(tomlkit.parse(text)) == text


# ---- canonical order, over every combination of tools ----

_TOOL_KEYS = [section.key for section in TOOL_SECTIONS if section.key != "protostar"]
_TABLE_FOR = {
    "coverage": "[tool.coverage.run]\nbranch = true\n",
    "pytest": '[tool.pytest.ini_options]\naddopts = "-q"\n',
    "mypy": '[tool.mypy]\nstrict = true\n\n[[tool.mypy.overrides]]\nmodule = ["t"]\n',
    "ruff": '[tool.ruff]\nline-length = 88\n\n[tool.ruff.lint]\nselect = ["E"]\n',
    "hatch": '[tool.hatch.build.targets.wheel]\npackages = ["src/x"]\n',
}


def _document_with(tools: tuple[str, ...]) -> str:
    """A pyproject in the worst order: uv's groups last, tools reversed, one unknown."""
    tables = [_TABLE_FOR.get(key, f"[tool.{key}]\nvalue = 1\n") for key in tools]
    return "\n".join(
        [
            '[project]\nname = "x"\nversion = "1"\n',
            *reversed(tables),
            "[tool.zzz_custom]\nvalue = 1\n",
            "[tool.protostar]\nversion = 1\n",
            '[dependency-groups]\ndev = ["ruff"]\n',
        ]
    )


def _tool_subsets() -> list[tuple[str, ...]]:
    return [
        subset
        for size in range(len(_TOOL_KEYS) + 1)
        for subset in itertools.combinations(_TOOL_KEYS, size)
    ]


@pytest.mark.parametrize("tools", _tool_subsets(), ids=lambda t: "+".join(t) or "none")
def test_layout_invariants_hold_for_every_combination_of_tools(
    tools: tuple[str, ...], caplog: pytest.LogCaptureFixture
) -> None:
    source = _document_with(tools)
    with caplog.at_level(logging.WARNING, logger="protostar"):
        formatted = format_document(tomlkit.parse(source))

    # The formatter proved parity instead of falling back, and changed no data.
    assert not caplog.records, [record.message for record in caplog.records]
    assert tomllib.loads(formatted) == tomllib.loads(source)
    # It is stable: formatting its own output changes nothing.
    assert format_document(tomlkit.parse(formatted)) == formatted

    lines = formatted.split("\n")
    header_lines = [
        i for i, line in enumerate(lines) if re.fullmatch(r"# ---- .+ ---- #", line)
    ]
    titles = [lines[i] for i in header_lines]
    assert len(titles) == len(set(titles)), "a header appears twice"

    def position(marker: str) -> int:
        return formatted.index(marker)

    banner = position(BANNER[1])
    assert position("[dependency-groups]") < banner
    if "hatch" in tools:
        assert position("[tool.hatch") < banner
    for key in _TOOL_KEYS:
        if key != "hatch" and key in tools:
            assert position(f"[tool.{key}") > banner
    # Unknown tools follow the known ones, and Protostar is always last.
    assert position("[tool.zzz_custom]") < position("[tool.protostar]")
    assert formatted.rstrip().endswith("version = 1")
    for key in tools:
        if key not in ("hatch", "coverage", "pytest"):
            assert position(f"[tool.{key}") < position("[tool.zzz_custom]")
    if "pytest" in tools and "coverage" in tools:
        assert formatted.count("# ---- Pytest ---- #") == 1


def test_formatting_ignores_where_previous_headers_were_left() -> None:
    """Headers in the wrong place are rebuilt, not relabelled."""
    source = (
        "# ---- Pytest ---- #\n\n[tool.ruff]\nline-length = 88\n\n"
        '# ---- Ruff ---- #\n\n[tool.pytest.ini_options]\naddopts = "-q"\n'
    )

    formatted = format_document(tomlkit.parse(source))

    assert formatted.index("# ---- Ruff ---- #") < formatted.index("[tool.ruff]")
    assert formatted.index("# ---- Pytest ---- #") < formatted.index("[tool.pytest")
    assert formatted.count("# ---- Ruff ---- #") == 1


def test_formatting_never_touches_the_inside_of_a_section() -> None:
    """Runs of blank lines inside a multi-line string are data, not layout."""
    source = '[project]\nname = "x"\ndescription = """a\n\n\n\nb"""\n'

    assert format_document(tomlkit.parse(source)).count("\n\n\n\n") == 1


# ---- inserting one section ----


def _sections(text: str) -> list[Section]:
    return split_sections(tomlkit.parse(text))


def test_insert_changes_only_the_bytes_at_its_seams() -> None:
    text = '[project]\nname = "x"\n\n[tool.ruff]\nline-length = 88\n\n[tool.black]\nx = 1\n'
    sections = _sections(text)
    before = [section.text for section in sections]

    insert_section(
        sections, Section(("tool", "mypy"), "[tool.mypy]\nstrict = true\n"), 2
    )

    after = [section.text for section in sections]
    assert after[:2] == before[:2]
    assert after[3:] == before[2:]
    assert after[2] == "[tool.mypy]\nstrict = true\n\n"
    assert tomllib.loads(join_sections(sections))["tool"]["mypy"] == {"strict": True}


def test_insert_at_the_end_supplies_a_missing_newline_and_blank_line() -> None:
    sections = _sections('[project]\nname = "x"')

    insert_section(sections, Section(("tool", "x"), "[tool.x]\na = 1\n"), 1)

    assert join_sections(sections) == '[project]\nname = "x"\n\n[tool.x]\na = 1\n'


def test_insert_uses_the_files_own_newline_style() -> None:
    sections = _sections('[project]\r\nname = "x"\r\n')

    insert_section(sections, Section(("tool", "x"), "[tool.x]\na = 1\n"), 1)

    text = join_sections(sections)
    assert "\r\n\r\n[tool.x]\r\na = 1\r\n" in text
    assert "\n" not in text.replace("\r\n", "")


# ---- composing a table's children ----


def test_compose_children_orders_and_separates_them() -> None:
    document = tomlkit.parse(
        "[tool.protostar]\nversion = 1\n[tool.protostar.context]\na = 1\n"
        "[tool.protostar.tools]\nmypy = true\n\n\n\n[tool.protostar.fallback]\nb = 2\n"
    )

    text = compose_children(
        document, ("tool", "protostar"), ("tools", "fallback", "context")
    )

    assert text == (
        "[tool.protostar]\nversion = 1\n\n[tool.protostar.tools]\nmypy = true\n\n"
        "[tool.protostar.fallback]\nb = 2\n\n[tool.protostar.context]\na = 1\n"
    )


def test_compose_children_keeps_comments_with_their_table() -> None:
    document = tomlkit.parse(
        "[tool.protostar]\nversion = 1\n\n[tool.protostar.b]\n# note about b\nx = 1\n"
        "\n[tool.protostar.a]\ny = 2\n"
    )

    text = compose_children(document, ("tool", "protostar"), ("a", "b"))

    assert text.index("[tool.protostar.a]") < text.index("[tool.protostar.b]")
    assert text.index("[tool.protostar.b]") < text.index("# note about b")


# ---- guards against drift ----


def _modules_tool_tables() -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    for module in TOOLING_MODULES:
        manifest = EnvironmentManifest()
        module.build(manifest)
        for contribution in manifest.filesystem.structured.get("pyproject.toml", []):
            parsed = tomllib.loads(
                contribution.content.replace("<% PYTHON_VERSION %>", "3")
            )
            tables.setdefault(module.config_key, set()).update(parsed.get("tool", {}))
    return tables


def test_every_tool_table_a_module_writes_has_a_layout_entry() -> None:
    """A new tool needs a spec entry, or its config lands unlabelled after the rest."""
    known = {section.key for section in TOOL_SECTIONS}
    unknown = {
        f"{module} writes tool.{table}"
        for module, tables in _modules_tool_tables().items()
        for table in tables - known
    }

    assert not unknown, sorted(unknown)


def test_every_tool_table_a_built_in_template_writes_has_a_layout_entry() -> None:
    known = {section.key for section in TOOL_SECTIONS}
    unknown: set[str] = set()
    templates = importlib.resources.files("protostar.templates")
    for path in templates.iterdir():
        if not path.name.endswith(".toml"):
            continue
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("dev", {}).get("pyproject", {}).values():
            content = entry if isinstance(entry, str) else entry["content"]
            content = re.sub(r"<%\s*[A-Z_]+\s*%>", "placeholder", content)
            unknown |= set(tomllib.loads(content).get("tool", {})) - known

    assert not unknown, sorted(unknown)


def test_section_names_come_from_the_layout_spec() -> None:
    assert {
        section.key: section.title for section in TOOL_SECTIONS if section.title
    } == TOOL_SECTION_NAMES


def test_tools_sharing_a_title_sit_next_to_each_other() -> None:
    order = sorted(
        TOOL_SECTIONS, key=lambda section: section_rank(("tool", section.key))
    )
    seen: list[str | None] = []
    for section in order:
        if not seen or seen[-1] != section.title:
            assert section.title not in seen, f"{section.title} is split up"
            seen.append(section.title)


def test_nothing_outside_the_layout_modules_reaches_into_tomlkit_internals() -> None:
    """tomlkit's private container state is not a stable API; only read the public body."""
    source_root = Path(__file__).parent.parent / "src" / "protostar"
    offenders: list[str] = []
    pattern = re.compile(r"\._map\b|\.body\.(?:sort|insert|remove|append|extend|pop)\(")
    for path in source_root.rglob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.name}:{number}: {line.strip()}")

    assert not offenders, offenders


# ---- the safety fallback is never silent ----

CORRUPTED = '[project]\nname = "corrupt"\n'


def test_a_fallback_is_reported_to_the_caller_and_returns_the_input(mocker) -> None:
    mocker.patch(
        "protostar.documents.pyproject_layout.format_sections", return_value=CORRUPTED
    )
    reasons: list[str] = []
    document = tomlkit.parse('[project]\nname = "app"\n')

    result = format_document(document, reasons.append)

    assert result == '[project]\nname = "app"\n'
    assert len(reasons) == 1
    assert "Parity mismatch" in reasons[0]


def test_a_successful_format_reports_nothing() -> None:
    reasons: list[str] = []

    format_document(tomlkit.parse('[project]\nname = "app"\n'), reasons.append)

    assert reasons == []


def test_reconcile_reports_when_it_could_not_format_a_new_pyproject(mocker) -> None:
    from protostar.documents.catalog import toml_spec
    from protostar.merge import MISSING, MergeLocation
    from protostar.toml_ast import reconcile_toml

    mocker.patch(
        "protostar.documents.pyproject_layout.format_sections", return_value=CORRUPTED
    )

    result = reconcile_toml(
        toml_spec("pyproject.toml"),
        "",
        {"project": {"name": "app"}},
        MISSING,
        MergeLocation("pyproject.toml"),
        initializing=True,
        missing_file=True,
    )

    assert len(result.layout_notes) == 1
    assert "Parity mismatch" in result.layout_notes[0]


# ---- placing the tables a merge adds ----


def _merge_in(original: str, key: str) -> str:
    """Adds ``[tool.<key>]`` the way a merge does, then places it."""
    from copy import deepcopy

    document = tomlkit.parse(original)
    added = tomlkit.parse(_TABLE_FOR.get(key, f"[tool.{key}]\nvalue = 1\n"))["tool"][
        key
    ]
    if "tool" not in document:
        document["tool"] = tomlkit.table(is_super_table=True)
    document["tool"][key] = deepcopy(added)
    return place_new_sections(original, document)


def _canonical(tools: tuple[str, ...]) -> str:
    """A freshly formatted file holding exactly these tool tables, then Protostar."""
    tables = [_TABLE_FOR.get(key, f"[tool.{key}]\nvalue = 1\n") for key in tools]
    source = "\n".join(
        [
            '[project]\nname = "x"\nversion = "1"\n',
            *tables,
            "[tool.protostar]\nversion = 1\n",
            '[dependency-groups]\ndev = ["ruff"]\n',
        ]
    )
    return format_document(tomlkit.parse(source))


_INSERTABLE = ("hatch", "ruff", "mypy", "pytest", "coverage", "rumdl")


def _present_and_added() -> list[tuple[tuple[str, ...], str]]:
    cases = []
    for size in range(len(_INSERTABLE)):
        for present in itertools.combinations(_INSERTABLE, size):
            for added in _INSERTABLE:
                if added not in present:
                    cases.append((present, added))
    return cases


@pytest.mark.parametrize(
    ("present", "added"),
    _present_and_added(),
    ids=lambda v: "+".join(v) if isinstance(v, tuple) else v,
)
def test_inserting_into_a_canonical_file_gives_the_canonical_file(
    present: tuple[str, ...], added: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Placing a table must match formatting the whole file with it in."""
    original = _canonical(present)
    with caplog.at_level(logging.WARNING, logger="protostar"):
        merged = _merge_in(original, added)

    assert not caplog.records, [record.message for record in caplog.records]
    assert merged == _canonical((*present, added))


_ADD_PAIRS = [
    (present, first, second)
    for present in [(), ("ruff",), ("pytest",), ("mypy", "rumdl")]
    for first, second in itertools.combinations(_INSERTABLE, 2)
    if first not in present and second not in present
]


@pytest.mark.parametrize(
    ("present", "first", "second"),
    _ADD_PAIRS,
    ids=lambda v: "+".join(v) if isinstance(v, tuple) else v,
)
def test_the_order_tables_are_added_in_does_not_matter(
    present: tuple[str, ...], first: str, second: str
) -> None:
    original = _canonical(present)

    one_way = _merge_in(_merge_in(original, first), second)
    other_way = _merge_in(_merge_in(original, second), first)

    assert one_way == other_way == _canonical((*present, first, second))


def test_a_new_tool_lands_between_its_neighbours_and_keeps_protostar_last() -> None:
    merged = _merge_in(_canonical(("ruff",)), "mypy")

    assert (
        merged.index("[tool.ruff]")
        < merged.index("# ---- Mypy ---- #")
        < merged.index("[tool.mypy]")
        < merged.index("# ---- Protostar ---- #")
        < merged.index("[tool.protostar]")
    )
    assert merged.rstrip().endswith("version = 1")


CUSTOM = (
    '# my project\n\n\n[project]\nname="x"   # inline\nversion = "1"\n\n\n\n'
    "# about black\n[tool.black]\nline-length=99\n\n\n[tool.zz]\nvalue = 1\n"
)


def test_a_merge_into_a_users_file_keeps_their_bytes() -> None:
    merged = _merge_in(CUSTOM, "ruff")

    # Every line the user wrote is still there, in order, unmodified.
    remaining = merged
    for line in CUSTOM.splitlines():
        if not line.strip():
            continue
        assert line in remaining, f"lost or altered: {line!r}"
        remaining = remaining[remaining.index(line) + len(line) :]
    assert tomllib.loads(merged)["tool"]["black"] == {"line-length": 99}
    assert tomllib.loads(merged)["tool"]["ruff"]["line-length"] == 88


def test_a_merge_labels_a_new_tool_and_adds_the_banner_only_once() -> None:
    merged = _merge_in(_merge_in(CUSTOM, "ruff"), "mypy")

    assert merged.count("# Tool Configuration") == 1
    assert merged.count("# ---- Ruff ---- #") == 1
    assert merged.count("# ---- Mypy ---- #") == 1
    assert merged.index("# Tool Configuration") < merged.index("# ---- Ruff ---- #")
    assert merged.index("[tool.ruff]") < merged.index("[tool.mypy]")
    # Their own tables follow the known tools, untouched.
    assert merged.index("[tool.mypy]") < merged.index("# about black")


def test_a_merge_does_not_label_a_table_the_user_already_had() -> None:
    original = '[project]\nname = "x"\n\n[tool.ruff]\nline-length = 99\n'

    merged = _merge_in(original, "mypy")

    assert "# ---- Ruff ---- #" not in merged
    assert "# ---- Mypy ---- #" in merged
    assert "[tool.ruff]\nline-length = 99" in merged


def test_a_sibling_table_shares_the_existing_header() -> None:
    merged = _merge_in(_canonical(("pytest",)), "coverage")

    assert merged.count("# ---- Pytest ---- #") == 1
    assert merged.index("[tool.pytest") < merged.index("[tool.coverage")


def test_a_new_root_table_lands_after_project() -> None:
    document = tomlkit.parse('[project]\nname = "x"\n\n[tool.ruff]\nline-length = 88\n')
    document["build-system"] = tomlkit.parse('[build-system]\nrequires = ["h"]\n')[
        "build-system"
    ]

    merged = place_new_sections(
        '[project]\nname = "x"\n\n[tool.ruff]\nline-length = 88\n', document
    )

    assert (
        merged.index("[project]")
        < merged.index("[build-system]")
        < merged.index("[tool.ruff]")
    )


def test_packaging_config_goes_above_a_banner_that_already_exists() -> None:
    merged = _merge_in(_canonical(("ruff",)), "hatch")

    assert merged.index("[tool.hatch") < merged.index("# Tool Configuration")
    assert merged.count("# Tool Configuration") == 1


def test_a_merge_follows_the_files_newline_style() -> None:
    original = '[project]\r\nname = "x"\r\n\r\n[tool.ruff]\r\nline-length = 99\r\n'

    merged = _merge_in(original, "mypy")

    assert "\n" not in merged.replace("\r\n", "")
    assert merged.startswith(original.rstrip("\r\n"))


def test_a_merge_supplies_a_missing_final_newline() -> None:
    merged = _merge_in('[project]\nname = "x"', "ruff")

    assert merged.endswith("\n")
    assert tomllib.loads(merged)["tool"]["ruff"]["line-length"] == 88


def test_a_merge_that_adds_nothing_changes_no_byte() -> None:
    document = tomlkit.parse(CUSTOM)
    document["project"]["version"] = "2"

    merged = place_new_sections(CUSTOM, document)

    assert merged == CUSTOM.replace('version = "1"', 'version = "2"')


def test_a_placement_that_cannot_be_proven_is_reported_and_falls_back(mocker) -> None:
    original = _canonical(("ruff",))
    document = tomlkit.parse(original)
    document["tool"]["mypy"] = tomlkit.parse("[tool.mypy]\nstrict = true\n")["tool"][
        "mypy"
    ]
    mocker.patch(
        "protostar.documents.pyproject_layout.join_sections",
        return_value='[project]\nname = "no"\n',
    )
    reasons: list[str] = []

    result = place_new_sections(original, document, reasons.append)

    assert result == tomlkit.dumps(document)
    assert len(reasons) == 1
    assert "placing new pyproject.toml sections" in reasons[0]


def test_a_comment_directly_above_a_table_stays_with_it() -> None:
    original = '[project]\nname = "x"\n\n# about black\n[tool.black]\nx = 1\n'

    merged = _merge_in(original, "ruff")

    assert merged.index("[tool.ruff]") < merged.index("# about black\n[tool.black]")
    assert merged.endswith("# about black\n[tool.black]\nx = 1\n")


def test_a_comment_set_apart_by_a_blank_line_is_not_moved() -> None:
    original = (
        '[project]\nname = "x"\n\n# a note about the project\n\n[tool.black]\nx = 1\n'
    )

    merged = _merge_in(original, "ruff")

    assert merged.index("# a note about the project") < merged.index("[tool.ruff]")
    assert merged.index("[tool.ruff]") < merged.index("[tool.black]")


def test_a_header_between_a_comment_and_its_table_is_not_treated_as_that_comment() -> (
    None
):
    """The comment sits above the managed header, so it does not describe what follows."""
    original = (
        '[project]\nname = "x"\n\n# ---- Ruff ---- #\n\n[tool.ruff]\nline-length = 88\n'
    )

    merged = _merge_in(original, "mypy")

    assert merged.count("# ---- Ruff ---- #") == 1
    assert merged.index("# ---- Ruff ---- #") < merged.index("[tool.ruff]")
    assert merged.index("[tool.ruff]") < merged.index("[tool.mypy]")


def test_a_merged_in_section_is_set_off_by_exactly_one_blank_line() -> None:
    """The user's own run of blank lines at the seam is normalized, not doubled."""
    merged = _merge_in(CUSTOM, "ruff")

    assert 'version = "1"\n\n' + BANNER[0] in merged
    assert (
        "\n\n\n" not in merged[merged.index(BANNER[0]) : merged.index("# about black")]
    )
    assert '[tool.ruff.lint]\nselect = ["E"]\n\n# about black' in merged


REMOVAL_ORIGINAL = """[project]
name = "x"

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88

[tool.example]
database = true

# ---- Protostar ---- #

[tool.protostar]
version = 1
"""


@pytest.mark.parametrize(
    ("removed", "expected"),
    [
        (
            "example",
            REMOVAL_ORIGINAL.replace("[tool.example]\ndatabase = true\n\n", ""),
        ),
        (
            "ruff",
            REMOVAL_ORIGINAL.replace(
                "# ---- Ruff ---- #\n\n[tool.ruff]\nline-length = 88\n\n", ""
            ),
        ),
    ],
)
def test_a_removed_table_takes_its_own_header_and_keeps_the_next(removed, expected):
    merged = tomlkit.parse(REMOVAL_ORIGINAL)
    del merged["tool"][removed]
    assert place_new_sections(REMOVAL_ORIGINAL, merged) == expected


def test_removing_every_managed_tool_keeps_the_banner_for_the_recipe():
    merged = tomlkit.parse(REMOVAL_ORIGINAL)
    del merged["tool"]["ruff"]
    del merged["tool"]["example"]
    assert place_new_sections(REMOVAL_ORIGINAL, merged) == REMOVAL_ORIGINAL.replace(
        "# ---- Ruff ---- #\n\n[tool.ruff]\nline-length = 88\n\n"
        "[tool.example]\ndatabase = true\n\n",
        "",
    )


# ---- the spec: where a section sorts and what labels it ----


@pytest.mark.parametrize(
    ("path", "rank"),
    [
        ((), (0, "")),
        (("project",), (1, "project")),
        (("build-system",), (2, "build-system")),
        (("dependency-groups",), (3, "dependency-groups")),
        (("uv",), (100, "uv")),
        (("tool",), (100, "tool")),
        (("a", "b"), (100, "a")),
        (("tool", "hatch"), (499, "hatch")),
        (("tool", "ruff"), (500, "ruff")),
        (("tool", "rumdl"), (507, "rumdl")),
        (("tool", "zzz"), (600, "zzz")),
        (("tool", "protostar"), (700, "protostar")),
    ],
)
def test_a_section_sorts_by_its_root_then_its_tool(path, rank) -> None:
    assert section_rank(path) == rank


@pytest.mark.parametrize(
    ("path", "title"),
    [
        (("tool", "ruff"), "Ruff"),
        (("tool", "coverage"), "Pytest"),
        (("tool", "hatch"), None),
        (("tool", "zzz"), None),
        (("tool",), None),
        (("project",), None),
        (("a", "ruff"), None),
        ((), None),
    ],
)
def test_only_a_known_tool_table_has_a_header_title(path, title) -> None:
    assert section_title(path) == title


def test_a_tail_announces_the_banner_by_its_title_and_headers_by_exact_line() -> None:
    rule, title = BANNER[0], BANNER[1]

    assert _announced(f"\n{rule}\n{title}\n{rule}\n\n# ---- Ruff ---- #\n") == (
        True,
        ["# ---- Ruff ---- #"],
    )
    assert _announced(f"\n{rule}\n\n") == (False, [])
    assert _announced(f"\n{title}\n") == (True, [])
    assert _announced("# ---- Mypy ---- #\n# ---- Mypy ---- #\n# ---- Nope ---- #") == (
        False,
        ["# ---- Mypy ---- #"],
    )


# ---- splitting a document into sections ----


def test_sections_are_named_by_their_table() -> None:
    document = tomlkit.parse(
        '[project]\nname = "x"\n\n[tool.ruff]\na = 1\n\n[a.b]\nc = 1\n\n[[tool.mypy.overrides]]\nm = 1\n'
    )

    assert [section.path for section in split_sections(document)] == [
        ("project",),
        ("tool", "ruff"),
        ("a",),
        ("tool", "mypy"),
    ]


@pytest.mark.parametrize("text", ["tool = 1\n", "tool = { ruff = { a = 1 } }\n"])
def test_a_tool_that_is_not_a_table_of_tables_is_one_section(text: str) -> None:
    sections = split_sections(tomlkit.parse(text))

    assert [(section.path, section.text) for section in sections] == [(("tool",), text)]


def test_a_section_that_is_only_managed_lines_is_all_tail() -> None:
    (section,) = split_sections(tomlkit.parse("# ---- Ruff ---- #\n"))

    assert (section.path, section.body, section.tail) == (
        (),
        "",
        "# ---- Ruff ---- #\n",
    )


def test_managed_lines_without_a_final_newline_still_end_a_section() -> None:
    sections = split_sections(
        tomlkit.parse('[project]\nname = "x"\n\n# ---- Ruff ---- #')
    )

    assert [(s.body, s.tail) for s in sections] == [
        ('[project]\nname = "x"\n', "\n# ---- Ruff ---- #")
    ]


# ---- inserting a section object ----


def test_insert_keeps_a_tail_the_previous_section_already_had() -> None:
    sections = [Section(("project",), "[project]\nname = 1", "\n# ---- Ruff ---- #")]

    insert_section(sections, Section(("tool", "x"), "[tool.x]\na = 1\n"), 1)

    assert [section.tail for section in sections] == [
        "\n# ---- Ruff ---- #\n\n",
        "",
    ]


def test_insert_keeps_a_tail_the_new_section_already_had() -> None:
    sections = _sections('[project]\nname = "x"\n')

    insert_section(
        sections,
        Section(("tool", "x"), "[tool.x]\na = 1\n", "# ---- Ruff ---- #\n"),
        0,
    )

    assert sections[0].tail == "# ---- Ruff ---- #\n\n"
    assert join_sections(sections).startswith("[tool.x]\na = 1\n# ---- Ruff ---- #\n\n")


def test_insert_leaves_a_body_that_already_ends_in_a_blank_line_alone() -> None:
    sections = _sections('[project]\nname = "x"\n')

    insert_section(sections, Section(("tool", "x"), "[tool.x]\na = 1\n\n"), 0)

    assert sections[0].text == "[tool.x]\na = 1\n\n"


# ---- composing children, at any depth ----


def test_compose_children_follows_the_order_then_the_rest_as_they_were() -> None:
    document = tomlkit.parse(
        "[tool.p]\nv = 1\n[tool.p.z]\nz = 1\n[tool.p.b]\nb = 1\n[tool.p.a]\na = 1\n"
    )

    text = compose_children(document, ("tool", "p"), ("a",))

    assert text == (
        "[tool.p]\nv = 1\n\n[tool.p.a]\na = 1\n\n[tool.p.z]\nz = 1\n\n"
        "[tool.p.b]\nb = 1\n"
    )


def test_compose_children_rebuilds_the_whole_path_of_a_nested_table() -> None:
    document = tomlkit.parse(
        "[tool.a.b]\nv = 1\n[tool.a.b.y]\ny = 1\n[tool.a.b.x]\nx = 1\n"
    )

    text = compose_children(document, ("tool", "a", "b"), ("x", "y"))

    assert text == "[tool.a.b]\nv = 1\n\n[tool.a.b.x]\nx = 1\n\n[tool.a.b.y]\ny = 1\n"


def test_compose_children_of_a_root_table() -> None:
    document = tomlkit.parse("[a]\nv = 1\n[a.y]\ny = 1\n[a.x]\nx = 1\n")

    text = compose_children(document, ("a",), ("x", "y"))

    assert text == "[a]\nv = 1\n\n[a.x]\nx = 1\n\n[a.y]\ny = 1\n"


# ---- the fallbacks say exactly what happened ----


def test_a_fallback_logs_why_and_hands_the_reason_to_the_caller(
    mocker, caplog: pytest.LogCaptureFixture
) -> None:
    mocker.patch(
        "protostar.documents.pyproject_layout.format_sections", return_value=CORRUPTED
    )
    reasons: list[str] = []

    with caplog.at_level(logging.WARNING, logger="protostar"):
        format_document(tomlkit.parse('[project]\nname = "app"\n'), reasons.append)

    reason = "AST Parity mismatch during pyproject.toml formatting"
    assert reasons == [reason]
    assert [record.message for record in caplog.records] == [
        f"{reason}; falling back to direct AST dump."
    ]


def test_a_formatter_that_raises_falls_back_with_its_error(
    mocker, caplog: pytest.LogCaptureFixture
) -> None:
    mocker.patch(
        "protostar.documents.pyproject_layout.format_sections", return_value="[broken"
    )
    reasons: list[str] = []

    with caplog.at_level(logging.WARNING, logger="protostar"):
        result = format_document(
            tomlkit.parse('[project]\nname = "app"\n\n\n\n'), reasons.append
        )

    assert result == '[project]\nname = "app"\n'
    assert len(reasons) == 1
    assert reasons[0].startswith("Validation error during pyproject.toml formatting (")
    assert [record.message for record in caplog.records] == [
        f"{reasons[0]}; falling back to direct AST dump."
    ]


def _place_with_join_returning(mocker, text: str, caplog) -> tuple[str, list[str]]:
    original = _canonical(("ruff",))
    document = tomlkit.parse(original)
    document["tool"]["mypy"] = tomlkit.parse("[tool.mypy]\nstrict = true\n")["tool"][
        "mypy"
    ]
    mocker.patch(
        "protostar.documents.pyproject_layout.join_sections", return_value=text
    )
    reasons: list[str] = []
    with caplog.at_level(logging.WARNING, logger="protostar"):
        result = place_new_sections(original, document, reasons.append)
    assert result == tomlkit.dumps(document)
    return result, reasons


def test_a_placement_that_changes_data_logs_a_parity_mismatch(
    mocker, caplog: pytest.LogCaptureFixture
) -> None:
    _, reasons = _place_with_join_returning(mocker, CORRUPTED, caplog)

    reason = "AST Parity mismatch while placing new pyproject.toml sections"
    assert reasons == [reason]
    assert [record.message for record in caplog.records] == [
        f"{reason}; falling back to direct AST dump."
    ]


def test_a_placement_that_is_not_toml_logs_the_error(
    mocker, caplog: pytest.LogCaptureFixture
) -> None:
    _, reasons = _place_with_join_returning(mocker, "[broken", caplog)

    assert len(reasons) == 1
    assert reasons[0].startswith(
        "Validation error while placing new pyproject.toml sections ("
    )
    assert [record.message for record in caplog.records] == [
        f"{reasons[0]}; falling back to direct AST dump."
    ]


# ---- placing and removing tables in a user's file, to the byte ----

_RULE = BANNER[0]
_CONFIGURATION = "\n".join(BANNER)


def _ruff_table() -> tomlkit.items.Table:
    return tomlkit.parse("[tool.ruff]\nline-length = 88\n")["tool"]["ruff"]


def _add_ruff(document: tomlkit.TOMLDocument) -> None:
    if "tool" not in document:
        document["tool"] = tomlkit.table(is_super_table=True)
    document["tool"]["ruff"] = _ruff_table()


def _placed(original: str, *edits) -> str:
    document = tomlkit.parse(original)
    for edit in edits:
        edit(document)
    return place_new_sections(original, document)


def test_a_root_table_that_sorts_first_goes_above_every_tool() -> None:
    def add_project(document: tomlkit.TOMLDocument) -> None:
        document["project"] = tomlkit.parse('[project]\nname = "x"\n')["project"]

    assert _placed("[tool.ruff]\nline-length = 88\n", add_project) == (
        '[project]\nname = "x"\n\n[tool.ruff]\nline-length = 88\n'
    )


def test_a_new_tool_first_in_a_file_brings_the_banner_and_its_header() -> None:
    assert _placed("[tool.mypy]\nstrict = true\n", _add_ruff) == (
        f"{_CONFIGURATION}\n\n# ---- Ruff ---- #\n\n"
        "[tool.ruff]\nline-length = 88\n\n[tool.mypy]\nstrict = true\n"
    )


def test_a_new_tool_first_in_a_file_that_has_its_banner_further_down_adds_only_a_header() -> (
    None
):
    original = (
        f"[tool.zzz]\nx = 1\n\n{_CONFIGURATION}\n\n# ---- Mypy ---- #\n"
        "[tool.mypy]\nstrict = true\n"
    )

    assert _placed(original, _add_ruff) == (
        f"# ---- Ruff ---- #\n\n[tool.ruff]\nline-length = 88\n\n{original}"
    )


def test_a_banner_rule_alone_is_not_the_banner() -> None:
    original = f'[project]\nname = "x"\n\n{_RULE}\n\n[tool.black]\nx = 1\n'

    merged = _placed(original, _add_ruff)

    assert merged.count("# Tool Configuration") == 1
    assert merged.index("# Tool Configuration") < merged.index("[tool.ruff]")


def test_a_title_further_down_is_the_banner_already_there() -> None:
    original = (
        '[project]\nname = "x"\n\n[tool.black]\nx = 1\n\n# Tool Configuration\n\n'
        "[tool.zz]\nv = 1\n"
    )

    assert _RULE not in _placed(original, _add_ruff)


def test_a_comment_block_above_a_table_moves_with_it_whole() -> None:
    original = '[project]\nname = "x"\n\n# one\n  # two\n[tool.black]\nx = 1\n'

    merged = _placed(original, _add_ruff)

    assert merged.endswith("line-length = 88\n\n# one\n  # two\n[tool.black]\nx = 1\n")


def test_a_comment_that_is_the_whole_section_moves_with_its_table() -> None:
    assert _placed("# about black\n[tool.black]\nx = 1\n", _add_ruff) == (
        f"\n{_CONFIGURATION}\n\n# ---- Ruff ---- #\n\n"
        "[tool.ruff]\nline-length = 88\n\n# about black\n[tool.black]\nx = 1\n"
    )


def test_taking_comments_leaves_the_rest_of_the_section_and_returns_the_block() -> None:
    kept = Section(("tool", "a"), "a = 1\n\n# one\n# two\n")
    only_comments = Section((), "# one\n# two\n")
    crlf = Section((), "x = 1\r\n# one\r\n")
    no_comment = Section((), "x = 1\n")

    assert _take_leading_comments(kept) == "# one\n# two\n"
    assert kept.body == "a = 1\n\n"
    assert _take_leading_comments(only_comments) == "# one\n# two\n"
    assert only_comments.body == ""
    assert _take_leading_comments(crlf) == "# one\r\n"
    assert crlf.body == "x = 1\r\n"
    assert _take_leading_comments(no_comment) == ""
    assert no_comment.body == "x = 1\n"


def test_comments_above_a_managed_header_stay_where_they_are() -> None:
    section = Section(("project",), "x = 1\n# note\n", "\n# ---- Ruff ---- #\n")

    assert _take_leading_comments(section) == ""
    assert section.body == "x = 1\n# note\n"


def test_an_indented_comment_above_a_table_moves_with_it() -> None:
    merged = _placed("  # indented\n[tool.black]\nx = 1\n", _add_ruff)

    assert merged.endswith("\n\n  # indented\n[tool.black]\nx = 1\n")


@pytest.mark.parametrize("trailing", ["   ", "\t", " # MAX", " # X"])
def test_what_the_previous_table_ends_with_is_never_trimmed(trailing: str) -> None:
    original = f'[project]\nname = "x"{trailing}\n\n[tool.zz]\nv = 1\n'

    merged = _placed(original, _add_ruff)

    assert merged.startswith(f'[project]\nname = "x"{trailing}\n\n{_RULE}\n')


def test_a_table_in_the_other_newline_style_is_converted_whole() -> None:
    crlf = tomlkit.parse("[tool.ruff]\r\nline-length = 88\r\n")["tool"]["ruff"]

    def add(document: tomlkit.TOMLDocument) -> None:
        document["tool"] = tomlkit.table(is_super_table=True)
        document["tool"]["ruff"] = crlf

    lf_file = _placed('[project]\nname = "x"\n', add)
    crlf_file = _placed('[project]\r\nname = "x"\r\n', add)

    assert "\r" not in lf_file
    assert lf_file.endswith("[tool.ruff]\nline-length = 88\n")
    assert crlf_file.replace("\r\n", "") == crlf_file.replace("\r", "").replace(
        "\n", ""
    )
    assert crlf_file.endswith("[tool.ruff]\r\nline-length = 88\r\n")


def test_tables_defined_out_of_order_keep_their_place_when_a_tool_is_added() -> None:
    original = (
        '[project]\nname="x"\n\n[tool.ruff]\na=1\n\n[project.scripts]\nx="y"\n\n'
        '[tool.ruff.lint]\nselect=["E"]\n'
    )

    def add_mypy(document: tomlkit.TOMLDocument) -> None:
        document["tool"]["mypy"] = tomlkit.parse("[tool.mypy]\nstrict = true\n")[
            "tool"
        ]["mypy"]

    assert _placed(original, add_mypy) == (
        f"{original}\n{_CONFIGURATION}\n\n# ---- Mypy ---- #\n\n"
        "[tool.mypy]\nstrict = true\n"
    )


def test_three_pieces_of_one_table_each_keep_their_own_spacing_when_a_tool_is_added() -> (
    None
):
    original = (
        '[project]\nname = "x"\n\n[tool.black]\nb = 1\n\n[project.scripts]\n'
        'x = "y"\n\n\n\n[tool.zz]\nz = 1\n\n[project.urls]\nu = "v"\n\n'
        "[tool.yy]\ny = 1\n"
    )

    def add_last(document: tomlkit.TOMLDocument) -> None:
        document["tool"]["zzz"] = tomlkit.parse("[tool.zzz]\nv = 1\n")["tool"]["zzz"]

    assert _placed(original, add_last) == f"{original}\n[tool.zzz]\nv = 1\n"


@pytest.mark.parametrize(
    ("present", "first", "second"),
    _ADD_PAIRS,
    ids=lambda v: "+".join(v) if isinstance(v, tuple) else v,
)
def test_tables_added_by_one_merge_land_as_if_added_one_at_a_time(
    present: tuple[str, ...], first: str, second: str
) -> None:
    def add_both(order: tuple[str, str]):
        def edit(document: tomlkit.TOMLDocument) -> None:
            if "tool" not in document:
                document["tool"] = tomlkit.table(is_super_table=True)
            for key in order:
                table = tomlkit.parse(
                    _TABLE_FOR.get(key, f"[tool.{key}]\nvalue = 1\n")
                )["tool"][key]
                document["tool"][key] = table

        return edit

    original = _canonical(present)

    assert (
        _placed(original, add_both((first, second)))
        == _placed(original, add_both((second, first)))
        == _canonical((*present, first, second))
    )


def test_an_edited_table_keeps_its_sort_position_and_its_header() -> None:
    original = _canonical(("ruff", "mypy"))

    def edit(document: tomlkit.TOMLDocument) -> None:
        document["tool"]["ruff"]["line-length"] = 100

    def add_pytest(document: tomlkit.TOMLDocument) -> None:
        document["tool"]["pytest"] = tomlkit.parse(_TABLE_FOR["pytest"])["tool"][
            "pytest"
        ]

    merged = _placed(original, edit, add_pytest)

    assert merged == format_document(
        tomlkit.parse(_canonical(("ruff", "mypy", "pytest")).replace("= 88", "= 100"))
    )


def test_an_edited_table_that_sorts_late_still_leaves_new_tables_before_it() -> None:
    original = '[project]\nname = "x"\n\n[tool.black]\nline-length = 99\n'

    def edit(document: tomlkit.TOMLDocument) -> None:
        document["tool"]["black"]["line-length"] = 100

    merged = _placed(original, edit, _add_ruff)

    assert merged.index("[tool.ruff]") < merged.index("[tool.black]")
    assert merged.endswith("[tool.black]\nline-length = 100\n")


def test_tables_added_in_one_merge_are_placed_by_rank_not_by_arrival() -> None:
    def add_mypy_then_ruff(document: tomlkit.TOMLDocument) -> None:
        document["tool"] = tomlkit.table(is_super_table=True)
        document["tool"]["mypy"] = tomlkit.parse("[tool.mypy]\nstrict = true\n")[
            "tool"
        ]["mypy"]
        document["tool"]["ruff"] = _ruff_table()

    assert _placed('[project]\nname = "x"\n', add_mypy_then_ruff) == (
        f'[project]\nname = "x"\n\n{_CONFIGURATION}\n\n# ---- Ruff ---- #\n\n'
        "[tool.ruff]\nline-length = 88\n\n# ---- Mypy ---- #\n\n"
        "[tool.mypy]\nstrict = true\n"
    )


@pytest.mark.parametrize(
    "dangling",
    [
        "# Tool Configuration\n",
        f"{_CONFIGURATION}\n",
        f"{_CONFIGURATION}\n\n# ---- Ruff ---- #\n",
        "# ---- Ruff ---- #\n",
    ],
)
def test_a_banner_or_header_left_at_the_end_of_a_file_labels_the_table_added_after_it(
    dangling: str,
) -> None:
    original = f'[project]\nname = "x"\n\n{dangling}'

    assert _placed(original, _add_ruff) == (
        f'[project]\nname = "x"\n\n{_CONFIGURATION}\n\n# ---- Ruff ---- #\n\n'
        "[tool.ruff]\nline-length = 88\n"
    )


# ---- removing tables ----


def _removed(original: str, *tables: str) -> str:
    document = tomlkit.parse(original)
    for table in tables:
        if table in document:
            del document[table]
        else:
            del document["tool"][table]
    return place_new_sections(original, document)


def test_removing_the_first_table_leaves_the_rest_as_they_were() -> None:
    assert _removed(REMOVAL_ORIGINAL, "project") == (
        "[tool.ruff]\nline-length = 88\n\n[tool.example]\ndatabase = true\n\n"
        "# ---- Protostar ---- #\n\n[tool.protostar]\nversion = 1\n"
    )


def test_removing_the_last_table_leaves_no_header_dangling() -> None:
    assert _removed(REMOVAL_ORIGINAL, "protostar") == REMOVAL_ORIGINAL.replace(
        "\n# ---- Protostar ---- #\n\n[tool.protostar]\nversion = 1\n", ""
    )


def test_removing_an_untitled_table_keeps_the_header_that_announced_it() -> None:
    original = (
        '[project]\nname = "x"\n\n# ---- Ruff ---- #\n\n[tool.example]\n'
        "database = true\n\n[tool.zzz]\nx = 1\n"
    )

    assert _removed(original, "example") == (
        '[project]\nname = "x"\n\n# ---- Ruff ---- #\n\n[tool.zzz]\nx = 1\n'
    )


@pytest.mark.parametrize("trailing", ["   ", " # MAX", " # X"])
def test_removing_a_table_does_not_trim_what_the_one_before_ends_with(
    trailing: str,
) -> None:
    original = (
        f'[project]\nname = "x"\n\n[tool.zz]\nv = 1{trailing}\n\n[tool.yy]\nv = 2\n'
    )

    assert _removed(original, "yy") == (
        f'[project]\nname = "x"\n\n[tool.zz]\nv = 1{trailing}\n'
    )
