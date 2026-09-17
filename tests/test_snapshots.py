import importlib.util
import io
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from rich.console import Console
from rich.style import Style
from rich.text import Text

# Dynamically import generate_docs_assets script
_docs_script_path = Path(__file__).parent.parent / "scripts" / "generate_docs_assets.py"
_spec = importlib.util.spec_from_file_location(
    "generate_docs_assets", _docs_script_path
)
assert _spec
assert _spec.loader
_docs_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_docs_mod)

_calculate_content_width = _docs_mod._calculate_content_width
_render_and_write_svg = _docs_mod._render_and_write_svg

SCENARIO_FIXTURES = ("api", "astro", "cli", "dsp", "embedded", "ml", "ml_merged")


def test_calculate_content_width_plain_text():
    """Verify width calculation for plain text and trailing whitespace exclusion."""
    console = Console(record=True, width=100, file=io.StringIO())
    console.print("Hello world")
    assert _calculate_content_width(console) == 11

    console = Console(record=True, width=100, file=io.StringIO())
    console.print("Line 1 (short)")
    console.print("Line 2 is much longer than the others")
    console.print("Line 3")
    assert _calculate_content_width(console) == len(
        "Line 2 is much longer than the others"
    )

    # Trailing whitespace should be ignored
    console = Console(record=True, width=100, file=io.StringIO())
    console.print("Text with trailing spaces      ")
    assert _calculate_content_width(console) == len("Text with trailing spaces")


def test_calculate_content_width_styled_background():
    """Verify that trailing whitespace with a visible background is counted."""
    console = Console(record=True, width=100, file=io.StringIO())
    text = Text("Prefix")
    text.append("    ", style=Style(bgcolor="blue"))
    console.print(text)
    # 6 (Prefix) + 4 (spaces with blue background) = 10
    assert _calculate_content_width(console) == 10

    # Inverted / reversed style also has a visible background
    console = Console(record=True, width=100, file=io.StringIO())
    text = Text("Reverse")
    text.append("   ", style=Style(reverse=True))
    console.print(text)
    assert _calculate_content_width(console) == 10


def test_calculate_content_width_empty_and_whitespace():
    """Verify behavior on empty buffers or buffers with only whitespace."""
    console = Console(record=True, width=100, file=io.StringIO())
    assert _calculate_content_width(console, min_width=1) == 1

    console = Console(record=True, width=100, file=io.StringIO())
    console.print("   \n   \n\n")
    assert _calculate_content_width(console, min_width=5) == 5


def test_calculate_content_width_wide_characters():
    """Verify that full-width characters (e.g., CJK) are measured by cell length."""
    console = Console(record=True, width=100, file=io.StringIO())
    # '你好' consists of 2 characters, but occupies 4 cells in terminal width
    console.print("你好")
    assert _calculate_content_width(console) == 4


def test_render_and_write_svg_shrinkwraps(tmp_path, monkeypatch):
    """Verify that _render_and_write_svg shrinkwraps terminal width to content."""
    monkeypatch.setattr(_docs_mod, "DOCS_TERMINALS_DIR", tmp_path)

    console = Console(record=True, width=100, file=io.StringIO())
    console.print("A" * 40)

    _render_and_write_svg(
        console, title="zsh", filename="test_shrinkwrap.svg", unique_id="test_id"
    )

    output_file = tmp_path / "test_shrinkwrap.svg"
    assert output_file.exists()
    content = output_file.read_text()

    # 40 chars * 12.2 px = 488 px
    # padding_width = 16 px -> terminal_width = 504 px
    # margin_width = 2 px -> svg width = 506 px
    viewbox = re.search(r'viewBox="([^"]+)"', content)
    assert viewbox is not None
    vb_parts = viewbox.group(1).split()
    assert float(vb_parts[2]) == pytest.approx(506, abs=1)

    # Terminal chrome rect width
    rect_match = re.search(r'<rect [^>]*width="([0-9.]+)"[^>]*rx="8"', content)
    assert rect_match is not None
    assert float(rect_match.group(1)) == pytest.approx(504, abs=1)


def test_render_and_write_svg_deterministic(tmp_path, monkeypatch):
    """Verify that SVG generation produces byte-for-byte identical output across runs."""
    monkeypatch.setattr(_docs_mod, "DOCS_TERMINALS_DIR", tmp_path)

    def render_output():
        console = Console(record=True, width=100, file=io.StringIO())
        console.print("Deterministic test output line 1")
        console.print("Deterministic test output line 2 with more content")
        return console

    _render_and_write_svg(
        render_output(),
        title="zsh",
        filename="deterministic_1.svg",
        unique_id="det_test",
    )
    _render_and_write_svg(
        render_output(),
        title="zsh",
        filename="deterministic_2.svg",
        unique_id="det_test",
    )

    svg1 = (tmp_path / "deterministic_1.svg").read_text()
    svg2 = (tmp_path / "deterministic_2.svg").read_text()
    assert svg1 == svg2


