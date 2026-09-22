"""Enforces the headless core: engine modules never import terminal UI packages."""

import json
import subprocess
import sys
from pathlib import Path

# Terminal UI libraries that belong to the CLI layer (protostar.cli) only.
UI_PACKAGES = frozenset({"rich", "questionary", "prompt_toolkit", "textual"})

# Runs in a fresh interpreter. pkgutil.walk_packages would import protostar.cli
# to recurse into it, so the walk uses iter_modules and never touches the CLI.
_PROBE = """
import importlib, json, pkgutil, sys
import protostar

UI = set(json.loads(sys.argv[1]))

def walk(path, prefix):
    for info in pkgutil.iter_modules(path, prefix):
        if info.name == "protostar.cli":
            continue
        yield info.name
        if info.ispkg:
            package = importlib.import_module(info.name)
            yield from walk(package.__path__, info.name + ".")

culprits = {}
engine = []
for name in walk(protostar.__path__, "protostar."):
    importlib.import_module(name)
    engine.append(name)
    for loaded in list(sys.modules):
        root = loaded.partition(".")[0]
        if root in UI:
            culprits.setdefault(root, name)

print(json.dumps({"engine": engine, "culprits": culprits}))
"""


def test_engine_modules_import_no_terminal_ui_packages(tmp_path: Path) -> None:
    """Importing every module outside protostar.cli loads no terminal UI package."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, json.dumps(sorted(UI_PACKAGES))],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    probe = json.loads(result.stdout)

    # Guards against a probe that silently imports nothing.
    assert "protostar.orchestrator" in probe["engine"]
    assert "protostar.documents.pyproject" in probe["engine"]
    assert probe["culprits"] == {}, (
        "Engine modules loaded terminal UI packages "
        "(package: engine module whose import first loaded it): "
        f"{probe['culprits']}"
    )
