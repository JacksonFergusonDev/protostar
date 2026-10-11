"""Textual TUI screen automation, async snapshot driving, and interactive SVGs."""

from __future__ import annotations

import asyncio
import importlib.resources
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

from protostar.config import TemplateSource, UserConfig
from protostar.fs import atomic_write_text
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from scripts.generate_docs_assets.common import (
    DOCS_TERMINALS_DIR,
    demo_project,
    stub_which,
)
from scripts.generate_docs_assets.svg import frame_terminal_svg


async def _settle(pilot: Any) -> None:
    """Waits for the app's workers, including those a finishing worker starts."""
    from textual.worker import WorkerCancelled

    await pilot.pause()
    for _ in range(10):
        workers = list(pilot.app.workers)
        if not workers:
            break
        for worker in workers:
            try:
                await worker.wait()
            except WorkerCancelled:
                pass
            await pilot.pause()
    await pilot.pause()


def _write_tui_svg(app: Any, filename: str, title: str = "protostar init") -> None:
    """Writes the app's current screen to DOCS_TERMINALS_DIR."""
    svg_content = app.export_screenshot(title=title)
    atomic_write_text(
        DOCS_TERMINALS_DIR / filename, frame_terminal_svg(svg_content, title)
    )


async def _capture_tui_screens() -> None:
    """Drives the recipe editor to the change review, capturing each screen."""
    from protostar.cli.tui.app import DecisionApp
    from protostar.cli.tui.recipe.screen import RecipeScreen
    from protostar.init_draft import DraftTemplate, InitDraft
    from protostar.templates import discover_templates

    config = UserConfig()
    target = importlib.resources.files("protostar.templates").joinpath("cli.toml")
    template = DraftTemplate(TemplateSource.load(str(target), built_in="cli"))
    app = DecisionApp(
        RecipeScreen(InitDraft(template=template), discover_templates(config), config)
    )
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        _write_tui_svg(app, "tui_recipe_editor.svg")
        await pilot.click("#continue")
        await _settle(pilot)
        _write_tui_svg(app, "tui_change_review.svg")
        app.exit(None)


def _conflict_manifest(renovate: str, line_length: int, command: str) -> Any:
    """A lifecycle manifest with a JSON value, a TOML key, and a text region."""
    manifest = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    manifest.filesystem.add_file_injection(
        ".github/renovate.json", json.dumps({"extends": [renovate]}) + "\n"
    )
    manifest.filesystem.add_structured(
        "pyproject.toml",
        f"[tool.ruff]\nline-length = {line_length}\n",
        producer="module:ruff",
    )
    manifest.filesystem.add_region(
        "AGENTS.md", f"Run `{command}` before pushing.", identity="demo:commands"
    )
    return manifest


async def _capture_conflict_screen() -> None:
    """Captures the sync conflict screen over three kinds of conflict."""
    from protostar.cli.tui.app import DecisionApp
    from protostar.cli.tui.conflicts.screen import ConflictScreen
    from protostar.executor import SystemExecutor
    from protostar.lifecycle import PreparedProject
    from protostar.preparation import prepare_review

    config = UserConfig()
    baseline = _conflict_manifest("config:recommended", 88, "just test")
    SystemExecutor(
        baseline, config, review=prepare_review(baseline, config, hook_revisions=())
    ).execute()
    renovate = Path(".github/renovate.json")
    renovate.write_text(renovate.read_text().replace("recommended", "base"))
    pyproject = Path("pyproject.toml")
    pyproject.write_text(pyproject.read_text().replace("88", "100"))
    agents = Path("AGENTS.md")
    agents.write_text(agents.read_text().replace("just test", "just check"))
    manifest = _conflict_manifest("config:best-practices", 120, "just ci")
    project = PreparedProject(
        manifest, config, prepare_review(manifest, config, hook_revisions=())
    )
    app = DecisionApp(ConflictScreen(project))
    async with app.run_test(size=(120, 36)) as pilot:
        await _settle(pilot)
        await pilot.press("down", "down", "b")
        await _settle(pilot)
        _write_tui_svg(app, "tui_sync_conflicts.svg", "protostar sync")
        app.exit(None)


def generate_tui_svgs() -> None:
    """Captures the recipe editor, change review, and conflict screen."""
    with (
        demo_project(),
        mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}),
        mock.patch("protostar.metadata.get_git_config", return_value=None),
        # Every tool installed, so the host's PATH never marks a row.
        mock.patch("shutil.which", stub_which),
    ):
        asyncio.run(_capture_tui_screens())
    orig_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            os.chdir(tmp_dir)
            asyncio.run(_capture_conflict_screen())
        finally:
            os.chdir(orig_cwd)
