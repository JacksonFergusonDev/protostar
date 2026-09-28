"""Machine-readable JSON payloads and API schema generators for agent interfaces."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import protostar.cli.schema
from protostar.cli.changes import classify, entries_record
from protostar.config import UserConfig
from protostar.errors import WorkspaceCollisionError
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.models import ExecutionResult
from protostar.modules import (
    BootstrapModule,
    PythonCore,
    RuffModule,
    SystemWorkspaceModule,
)
from protostar.preparation import ExecutionPolicy, prepare_review, review_phase
from scripts.generate_docs_assets.common import _write_generated_doc


def generate_agent_payloads() -> None:
    """Generates JSON payloads for the Agent & Machine Interface documentation."""
    orig_cwd = Path.cwd()
    import scripts.generate_docs_assets as pkg

    temp_dir_cls = getattr(pkg, "tempfile", tempfile).TemporaryDirectory
    with temp_dir_cls() as tmp_dir:
        try:
            os.chdir(tmp_dir)
            # 1. Planned payload computed dynamically from an EnvironmentManifest
            manifest = EnvironmentManifest(
                metadata={
                    "description": "High-velocity CLI application.",
                    "author_name": "Demo Author",
                    "license": "MIT",
                }
            )
            bootstrap_mods: list[BootstrapModule] = [
                SystemWorkspaceModule(),
                PythonCore(user_config=UserConfig()),
                RuffModule(),
            ]
            for b_mod in bootstrap_mods:
                b_mod.build(manifest)

            # Set mock IDE settings for stable deterministic fixtures
            manifest.ide_settings = {
                "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
                "python.terminal.activateEnvironment": True,
            }

            # Analysis reads a separate example project, so the manifest above
            # stays that of a new one.
            from protostar.analysis import analyze_project

            existing = Path(tmp_dir, "existing")
            existing.mkdir()
            (existing / "pyproject.toml").write_text(
                '[project]\nname = "demo"\nrequires-python = ">=3.12"\n'
                'authors = [{ name = "Demo Author" }]\n'
                'dependencies = []\n\n[dependency-groups]\ndev = ["pytest"]\n\n'
                "[tool.ruff]\nline-length = 100\n"
            )
            (existing / "LICENSE").write_text(
                "MIT License\n\nCopyright (c) 2024 Demo Author\n"
            )
            prepared = prepare_review(
                manifest,
                UserConfig(),
                policy=ExecutionPolicy.INITIALIZATION,
                phase=review_phase(manifest),
            )
            planned_payload = {
                "api_version": protostar.cli.schema.CLI_API_VERSION,
                "status": "planned",
                "manifest": manifest.to_dict(),
                "entries": entries_record(classify(manifest, prepared)),
                "review": prepared.to_dict(),
                "analysis": analyze_project(existing).to_dict(),
            }
            _write_generated_doc(
                "agent_payload_planned.json", json.dumps(planned_payload, indent=2)
            )
        finally:
            os.chdir(orig_cwd)

    # Lifecycle examples use the shipped preparation and presentation path.
    from protostar.cli.reviews import review_payload
    from protostar.sync_state import serialize_state

    with temp_dir_cls() as tmp_dir:
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

    # 2. Success payload generated dynamically using ExecutionResult
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

    # 3. Error payload generated dynamically using WorkspaceCollisionError
    err = WorkspaceCollisionError(paths=frozenset([Path("pyproject.toml")]))
    error_dict: dict[str, Any] = {
        "type": type(err).__name__,
        "message": str(err),
    }
    if err.hint:
        error_dict["hint"] = err.hint
    if err.docs_url:
        error_dict["docs_url"] = err.docs_url
    if isinstance(err, WorkspaceCollisionError):
        error_dict["paths"] = sorted(str(p) for p in err.paths)

    error_payload = {
        "api_version": protostar.cli.schema.CLI_API_VERSION,
        "status": "error",
        "error": error_dict,
    }
    _write_generated_doc(
        "agent_payload_error.json", json.dumps(error_payload, indent=2)
    )
