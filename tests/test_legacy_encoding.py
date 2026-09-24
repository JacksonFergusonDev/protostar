"""CLI output on streams that cannot encode Unicode, as when redirected on Windows."""

import io
import sys

import pytest
from rich.console import Console

from protostar.cli import completion, ui
from protostar.cli.main import main
from protostar.config import UserConfig
from protostar.errors import ConfigurationError, ProtostarError
from protostar.manifest import (
    DiagnosticEvent,
    DiagnosticPhase,
    EnvironmentManifest,
    Severity,
)
from protostar.merge import (
    MISSING,
    ConflictReason,
    ConflictSides,
    MergeConflict,
    MergeLocation,
)
from protostar.models import ExecutionResult, InitRequest, RollbackContext
from protostar.orchestrator import Orchestrator


def cp1252_stream(errors: str = "strict") -> io.TextIOWrapper:
    """A Windows-style redirected stream: locale code page, strict by default."""
    return io.TextIOWrapper(
        io.BytesIO(), encoding="cp1252", errors=errors, newline="\n"
    )


def written(stream: io.TextIOWrapper) -> str:
    stream.flush()
    assert isinstance(stream.buffer, io.BytesIO)
    return stream.buffer.getvalue().decode("cp1252")


@pytest.fixture
def legacy_console(monkeypatch):
    """Points the CLI console at a strict cp1252 stream; returns what it wrote."""
    stream = cp1252_stream()
    console = Console(
        file=stream, width=100, force_terminal=False, color_system=None, _environ={}
    )
    monkeypatch.setattr(ui, "console", console)
    monkeypatch.setattr(ui, "is_json_mode", False)
    return lambda: written(stream)


def raise_from_cli(mocker, error: BaseException) -> None:
    """Runs main() with its first dispatch step raising ``error``."""
    mocker.patch("protostar.cli.main.parser.build_parser")
    mocker.patch(
        "protostar.cli.parser.intercept_interactive_wizards", side_effect=error
    )


def test_glyph_falls_back_only_where_the_stream_cannot_encode(legacy_console):
    assert ui.glyph("✓", "+") == "+"
    assert ui.glyph("•", "*") == "•"  # cp1252 has a bullet


def test_glyph_keeps_the_symbol_on_a_unicode_stream(monkeypatch):
    monkeypatch.setattr(ui, "console", Console(file=io.StringIO()))
    assert ui.glyph("✓", "+") == "✓"


def test_printable_replaces_only_unencodable_characters(legacy_console):
    assert ui.printable("C:\\Users\\田中 — café") == "C:\\Users\\?? — café"


def test_diagnostic_summary_warning_mark(legacy_console, mocker):
    warning = DiagnosticEvent(
        DiagnosticPhase.IDE, "Missing extensions", Severity.WARNING
    )
    mocker.patch.object(Orchestrator, "plan", return_value=EnvironmentManifest())
    mocker.patch.object(
        Orchestrator,
        "execute",
        return_value=ExecutionResult(frozenset(), frozenset(), (warning,)),
    )
    request = InitRequest()

    ui._run_engine(Orchestrator([], UserConfig(), request=request), request)

    assert "! [IDE] Missing extensions" in legacy_console()


def test_open_conflicts_with_a_choice_point_to_sync(legacy_console, mocker):
    """Each settleable conflict counts once; one settled by hand points nowhere."""
    settleable = MergeConflict(
        MergeLocation(".github/renovate.json", ("value",)),
        ConflictReason.UNOWNED,
        ConflictSides(MISSING, "mine", "template"),
    )
    by_hand = MergeConflict(MergeLocation("justfile"), ConflictReason.UNOWNED)
    events = tuple(
        DiagnosticEvent(
            DiagnosticPhase.EXECUTOR,
            f"Preserving local contribution in {conflict.location.file}.",
            Severity.WARNING,
            conflict=conflict,
        )
        # Initialization can report a conflict once per batch.
        for conflict in (settleable, settleable, by_hand)
    )
    mocker.patch.object(Orchestrator, "plan", return_value=EnvironmentManifest())
    execute = mocker.patch.object(
        Orchestrator,
        "execute",
        return_value=ExecutionResult(frozenset(), frozenset(), events),
    )
    request = InitRequest()

    ui._run_engine(Orchestrator([], UserConfig(), request=request), request)
    assert "1 conflict kept your version. Run protostar sync" in legacy_console()

    execute.return_value = ExecutionResult(frozenset(), frozenset(), events[2:])
    ui._run_engine(Orchestrator([], UserConfig(), request=request), request)
    assert "protostar sync" not in legacy_console().split("PARTIAL SUCCESS")[-1]


