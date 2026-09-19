import tomllib
from pathlib import Path

import tomlkit

from protostar.toml_ast import (
    format_pyproject_toml,
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

    formatted = format_pyproject_toml(doc)

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
    pass1 = format_pyproject_toml(doc)
    doc2 = tomlkit.parse(pass1)
    pass2 = format_pyproject_toml(doc2)

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

    formatted = format_pyproject_toml(doc)

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
    formatted = format_pyproject_toml(doc)

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
    formatted = format_pyproject_toml(doc)

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
    formatted = format_pyproject_toml(doc)

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

    formatted = format_pyproject_toml(doc)
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

    formatted = format_pyproject_toml(doc)
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
    formatted = format_pyproject_toml(doc)

    assert "# ---- rumdl ---- #" in formatted
    assert "# ---- rumdl ---- #\n\n[tool.rumdl]" in formatted


def test_set_extension_preserves_existing_member_comments():
    """Accepted set additions retain the local array's nodes and presentation."""
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
        result.content,
        desired.unwrap(),
        result.baseline,
        MergeLocation("pyproject.toml"),
        desired_ast=desired,
    )
    assert repeated.content == result.content


def test_adding_tool_preserves_existing_document_presentation():
    """Semantic equality never authorizes reformatting pre-existing tables."""
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
    result = reconcile_toml(
        original,
        desired.unwrap(),
        base,
        MergeLocation("pyproject.toml"),
        desired_ast=desired,
    )
    assert result.content.startswith(original)
    assert "[tool.mypy]\nstrict=true\n" in result.content
    repeated = reconcile_toml(
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
    formatted = format_pyproject_toml(tomlkit.parse(UV_APPENDED_LAYOUT))
    pos = _header_positions(formatted)

    assert -1 not in pos.values()
    assert pos["[dependency-groups]"] < pos["[tool.hatch"] < pos["# Tool Configuration"]
    assert pos["# Tool Configuration"] < pos["# ---- Ruff ---- #"]


def test_format_pyproject_toml_labels_the_protostar_section_last():
    formatted = format_pyproject_toml(tomlkit.parse(UV_APPENDED_LAYOUT))
    pos = _header_positions(formatted)

    assert (
        pos["# ---- Ruff ---- #"]
        < pos["# ---- Protostar ---- #"]
        < pos["[tool.protostar]"]
    )
    assert formatted.count("# ---- Protostar ---- #") == 1


def test_format_pyproject_toml_separates_every_table_with_a_blank_line():
    formatted = format_pyproject_toml(tomlkit.parse(UV_APPENDED_LAYOUT))
    lines = formatted.split("\n")

    for index, line in enumerate(lines[1:], start=1):
        if line.startswith("["):
            previous = lines[index - 1]
            assert previous == "" or previous.startswith("#"), (
                f"no blank line before {line!r}"
            )


def test_format_pyproject_toml_layout_is_idempotent_with_protostar_section():
    once = format_pyproject_toml(tomlkit.parse(UV_APPENDED_LAYOUT))
    twice = format_pyproject_toml(tomlkit.parse(once))

    assert once == twice


def test_finalize_new_pyproject_fixes_the_layout_uv_and_the_recipe_leave():
    from protostar.toml_ast import finalize_new_pyproject

    finalized = finalize_new_pyproject(UV_APPENDED_LAYOUT)

    assert finalized == format_pyproject_toml(tomlkit.parse(UV_APPENDED_LAYOUT))
    assert tomllib.loads(finalized) == tomllib.loads(UV_APPENDED_LAYOUT)
