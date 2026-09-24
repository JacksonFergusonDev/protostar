"""The CLI's persistent progress trail and its wiring to the headless engine."""

import io

import pytest
from rich.console import Console
from rich.status import Status

from protostar.cli import ui
from protostar.config import UserConfig
from protostar.errors import CommandExecutionError
from protostar.manifest import EnvironmentManifest
from protostar.merge import NO_RESOLUTIONS
from protostar.models import ExecutionResult, InitRequest
from protostar.orchestrator import Orchestrator
from protostar.progress import no_progress

EMPTY_RESULT = ExecutionResult(frozenset(), frozenset(), ())


@pytest.fixture
def screen(monkeypatch) -> io.StringIO:
    """Routes the CLI console to a non-terminal buffer, as when output is piped."""
    buffer = io.StringIO()
    console = Console(
        file=buffer, width=80, force_terminal=False, color_system=None, _environ={}
    )
    monkeypatch.setattr(ui, "console", console)
    return buffer


def test_no_progress_runs_the_step_body():
    ran = []
    with no_progress("Anything"):
        ran.append(True)
    assert ran == [True]


def test_trail_leaves_a_check_for_each_completed_step(screen):
    with ui.progress_trail("Preparing workspace") as step:
        with step("Writing project files"):
            pass
        with step("Installing 2 standard dependencies"):
            pass

    assert screen.getvalue() == (
        "  ✔ Writing project files\n  ✔ Installing 2 standard dependencies\n"
    )


def _fail_second_step(
    error: BaseException, label: str = "Installing 1 standard dependency"
) -> None:
    with ui.progress_trail("Preparing workspace") as step:
        with step("Initializing git repository"):
            pass
        with step(label):
            raise error


def test_trail_marks_the_failed_step_and_reraises(screen):
    error = CommandExecutionError(command=["uv", "add"], returncode=1, stderr="")

    with pytest.raises(CommandExecutionError) as caught:
        _fail_second_step(error)

    assert caught.value is error
    assert screen.getvalue().splitlines() == [
        "  ✔ Initializing git repository",
        "  ✖ Installing 1 standard dependency",
    ]


def test_trail_marks_an_interrupted_step(screen):
    with pytest.raises(KeyboardInterrupt):
        _fail_second_step(KeyboardInterrupt())

    assert screen.getvalue().splitlines()[-1] == "  ✖ Installing 1 standard dependency"


def test_trail_prints_template_labels_literally(screen):
    label = "[bold red]boom[/] [link=https://example.com]click[/link]"

    with ui.progress_trail("Preparing workspace") as step, step(label):
        pass

    assert screen.getvalue() == f"  ✔ {label}\n"


def test_trail_degrades_on_a_legacy_encoded_stream(monkeypatch):
    """A cp1252 stream, as on Windows when output is piped, gets ASCII marks.

    Nothing the trail prints may raise: an exception escaping a step would roll
    back the work it just reported.
    """
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\n")
    console = Console(
        file=stream, width=80, force_terminal=False, color_system=None, _environ={}
    )
    monkeypatch.setattr(ui, "console", console)

    with pytest.raises(KeyboardInterrupt):
        _fail_second_step(KeyboardInterrupt(), "Running seed → cache")

    stream.flush()
    assert stream.buffer.getvalue().decode("cp1252").splitlines() == [
        "  + Initializing git repository",
        "  x Running seed ? cache",
    ]


def test_trail_animates_only_the_running_step(screen, mocker):
    update = mocker.spy(Status, "update")

    with ui.progress_trail("Preparing workspace") as step, step("Installing hooks"):
        pass

    assert [str(call.args[1]) for call in update.call_args_list] == [
        "Installing hooks",
        " ",
    ]


def _engine(mocker, execute):
    mocker.patch.object(Orchestrator, "plan", return_value=EnvironmentManifest())
    return mocker.patch.object(Orchestrator, "execute", side_effect=execute)


def test_run_engine_renders_engine_steps_under_the_banner(screen, mocker, monkeypatch):
    monkeypatch.setattr(ui, "is_json_mode", False)

    def execute(manifest, *, hook_revisions, progress, resolutions):
        with progress("Initializing git repository"):
            pass
        return EMPTY_RESULT

    _engine(mocker, execute)
    request = InitRequest()
    ui._run_engine(Orchestrator([], UserConfig(), request=request), request)

    banner, step = screen.getvalue().splitlines()[:2]
    assert banner.startswith("IGNITION SEQUENCE INITIATED ─")
    assert step == "  ✔ Initializing git repository"


def test_run_engine_json_mode_executes_without_progress(screen, mocker, monkeypatch):
    monkeypatch.setattr(ui, "is_json_mode", True)
    execute = _engine(
        mocker, lambda manifest, *, hook_revisions, resolutions: EMPTY_RESULT
    )
    request = InitRequest()

    result = ui._run_engine(Orchestrator([], UserConfig(), request=request), request)

    assert result is EMPTY_RESULT
    assert execute.call_args.kwargs == {
        "hook_revisions": None,
        "resolutions": NO_RESOLUTIONS,
    }
    assert screen.getvalue() == ""
