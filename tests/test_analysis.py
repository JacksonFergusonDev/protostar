"""Existing-project analysis reads tools and facts without changing anything."""

import importlib.resources
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from protostar.analysis import (
    AnalysisNote,
    Fact,
    NoteKind,
    ProjectAnalysis,
    analyze_project,
)
from protostar.cli.main import main
from protostar.config import UserConfig
from protostar.init_draft import InitDraft, resolve_init
from protostar.metadata import LicenseType
from protostar.modules import (
    TOOLING_MODULES,
    PathSignal,
    RequirementSignal,
    SectionSignal,
    TableSignal,
)
from protostar.recipe import Tool, edit_recipe
from protostar.workflows import TargetOS

_PYPROJECT = """\
[project]
name = "legacy"
version = "0.3.1"
description = "A legacy service."
requires-python = ">=3.12"
authors = [{ name = "Ada Lovelace", email = "ada@example.com" }]
dependencies = ["httpx"]
classifiers = [
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX :: Linux",
    "Operating System :: MacOS :: MacOS X",
]

[project.urls]
Homepage = "https://example.com"
Repository = "https://github.com/ada/legacy"

[dependency-groups]
dev = ["ruff>=0.5", "pytest", { include-group = "docs" }]
docs = []

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
"""


def write(root: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


@pytest.fixture
def legacy(tmp_path: Path) -> Path:
    """The repository from the enrollment experiment, before Protostar."""
    write(
        tmp_path,
        {
            "pyproject.toml": _PYPROJECT,
            "justfile": "test:\n    uv run pytest\n",
            ".pre-commit-config.yaml": "repos: []\n",
            ".github/workflows/ci.yml": "name: CI\n",
            ".github/workflows/docs.yml": "name: Docs\n",
            "LICENSE": "MIT License\n\nCopyright (c) 2021 Ada Lovelace\n",
        },
    )
    return tmp_path


def value[T](found: Fact[T] | None) -> T | None:
    return found.value if found else None


def fact[T](found: Fact[T] | None) -> Fact[T]:
    assert found is not None
    return found


def sources(analysis: ProjectAnalysis) -> dict[Tool, tuple[str, ...]]:
    return {evidence.tool: evidence.sources for evidence in analysis.tools}


def test_finds_the_tools_and_facts_of_an_existing_project(legacy):
    analysis = analyze_project(legacy)

    assert analysis.existing
    assert sources(analysis) == {
        Tool.RUFF: (
            "pyproject.toml [tool.ruff]",
            "ruff in pyproject.toml dependencies",
        ),
        Tool.PYTEST: (
            "pyproject.toml [tool.pytest]",
            "pytest in pyproject.toml dependencies",
        ),
        Tool.PRE_COMMIT: (".pre-commit-config.yaml",),
        Tool.CI: (".github/workflows/ci.yml",),
        Tool.JUST: ("justfile",),
    }
    facts = analysis.facts
    assert value(facts.python_version) == "3.12"
    assert value(facts.minimum_python) == "3.12"
    assert value(facts.description) == "A legacy service."
    assert value(facts.author_name) == "Ada Lovelace"
    assert value(facts.author_email) == "ada@example.com"
    assert value(facts.github_username) == "ada"
    assert value(facts.license) is LicenseType.MIT
    assert value(facts.supported_os) == (
        TargetOS.MACOS,
        TargetOS.LINUX,
    )
    assert value(facts.current_year) == "2021"
    assert analysis.notes == (
        AnalysisNote(NoteKind.OTHER_WORKFLOW, ".github/workflows/docs.yml"),
    )


def test_serializes_deterministically(legacy):
    payload = analyze_project(legacy).to_dict()

    assert payload == json.loads(json.dumps(payload))
    assert [item["tool"] for item in payload["tools"]] == sorted(
        item["tool"] for item in payload["tools"]
    )
    assert list(payload["facts"]) == sorted(payload["facts"])
    assert payload["facts"]["license"] == {
        "value": "MIT",
        "source": "pyproject.toml [project].classifiers",
    }
    assert payload["facts"]["supported_os"]["value"] == ["MacOS", "Linux"]
    assert payload["docker"] == []


def test_reads_without_writing_or_running_anything(legacy, mocker):
    run = mocker.patch.object(subprocess, "run", side_effect=AssertionError)
    popen = mocker.patch.object(subprocess, "Popen", side_effect=AssertionError)

    def tree() -> dict[str, tuple[bytes, int]]:
        return {
            path.relative_to(legacy).as_posix(): (
                path.read_bytes(),
                path.stat().st_mtime_ns,
            )
            for path in sorted(legacy.rglob("*"))
            if path.is_file()
        }

    before = tree()
    analyze_project(legacy)

    assert tree() == before
    run.assert_not_called()
    popen.assert_not_called()


def test_an_empty_directory_is_not_an_existing_project(tmp_path):
    assert analyze_project(tmp_path) == ProjectAnalysis(existing=False)


def test_a_tool_file_alone_makes_an_existing_project(tmp_path):
    write(tmp_path, {"Dockerfile": "FROM python:3.12\n"})

    analysis = analyze_project(tmp_path)

    assert analysis.existing
    assert analysis.docker == ("Dockerfile",)


def test_legacy_ini_configuration_counts(tmp_path):
    write(
        tmp_path,
        {
            "setup.cfg": "[metadata]\nname = old\n\n[mypy]\nstrict = true\n",
            "tox.ini": "[pytest]\naddopts = -q\n",
        },
    )

    assert sources(analyze_project(tmp_path)) == {
        Tool.MYPY: ("setup.cfg [mypy]",),
        Tool.PYTEST: ("tox.ini [pytest]",),
    }


def test_a_path_matches_only_its_exact_spelling(tmp_path):
    # On a case-insensitive filesystem, `justfile` would also exist.
    write(tmp_path, {"Justfile": "default:\n"})

    assert sources(analyze_project(tmp_path)) == {Tool.JUST: ("Justfile",)}


def test_prek_wins_the_hook_runner_when_the_project_names_it(tmp_path):
    write(
        tmp_path,
        {
            ".pre-commit-config.yaml": "repos: []\n",
            "pyproject.toml": '[dependency-groups]\ndev = ["prek"]\n',
        },
    )

    found = sources(analyze_project(tmp_path))

    assert Tool.PRE_COMMIT not in found
    assert found[Tool.PREK] == (
        ".pre-commit-config.yaml",
        "prek in pyproject.toml dependencies",
    )


def test_requirements_come_from_every_dependency_list(tmp_path):
    write(
        tmp_path,
        {
            "pyproject.toml": """\
[project]
dependencies = ["not a requirement ==", "Mypy[reports]>=1"]

[project.optional-dependencies]
lint = ["ruff"]

[tool.uv]
dev-dependencies = ["pytest; python_version >= '3.12'"]
""",
        },
    )

    assert set(sources(analyze_project(tmp_path))) == {
        Tool.MYPY,
        Tool.RUFF,
        Tool.PYTEST,
    }


def test_a_mkdocs_site_is_not_zensical(tmp_path):
    write(tmp_path, {"mkdocs.yml": "site_name: Old\n"})

    assert Tool.ZENSICAL not in sources(analyze_project(tmp_path))


def test_a_generated_workflow_alias_is_not_a_note(tmp_path):
    write(tmp_path, {".github/workflows/ci.yaml": "name: CI\n"})

    analysis = analyze_project(tmp_path)

    assert sources(analysis) == {Tool.CI: (".github/workflows/ci.yaml",)}
    assert analysis.notes == ()


def test_an_unreadable_file_is_a_note_not_an_error(tmp_path):
    write(tmp_path, {"pyproject.toml": "[project\nname = broken\n"})
    (tmp_path / "LICENSE").write_bytes(b"\xff\xfe not utf-8")
    write(tmp_path, {"setup.cfg": "[mypy\nstrict\n"})

    analysis = analyze_project(tmp_path)

    assert analysis.existing
    assert analysis.tools == ()
    assert analysis.facts.to_dict() == {}
    assert {note.path for note in analysis.notes} == {
        "pyproject.toml",
        "LICENSE",
        "setup.cfg",
    }
    assert {note.kind for note in analysis.notes} == {NoteKind.UNREADABLE}


@pytest.mark.parametrize(
    ("requires", "expected"),
    [
        (">=3.11", "3.11"),
        (">=3.11.4,<4", "3.11"),
        ("~=3.10", "3.10"),
        ("==3.12.*", "3.12"),
        (">3.9", None),
        ("<4", None),
        ("not a specifier", None),
    ],
)
def test_minimum_python_is_the_lowest_inclusive_bound(tmp_path, requires, expected):
    write(tmp_path, {"pyproject.toml": f'[project]\nrequires-python = "{requires}"\n'})

    assert value(analyze_project(tmp_path).facts.minimum_python) == expected


def test_a_pinned_interpreter_stands_in_without_a_minimum(tmp_path):
    write(tmp_path, {".python-version": "3.13.1\n"})

    facts = analyze_project(tmp_path).facts

    assert facts.minimum_python is None
    assert value(facts.python_version) == "3.13"
    assert fact(facts.python_version).source == ".python-version"


@pytest.mark.parametrize(
    ("project", "expected", "source"),
    [
        ('license = "GPL-3.0-or-later"', LicenseType.GPL_3_0, "[project].license"),
        ('license = "apache-2.0"', LicenseType.APACHE_2_0, "[project].license"),
        ('license = { text = "MIT" }', LicenseType.MIT, "[project].license"),
        (
            'classifiers = ["License :: OSI Approved :: GNU Affero General Public License v3"]',
            LicenseType.AGPL_3_0,
            "[project].classifiers",
        ),
    ],
)
def test_license_from_the_project_table(tmp_path, project, expected, source):
    write(tmp_path, {"pyproject.toml": f"[project]\n{project}\n"})

    found = analyze_project(tmp_path).facts.license

    assert value(found) is expected
    assert fact(found).source == f"pyproject.toml {source}"


def test_the_bsd_classifier_names_no_single_license(tmp_path):
    write(
        tmp_path,
        {
            "pyproject.toml": '[project]\nclassifiers = ["License :: OSI Approved :: BSD License"]\n'
        },
    )

    assert analyze_project(tmp_path).facts.license is None


@pytest.mark.parametrize(
    ("resource", "expected"),
    [
        ("mit.txt", LicenseType.MIT),
        ("bsd_3.txt", LicenseType.BSD_3_CLAUSE),
        ("apache_2_0.txt", LicenseType.APACHE_2_0),
        ("gpl_3.txt", LicenseType.GPL_3_0),
        ("lgpl_3.txt", LicenseType.LGPL_3_0),
        ("agpl_3.txt", LicenseType.AGPL_3_0),
    ],
)
def test_license_from_every_shipped_license_text(tmp_path, resource, expected):
    shipped = (
        importlib.resources.files("protostar.licenses")
        .joinpath(resource)
        .read_text(encoding="utf-8")
    )
    text = shipped.replace("<% CURRENT_YEAR %>", "2019").replace(
        "<% AUTHOR_NAME %>", "Ada"
    )
    write(tmp_path, {"COPYING": text})

    facts = analyze_project(tmp_path).facts

    assert value(facts.license) is expected
    assert fact(facts.license).source == "COPYING"
    # GPL texts carry only the Free Software Foundation's copyright line.
    assert value(facts.current_year) == (
        "2019" if "<% CURRENT_YEAR %>" in shipped else None
    )


def test_os_independent_means_every_supported_system(tmp_path):
    write(
        tmp_path,
        {
            "pyproject.toml": '[project]\nclassifiers = ["Operating System :: OS Independent"]\n'
        },
    )

    found = analyze_project(tmp_path).facts.supported_os

    assert value(found) == tuple(TargetOS)


def test_every_tooling_module_declares_signals():
    for module in TOOLING_MODULES:
        assert module.signals, f"{module.name} declares no signals"
        for signal in module.signals:
            assert isinstance(
                signal, PathSignal | TableSignal | SectionSignal | RequirementSignal
            )


# Resolution: facts fill what the draft leaves unset.


def test_facts_replace_placeholders_in_the_recipe(legacy, monkeypatch):
    monkeypatch.chdir(legacy)
    config = UserConfig(python_version="3.14")

    _, request = resolve_init(InitDraft(analysis=analyze_project(legacy)), config)

    recipe = request.recipe
    assert recipe is not None
    context = dict(recipe.context)
    assert recipe.python == "3.12"
    assert context["PYTHON_VERSION"] == "3.12"
    assert context["AUTHOR_NAME"] == "Ada Lovelace"
    assert context["CURRENT_YEAR"] == "2021"


def test_facts_fill_only_the_metadata_the_tools_read(legacy, monkeypatch):
    monkeypatch.chdir(legacy)
    config = UserConfig(ci=True, supported_os=["Windows"])

    _, request = resolve_init(InitDraft(analysis=analyze_project(legacy)), config)

    # CI reads the minimum Python and operating systems; nothing reads the
    # license, so an existing project gains no LICENSE file from its facts.
    metadata = request.metadata
    assert metadata is not None
    assert metadata["minimum_python"] == "3.12"
    assert metadata["supported_os"] == ["MacOS", "Linux"]
    assert "license" not in metadata


def test_draft_values_outrank_facts(legacy, monkeypatch):
    monkeypatch.chdir(legacy)
    draft = InitDraft(
        analysis=analyze_project(legacy),
        python_version="3.13",
        metadata=(("author_name", "Grace"),),
    )

    _, request = resolve_init(draft, UserConfig())

    recipe = request.recipe
    assert recipe is not None
    context = dict(recipe.context)
    assert recipe.python == "3.13"
    assert context["AUTHOR_NAME"] == "Grace"


def test_analysis_never_selects_tools(legacy, monkeypatch):
    monkeypatch.chdir(legacy)
    config = UserConfig(ruff=False, pytest=False, just=False, ci=False)

    modules, request = resolve_init(InitDraft(analysis=analyze_project(legacy)), config)

    assert request.recipe is not None
    assert request.recipe.tools == ()
    assert not {type(module).__name__ for module in modules} & {
        "RuffModule",
        "PytestModule",
        "JustModule",
        "CIModule",
    }


# The machine interface shows agents what analysis found.


def run_dry_run(capsys, monkeypatch, root: Path) -> dict[str, Any]:
    monkeypatch.chdir(root)
    monkeypatch.setattr("protostar.cli.ui.is_json_mode", True)
    monkeypatch.setattr(
        "sys.argv", ["protostar", "init", "--no-config", "--dry-run", "--json"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    return json.loads(capsys.readouterr().out)


def test_dry_run_json_carries_the_analysis(capsys, monkeypatch, legacy):
    payload = run_dry_run(capsys, monkeypatch, legacy)

    assert payload["status"] == "planned"
    assert payload["analysis"] == analyze_project(legacy).to_dict()


def test_dry_run_json_has_no_analysis_once_a_recipe_exists(capsys, monkeypatch, legacy):
    monkeypatch.chdir(legacy)
    _, request = resolve_init(InitDraft(), UserConfig())
    pyproject = legacy / "pyproject.toml"
    assert request.recipe is not None
    pyproject.write_text(edit_recipe(pyproject.read_text(), request.recipe))

    payload = run_dry_run(capsys, monkeypatch, legacy)

    assert payload["analysis"] is None
