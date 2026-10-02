"""Help and version requests never load operation implementations."""

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

_PROBE = """
import contextlib, io, json, sys
from protostar.cli import main
sys.argv = ["protostar", *json.loads(sys.argv[1])]
output = io.StringIO()
code = 0
with contextlib.redirect_stdout(output):
    try:
        main()
    except SystemExit as error:
        code = error.code
print(json.dumps({"code": code, "output": output.getvalue(), "modules": sorted(sys.modules)}))
"""


@pytest.mark.integration
@pytest.mark.parametrize(
    "arguments",
    [
        ["help", "init"],
        ["help", "config"],
        ["sync", "--help"],
        ["status", "--help"],
        ["diff", "--help"],
        ["guide", "--help"],
        ["eject", "--help"],
        ["check-template", "--help"],
        ["--version"],
        ["--json", "--help"],
    ],
)
def test_information_requests_load_no_operation_implementations(
    arguments: list[str],
    tmp_path: Path,
    real_tool_env: Callable[[], dict[str, str]],
) -> None:
    """Parse and display each request in a fresh, isolated interpreter."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, json.dumps(arguments)],
        cwd=tmp_path,
        env=real_tool_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    probe = json.loads(result.stdout)
    assert probe["code"] == 0
    assert probe["output"].strip()
    loaded = set(probe["modules"])
    assert "protostar.modules.tooling_layer" in loaded
    forbidden = {
        "protostar.analysis",
        "protostar.init_draft",
        "protostar.preparation",
        "protostar.lifecycle",
        "protostar.orchestrator",
        "protostar.executor",
        "protostar.reconciliation",
        "protostar.documents.catalog",
        "protostar.toml_ast",
        "protostar.yaml_ast",
        "protostar.jsonc_ast",
        "protostar.cli.reviews",
        "protostar.cli.guide",
        "protostar.cli.eject",
        "protostar.cli.check_template",
        "textual",
        "ruamel.yaml",
    }
    assert not loaded & forbidden
    if "--json" in arguments:
        assert isinstance(json.loads(probe["output"]), dict)
    else:
        assert not loaded & {
            "protostar.manifest",
            "protostar.recipe",
            "protostar.sync_state",
        }
