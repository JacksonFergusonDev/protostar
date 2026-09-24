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


def test_text_output_shows_the_line(tmp_path, monkeypatch, capsys):
    run(monkeypatch, template(tmp_path, CLEAN + "\ndependancies = []\n"))
    assert "protostar.toml:4 → dependancies" in capsys.readouterr().out


def github(monkeypatch, capsys, *argv: str) -> tuple[int, list[str]]:
    code = run(monkeypatch, *argv, "--output-format", "github")
    return code, capsys.readouterr().out.splitlines()


def test_github_annotates_each_finding_on_its_line(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_WORKSPACE", raising=False)
    template(tmp_path, CLEAN + "rufff = true\ndependancies = []\n")
    code, lines = github(monkeypatch, capsys, "template")
    assert code == 1
    assert lines[:2] == [
        "::error file=template/protostar.toml,title=invalid-template::The template "
        "sets unknown tooling flags: rufff.%0AHint: Use recognized tool names with "
        "boolean selections: " + lines[0].split("selections: ", 1)[1],
        "::warning file=template/protostar.toml,line=4,title=unknown-key%3A "
        "dependancies::Protostar ignores the root key 'dependancies'.%0AHint: Check "
        "its spelling against the template schema (protostar export-schema).",
    ]
    assert lines[-1] == "✗ Template check failed: 1 error, 1 warning."


def test_github_paths_are_relative_to_the_workspace(tmp_path, monkeypatch, capsys):
    source = template(tmp_path, "ruff = true\n")
    step_directory = tmp_path / "template"
    monkeypatch.chdir(step_directory)
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    _, lines = github(monkeypatch, capsys, ".")
    assert lines[0].startswith("::warning file=template/protostar.toml,title=")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path / "elsewhere"))
    _, lines = github(monkeypatch, capsys, source)
    assert lines[0].startswith("::warning title=")


def test_github_escapes_template_text(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    template(tmp_path, CLEAN + '"50%,\\n::x" = 1\n')
    _, lines = github(monkeypatch, capsys, "template")
    # The key holds a real newline, which must not start a new command.
    (annotation,) = [line for line in lines if line.startswith("::")]
    assert "title=unknown-key%3A 50%25%2C%0A%3A%3Ax::" in annotation
    assert "root key '50%25,%0A::x'" in annotation


def test_github_escapes_newlines_in_messages():
    from protostar.cli.check_template import _annotation
    from protostar.template_check import Severity

    assert (
        _annotation(Severity.ERROR, "a\r\nb%", title="t:1,2", file="x,y.toml", line=3)
        == "::error file=x%2Cy.toml,line=3,title=t%3A1%2C2::a%0D%0Ab%25"
    )


def test_github_annotates_a_retrieval_failure(tmp_path, monkeypatch, capsys):
    code, lines = github(monkeypatch, capsys, str(tmp_path / "absent"))
    assert code == 65
    assert lines[0].startswith(
        "::error title=Template not retrieved::Could not retrieve "
    )
    assert "Configuration file not found" in lines[0]


def test_github_remote_findings_annotate_the_run():
    from protostar.cli.check_template import _workspace_path

    assert _workspace_path("https://example.com/t.toml", "protostar.toml") is None


def test_github_cannot_be_combined_with_json(tmp_path, monkeypatch, capsys):
    code = run(
        monkeypatch, template(tmp_path, CLEAN), "--output-format", "github", "--json"
    )
    assert code == 64
    assert json.loads(capsys.readouterr().out)["error"]["type"] == "InvalidUsageError"
