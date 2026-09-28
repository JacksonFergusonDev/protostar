"""Headless init settles the conflicts and proposals its dry-run lists."""

import json
import sys
import tomllib

import pytest

from protostar.cli import main, ui

FLAGS = ("--ruff", "--no-prek", "--no-pre-commit")
LOCAL = '[project]\nname = "existing"\n\n[tool.ruff]\nline-length = 150\n'


@pytest.fixture
def project(tmp_path, monkeypatch, mocker):
    """A project whose pyproject.toml collides with the ruff baseline."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(LOCAL)
    monkeypatch.setattr("protostar.metadata.get_git_config", lambda key: None)
    process = mocker.MagicMock(returncode=0)
    process.communicate.return_value = ("", "")
    process.poll.return_value = 0
    mocker.patch("subprocess.Popen", return_value=process)
    monkeypatch.setattr(ui, "is_json_mode", False)
    return tmp_path


def run(monkeypatch, capsys, *args):
    """Runs the CLI with ``--json`` and returns its exit code and payload."""
    monkeypatch.setattr(sys, "argv", ["protostar", *args, "--json"])
    monkeypatch.setattr(ui, "is_json_mode", False)
    try:
        main()
        code = 0
    except SystemExit as exit_:
        code = int(exit_.code or 0)
    return code, json.loads(capsys.readouterr().out)


def decisions(monkeypatch, capsys):
    """Returns the dry-run's open conflict and its proposals."""
    code, payload = run(monkeypatch, capsys, "init", "--dry-run", *FLAGS)
    assert code == 0, payload
    (conflict,) = payload["review"]["conflicts"]
    assert conflict["keys"] == ["tool", "ruff", "line-length"]
    return conflict, payload["review"]["proposals"]


@pytest.mark.parametrize(("choice", "length"), [("desired", 88), ("local", 150)])
def test_resolve_settles_a_conflict_and_records_it(
    project, monkeypatch, capsys, choice, length
):
    conflict, _ = decisions(monkeypatch, capsys)

    code, payload = run(
        monkeypatch,
        capsys,
        "init",
        "--force-merge",
        "--resolve",
        f"{conflict['id']}={choice}",
        *FLAGS,
    )

    assert code == 0, payload
    assert f"line-length = {length}\n" in (project / "pyproject.toml").read_text()
    # The choice is the new baseline, so the project has nothing left to settle.
    code, status = run(monkeypatch, capsys, "status")
    assert code == 0, status
    assert status["review"]["conflicts"] == []


def test_keeping_proposals_out_leaves_your_content(project, monkeypatch, capsys):
    conflict, proposals = decisions(monkeypatch, capsys)
    kept = [f"{c['id']}=local" for c in (conflict, *proposals)]

    code, payload = run(
        monkeypatch,
        capsys,
        "init",
        "--force-merge",
        *(arg for choice in kept for arg in ("--resolve", choice)),
        *FLAGS,
    )

    assert code == 0, payload
    written = tomllib.loads((project / "pyproject.toml").read_text())
    # Only the recipe is added; none of the proposed content is.
    assert written["tool"]["ruff"] == {"line-length": 150}
    assert "dependency-groups" not in written


def test_a_file_selector_settles_every_decision_in_it(project, monkeypatch, capsys):
    conflict, proposals = decisions(monkeypatch, capsys)

    code, payload = run(
        monkeypatch,
        capsys,
        "init",
        "--dry-run",
        "--resolve",
        "pyproject.toml=local",
        *FLAGS,
    )

    assert code == 0, payload
    review = payload["review"]
    assert review["conflicts"] == []
    assert [c["id"] for c in review["resolved"]] == [conflict["id"]]
    assert {p["id"]: p["resolution"] for p in review["proposals"]} == {
        p["id"]: "local" for p in proposals
    }
    (entry,) = (e for e in payload["entries"] if e["path"] == "pyproject.toml")
    assert entry["conflicts"] == []


def test_dry_run_with_resolve_shows_the_settled_outcome(project, monkeypatch, capsys):
    conflict, _ = decisions(monkeypatch, capsys)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "protostar",
            "init",
            "--dry-run",
            "--resolve",
            f"{conflict['id']}=desired",
            *FLAGS,
        ],
    )
    monkeypatch.setattr(ui, "is_json_mode", False)

    with pytest.raises(SystemExit) as exit_:
        main()

    assert exit_.value.code == 0
    output = capsys.readouterr().out
    assert f"Resolved {conflict['id']}: " in output
    assert "took the update" in output
    assert f"Conflict {conflict['id']}" not in output
    assert (project / "pyproject.toml").read_text() == LOCAL


def test_an_unknown_id_is_an_error_envelope(project, monkeypatch, capsys):
    code, payload = run(
        monkeypatch,
        capsys,
        "init",
        "--force-merge",
        "--resolve",
        "000000000000=desired",
        *FLAGS,
    )

    assert code != 0
    assert payload["error"]["type"] == "UnmatchedResolutionError"
    assert payload["error"]["unmatched_resolutions"] == ["000000000000"]
    assert (project / "pyproject.toml").read_text() == LOCAL


def test_resolve_does_not_choose_a_collision_strategy(project, monkeypatch, capsys):
    conflict, _ = decisions(monkeypatch, capsys)

    code, payload = run(
        monkeypatch,
        capsys,
        "init",
        "--resolve",
        f"{conflict['id']}=desired",
        *FLAGS,
    )

    assert code != 0
    assert payload["error"]["type"] == "WorkspaceCollisionError"
    assert "--force-merge" in payload["error"]["hint"]
    assert (project / "pyproject.toml").read_text() == LOCAL


def test_resolve_skips_the_change_review(project, monkeypatch, mocker):
    """Choices made on the command line never open the interactive review."""
    from protostar.cli.main import handle_init
    from protostar.cli.parser import build_parser
    from protostar.merge import ResolutionChoice

    mocker.patch("protostar.cli.main.is_interactive", return_value=True)
    reviewed = mocker.patch("protostar.cli.main.review_changes")
    engine = mocker.patch("protostar.cli.ui._run_engine")
    args = build_parser().parse_args(
        ["init", "--resolve", "pyproject.toml=local", *FLAGS]
    )

    handle_init(args)

    reviewed.assert_not_called()
    decision = engine.call_args.args[2]
    assert decision.hook_revisions == ()
    assert set(decision.resolutions.values()) == {ResolutionChoice.LOCAL}
    assert len(decision.resolutions) == 3
