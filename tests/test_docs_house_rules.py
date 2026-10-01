"""The docs follow house-style's documentation rules, which check_docs_drift enforces."""

from pathlib import Path

import pytest

from scripts import check_docs_drift

NAV = """[project]
nav = [
    { "Home" = "index.md" },
    { "Guide" = [{ "Usage" = "guide/usage.md" }] },
]
"""


@pytest.fixture
def docs_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated repository whose pages follow every rule."""
    (tmp_path / "zensical.toml").write_text(NAV, encoding="utf-8")
    pages = {
        "index.md": '---\nicon: material/home\ndescription: "Home."\n---\n',
        "guide/usage.md": '---\ndescription: "Usage."\n---\n',
    }
    for name, content in pages.items():
        path = tmp_path / "docs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for name in ("README.md", "CONTRIBUTING.md", "AGENTS.md"):
        (tmp_path / name).write_text("# Notes\n", encoding="utf-8")
    monkeypatch.setattr(check_docs_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_docs_drift, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(check_docs_drift, "README", tmp_path / "README.md")
    monkeypatch.setattr(check_docs_drift, "CONTRIBUTING", tmp_path / "CONTRIBUTING.md")
    monkeypatch.setattr(check_docs_drift, "AGENTS", tmp_path / "AGENTS.md")
    return tmp_path


def _write(repo: Path, name: str, content: str) -> None:
    (repo / "docs" / name).write_text(content, encoding="utf-8")


def test_pages_that_follow_the_rules_pass(docs_repo: Path) -> None:
    assert check_docs_drift.check_page_front_matter() == []
    assert check_docs_drift.check_card_grids() == []


@pytest.mark.parametrize(
    ("name", "content", "problem"),
    [
        (
            "index.md",
            "---\nicon: material/home\n---\n",
            "needs a one-sentence description",
        ),
        ("index.md", '---\ndescription: "Home."\n---\n', "needs an icon"),
        (
            "guide/usage.md",
            '---\nicon: material/book\ndescription: "Usage."\n---\n',
            "only top-level pages carry a nav icon",
        ),
    ],
)
def test_front_matter_rules(
    docs_repo: Path, name: str, content: str, problem: str
) -> None:
    _write(docs_repo, name, content)

    problems = check_docs_drift.check_page_front_matter()

    assert len(problems) == 1
    assert problem in problems[0]


@pytest.mark.parametrize(
    ("cards", "passes"),
    [(1, False), (2, True), (3, False), (4, True), (5, False), (6, True), (7, False)],
)
def test_card_grids_hold_two_four_or_six(
    docs_repo: Path, cards: int, passes: bool
) -> None:
    items = "".join(f"- __Card {n}__\n\n    Why it matters.\n\n" for n in range(cards))
    _write(
        docs_repo,
        "guide/usage.md",
        f'---\ndescription: "Usage."\n---\n\n<div class="grid cards" markdown>\n\n{items}</div>\n',
    )

    problems = check_docs_drift.check_card_grids()

    assert (problems == []) is passes
