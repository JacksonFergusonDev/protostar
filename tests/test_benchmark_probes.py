"""The probes count each cost once, by a label every host agrees on."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import tomlkit
from ruamel.yaml import YAML

from protostar.system import ProcessRunner
from scripts.benchmarks import probes


@pytest.mark.parametrize(
    ("command", "label"),
    [
        (["uv", "add", "--no-sync", "--dev", "ruff", "mypy"], "uv add --no-sync --dev"),
        (["uv", "add", "--group", "docs", "zensical"], "uv add --group"),
        (
            ["uv", "init", "--bare", "--python", "3.13"],
            "uv init --bare --python",
        ),
        (["/usr/local/bin/git", "init"], "git init"),
        (["git", "config", "--global", "user.name"], "git config --global user.name"),
    ],
)
def test_a_command_is_labelled_without_its_values_or_packages(
    command: list[str], label: str
) -> None:
    assert probes.command_label(command) == label


def test_a_parse_that_calls_another_parse_counts_once() -> None:
    """``tomlkit.loads`` calls ``parse``; only the outer call is a parse."""
    with probes.record() as recorder:
        tomlkit.parse("a = 1\n")
        tomlkit.loads("b = 2\n")
        YAML().load("c: 3\n")

    assert recorder.counts == {"parse:toml": 2, "parse:yaml": 1}


def test_recording_ends_with_every_seam_restored() -> None:
    parse, compose, popen = tomlkit.parse, YAML.compose, subprocess.Popen.__init__

    with probes.record():
        assert tomlkit.parse is not parse

    assert (tomlkit.parse, YAML.compose, subprocess.Popen.__init__) == (
        parse,
        compose,
        popen,
    )


def test_a_managed_command_is_not_counted_again_as_a_process() -> None:
    """``ProcessRunner`` starts its own process, which is the command itself."""
    command = [sys.executable, "-c", "pass"]

    with probes.record() as recorder:
        ProcessRunner().run(command)
        subprocess.run(command, check=True)

    label = probes.command_label(command)
    assert recorder.counts == {f"command:{label}": 1, f"subprocess:{label}": 1}


def test_a_watched_module_is_wrapped_when_it_is_first_imported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recording loads nothing: a parser's module is wrapped as it is imported."""
    (tmp_path / "late_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "late_module", raising=False)
    seen: list[int] = []
    finder = probes._OnImport({"late_module": lambda module: seen.append(module.VALUE)})
    sys.meta_path.insert(0, finder)
    try:
        import late_module  # type: ignore[import-not-found]
    finally:
        sys.meta_path.remove(finder)

    assert seen == [late_module.VALUE]


def test_only_packages_imported_during_the_run_are_reported() -> None:
    before = frozenset(sys.modules)

    assert probes.imported_packages(before) == []