def test_remote_template_warning_banner(legacy_console, mocker):
    manifest = EnvironmentManifest()
    manifest.tasks.add_system_task(["git", "init"])
    mocker.patch.object(Orchestrator, "plan", return_value=manifest)
    request = InitRequest(is_external=True, is_trusted=False)

    with pytest.raises(ProtostarError, match="Untrusted external template"):
        ui._run_engine(Orchestrator([], UserConfig(), request=request), request)

    assert "!  REMOTE TEMPLATE WARNING !" in legacy_console()


def test_rollback_report_marks_and_docs_link(legacy_console, mocker):
    error = ProtostarError("Command execution failed")
    error.rollback_context = RollbackContext(
        touched_paths=frozenset({"src/app.py"}),
        completed_tasks=(),
        interrupted_task=None,
        is_external=False,
    )
    raise_from_cli(mocker, error)

    with pytest.raises(SystemExit):
        main()

    output = legacy_console()
    assert (
        "+ Protostar successfully rolled back all tracked workspace changes:" in output
    )
    assert "Docs: Rollback ->" in output


def test_completion_guide_detected_environment(legacy_console):
    completion.print_completion_guide()

    assert legacy_console().startswith("+ Detected Environment: ")


def test_main_error_text_outside_the_code_page_is_replaced(mocker, monkeypatch):
    """Arbitrary data in output, like a non-Latin user path, cannot crash the CLI."""
    stdout = cp1252_stream()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(ui, "is_json_mode", False)
    raise_from_cli(
        mocker, ConfigurationError("Cannot read C:\\Users\\田中\\template.toml")
    )

    with pytest.raises(SystemExit) as caught:
        main()

    assert caught.value.code == 78
    assert "Cannot read C:\\Users\\??\\template.toml" in written(stdout)


def test_main_crash_report_survives_rich_traceback_markers(mocker, monkeypatch):
    """Rich marks traceback lines with U+2771, which cp1252 cannot encode."""
    stdout = cp1252_stream()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(ui, "is_json_mode", False)
    raise_from_cli(mocker, RuntimeError("boom"))

    with pytest.raises(SystemExit) as caught:
        main()

    assert caught.value.code == 70
    output = written(stdout)
    assert "CRITICAL FAILURE" in output
    assert "RuntimeError: boom" in output


def test_replace_unencodable_output_keeps_an_explicit_handler(monkeypatch):
    strict, chosen = cp1252_stream(), cp1252_stream(errors="backslashreplace")
    monkeypatch.setattr(sys, "stdout", strict)
    monkeypatch.setattr(sys, "stderr", chosen)

    ui.replace_unencodable_output()

    assert (strict.errors, chosen.errors) == ("replace", "backslashreplace")


def test_review_lists_proposals_and_kept_edits(legacy_console, tmp_path, monkeypatch):
    from protostar.cli.reviews import render_review
    from protostar.config import UserConfig
    from protostar.manifest import CollisionStrategy, EnvironmentManifest
    from protostar.preparation import ExecutionPolicy, prepare_review

    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "ünïcode"\n', encoding="utf-8"
    )
    manifest = EnvironmentManifest(collision_strategy=CollisionStrategy.MERGE)
    manifest.filesystem.add_structured(
        "pyproject.toml", "[tool.ruff]\nline-length = 88\n", producer="module:test"
    )
    review = prepare_review(
        manifest, UserConfig(), policy=ExecutionPolicy.INITIALIZATION
    )

    render_review(review)

    written = legacy_console()
    assert "1 changes to your files" in written
    assert "Proposed " in written
    assert "pyproject.toml tool: applies; decline with local." in written


def test_template_check_marks(legacy_console, monkeypatch, tmp_path):
    (tmp_path / "protostar.toml").write_text("ruff = true\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["protostar", "check-template", str(tmp_path)])

    main()

    written = legacy_console()
    assert "+ Template check passed with 2 warnings." in written
    assert "protostar.toml -> name" in written
