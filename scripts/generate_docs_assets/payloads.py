"""Machine-readable JSON payloads and API schema generators for agent interfaces."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import protostar.cli.schema
from protostar.config import UserConfig
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.models import ExecutionResult
from protostar.preparation import prepare_review
from scripts.generate_docs_assets.common import (
    _write_generated_doc,
    cli_json,
    demo_project,
    stable_host,
)

# An existing project with no recipe yet, so the planned payload shows analysis.
_EXISTING_PYPROJECT = (
    '[project]\nname = "demo"\nrequires-python = ">=3.12"\n'
    'authors = [{ name = "Demo Author" }]\n'
    'dependencies = []\n\n[dependency-groups]\ndev = ["pytest"]\n\n'
    "[tool.ruff]\nline-length = 100\n"
)


def generate_agent_payloads() -> None:
    """Generates JSON payloads for the Agent & Machine Interface documentation."""
    orig_cwd = Path.cwd()
    # 1. The payloads a reader's own command prints: a dry run in an existing
    #    project, and the collision an init without a strategy stops at.
    with demo_project(), stable_host():
        Path("pyproject.toml").write_text(_EXISTING_PYPROJECT, encoding="utf-8")
        Path("LICENSE").write_text(
            "MIT License\n\nCopyright (c) 2024 Demo Author\n", encoding="utf-8"
        )
        planned = cli_json("init", "--dry-run", "--force-merge")
        error = cli_json("init", "--template", "cli", allow_error=True)
    _write_generated_doc("agent_payload_planned.json", json.dumps(planned, indent=2))
    _write_generated_doc("agent_payload_error.json", json.dumps(error, indent=2))

    # Lifecycle examples use the shipped preparation and presentation path.
    from protostar.cli.reviews import review_payload
    from protostar.sync_state import serialize_state

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            os.chdir(tmp_dir)
            baseline = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
            baseline.filesystem.add_file_injection(
                ".github/renovate.json", '{"value": "original"}\n'
            )
            initial = prepare_review(baseline, UserConfig(), hook_revisions=())
            Path("protostar.lock").write_text(serialize_state(initial.candidate_state))
            manifest = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
            manifest.filesystem.add_file_injection("safe.txt", "accepted\n")
            manifest.filesystem.add_file_injection(
                ".github/renovate.json", '{"value": "desired"}\n'
            )
            Path(".github").mkdir()
            Path(".github/renovate.json").write_text('{"value": "local"}\n')
            review = prepare_review(manifest, UserConfig(), hook_revisions=())
            payload = review_payload(review)
            _write_generated_doc(
                "agent_payload_reviewed.json", json.dumps(payload, indent=2)
            )
            payload["check_passed"] = not review.pending
            _write_generated_doc(
                "agent_payload_check.json", json.dumps(payload, indent=2)
            )
        finally:
            os.chdir(orig_cwd)

    # 2. Success payload, through ExecutionResult's own serialization
    paths = frozenset(
        [
            ".gitignore",
            "pyproject.toml",
            "src/my_app/__init__.py",
            "tests/test_cli.py",
        ]
    )
    result = ExecutionResult(
        created_paths=paths,
        mutated_paths=frozenset(),
        diagnostics=(),
    )
    success_payload = {
        "api_version": protostar.cli.schema.CLI_API_VERSION,
        "status": "success",
        "result": result.to_dict(),
    }
    _write_generated_doc(
        "agent_payload_success.json", json.dumps(success_payload, indent=2)
    )
