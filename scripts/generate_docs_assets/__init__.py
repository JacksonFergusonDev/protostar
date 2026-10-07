"""Documentation presentation asset and fixture generation package."""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import OutputStyle, report
from scripts.generate_docs_assets.cli_tables import generate_cli_tables
from scripts.generate_docs_assets.cli_terminals import (
    generate_cli_dry_run_svg,
    generate_cli_help_svgs,
    generate_cli_init_svg,
    generate_cli_missing_dependency_svg,
    generate_cli_missing_tools_svg,
    generate_cli_status_svg,
    generate_diagnostic_panel_svg,
    generate_guide_svgs,
)
from scripts.generate_docs_assets.common import (
    DOCS_GENERATED_DIR,
    DOCS_TERMINALS_DIR,
    REPO_ROOT,
    SNAPSHOTS_DIR,
)
from scripts.generate_docs_assets.diffs import generate_diff_fixtures
from scripts.generate_docs_assets.key_tables import generate_key_tables
from scripts.generate_docs_assets.payloads import generate_agent_payloads
from scripts.generate_docs_assets.schemas import generate_schema_tables
from scripts.generate_docs_assets.tables import (
    generate_capability_tables,
    generate_default_config,
    generate_manifest_state,
    generate_template_schema_fixture,
)
from scripts.generate_docs_assets.tui_terminals import generate_tui_svgs

__all__ = [
    "DOCS_GENERATED_DIR",
    "DOCS_TERMINALS_DIR",
    "REPO_ROOT",
    "SNAPSHOTS_DIR",
    "generate_agent_payloads",
    "generate_capability_tables",
    "generate_cli_dry_run_svg",
    "generate_cli_help_svgs",
    "generate_cli_init_svg",
    "generate_cli_missing_dependency_svg",
    "generate_cli_missing_tools_svg",
    "generate_cli_status_svg",
    "generate_cli_tables",
    "generate_default_config",
    "generate_diagnostic_panel_svg",
    "generate_diff_fixtures",
    "generate_docs_assets",
    "generate_guide_svgs",
    "generate_key_tables",
    "generate_manifest_state",
    "generate_schema_tables",
    "generate_template_schema_fixture",
    "generate_tui_svgs",
]


def generate_docs_assets() -> None:
    """Generates all static documentation assets (SVGs, Markdown tables, payloads)."""
    DOCS_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_TERMINALS_DIR.mkdir(parents=True, exist_ok=True)

    report("Generating static documentation assets...", style=OutputStyle.TITLE)
    generate_cli_help_svgs()
    generate_cli_dry_run_svg()
    generate_cli_init_svg()
    generate_cli_missing_dependency_svg()
    generate_cli_missing_tools_svg()
    generate_cli_status_svg()
    generate_guide_svgs()
    generate_tui_svgs()
    generate_default_config()
    generate_capability_tables()
    generate_cli_tables()
    generate_key_tables()
    generate_manifest_state()
    generate_agent_payloads()
    generate_schema_tables()
    generate_template_schema_fixture()
    generate_diagnostic_panel_svg()
    report("OK Static documentation assets generated.\n", style=OutputStyle.SUCCESS)
