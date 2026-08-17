import tomllib
from pathlib import Path

import tomlkit

from protostar.manifest import Severity
from protostar.toml_ast import (
    deep_merge_tomlkit,
    format_pyproject_toml,
    merge_toml_payloads,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_deep_merge_tomlkit_complex_fixtures():
    """Test the recursive dictionary merge algorithm using chaotic tomlkit structures."""
    base_content = (FIXTURES_DIR / "base_complex.toml").read_text()
    payload_content = (FIXTURES_DIR / "payload_complex.toml").read_text()

    base_doc = tomlkit.parse(base_content)
    payload_doc = tomlkit.parse(payload_content)

    deep_merge_tomlkit(base_doc, payload_doc)

    merged_dict = base_doc.unwrap()

    # 1. Verify scalar overrides (line-length changed 120 -> 88)
    assert merged_dict["tool"]["ruff"]["line-length"] == 88

    # 2. Verify non-colliding existing keys were preserved
    assert merged_dict["tool"]["ruff"]["target-version"] == "py310"
    assert merged_dict["project"]["name"] == "protostar-test"

    # 3. Verify nested list replacements
    assert "UP" in merged_dict["tool"]["ruff"]["lint"]["select"]

    # 4. Verify new root tables were injected
    assert merged_dict["tool"]["mypy"]["strict"] is True

    # 5. Verify Array of Tables (AoT) concatenation (MERGE strategy default behavior)
    assert len(merged_dict["tool"]["mypy"]["overrides"]) == 2
    assert merged_dict["tool"]["mypy"]["overrides"][0]["module"] == "tests.*"
    assert merged_dict["tool"]["mypy"]["overrides"][1]["module"] == "legacy_module.*"

    # 6. Verify comments survived the AST manipulation
    dumped = tomlkit.dumps(base_doc)
    assert "# We expect this comment to survive the merge" in dumped
    assert "# A random comment inside an array" in dumped


def test_deep_merge_tomlkit_empty_aot():
    """Test that injecting an empty Array of Tables safely bypasses the newline append logic."""
    base = tomlkit.document()
    payload = tomlkit.document()

    payload.append("empty_array", tomlkit.aot())
    deep_merge_tomlkit(base, payload)

    result = base.unwrap()
    assert "empty_array" in result
    assert len(result["empty_array"]) == 0


def test_deep_merge_tomlkit_fresh_doc():
    base = tomlkit.document()
    payload = tomlkit.parse("[tool.ruff]\nline-length = 88\n")

    deep_merge_tomlkit(base, payload)

    assert "tool" in base
    assert base["tool"]["ruff"]["line-length"] == 88


def test_deep_merge_tomlkit_preserves_foreign_comments():
    base_toml = """# File header comment
[tool.ruff]
# Ruff config comment
line-length = 88 # Inline comment
"""
    base = tomlkit.parse(base_toml)
    payload = tomlkit.parse('[tool.ruff.lint]\nselect = ["E", "F"]\n')

    deep_merge_tomlkit(base, payload)

    dumped = tomlkit.dumps(base)
    assert "# File header comment" in dumped
    assert "# Ruff config comment" in dumped
    assert "# Inline comment" in dumped
    assert 'select = ["E", "F"]' in dumped


def test_deep_merge_tomlkit_overwrite_purges_unmatched_scalars():
    base_toml = """[tool.ruff]
line-length = 120
target-version = "py312"

[tool.pytest.ini_options]
minversion = "7.0"
"""
    base = tomlkit.parse(base_toml)
    payload = tomlkit.parse("[tool.ruff]\nline-length = 88\n")

    # Overwrite mode should purge unmatched scalar 'target-version' in [tool.ruff],
    # but keep sibling table [tool.pytest.ini_options]
    deep_merge_tomlkit(base, payload, overwrite=True)

    assert base["tool"]["ruff"]["line-length"] == 88
    assert "target-version" not in base["tool"]["ruff"]
    assert base["tool"]["pytest"]["ini_options"]["minversion"] == "7.0"


def test_deep_merge_tomlkit_replace_marker():
    base_toml = """[tool.example]
keep_this = true

[tool.example.nested]
old_key = 1
"""
    base = tomlkit.parse(base_toml)
    payload_toml = """[tool.example.nested]
__replace__ = true
new_key = 2
"""
    payload = tomlkit.parse(payload_toml)

    deep_merge_tomlkit(base, payload)

    assert base["tool"]["example"]["nested"]["new_key"] == 2
    assert "old_key" not in base["tool"]["example"]["nested"]
    assert "__replace__" not in base["tool"]["example"]["nested"]


def test_deep_merge_tomlkit_replace_nested_hierarchy():
    base_toml = """[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["A", "B"]
ignore = ["E501"]
"""
    payload_toml = """[tool.ruff.lint]
__replace__ = true
select = ["A", "B", "C4", "D"]
ignore = ["D100"]

[tool.ruff.lint.pydocstyle]
convention = "google"
"""
    base_doc = tomlkit.parse(base_toml)
    payload_doc = tomlkit.parse(payload_toml)

    deep_merge_tomlkit(base_doc, payload_doc)

    assert base_doc["tool"]["ruff"]["line-length"] == 88
    lint = base_doc["tool"]["ruff"]["lint"]
    assert lint["select"] == ["A", "B", "C4", "D"]
    assert lint["ignore"] == ["D100"]
    assert lint["pydocstyle"]["convention"] == "google"
    assert "__replace__" not in lint


def test_deep_merge_tomlkit_aot_append_vs_overwrite():
    base_toml = """[[tool.mypy.overrides]]
module = "tests.*"
ignore_errors = true
"""
    base = tomlkit.parse(base_toml)
    payload = tomlkit.parse("""[[tool.mypy.overrides]]
module = "legacy_module.*"
ignore_errors = false
""")

    # Append mode (overwrite=False)
    deep_merge_tomlkit(base, payload, overwrite=False)
    assert len(base["tool"]["mypy"]["overrides"]) == 2
    assert base["tool"]["mypy"]["overrides"][0]["module"] == "tests.*"
    assert base["tool"]["mypy"]["overrides"][1]["module"] == "legacy_module.*"

    # Overwrite mode replaces entire AoT
    base2 = tomlkit.parse(base_toml)
    deep_merge_tomlkit(base2, payload, overwrite=True)
    assert len(base2["tool"]["mypy"]["overrides"]) == 1
    assert base2["tool"]["mypy"]["overrides"][0]["module"] == "legacy_module.*"


def test_deep_merge_tomlkit_array_deduplication():
    base = tomlkit.parse('[project]\ndependencies = ["fastapi", "uvicorn"]\n')
    payload = tomlkit.parse('[project]\ndependencies = ["uvicorn", "pydantic"]\n')

    deep_merge_tomlkit(base, payload, overwrite=False)

    deps = list(base["project"]["dependencies"])
    assert deps == ["fastapi", "uvicorn", "pydantic"]


def test_deep_merge_tomlkit_type_parity_guard_table():
    base = tomlkit.parse('[tool]\nruff = "not a table"\n')
    payload = tomlkit.parse("[tool.ruff]\nline-length = 88\n")
    conflicts = []

    deep_merge_tomlkit(
        base,
        payload,
        on_conflict=lambda msg, sev: conflicts.append((msg, sev)),
    )

    assert len(conflicts) == 1
    msg, sev = conflicts[0]
    assert sev == Severity.WARNING
    assert "Expected a Table for key 'ruff'" in msg
    assert base["tool"]["ruff"] == "not a table"


def test_deep_merge_tomlkit_type_parity_guard_aot():
    base = tomlkit.parse('[tool.mypy]\noverrides = "not an AoT"\n')
    payload = tomlkit.parse('[[tool.mypy.overrides]]\nmodule = "tests.*"\n')
    conflicts = []

    deep_merge_tomlkit(
        base,
        payload,
        on_conflict=lambda msg, sev: conflicts.append((msg, sev)),
    )

    assert len(conflicts) == 1
    assert "Expected an Array of Tables" in conflicts[0][0]


def test_deep_merge_tomlkit_type_parity_guard_array():
    base = tomlkit.parse('[project]\ndependencies = "not an array"\n')
    payload = tomlkit.parse('[project]\ndependencies = ["pytest"]\n')
    conflicts = []

    deep_merge_tomlkit(
        base,
        payload,
        on_conflict=lambda msg, sev: conflicts.append((msg, sev)),
    )

    assert len(conflicts) == 1
    assert "Expected an Array for key 'dependencies'" in conflicts[0][0]


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


def test_merge_toml_payloads_pyproject():
    orig = """[project]
name = "my-app"
version = "0.1.0"
"""
    payloads = [
        "[tool.ruff]\nline-length = 88\n",
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
    ]

    result = merge_toml_payloads(orig, payloads, is_pyproject=True)

    assert "[project]" in result
    assert "[tool.ruff]" in result
    assert "[tool.pytest.ini_options]" in result
    assert "# Tool Configuration" in result
    assert "# ---- Ruff ---- #" in result
    assert "# ---- Pytest ---- #" in result
    # Check valid TOML
    parsed = tomllib.loads(result)
    assert parsed["project"]["name"] == "my-app"
    assert parsed["tool"]["ruff"]["line-length"] == 88


def test_merge_toml_payloads_generic():
    orig = '[database]\nurl = "sqlite:///:memory:"\n'
    payloads = ["[database]\npool_size = 5\n", '[logging]\nlevel = "DEBUG"\n']

    result = merge_toml_payloads(orig, payloads, is_pyproject=False)
    parsed = tomllib.loads(result)
    assert parsed["database"]["url"] == "sqlite:///:memory:"
    assert parsed["database"]["pool_size"] == 5
    assert parsed["logging"]["level"] == "DEBUG"
