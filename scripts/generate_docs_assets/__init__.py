"""Documentation presentation asset and fixture generation package."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import protostar.cli.schema
from scripts.generate_docs_assets.cli_terminals import (
    generate_cli_dry_run_svg,
    generate_cli_help_svgs,
    generate_cli_init_svg,
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
    _write_generated_doc,
)
from scripts.generate_docs_assets.diffs import generate_diff_fixtures
from scripts.generate_docs_assets.payloads import generate_agent_payloads
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
    "generate_cli_missing_tools_svg",
    "generate_cli_status_svg",
    "generate_default_config",
    "generate_diagnostic_panel_svg",
    "generate_diff_fixtures",
    "generate_docs_assets",
    "generate_guide_svgs",
    "generate_manifest_state",
    "generate_template_schema_fixture",
    "generate_tui_svgs",
    "tempfile",
]


def generate_docs_assets() -> None:
    """Generates all static documentation assets (SVGs, Markdown tables, schemas, payloads)."""
    DOCS_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_TERMINALS_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating static documentation assets...")
    generate_cli_help_svgs()
    generate_cli_dry_run_svg()
    generate_cli_init_svg()
    generate_cli_missing_tools_svg()
    generate_cli_status_svg()
    generate_guide_svgs()
    generate_tui_svgs()
    generate_default_config()
    generate_capability_tables()
    generate_manifest_state()
    generate_agent_payloads()
    _write_generated_doc(
        "review_schema.json", json.dumps(protostar.cli.schema.review_schema(), indent=2)
    )
    _write_generated_doc(
        "application_schema.json",
        json.dumps(protostar.cli.schema.application_schema(), indent=2),
    )
    generate_template_schema_fixture()
    generate_diagnostic_panel_svg()
    print("✔ Static documentation assets generated.\n")
