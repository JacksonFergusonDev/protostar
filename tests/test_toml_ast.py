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