def test_existing_svg_documentation_fixtures():
    """Verify that all generated SVG documentation fixtures exist and have shrinkwrapped widths."""
    terminals_dir = Path("docs/assets/terminals")
    expected_fixtures = {
        "cli_config_help.svg": 933,  # 75 cols
        "cli_dry_run.svg": 1080,  # 80 cols
        "diagnostic_panel.svg": 1006,  # 81 cols
        "cli_help.svg": 1165,  # 94 cols
        "cli_init_help.svg": 1238,  # 100 cols
    }

    for filename, expected_width in expected_fixtures.items():
        svg_path = terminals_dir / filename
        assert svg_path.exists(), f"Missing terminal SVG fixture {filename}"
        content = svg_path.read_text(encoding="utf-8")

        # Must parse as valid XML
        root = ET.fromstring(content)
        assert root.tag.endswith("svg")

        # Verify viewBox width matches expected shrinkwrapped dimension
        viewbox = root.attrib.get("viewBox")
        assert viewbox is not None
        vb_width = float(viewbox.split()[2])
        assert vb_width == pytest.approx(expected_width, abs=1)


def test_scenario_fixtures_capture_consistent_reconciliation_state():
    """Verify scenario snapshots retain state and its materialized dependencies."""
    snapshots_dir = Path("tests/snapshots")
    for name in SCENARIO_FIXTURES:
        root = snapshots_dir / name
        state_path = root / ".protostar.lock.toml"
        assert state_path.exists(), f"Missing reconciliation state for {name}"
        state = tomllib.loads(state_path.read_text())
        pyproject = tomllib.loads((root / "pyproject.toml").read_text())
        groups = {
            "main": pyproject.get("project", {}).get("dependencies", []),
            **pyproject.get("dependency-groups", {}),
        }
        for record in state.get("dependencies", []):
            assert record["materialized"] in groups[record["group"]]


def test_ml_rerun_preserves_foreign_workspace_content_and_tool_order():
    """Verify the merged fixture exercises preservation without template switching."""
    root = Path("tests/snapshots/ml_merged")
    pyproject_text = (root / "pyproject.toml").read_text()
    pyproject = tomllib.loads(pyproject_text)
    dependencies = pyproject["project"]["dependencies"]
    assert any(requirement.startswith("astropy>=") for requirement in dependencies)
    assert any(requirement.startswith("specutils>=") for requirement in dependencies)
    original_text = Path("tests/snapshots/ml/pyproject.toml").read_text()
    original_tools = original_text[original_text.index("# ---- Ruff ---- #") :]
    merged_tools = pyproject_text[pyproject_text.index("# ---- Ruff ---- #") :]
    assert merged_tools.startswith(original_tools)
    assert merged_tools[len(original_tools) :].lstrip().startswith("# ---- Mypy ---- #")
    ignores = (root / ".gitignore").read_text()
    assert all(pattern in ignores for pattern in ("*.csv", "*.fits", "*.parquet"))

    state = tomllib.loads((root / ".protostar.lock.toml").read_text())
    owned_names = {record["name"] for record in state["dependencies"]}
    assert "mypy" in owned_names
    assert "astropy" not in owned_names


def test_exit_codes_documentation_matches_cli_behavior():
    """Verifies that table_exit_codes.md accurately documents CLI exit code mappings."""
    table_path = Path("docs/generated/table_exit_codes.md")
    assert table_path.exists()
    content = table_path.read_text(encoding="utf-8")

    # Assert accurate exit code mappings
    assert "| `78` | `os.EX_CONFIG` | `ConfigurationError` |" in content
    assert "| `65` | `os.EX_DATAERR` | `TemplateResolutionError` |" in content
    assert (
        "| `69` | `os.EX_UNAVAILABLE` | `MissingDependencyError`<br>`AggregatedDependencyError` |"
        in content
    )
    assert "| `74` | `os.EX_IOERR` | `FileSystemError` |" in content
    assert "| `75` | `os.EX_TEMPFAIL` | `NetworkFetchError` |" in content
    assert "| `77` | `os.EX_NOPERM` | `SecurityViolationError` |" in content
    assert "| `70` | `os.EX_SOFTWARE` | *(Unhandled exception)* |" in content

    # Ensure stale / inaccurate errors are absent
    assert "InvalidRollbackStateError" not in content
    assert "`73`" not in content
