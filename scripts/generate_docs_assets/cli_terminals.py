"""CLI execution simulation, prompt recording, and command help/preview SVGs."""

from __future__ import annotations

import argparse
import importlib.resources
import io
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest import mock

import tomlkit
from rich.console import Console
from rich.text import Text

import protostar.cli
from protostar.cli.changes import hook_snapshot, prepare_draft, print_dry_run
from protostar.cli.reviews import handle_review
from protostar.config import TemplateSource, UserConfig
from protostar.manifest import DiagnosticEvent, DiagnosticPhase, Severity
from protostar.models import InitRequest
from protostar.modules import (
    TOOLING_MODULES,
    BootstrapModule,
    PythonCore,
    SystemWorkspaceModule,
)
from protostar.orchestrator import Orchestrator
from protostar.system import ProcessRunner
from scripts.generate_docs_assets.svg import (
    _print_prompt,
    _recording_console,
    _render_and_write_svg,
)


def generate_cli_help_svgs() -> None:
    """Captures isolated SVG snapshots of the Protostar CLI help menus via Rich."""
    original_global_console = protostar.cli.ui.console

    def _render_svg(
        target_parser: argparse.ArgumentParser, prompt_cmd: str, filename: str
    ) -> None:
        record_console = Console(
            record=True,
            width=100,
            force_terminal=True,
            color_system="truecolor",
            legacy_windows=False,
            file=io.StringIO(),
            _environ={},
        )

        prompt = Text.assemble(
            ("❯ ", "bright_black"),  # noqa: RUF001
            ("protostar ", "bold cyan"),
            (f"{prompt_cmd}\n", "white"),
        )
        record_console.print(prompt)

        protostar.cli.ui.console = record_console
        target_parser.print_help()

        _render_and_write_svg(
            record_console,
            title="zsh",
            filename=filename,
            unique_id=filename.replace(".svg", ""),
        )

    try:
        parser = protostar.cli.parser.build_parser()
        _render_svg(parser, "help", "cli_help.svg")

        subparsers = next(
            (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
            None,
        )
        if subparsers and "init" in subparsers.choices:
            init_parser = subparsers.choices["init"]
            _render_svg(init_parser, "help init", "cli_init_help.svg")

        if subparsers and "config" in subparsers.choices:
            config_parser = subparsers.choices["config"]
            _render_svg(config_parser, "help config", "cli_config_help.svg")
        if subparsers:
            for command in ("status", "diff", "sync", "guide"):
                _render_svg(
                    subparsers.choices[command],
                    f"help {command}",
                    f"cli_{command}_help.svg",
                )
    finally:
        protostar.cli.ui.console = original_global_console


@contextmanager
def _demo_project() -> Iterator[None]:
    """Runs the body inside a fresh, fixed-name project directory.

    Paths render with the directory's name, so it is fixed for byte-stable output;
    the regression snapshots use the same name.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        orig_cwd = os.getcwd()
        project_dir = Path(tmpdir) / "demo_project"
        project_dir.mkdir()
        os.chdir(project_dir)
        try:
            yield
        finally:
            os.chdir(orig_cwd)


def _cli_template_engine(alias: str = "cli") -> tuple[Orchestrator, InitRequest]:
    """Builds the engine `protostar init --template <alias>` would run with defaults."""
    target = importlib.resources.files("protostar.templates").joinpath(f"{alias}.toml")
    blueprint = TemplateSource.load(str(target), built_in=alias).render({})
    user_config = UserConfig()
    modules: list[BootstrapModule] = [SystemWorkspaceModule(), PythonCore()]
    for mod in TOOLING_MODULES:
        is_active = getattr(user_config, mod.config_key, False)
        opinions = blueprint.opinions(None)
        if mod.config_key in opinions:
            is_active = opinions[mod.config_key]
        if is_active:
            modules.append(mod)
    request = InitRequest(template_blueprint=blueprint)
    return Orchestrator(modules, user_config, request=request), request


def generate_cli_dry_run_svg() -> None:
    """Captures an SVG snapshot of the dry-run CLI diagnostics preview via Rich."""
    original_global_console = protostar.cli.ui.console
    record_console = _recording_console()
    _print_prompt(record_console, "init --template cli --dry-run")

    try:
        protostar.cli.ui.console = record_console
        with _demo_project():
            engine, request = _cli_template_engine()
            with mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}):
                manifest = engine.plan()
                print_dry_run(
                    prepare_draft(
                        request, manifest, UserConfig(), hook_snapshot().revisions, {}
                    )
                )

        _render_and_write_svg(
            record_console,
            title="zsh",
            filename="cli_dry_run.svg",
            unique_id="cli_dry_run",
        )
    finally:
        protostar.cli.ui.console = original_global_console


def _stub_subprocess(_runner: ProcessRunner, command: list[str], **_: Any) -> None:
    """Stands in for every engine subprocess, creating only what later steps probe."""
    if command[:2] == ["git", "init"]:
        Path(".git").mkdir()


def _stub_which(name: str) -> str | None:
    """Reports every required binary present and no IDE CLI to probe."""
    return None if name in ("code", "cursor") else f"/usr/bin/{name}"


def _stub_which_without_tools(name: str) -> str | None:
    """Reports every binary present except the IDE CLIs, direnv, and just."""
    return None if name in ("direnv", "just") else _stub_which(name)


def generate_cli_missing_tools_svg() -> None:
    """Captures an init whose direnv and just are missing, ending with their install command.

    Homebrew is stubbed present, so the command is the same on every host.
    """
    original_global_console = protostar.cli.ui.console
    record_console = _recording_console(terminal=False)
    _print_prompt(record_console, "init --template cli")

    try:
        protostar.cli.ui.console = record_console
        with (
            _demo_project(),
            mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}),
            mock.patch.object(ProcessRunner, "run", _stub_subprocess),
            mock.patch("shutil.which", _stub_which_without_tools),
        ):
            engine, request = _cli_template_engine()
            protostar.cli.ui._run_engine(engine, request)

        _render_and_write_svg(
            record_console,
            title="zsh",
            filename="cli_missing_tools.svg",
            unique_id="cli_missing_tools",
        )
    finally:
        protostar.cli.ui.console = original_global_console


def _stub_subprocess_adding(
    runner: ProcessRunner, command: list[str], **kwargs: Any
) -> None:
    """Records each ``uv add`` in pyproject.toml, as uv would, so none reads as pending."""
    if command[:2] != ["uv", "add"]:
        _stub_subprocess(runner, command, **kwargs)
        return
    packages = command[2:]
    group = None
    if packages[0] == "--dev":
        group, packages = "dev", packages[1:]
    elif packages[0] == "--group":
        group, packages = packages[1], packages[2:]
    document = tomlkit.parse(Path("pyproject.toml").read_text())
    if group is None:
        requirements = document["project"].setdefault("dependencies", tomlkit.array())
    else:
        groups = document.setdefault("dependency-groups", tomlkit.table())
        requirements = groups.setdefault(group, tomlkit.array())
    requirements.extend(packages)
    Path("pyproject.toml").write_text(tomlkit.dumps(document))


def generate_cli_status_svg() -> None:
    """Captures status after a recipe edit, over a file and a value edited by hand.

    Turning off just retracts the edited justfile, a conflict; turning on Docker
    adds its files; the edited line length is a kept edit.
    """
    original_global_console = protostar.cli.ui.console
    record_console = _recording_console()
    _print_prompt(record_console, "status")

    try:
        with (
            _demo_project(),
            mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}),
            mock.patch.object(ProcessRunner, "run", _stub_subprocess_adding),
            mock.patch("shutil.which", _stub_which),
        ):
            engine, request = _cli_template_engine()
            protostar.cli.ui.console = _recording_console(terminal=False)
            protostar.cli.ui._run_engine(engine, request)

            justfile = Path("justfile")
            justfile.write_text(
                justfile.read_text().replace("uv run pytest", "uv run pytest -x", 1)
            )
            pyproject = Path("pyproject.toml")
            pyproject.write_text(
                pyproject.read_text()
                .replace("line-length = 88", "line-length = 100")
                .replace(
                    "[tool.protostar.fallback]",
                    "[tool.protostar.tools]\ndocker = true\njust = false\n\n"
                    "[tool.protostar.fallback]",
                )
            )
            protostar.cli.ui.console = record_console
            handle_review(argparse.Namespace(command="status"))

        _render_and_write_svg(
            record_console,
            title="zsh",
            filename="cli_status.svg",
            unique_id="cli_status",
        )
    finally:
        protostar.cli.ui.console = original_global_console


def generate_guide_svgs() -> None:
    """Captures `protostar guide` for a CLI and a workbench project.

    Each project is scaffolded by the real engine on stubbed subprocesses, so
    the guide reads the recipe, ledger, and pyproject.toml execution wrote.
    """
    from protostar.cli.guide import render_guide
    from protostar.guide import project_guide

    original_global_console = protostar.cli.ui.console
    try:
        for alias in ("cli", "ml"):
            record_console = _recording_console(terminal=False)
            with (
                _demo_project(),
                mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}),
                mock.patch.object(ProcessRunner, "run", _stub_subprocess),
                mock.patch("shutil.which", _stub_which),
            ):
                engine, request = _cli_template_engine(alias)
                protostar.cli.ui.console = _recording_console(terminal=False)
                protostar.cli.ui._run_engine(engine, request)
                _print_prompt(record_console, "guide")
                record_console.print(render_guide(project_guide()))

            _render_and_write_svg(
                record_console,
                title="zsh",
                filename=f"cli_guide_{alias}.svg",
                unique_id=f"cli_guide_{alias}",
            )
    finally:
        protostar.cli.ui.console = original_global_console


def generate_cli_init_svg() -> None:
    """Captures the init progress trail by running the real engine on stubbed subprocesses.

    The step labels come from the engine itself, so the image cannot drift from the
    CLI. A non-terminal console keeps Rich's animated spinner out of the recording
    while the checklist lines still print.
    """
    original_global_console = protostar.cli.ui.console
    record_console = _recording_console(terminal=False)
    _print_prompt(record_console, "init --template cli")

    try:
        protostar.cli.ui.console = record_console
        with (
            _demo_project(),
            mock.patch.dict(os.environ, {"PROTOSTAR_OFFLINE_HOOK_REGISTRY": "1"}),
            mock.patch.object(ProcessRunner, "run", _stub_subprocess),
            mock.patch("shutil.which", _stub_which),
        ):
            engine, request = _cli_template_engine()
            protostar.cli.ui._run_engine(engine, request)

        _render_and_write_svg(
            record_console,
            title="zsh",
            filename="cli_init.svg",
            unique_id="cli_init",
        )
    finally:
        protostar.cli.ui.console = original_global_console


def generate_diagnostic_panel_svg() -> None:
    """Captures an SVG snapshot of a styled Rich Diagnostic Summary panel."""
    record_console = Console(
        record=True,
        width=90,
        force_terminal=True,
        color_system="truecolor",
        legacy_windows=False,
        file=io.StringIO(),
        _environ={},
    )

    events = [
        DiagnosticEvent(
            phase=DiagnosticPhase.GIT,
            message="Initialized fresh git repository in workspace.",
            severity=Severity.INFO,
        ),
        DiagnosticEvent(
            phase=DiagnosticPhase.DIRENV,
            message="Auto-activation hook skipped; binary not found in PATH.",
            severity=Severity.SKIP,
            detail="Install direnv to enable seamless directory traversal activation.",
        ),
        DiagnosticEvent(
            phase=DiagnosticPhase.MARKDOWNLINT,
            message="Linter configuration scaffolded with relaxed schema rules.",
            severity=Severity.WARNING,
            detail="Install markdownlint-cli2 to enable git hook verification.",
        ),
    ]

    record_console.print(protostar.cli.ui.diagnostics_report(events))

    _render_and_write_svg(
        record_console,
        title="Diagnostic Summary",
        filename="diagnostic_panel.svg",
        unique_id="diagnostic_panel",
    )
