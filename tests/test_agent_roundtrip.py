import json

import pytest

from protostar.cli import main


def test_agent_capabilities_discovery(capsys, monkeypatch):
    monkeypatch.setattr("protostar.cli.is_json_mode", True)
    monkeypatch.setattr("sys.argv", ["protostar", "--json"])

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "success"
    assert "capabilities" in payload
    assert "init" in payload["capabilities"]["commands"]


def test_agent_dry_run_and_execute(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("protostar.cli.is_json_mode", True)

    # Dry run
    monkeypatch.setattr(
        "sys.argv",
        ["protostar", "init", "--template", "minimal", "--dry-run", "--json"],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "planned"
    assert "manifest" in payload
    assert len(payload["manifest"]["filesystem"]["directories"]) > 0

    # Execute
    monkeypatch.setattr(
        "sys.argv", ["protostar", "init", "--template", "minimal", "--json"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out.splitlines()[-1])
    assert payload["status"] == "success"
    assert "result" in payload
    assert len(payload["result"]["touched_paths"]) > 0
