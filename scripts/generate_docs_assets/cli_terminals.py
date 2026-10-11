"""Terminal SVGs of real CLI runs: help, dry run, init, status, guide, and diagnostics.

Every image runs the command a reader types, in-process, with subprocesses
stubbed and the host held fixed (``stable_host()``), so the output is the
CLI's own and the same on every machine.
"""

from __future__ import annotations

import argparse
import contextlib
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any
from unittest import mock

import tomlkit
from rich.console import Console

import protostar.cli
from protostar.manifest import DiagnosticEvent
from protostar.system import ProcessRunner
from scripts.generate_docs_assets.common import (
    demo_project,
    run_cli,
    stable_host,
    stub_which,
)
from scripts.generate_docs_assets.svg import (
    _print_prompt,
    _recording_console,
    _render_and_write_svg,
)


@contextlib.contextmanager
def _printing_to(console: Console) -> Iterator[None]:
    """Sends the CLI's output to ``console`` for the length of the block."""
    original = protostar.cli.ui.console
    protostar.cli.ui.console = console
    try:
        yield
    finally:
        protostar.cli.ui.console = original


def _capture(
    arguments: str,
    filename: str,
    *,
    console: Console | None = None,
) -> Callable[[], None]:
    """Returns a writer for the SVG of ``protostar <arguments>`` recorded so far."""
    console = console or _recording_console(terminal=False)
    _print_prompt(console, arguments)

    def write() -> None:
        _render_and_write_svg(
            console,
            title="zsh",
            filename=filename,
            unique_id=filename.removesuffix(".svg"),
        )

    return write


def generate_cli_help_svgs() -> None:
    """Captures the help of the CLI and of ``protostar config``."""
    parser = protostar.cli.parser.build_parser()
    subparsers = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    for target, arguments, filename in (
        (parser, "help", "cli_help.svg"),
        (subparsers.choices["config"], "help config", "cli_config_help.svg"),
    ):
        console = _recording_console()
        write = _capture(arguments, filename, console=console)
        with _printing_to(console):
            target.print_help()
        write()


def generate_cli_dry_run_svg() -> None:
    """Captures ``protostar init --template cli --dry-run``."""
    console = _recording_console()
    write = _capture(
        "init --template cli --dry-run", "cli_dry_run.svg", console=console
    )
    with demo_project(), stable_host(), _printing_to(console):
        run_cli("init", "--template", "cli", "--dry-run")
    write()


def _stub_subprocess(_runner: ProcessRunner, command: list[str], **_: Any) -> None:
    """Stands in for every engine subprocess, creating only what later steps probe."""
    if command[:2] == ["git", "init"]:
        Path(".git").mkdir()


def _without(*names: str) -> Callable[[str], str | None]:
    """Reports every binary present except ``names`` and the IDE CLIs."""
    return lambda name: None if name in names else stub_which(name)


@contextlib.contextmanager
def _stubbed_init(
    which: Callable[[str], str | None] = stub_which,
    subprocess: Callable[..., None] = _stub_subprocess,
) -> Iterator[None]:
    """Holds the host fixed and stubs every command an ``init`` runs."""
    with stable_host(which), mock.patch.object(ProcessRunner, "run", subprocess):
        yield


def generate_cli_missing_tools_svg() -> None:
    """Captures an init whose direnv and just are missing, ending with their install command.

    Homebrew is stubbed present, so the command is the same on every host.
    """
    console = _recording_console(terminal=False)
    write = _capture("init --template cli", "cli_missing_tools.svg", console=console)
    with demo_project(), _stubbed_init(which=_without("direnv", "just")):
        with _printing_to(console):
            run_cli("init", "--template", "cli")
    write()


def generate_cli_missing_dependency_svg() -> None:
    """Captures an init on a machine without uv, which stops before writing anything.

    Homebrew is stubbed present, so the install command is the same on every host.
    """
    console = _recording_console(terminal=False)
    write = _capture(
        "init --template cli", "cli_missing_dependency.svg", console=console
    )
    with demo_project(), stable_host(_without("uv")), _printing_to(console):
        run_cli("init", "--template", "cli", failing=True)
    write()


def _stub_subprocess_adding(
    runner: ProcessRunner, command: list[str], **kwargs: Any
) -> None:
    """Records each ``uv add`` in pyproject.toml, as uv would, so none reads as pending."""
    if command[:2] != ["uv", "add"]:
        _stub_subprocess(runner, command, **kwargs)
        return
    packages = [word for word in command[2:] if word != "--no-sync"]
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
    console = _recording_console()
    write = _capture("status", "cli_status.svg", console=console)
    with (
        demo_project(),
        _stubbed_init(subprocess=_stub_subprocess_adding),
    ):
        with _printing_to(_recording_console(terminal=False)):
            run_cli("init", "--template", "cli")
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
        with _printing_to(console):
            run_cli("status")
    write()


def generate_guide_svgs() -> None:
    """Captures ``protostar guide`` for a CLI and a workbench project.

    Each project is scaffolded by a real init on stubbed subprocesses, so the
    guide reads the recipe, ledger, and pyproject.toml execution wrote.
    """
    for alias in ("cli", "astro"):
        console = _recording_console(terminal=False)
        with demo_project(), _stubbed_init():
            with _printing_to(_recording_console(terminal=False)):
                run_cli("init", "--template", alias)
            write = _capture("guide", f"cli_guide_{alias}.svg", console=console)
            with _printing_to(console):
                run_cli("guide")
        write()


def generate_cli_init_svg() -> None:
    """Captures the init progress trail of a real run on stubbed subprocesses.

    A non-terminal console keeps Rich's animated spinner out of the recording
    while the checklist lines still print.
    """
    console = _recording_console(terminal=False)
    write = _capture("init --template cli", "cli_init.svg", console=console)
    with demo_project(), _stubbed_init(), _printing_to(console):
        run_cli("init", "--template", "cli")
    write()


def generate_diagnostic_panel_svg() -> None:
    """Captures the diagnostics a real init reports, on a machine without direnv."""
    reported: list[Sequence[DiagnosticEvent]] = []
    render = protostar.cli.ui.diagnostics_report

    def record(events: Sequence[DiagnosticEvent]) -> Any:
        reported.append(events)
        return render(events)

    with (
        demo_project(),
        _stubbed_init(which=_without("direnv", "just")),
        mock.patch.object(protostar.cli.ui, "diagnostics_report", record),
        _printing_to(_recording_console(terminal=False)),
    ):
        run_cli("init", "--template", "cli")
    if not reported:
        raise SystemExit("The diagnostics run reported nothing to show.")

    console = _recording_console()
    # Narrower than a run's output, so the panel reads as a panel on the page.
    console.width = 80
    console.print(render(reported[-1]))
    _render_and_write_svg(
        console,
        title="Diagnostic Summary",
        filename="diagnostic_panel.svg",
        unique_id="diagnostic_panel",
    )
