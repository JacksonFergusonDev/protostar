"""`protostar check-template`: exit codes, output, and machine mode."""

import json
from pathlib import Path

from protostar.cli.main import main

CLEAN = 'name = "Service"\ndescription = "A service"\n'


def template(tmp_path: Path, body: str) -> str:
    root = tmp_path / "template"
    root.mkdir()
    (root / "protostar.toml").write_text(body, encoding="utf-8")
    return str(root)


def run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr("sys.argv", ["protostar", "check-template", *argv])
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", "--json" in argv)
    try:
        main()
    except SystemExit as exit_info:
        return int(exit_info.code or 0)
    return 0


def test_a_clean_template_passes(tmp_path, monkeypatch, capsys):
    assert run(monkeypatch, template(tmp_path, CLEAN)) == 0
    assert "Template check passed." in capsys.readouterr().out


def test_the_source_defaults_to_the_current_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(template(tmp_path, CLEAN))
    assert run(monkeypatch) == 0


def test_an_error_fails_the_check(tmp_path, monkeypatch, capsys):
    assert run(monkeypatch, template(tmp_path, CLEAN + "rufff = true\n")) == 1
    out = capsys.readouterr().out
    assert "invalid-template" in out
    assert "unknown tooling flags: rufff" in out
    assert "Template check failed: 1 error." in out


def test_warnings_fail_only_under_strict(tmp_path, monkeypatch, capsys):
    source = template(tmp_path, "ruff = true\n")
    assert run(monkeypatch, source) == 0
    assert "Template check passed with 2 warnings." in capsys.readouterr().out
    assert run(monkeypatch, source, "--strict") == 1
    assert "Template check failed: 2 warnings." in capsys.readouterr().out


def test_template_text_is_not_markup(tmp_path, monkeypatch, capsys):
    run(monkeypatch, template(tmp_path, CLEAN + '"[bold]x" = ["y"]\n'))
    assert "'[bold]x'" in capsys.readouterr().out


def test_json_reports_the_check_on_stdout_only(tmp_path, monkeypatch, capsys):
    assert (
        run(monkeypatch, template(tmp_path, "ruff = true\n"), "--strict", "--json") == 1
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "failed"
    assert payload["strict"] is True
    assert payload["check"]["warnings"] == 2
    assert {f["rule"] for f in payload["check"]["findings"]} == {"missing-metadata"}


def test_a_template_that_cannot_be_retrieved_is_not_checked(
    tmp_path, monkeypatch, capsys
):
    missing = str(tmp_path / "absent")
    assert run(monkeypatch, missing) == 65
    out = " ".join(capsys.readouterr().out.split())
    assert "nothing was checked" in out
    assert "Template check" not in out


def test_json_reports_a_retrieval_failure_as_an_error(tmp_path, monkeypatch, capsys):
    assert run(monkeypatch, str(tmp_path / "absent"), "--json") == 65
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert payload["error"]["type"] == "TemplateResolutionError"
