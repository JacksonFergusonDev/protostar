"""The pyproject.toml layout model: exactness, canonical order, and its guards."""

import importlib.resources
import itertools
import logging
import re
import tomllib
from pathlib import Path

import pytest
import tomlkit

from protostar.manifest import EnvironmentManifest
from protostar.modules import TOOLING_MODULES
from protostar.toml_layout import (
    BANNER,
    TOOL_SECTION_NAMES,
    TOOL_SECTIONS,
    Section,
    compose_children,
    format_document,
    insert_section,
    join_sections,
    section_rank,
    split_sections,
)

SNAPSHOTS = Path(__file__).parent / "snapshots"
# ml_merged is the product of a merge, which never reformats; it is not a fresh layout.
FRESH_SNAPSHOTS = ["api", "astro", "cli", "dsp", "embedded", "ml"]

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
    mocker.patch("protostar.toml_layout.format_sections", return_value=CORRUPTED)
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
    from protostar.merge import MISSING, MergeLocation
    from protostar.toml_ast import reconcile_toml

    mocker.patch("protostar.toml_layout.format_sections", return_value=CORRUPTED)

    result = reconcile_toml(
        "",
        {"project": {"name": "app"}},
        MISSING,
        MergeLocation("pyproject.toml"),
        initializing=True,
        missing_file=True,
    )

    assert len(result.layout_notes) == 1
    assert "Parity mismatch" in result.layout_notes[0]
