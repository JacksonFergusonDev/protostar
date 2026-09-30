"""Public descriptions cannot drift from the project's package metadata."""

from pathlib import Path

import pytest

from scripts import check_docs_drift


@pytest.fixture
def description_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Creates an isolated repository whose public descriptions agree."""
    files = {
        "pyproject.toml": '[project]\ndescription = "Useful Python scaffolding."\n',
        "zensical.toml": '[project]\nsite_description = "Useful Python scaffolding."\n',
        "README.md": "### Useful Python scaffolding\n",
        "docs/index.md": (
            '---\ndescription: "Useful Python scaffolding."\n---\n'
            "    <h1>Useful Python scaffolding.</h1>\n"
        ),
        ".github/ISSUE_TEMPLATE/feature_request.yml": (
            "body:\n  - type: markdown\n    attributes:\n      value: |\n"
            "        Protostar is useful Python scaffolding.\n"
        ),
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(check_docs_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_docs_drift, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(check_docs_drift, "README", tmp_path / "README.md")
    return tmp_path


def test_descriptions_agree(description_repo: Path) -> None:
    """Presentation differences in punctuation, casing, and indentation are allowed."""
    assert check_docs_drift.check_project_description() == []


@pytest.mark.parametrize(
    ("filename", "original"),
    [
        ("zensical.toml", "Useful Python scaffolding."),
        ("README.md", "Useful Python scaffolding"),
        ("docs/index.md", 'description: "Useful Python scaffolding."'),
        ("docs/index.md", "<h1>Useful Python scaffolding.</h1>"),
        (".github/ISSUE_TEMPLATE/feature_request.yml", "useful Python scaffolding."),
    ],
)
def test_description_drift_is_reported(
    description_repo: Path, filename: str, original: str
) -> None:
    """Changing any public description reports its file and canonical source."""
    path = description_repo / filename
    path.write_text(
        path.read_text(encoding="utf-8").replace(original, "Outdated description"),
        encoding="utf-8",
    )
    problems = check_docs_drift.check_project_description()
    assert len(problems) == 1
    assert filename in problems[0]
    assert "pyproject.toml" in problems[0]


def test_project_description_change_requires_public_updates(
    description_repo: Path,
) -> None:
    """Changing the canonical description flags every outdated public occurrence."""
    (description_repo / "pyproject.toml").write_text(
        '[project]\ndescription = "A new project description."\n', encoding="utf-8"
    )
    assert len(check_docs_drift.check_project_description()) == 5
