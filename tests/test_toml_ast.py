import tomllib
from pathlib import Path

import pytest
import tomlkit
from pytest_mock import MockerFixture

from protostar.documents.pyproject_layout import format_document
from protostar.errors import ConfigurationError
from protostar.intent import StructuredContribution
from protostar.merge import (
    MISSING,
    ConflictReason,
    MergeLocation,
    MergePolicy,
    ResolutionChoice,
    Value,
)
from protostar.toml_ast import (
    FlatNames,
    TomlDocumentSpec,
    aggregate_toml_document,
    reconcile_toml,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_format_pyproject_toml_canonical_ordering():
    doc = tomlkit.parse("""
[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 88

[build-system]
requires = ["flit_core >=3.2,<4"]
build-backend = "flit_core.buildapi"

[project]
name = "test-pkg"
version = "0.1.0"
""")

    formatted = format_document(doc)

    # 1. Verify [project] precedes [build-system] and [tool]
    proj_idx = formatted.find("[project]")
    build_idx = formatted.find("[build-system]")
    tool_idx = formatted.find("[tool.ruff]")
    assert proj_idx < build_idx < tool_idx

    # 2. Verify headers were injected
    assert "# ==================================================" in formatted
    assert "# Tool Configuration" in formatted
    assert "# ---- Ruff ---- #" in formatted
    assert "# ---- Pytest ---- #" in formatted


def test_format_pyproject_toml_idempotency():
    doc = tomlkit.parse("""
[project]
name = "test"

[tool.ruff]
line-length = 88
""")
    pass1 = format_document(doc)
    doc2 = tomlkit.parse(pass1)
    pass2 = format_document(doc2)

    assert pass1 == pass2


def test_format_pyproject_toml_relabels_reordered_existing_sections():
    """Keep managed headers attached to their tables after canonical ordering."""
    doc = tomlkit.parse("""
# ---- Ruff ---- #

[tool.ruff]
line-length = 88

# ---- Pytest ---- #

[tool.pytest.ini_options]
testpaths = ["tests"]

# ---- Mypy ---- #

[tool.mypy]
strict = true
""")

    formatted = format_document(doc)

    assert formatted.count("# ---- Ruff ---- #") == 1
    assert formatted.count("# ---- Mypy ---- #") == 1
    assert formatted.count("# ---- Pytest ---- #") == 1
    assert formatted.index("# ---- Ruff ---- #") < formatted.index("[tool.ruff]")
    assert formatted.index("# ---- Mypy ---- #") < formatted.index("[tool.mypy]")
    assert formatted.index("# ---- Pytest ---- #") < formatted.index(
        "[tool.pytest.ini_options]"
    )
    assert formatted.index("[tool.ruff]") < formatted.index("[tool.mypy]")
    assert formatted.index("[tool.mypy]") < formatted.index("[tool.pytest.ini_options]")


def test_format_pyproject_toml_coverage_grouped_under_pytest():
    """Test that coverage tables are placed directly under Pytest and before Commitizen."""
    raw = """
[project]
name = "demo"

[tool.commitizen]
name = "cz"

[tool.pytest.ini_options]
addopts = "--strict-markers"

[tool.coverage.run]
branch = true

[tool.coverage.report]
show_missing = true
"""
    doc = tomlkit.parse(raw)
    formatted = format_document(doc)

    pytest_header_pos = formatted.find("# ---- Pytest ---- #")
    pytest_ini_pos = formatted.find("[tool.pytest.ini_options]")
    cov_run_pos = formatted.find("[tool.coverage.run]")
    cov_rep_pos = formatted.find("[tool.coverage.report]")
    cz_header_pos = formatted.find("# ---- Commitizen ---- #")
    cz_pos = formatted.find("[tool.commitizen]")

    assert (
        pytest_header_pos
        < pytest_ini_pos
        < cov_run_pos
        < cov_rep_pos
        < cz_header_pos
        < cz_pos
    )


def test_format_pyproject_toml_root_table_ordering():
    """Test that root scalars, project, build-system, dependency-groups, and tool tables are ordered."""
    raw = """
[tool.ruff]
line-length = 88

[dependency-groups]
dev = ["pytest"]

[build-system]
requires = ["hatchling"]

[project]
name = "app"
version = "0.1.0"
"""
    doc = tomlkit.parse(raw)
    formatted = format_document(doc)

    project_pos = formatted.find("[project]")
    build_pos = formatted.find("[build-system]")
    dep_pos = formatted.find("[dependency-groups]")
    tool_pos = formatted.find("# ==================================================")

    assert project_pos < build_pos < dep_pos < tool_pos


def test_format_pyproject_toml_aot_and_subtables_only():
    """Test that subtables and array of tables without root tables are detected and formatted with headers."""
    raw = """
[[tool.mypy.overrides]]
module = ["tests.*"]
ignore_errors = true

[tool.ty.rules]
redundant-cast = "warn"

[tool.coverage.report]
fail_under = 80
"""
    doc = tomlkit.parse(raw)
    formatted = format_document(doc)

    assert "# ---- Mypy ---- #\n\n[[tool.mypy.overrides]]" in formatted
    assert "# ---- Ty ---- #\n\n[tool.ty.rules]" in formatted
    assert "# ---- Pytest ---- #\n\n[tool.coverage.report]" in formatted
    assert formatted.endswith("\n")
    assert not formatted.endswith("\n\n")


def test_format_pyproject_toml_semantic_data_mismatch_fallback(mocker):
    """Test that formatting safely falls back to raw dump if parsed check data differs from expected."""
    raw = """
[project]
name = "app"

[tool.ruff]
line-length = 88
"""
    doc = tomlkit.parse(raw)

    # Mock tomllib.loads: first call (raw_dump) returns dict A, second call (new_content) returns dict B
    calls = [
        {"project": {"name": "app"}, "tool": {"ruff": {"line-length": 88}}},
        {"project": {"name": "corrupted"}},
    ]
    mocker.patch("tomllib.loads", side_effect=lambda _: calls.pop(0))

    formatted = format_document(doc)
    assert "[tool.ruff]" in formatted
    assert formatted.endswith("\n")
    assert not formatted.endswith("\n\n")


def test_format_pyproject_toml_parity_fallback(mocker):
    doc = tomlkit.parse("""
[project]
name = "test"
""")
    # Force tomllib.loads to throw or mismatch
    mocker.patch("tomllib.loads", side_effect=ValueError("Parity mismatch"))

    formatted = format_document(doc)
    assert "[project]" in formatted
    assert 'name = "test"' in formatted


def test_format_pyproject_toml_rumdl_header():
    """Test that rumdl table is preceded by # ---- rumdl ---- # header."""
    raw = """
[project]
name = "demo"

[tool.rumdl]
disable = ["MD013"]
"""
    doc = tomlkit.parse(raw)
    formatted = format_document(doc)

    assert "# ---- rumdl ---- #" in formatted
    assert "# ---- rumdl ---- #\n\n[tool.rumdl]" in formatted


def test_set_extension_preserves_existing_member_comments():
    """Accepted set additions retain the local array's nodes and presentation."""
    from protostar.documents import toml_spec
    from protostar.merge import MergeLocation
    from protostar.toml_ast import reconcile_toml

    original = (
        "[tool.ruff.lint]\nselect = [\n"
        '  "E", # user explanation\n'
        '  "F", # another explanation\n'
        "] # local array comment\n"
    )
    desired = tomlkit.parse('[tool.ruff.lint]\nselect = ["E", "F", "I"]\n')
    result = reconcile_toml(
        toml_spec("pyproject.toml"),
        original,
        desired.unwrap(),
        tomlkit.parse(original).unwrap(),
        MergeLocation("pyproject.toml"),
        desired_ast=desired,
    )
    assert '  "E", # user explanation\n' in result.content
    assert '  "F", # another explanation\n' in result.content
    assert "] # local array comment\n" in result.content
    assert tomlkit.parse(result.content).unwrap() == desired.unwrap()
    repeated = reconcile_toml(
        toml_spec("pyproject.toml"),
        result.content,
        desired.unwrap(),
        result.baseline,
        MergeLocation("pyproject.toml"),
        desired_ast=desired,
    )
    assert repeated.content == result.content


def test_adding_tool_preserves_existing_document_presentation():
    """Semantic equality never authorizes reformatting pre-existing tables."""
    from protostar.documents import toml_spec
    from protostar.merge import MergeLocation
    from protostar.toml_ast import reconcile_toml

    original = (
        '# Project rationale\n[project]\nname="demo"\n\n\n'
        '# Pytest rationale\n[tool.pytest.ini_options]\ntestpaths=["tests"]\n\n\n'
        "# Ruff rationale\n[tool.ruff]\nline-length=88\n"
    )
    desired = tomlkit.parse("[tool.ruff]\nline-length=88\n[tool.mypy]\nstrict=true\n")
    base = tomlkit.parse(original).unwrap()
    del base["project"]
    # Only what the producers still declare is owned; the rest would retract.
    del base["tool"]["pytest"]
    result = reconcile_toml(
        toml_spec("pyproject.toml"),
        original,
        desired.unwrap(),
        base,
        MergeLocation("pyproject.toml"),
        desired_ast=desired,
    )
    assert result.content.startswith(original)
    assert "[tool.mypy]\nstrict=true\n" in result.content
    repeated = reconcile_toml(
        toml_spec("pyproject.toml"),
        result.content,
        desired.unwrap(),
        result.baseline,
        MergeLocation("pyproject.toml"),
        desired_ast=desired,
    )
    assert repeated.content == result.content


UV_APPENDED_LAYOUT = """
[project]
name = "app"
version = "0.1.0"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 88

[tool.hatch.build.targets.wheel]
packages = ["src/app"]

[tool.protostar]
version = 1
[dependency-groups]
dev = ["ruff"]
"""


def _header_positions(formatted: str) -> dict[str, int]:
    return {
        marker: formatted.find(marker)
        for marker in (
            "[dependency-groups]",
            "[tool.hatch",
            "# Tool Configuration",
            "# ---- Ruff ---- #",
            "# ---- Protostar ---- #",
            "[tool.protostar]",
        )
    }


def test_format_pyproject_toml_keeps_only_tooling_under_the_banner():
    """Dependency groups and packaging config sit above the Tool Configuration banner."""
    formatted = format_document(tomlkit.parse(UV_APPENDED_LAYOUT))
    pos = _header_positions(formatted)

    assert -1 not in pos.values()
    assert pos["[dependency-groups]"] < pos["[tool.hatch"] < pos["# Tool Configuration"]
    assert pos["# Tool Configuration"] < pos["# ---- Ruff ---- #"]


def test_format_pyproject_toml_labels_the_protostar_section_last():
    formatted = format_document(tomlkit.parse(UV_APPENDED_LAYOUT))
    pos = _header_positions(formatted)

    assert (
        pos["# ---- Ruff ---- #"]
        < pos["# ---- Protostar ---- #"]
        < pos["[tool.protostar]"]
    )
    assert formatted.count("# ---- Protostar ---- #") == 1


def test_format_pyproject_toml_separates_every_table_with_a_blank_line():
    formatted = format_document(tomlkit.parse(UV_APPENDED_LAYOUT))
    lines = formatted.split("\n")

    for index, line in enumerate(lines[1:], start=1):
        if line.startswith("["):
            previous = lines[index - 1]
            assert previous == "" or previous.startswith("#"), (
                f"no blank line before {line!r}"
            )


def test_format_pyproject_toml_layout_is_idempotent_with_protostar_section():
    once = format_document(tomlkit.parse(UV_APPENDED_LAYOUT))
    twice = format_document(tomlkit.parse(once))

    assert once == twice


def test_finalize_new_pyproject_fixes_the_layout_uv_and_the_recipe_leave():
    from protostar.documents.pyproject import finalize_new_pyproject

    finalized = finalize_new_pyproject(UV_APPENDED_LAYOUT)

    assert finalized == format_document(tomlkit.parse(UV_APPENDED_LAYOUT))
    assert tomllib.loads(finalized) == tomllib.loads(UV_APPENDED_LAYOUT)


CANONICAL_WITH_RECIPE = """[project]
name = "demo"

[dependency-groups]
dev = ["ruff"]

# ==================================================
# Tool Configuration
# ==================================================

# ---- Ruff ---- #

[tool.ruff]
line-length = 88

# ---- Protostar ---- #

[tool.protostar]
version = 1
"""


def test_a_tool_added_to_an_existing_project_is_placed_before_protostar():
    from protostar.documents import toml_spec
    from protostar.merge import MergeLocation
    from protostar.toml_ast import reconcile_toml

    desired = tomlkit.parse("[tool.ruff]\nline-length=88\n[tool.mypy]\nstrict=true\n")
    result = reconcile_toml(
        toml_spec("pyproject.toml"),
        CANONICAL_WITH_RECIPE,
        desired.unwrap(),
        {"tool": {"ruff": {"line-length": 88}}},
        MergeLocation("pyproject.toml"),
        desired_ast=desired,
    )

    content = result.content
    assert (
        content.index("[tool.ruff]")
        < content.index("# ---- Mypy ---- #")
        < content.index("[tool.mypy]")
        < content.index("# ---- Protostar ---- #")
        < content.index("[tool.protostar]")
    )
    assert content.count("# ---- Protostar ---- #") == 1
    assert content.count("# Tool Configuration") == 1
    assert not result.layout_notes


def test_placing_a_new_tool_is_stable_when_repeated():
    from protostar.documents import toml_spec
    from protostar.merge import MergeLocation
    from protostar.toml_ast import reconcile_toml

    desired = tomlkit.parse("[tool.ruff]\nline-length=88\n[tool.mypy]\nstrict=true\n")
    first = reconcile_toml(
        toml_spec("pyproject.toml"),
        CANONICAL_WITH_RECIPE,
        desired.unwrap(),
        {"tool": {"ruff": {"line-length": 88}}},
        MergeLocation("pyproject.toml"),
        desired_ast=desired,
    )
    repeated = reconcile_toml(
        toml_spec("pyproject.toml"),
        first.content,
        desired.unwrap(),
        first.baseline,
        MergeLocation("pyproject.toml"),
        desired_ast=desired,
    )

    assert repeated.content == first.content


def test_a_non_pyproject_toml_target_is_left_to_a_plain_dump():
    from protostar.documents import toml_spec
    from protostar.merge import MergeLocation
    from protostar.toml_ast import reconcile_toml

    original = "[tool.a]\nx = 1\n\n[tool.zzz]\ny = 2\n"
    desired = tomlkit.parse("[tool.a]\nx = 1\n[tool.b]\nz = 3\n")
    result = reconcile_toml(
        toml_spec("ruff.toml"),
        original,
        desired.unwrap(),
        {"tool": {"a": {"x": 1}}},
        MergeLocation("ruff.toml"),
        desired_ast=desired,
    )

    assert "# ----" not in result.content
    assert result.content.startswith(original)


SEEDED = TomlDocumentSpec(
    policy=MergePolicy(frozenset({("theme", "features")})),
    seed_paths=frozenset({("site", "name"), ("site", "nav")}),
)


def test_seed_paths_are_written_only_when_creating_the_document():
    desired = tomlkit.parse(
        '[site]\nname = "demo"\nnav = ["index.md"]\n[theme]\nfeatures = ["a"]\n'
    )
    created = reconcile_toml(
        SEEDED,
        "",
        desired.unwrap(),
        MISSING,
        MergeLocation("site.toml"),
        initializing=True,
        missing_file=True,
        desired_ast=desired,
    )
    assert tomlkit.parse(created.content).unwrap() == desired.unwrap()
    assert created.baseline == desired.unwrap()

    edited = created.content.replace('"demo"', '"mine"').replace('["index.md"]', "[]")
    changed = tomlkit.parse(
        '[site]\nname = "renamed"\nnav = ["home.md"]\n[theme]\nfeatures = ["a", "b"]\n'
    )
    synced = reconcile_toml(
        SEEDED,
        edited,
        changed.unwrap(),
        created.baseline,
        MergeLocation("site.toml"),
        desired_ast=changed,
    )
    assert tomlkit.parse(synced.content).unwrap() == {
        "site": {"name": "mine", "nav": []},
        "theme": {"features": ["a", "b"]},
    }
    assert not synced.conflicts
    assert synced.baseline == {
        "site": {"name": "demo", "nav": ["index.md"]},
        "theme": {"features": ["a", "b"]},
    }


def test_seed_paths_never_touch_an_existing_document():
    desired = tomlkit.parse('[site]\nname = "demo"\n[theme]\nfeatures = ["a"]\n')
    original = "[theme]\nfeatures = []\n"
    result = reconcile_toml(
        SEEDED,
        original,
        desired.unwrap(),
        MISSING,
        MergeLocation("site.toml"),
        desired_ast=desired,
    )
    assert tomlkit.parse(result.content).unwrap() == {"theme": {"features": ["a"]}}
    assert "[site]" not in result.content


def test_overwrite_reapplies_seed_paths_and_keeps_foreign_keys():
    desired = tomlkit.parse('[site]\nname = "demo"\n')
    result = reconcile_toml(
        SEEDED,
        '[site]\nname = "mine"\nurl = "https://example.com"\n',
        desired.unwrap(),
        {"site": {"name": "demo"}},
        MergeLocation("site.toml"),
        overwrite=True,
        desired_ast=desired,
    )
    assert tomlkit.parse(result.content).unwrap() == {
        "site": {"name": "demo", "url": "https://example.com"}
    }


def test_overwrite_carries_a_dotted_key_table_into_an_existing_table():
    """Dotted keys spread one table over several entries, read back as a proxy."""
    desired = tomlkit.parse(
        "[site.extensions]\n"
        "abbr = {}\n"
        "pymdownx.arithmatex.generic = true\n"
        "toc.permalink = true\n"
        "pymdownx.highlight.line_spans = '__span'\n"
        "pymdownx.keys = {}\n"
    )
    original = '[site.extensions]\nadmonition = {}\n"pymdownx.details" = {}\n'
    result = reconcile_toml(
        SEEDED,
        original,
        desired.unwrap(),
        MISSING,
        MergeLocation("site.toml"),
        overwrite=True,
        desired_ast=desired,
    )
    extensions = tomlkit.parse(result.content).unwrap()["site"]["extensions"]
    assert extensions == {
        "admonition": {},
        "pymdownx.details": {},
        **desired.unwrap()["site"]["extensions"],
    }
    assert "pymdownx.arithmatex.generic = true\n" in result.content
    assert "pymdownx.keys = {}\n" in result.content


ZENSICAL_EXTENSIONS = (
    "[project.markdown_extensions]\n"
    "toc.permalink = true\n"
    "pymdownx.details = {}\n"
    "pymdownx.highlight.line_spans = '__span'\n"
    "pymdownx.keys = {}\n"
)


def zensical_reconcile(original, base=MISSING, **kwargs):
    from protostar.documents import zensical

    desired = tomlkit.parse(ZENSICAL_EXTENSIONS)
    return reconcile_toml(
        zensical.SPEC,
        original,
        desired.unwrap(),
        base,
        MergeLocation(zensical.TARGET),
        desired_ast=desired,
        **kwargs,
    )


def extensions(content):
    return tomllib.loads(content)["project"]["markdown_extensions"]


def test_overwrite_updates_quoted_extension_names_in_place():
    """A quoted name and the seed's nested one are the same Zensical extension."""
    original = (
        "[project.markdown_extensions]\n"
        '"pymdownx.details" = {}\n'
        '"pymdownx.highlight" = { line_spans = "old" }\n'
    )
    result = zensical_reconcile(original, overwrite=True)
    assert extensions(result.content) == {
        "pymdownx.details": {},
        "pymdownx.highlight": {"line_spans": "__span"},
        "toc": {"permalink": True},
        "pymdownx.keys": {},
    }
    assert '"pymdownx.keys" = {}\n' in result.content
    # The inline spelling is layout only: the baseline holds plain values.
    owned = result.baseline["project"]["markdown_extensions"]
    assert type(owned["pymdownx.keys"]) is dict
    repeated = zensical_reconcile(result.content, result.baseline, overwrite=True)
    assert repeated.content == result.content


def test_overwrite_keeps_a_nested_document_nested():
    original = "[project.markdown_extensions]\npymdownx.details = {}\n"
    result = zensical_reconcile(original, overwrite=True)
    assert extensions(result.content) == {
        "pymdownx": {
            "details": {},
            "highlight": {"line_spans": "__span"},
            "keys": {},
        },
        "toc": {"permalink": True},
    }
    assert "pymdownx.keys = {}\n" in result.content
    # A table added inside a dotted-key table stays on its dotted line.
    assert 'pymdownx.highlight = { line_spans = "__span" }\n' in result.content
    assert "[pymdownx" not in result.content


def test_a_shadowed_quoted_spelling_is_left_as_it_is():
    """Zensical reads the nested spelling; the quoted one it hides stays put."""
    original = (
        "[project.markdown_extensions]\n"
        '"pymdownx.keys" = { hidden = true }\n'
        "pymdownx.keys = { read = true }\n"
    )
    result = zensical_reconcile(original, overwrite=True)
    table = extensions(result.content)
    assert table["pymdownx.keys"] == {"hidden": True}
    assert table["pymdownx"]["keys"] == {"read": True}


def test_respelling_an_owned_extension_is_not_an_edit():
    """Owned in the nested spelling, rewritten quoted by hand: nothing to decide."""
    written = zensical_reconcile("", initializing=True)
    respelled = (
        "[project.markdown_extensions]\n"
        "toc.permalink = true\n"
        '"pymdownx.details" = {}\n'
        '"pymdownx.highlight" = { line_spans = "__span" }\n'
        '"pymdownx.keys" = {}\n'
    )
    result = zensical_reconcile(respelled, written.baseline)
    assert result.content == respelled
    assert not result.conflicts
    assert not result.preserved
    assert not result.proposals


def test_a_fresh_document_keeps_the_seed_spelling():
    result = zensical_reconcile("", initializing=True)
    assert result.content.count("pymdownx.") == 3
    assert '"pymdownx' not in result.content
    assert extensions(result.content)["toc"] == {"permalink": True}


def test_a_baseline_keeps_the_document_spelling():
    """A lockfile never changes because names are compared flat."""
    written = zensical_reconcile("", initializing=True)
    assert written.baseline == tomlkit.parse(ZENSICAL_EXTENSIONS).unwrap()
    repeated = zensical_reconcile(written.content, written.baseline)
    assert repeated.content == written.content
    assert repeated.baseline == written.baseline


_SECTIONED = """[project]
name = "app"

# ---- Ruff ---- #

[tool.ruff.lint]
select = ["E"]

# ---- Mypy ---- #

[tool.mypy]
strict = true
"""
_SECTIONED_BASE: dict[str, Value] = {
    "project": {"name": "app"},
    "tool": {"ruff": {"lint": {"select": ["E"]}}, "mypy": {"strict": True}},
}


def test_a_key_added_to_a_table_stays_above_the_next_sections_header():
    """The header comment opens the next section, so new values go above it."""
    from protostar.documents import toml_spec

    desired: dict[str, Value] = {
        "project": {"name": "app"},
        "tool": {
            "ruff": {"lint": {"select": ["E"], "extend-select": ["SIM"], "fix": True}},
            "mypy": {"strict": True},
        },
    }
    result = reconcile_toml(
        toml_spec("pyproject.toml"),
        _SECTIONED,
        desired,
        _SECTIONED_BASE,
        MergeLocation("pyproject.toml"),
    )

    assert result.content == _SECTIONED.replace(
        'select = ["E"]\n',
        'select = ["E"]\nextend-select = ["SIM"]\nfix = true\n',
    )
    assert result.content.count("# ---- Mypy ---- #") == 1


def test_a_key_added_to_a_table_without_a_closing_comment_is_appended():
    from protostar.documents import toml_spec

    original = '[tool.ruff.lint]\nselect = ["E"]\n\n[tool.mypy]\nstrict = true\n'
    base: dict[str, Value] = {
        "tool": {"ruff": {"lint": {"select": ["E"]}}, "mypy": {"strict": True}}
    }
    desired: dict[str, Value] = {
        "tool": {
            "ruff": {"lint": {"select": ["E"], "extend-select": ["SIM"]}},
            "mypy": {"strict": True},
        }
    }
    result = reconcile_toml(
        toml_spec("pyproject.toml"),
        original,
        desired,
        base,
        MergeLocation("pyproject.toml"),
    )

    assert result.content == original.replace(
        'select = ["E"]\n', 'select = ["E"]\nextend-select = ["SIM"]\n'
    )


# --- aggregation -----------------------------------------------------------------


def _aggregate(*contributions: tuple[str, str]):
    return aggregate_toml_document(
        [
            StructuredContribution(producer, content)
            for producer, content in contributions
        ]
    )


def test_a_later_module_overrides_an_earlier_one_at_any_depth():
    result = _aggregate(
        ("module:a", "[tool.x]\na = 1\n"),
        ("module:b", "[tool.x]\na = 2\n"),
    )

    assert result.value == {"tool": {"x": {"a": 2}}}
    assert tomlkit.dumps(result.document) == "[tool.x]\na = 2\n"


def test_a_template_overrides_every_module_whatever_its_order():
    result = _aggregate(
        ("template:t", "[tool.x]\na = 9\n"),
        ("module:a", "[tool.x]\na = 1\n"),
    )

    assert result.value == {"tool": {"x": {"a": 9}}}


def test_aggregation_continues_past_a_merged_table():
    result = _aggregate(
        ("module:a", "[t.x]\na = 1\n"),
        ("module:b", "[t.x]\nb = 2\n[t.y]\nc = 3\n"),
    )

    assert result.value == {"t": {"x": {"a": 1, "b": 2}, "y": {"c": 3}}}
    assert tomlkit.dumps(result.document) == "[t.x]\na = 1\nb = 2\n\n[t.y]\nc = 3\n"


def test_keys_a_contribution_adds_after_repeating_one_are_set_apart():
    """A blank line keeps each contribution's own keys together."""
    result = _aggregate(
        ("module:a", "[tool.x]\na = 1\n"),
        ("module:b", "[tool.x]\na = 1\nb = 2\nc = 3\n"),
    )

    assert tomlkit.dumps(result.document) == "[tool.x]\na = 1\n\nb = 2\nc = 3\n"


def test_keys_a_contribution_only_adds_are_not_set_apart():
    result = _aggregate(
        ("module:a", "[tool.x]\na = 1\n"),
        ("module:b", "[tool.x]\nb = 2\n"),
    )

    assert tomlkit.dumps(result.document) == "[tool.x]\na = 1\nb = 2\n"


# --- reconciliation edges ----------------------------------------------------------

PLAIN = TomlDocumentSpec()
PLAIN_LOCATION = MergeLocation("settings.toml")


def test_an_invalid_document_is_reported_with_a_hint():
    with pytest.raises(ConfigurationError) as error:
        reconcile_toml(PLAIN, "a = = 1", {}, MISSING, PLAIN_LOCATION)

    assert str(error.value) == "Invalid structured TOML file."
    assert error.value.hint == "Correct the target TOML syntax before retrying."


def test_an_unowned_document_takes_changes_without_proposals_by_default():
    result = reconcile_toml(PLAIN, "b = 1\n", {"a": 2}, MISSING, PLAIN_LOCATION)

    assert result.content == "b = 1\na = 2\n"
    assert not result.proposals


def test_a_deleted_owned_document_is_a_conflict_on_the_whole_file():
    result = reconcile_toml(
        PLAIN, "", {"a": 2}, {"a": 1}, PLAIN_LOCATION, missing_file=True
    )

    assert result.content == ""
    assert result.baseline == {"a": 1}
    [conflict] = result.conflicts
    assert (conflict.reason, conflict.location) == (
        ConflictReason.DELETED_ANCESTOR,
        PLAIN_LOCATION,
    )

    kept = reconcile_toml(
        PLAIN,
        "",
        {"a": 2},
        {"a": 1},
        PLAIN_LOCATION,
        missing_file=True,
        resolutions={conflict.id: ResolutionChoice.LOCAL},
    )
    assert (kept.content, kept.baseline, kept.conflicts) == ("", {"a": 2}, ())
    assert [settled.resolution for settled in kept.resolved] == [ResolutionChoice.LOCAL]


def test_a_declined_proposal_for_a_missing_document_is_reported():
    [proposal] = reconcile_toml(
        PLAIN, "", {"a": 2}, MISSING, PLAIN_LOCATION, missing_file=True, proposing=True
    ).proposals

    declined = reconcile_toml(
        PLAIN,
        "",
        {"a": 2},
        MISSING,
        PLAIN_LOCATION,
        missing_file=True,
        proposing=True,
        resolutions={proposal.id: ResolutionChoice.LOCAL},
    )

    assert declined.content == ""
    assert [settled.resolution for settled in declined.proposals] == [
        ResolutionChoice.LOCAL
    ]


def test_a_new_table_of_tables_writes_only_its_childrens_headers():
    result = reconcile_toml(
        PLAIN,
        "[project]\nname = 'x'\n",
        {"project": {"name": "x"}, "tool": {"ruff": {"a": 1}}},
        MISSING,
        PLAIN_LOCATION,
    )

    assert result.content == "[project]\nname = 'x'\n\n[tool.ruff]\na = 1\n"


def test_overwrite_keeps_owning_values_it_no_longer_declares():
    result = reconcile_toml(
        PLAIN,
        "a = 1\nold = 1\n",
        {"a": 2},
        {"a": 1, "old": 1},
        PLAIN_LOCATION,
        overwrite=True,
    )

    assert result.content == "a = 2\nold = 1\n"
    assert result.baseline == {"a": 2, "old": 1}


@pytest.mark.parametrize(
    ("original", "content"),
    [
        pytest.param("a = 1", "a = 1\nb = 2", id="no-final-newline"),
        pytest.param("a = 1\r\n", "a = 1\r\nb = 2\r\n", id="crlf"),
        pytest.param(
            "a = 1\n[u]\nc = 1 # X  \n",
            "a = 1\nb = 2\n\n[u]\nc = 1 # X  \n",
            id="last-line-kept-exactly",
        ),
        pytest.param(
            "a = 1\n[u]\nc = 1 # X\n",
            "a = 1\nb = 2\n\n[u]\nc = 1 # X\n",
            id="last-character-kept",
        ),
    ],
)
def test_a_changed_document_keeps_its_own_ending(original, content):
    desired = tomlkit.parse(original).unwrap() | {"b": 2}

    result = reconcile_toml(
        PLAIN, original, desired, tomlkit.parse(original).unwrap(), PLAIN_LOCATION
    )

    assert result.content == content


def test_a_layout_that_falls_back_says_why(mocker: MockerFixture):
    from protostar.documents import toml_spec

    mocker.patch(
        "protostar.documents.pyproject_layout.join_sections", return_value="= broken"
    )
    original = "[project]\nname = 'x'\n"

    result = reconcile_toml(
        toml_spec("pyproject.toml"),
        original,
        {"project": {"name": "x"}, "tool": {"mypy": {"strict": True}}},
        {"project": {"name": "x"}},
        MergeLocation("pyproject.toml"),
    )

    [note] = result.layout_notes
    assert note.startswith("Validation error while placing new pyproject.toml sections")
    assert tomllib.loads(result.content)["tool"] == {"mypy": {"strict": True}}


def test_a_key_added_below_several_keys_stays_above_the_closing_comment():
    from protostar.documents import toml_spec

    original = _SECTIONED.replace('select = ["E"]\n', 'select = ["E"]\nfix = true\n')
    base: dict[str, Value] = {
        "project": {"name": "app"},
        "tool": {
            "ruff": {"lint": {"select": ["E"], "fix": True}},
            "mypy": {"strict": True},
        },
    }
    desired: dict[str, Value] = {
        "project": {"name": "app"},
        "tool": {
            "ruff": {"lint": {"select": ["E"], "fix": True, "preview": True}},
            "mypy": {"strict": True},
        },
    }

    result = reconcile_toml(
        toml_spec("pyproject.toml"),
        original,
        desired,
        base,
        MergeLocation("pyproject.toml"),
    )

    assert result.content == original.replace(
        "fix = true\n", "fix = true\npreview = true\n"
    )


def test_an_inline_table_keeps_the_desired_spelling_under_a_dotted_key():
    desired = tomlkit.parse("tool.x.a = 1\ntool.x.b = {c=1}\n")

    result = reconcile_toml(
        PLAIN,
        "tool.x.a = 1\n",
        desired.unwrap(),
        {"tool": {"x": {"a": 1}}},
        PLAIN_LOCATION,
        desired_ast=desired,
    )

    assert result.content == "tool.x.a = 1\ntool.x.b = {c=1}\n"


@pytest.mark.parametrize(
    ("original", "desired_text", "content"),
    [
        pytest.param(
            "[tool.b]\nm = 1\n",
            "[tool.a.x]\nk = 1\n[tool.b]\nm = 1\n[tool.a.y]\nn = 1\n",
            "[tool.b]\nm = 1\n\n[tool.a.x]\nk = 1\n\n[tool.a.y]\nn = 1\n",
            id="headers",
        ),
        pytest.param(
            "[tool]\nb = 2\n",
            "[tool]\na.x = 1\nb = 2\na.y = 3\n",
            "[tool]\nb = 2\na.x = 1\na.y = 3\n",
            id="dotted-keys",
        ),
    ],
)
def test_a_table_the_desired_document_spreads_out_is_added_whole(
    original, desired_text, content
):
    desired = tomlkit.parse(desired_text)

    result = reconcile_toml(
        PLAIN,
        original,
        desired.unwrap(),
        tomlkit.parse(original).unwrap(),
        PLAIN_LOCATION,
        desired_ast=desired,
    )

    assert result.content == content


def test_a_table_added_under_a_dotted_root_key_stays_inline():
    original = "tool.x.a = 1\n"
    desired = tomlkit.parse("tool.x.a = 1\ntool.x.b = { c = 1 }\n")

    result = reconcile_toml(
        PLAIN,
        original,
        desired.unwrap(),
        {"tool": {"x": {"a": 1}}},
        PLAIN_LOCATION,
        desired_ast=desired,
    )

    assert result.content == "tool.x.a = 1\ntool.x.b = { c = 1 }\n"


# --- flat names --------------------------------------------------------------------

FLAT = TomlDocumentSpec(flat_names=(FlatNames(("ext",), frozenset({("a",), ("z",)})),))


def _flat(original: str, desired_text: str) -> tuple[str, Value]:
    desired = tomlkit.parse(desired_text)
    result = reconcile_toml(
        FLAT, original, desired.unwrap(), MISSING, PLAIN_LOCATION, desired_ast=desired
    )
    return result.content, result.baseline


def test_a_new_name_keeps_the_desired_spelling_when_the_document_has_none():
    content, baseline = _flat("[ext]\n", '[ext]\n"a.b" = {}\n')

    assert content == '[ext]\n"a.b" = {}\n'
    assert baseline == {"ext": {"a.b": {}}}


def test_a_new_name_follows_the_documents_nested_spelling():
    content, baseline = _flat("[ext]\na.x = {}\n", '[ext]\n"a.b" = {}\n')

    assert content == "[ext]\na.x = {}\na.b = {}\n"
    assert baseline == {"ext": {"a": {"b": {}}}}


def test_a_new_name_follows_its_own_namespaces_quoted_spelling():
    """Another namespace being nested says nothing about this one."""
    content, _ = _flat('[ext]\nz.q = {}\n"a.y" = {}\n', "[ext]\na.b = {}\n")

    assert content == '[ext]\nz.q = {}\n"a.y" = {}\n"a.b" = {}\n'


def test_a_dotted_name_inside_a_namespace_keeps_its_dots():
    content, _ = _flat("[ext]\n", '[ext]\na."b.c" = {}\n')

    assert tomllib.loads(content) == {"ext": {"a": {"b.c": {}}}}


def test_a_deleted_documents_baseline_keeps_the_desired_spelling():
    desired = tomlkit.parse('[ext]\n"a.b" = { x = 2 }\n')

    result = reconcile_toml(
        FLAT,
        "",
        desired.unwrap(),
        {"ext": {"a.b": {"x": 1}}},
        PLAIN_LOCATION,
        missing_file=True,
        desired_ast=desired,
    )

    assert result.content == ""
    assert result.baseline == {"ext": {"a.b": {"x": 1}}}


def test_a_name_outside_every_namespace_keeps_its_spelling():
    content, _ = _flat("[ext]\n", "[ext]\n[ext.toc]\nx = 1\n")

    assert content == "[ext]\n[ext.toc]\nx = 1\n"


def test_flat_names_under_a_missing_parent_are_skipped():
    spec = TomlDocumentSpec(
        flat_names=(FlatNames(("p", "q", "ext"), frozenset({("a",)})),)
    )

    result = reconcile_toml(
        spec, "[r]\nx = 1\n", {"r": {"x": 1}}, MISSING, PLAIN_LOCATION
    )

    assert result.content == "[r]\nx = 1\n"


NESTED = TomlDocumentSpec(
    flat_names=(FlatNames(("ext",), frozenset({("a",), ("a", "b")})),)
)


def _respelled(spec, original, desired_text, base=MISSING, **kwargs):
    desired = tomlkit.parse(desired_text)
    return reconcile_toml(
        spec,
        original,
        desired.unwrap(),
        base,
        PLAIN_LOCATION,
        desired_ast=desired,
        **kwargs,
    )


def test_the_nested_spelling_is_read_wherever_the_quoted_one_sits():
    result = _respelled(
        FLAT,
        '[ext]\na.b = { v = 1 }\n"a.b" = { hidden = true }\n',
        "[ext]\na.b = { v = 2 }\n",
        overwrite=True,
    )

    assert result.content == '[ext]\na.b = { v = 2 }\n"a.b" = { hidden = true }\n'


def test_every_shadowed_spelling_of_a_name_is_left_as_it_is():
    """Under nested namespaces one name has three spellings; the deepest is read."""
    result = _respelled(
        NESTED,
        '[ext]\n"a.b.c" = { q = 1 }\na."b.c" = { q = 2 }\na.b.c = { q = 3 }\n',
        "[ext]\na.b.c = { q = 9 }\n",
        overwrite=True,
    )

    assert result.content == (
        '[ext]\n"a.b.c" = { q = 1 }\na."b.c" = { q = 2 }\na.b.c = { q = 9 }\n'
    )


def test_a_new_name_nests_under_its_deepest_namespace():
    result = _respelled(NESTED, "[ext]\na.x = {}\n", '[ext]\n"a.b.c" = {}\n')

    assert result.content == "[ext]\na.x = {}\na.b = { c = {} }\n"


def test_an_owned_name_outside_every_namespace_keeps_its_dots():
    result = _respelled(FLAT, "[ext]\n", "[ext]\n", {"ext": {"q.x": {}}})

    assert result.baseline == {"ext": {"q.x": {}}}


def test_a_value_named_like_its_namespace_is_one_name():
    assert _respelled(FLAT, "[ext]\n", "[ext]\na = 1\n").content == "[ext]\na = 1\n"


def test_a_namespace_that_also_holds_a_value_stays_quoted():
    result = _respelled(FLAT, '[ext]\na = 1\n"a.y" = {}\n', "[ext]\na.b = {}\n")

    assert result.content == '[ext]\na = 1\n"a.y" = {}\n"a.b" = {}\n'


def test_a_table_added_under_a_dotted_key_at_the_root_stays_inline():
    result = reconcile_toml(
        PLAIN,
        "tool.a = 1\n",
        {"tool": {"a": 1, "b": {"c": 1}}},
        {"tool": {"a": 1}},
        PLAIN_LOCATION,
    )

    assert result.content == "tool.a = 1\ntool.b = { c = 1 }\n"


@pytest.mark.parametrize(
    ("original", "desired", "expected"),
    [
        (
            "x = { a = 1 }\n",
            {"x": {"a": 1, "n": {"c": 2}}},
            "x = { a = 1, n = { c = 2 }}\n",
        ),
        (
            "[t]\nx = { a = { b = 1 } }\n",
            {"t": {"x": {"a": {"b": 1, "n": {"c": 2}}}}},
            "[t]\nx = { a = { b = 1, n = { c = 2 }} }\n",
        ),
    ],
)
def test_a_table_added_inside_an_inline_table_stays_inline(original, desired, expected):
    base = tomllib.loads(original)

    result = reconcile_toml(PLAIN, original, desired, base, PLAIN_LOCATION)

    assert result.content == expected


def test_a_key_added_beside_a_retracted_one_stays_above_the_closing_comment():
    """A retracted key leaves a placeholder that must not hide the comment."""
    spec = TomlDocumentSpec(policy=MergePolicy(complete=True))

    result = reconcile_toml(
        spec,
        "[a]\nx = 1\ny = 2\n# next\n\n[b]\nq = 1\n",
        {"a": {"x": 1, "z": 3}, "b": {"q": 1}},
        {"a": {"x": 1, "y": 2}, "b": {"q": 1}},
        PLAIN_LOCATION,
    )

    assert result.content == "[a]\nx = 1\nz = 3\n# next\n\n[b]\nq = 1\n"


def test_a_changed_key_leaves_the_added_one_right_above_the_closing_comment():
    result = reconcile_toml(
        PLAIN,
        "[a]\nx = 1\ny = 1\n# next\n\n[b]\nq = 1\n",
        {"a": {"x": 2, "y": 1, "z": 3}, "b": {"q": 1}},
        {"a": {"x": 1, "y": 1}, "b": {"q": 1}},
        PLAIN_LOCATION,
    )

    assert result.content == "[a]\nx = 2\ny = 1\nz = 3\n# next\n\n[b]\nq = 1\n"
