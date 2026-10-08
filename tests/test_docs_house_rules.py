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
    assert check_docs_drift.check_link_icons() == []


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


@pytest.mark.parametrize(
    ("item", "passes"),
    [
        ("- **[Next](next.md):** What it covers.", False),
        ("- __[Next](next.md):__ What it covers.", False),
        (
            '- **[Next<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](next.md):** What it covers.',
            True,
        ),
        ("- **[uv](https://docs.astral.sh/uv/)** installs packages.", True),
        ("- See [Next](next.md) for more.", True),
    ],
)
def test_standalone_list_links_carry_an_icon(
    docs_repo: Path, item: str, passes: bool
) -> None:
    _write(docs_repo, "guide/usage.md", f'---\ndescription: "Usage."\n---\n\n{item}\n')

    problems = check_docs_drift.check_link_icons()

    assert (problems == []) is passes


@pytest.mark.parametrize(
    ("target", "problem"),
    [
        ("metrics/", None),
        ("metrics/#benchmarks", None),
        ("metrics/#rollback", None),
        ("metrics/#mutations", None),
        ("metrics/#missing", "has no such heading"),
        ("metrics/missing/", "has no page"),
    ],
)
def test_metrics_links_validate_dashboard_anchors(
    docs_repo: Path, target: str, problem: str | None
) -> None:
    site_url = "https://protostar.example"
    with (docs_repo / "zensical.toml").open("a", encoding="utf-8") as config:
        config.write(f'site_url = "{site_url}/"\n')
    dashboard = docs_repo / "metrics" / "index.html"
    dashboard.parent.mkdir()
    dashboard.write_text(
        '<section id="benchmarks"></section>\n'
        '<section id="rollback"></section>\n'
        '<section id="mutations"></section>\n',
        encoding="utf-8",
    )
    (docs_repo / "README.md").write_text(
        f"[Results]({site_url}/{target})\n", encoding="utf-8"
    )

    problems = check_docs_drift.check_site_links()

    if problem is None:
        assert problems == []
    else:
        assert len(problems) == 1
        assert problem in problems[0]


def test_metrics_links_require_dashboard_source(docs_repo: Path) -> None:
    site_url = "https://protostar.example"
    with (docs_repo / "zensical.toml").open("a", encoding="utf-8") as config:
        config.write(f'site_url = "{site_url}/"\n')
    (docs_repo / "README.md").write_text(
        f"[Results]({site_url}/metrics/#rollback)\n", encoding="utf-8"
    )

    problems = check_docs_drift.check_site_links()

    assert len(problems) == 1
    assert "has no page" in problems[0]


def test_plain_prose_passes_the_voice_check(docs_repo: Path) -> None:
    _write(
        docs_repo,
        "guide/usage.md",
        '---\ndescription: "Usage."\n---\n\nRun `just lint`.\n\n| Tool | Flag |\n| --- | --- |\n| uv | — |\n\n```text\nx — y, simply\n```\n',
    )

    assert check_docs_drift.check_writing_voice() == []


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        ("It merges — and keeps your edits.", "an em dash"),
        ("| It merges — fast | yes |", "an em dash"),
        ("Simply run the command.", "'Simply'"),
        ("A seamless update.", "'seamless'"),
        ("It leverages uv.", "'leverages'"),
        ("Every failure maps to POSIX exit codes.", "'POSIX exit'"),
        ("It returns POSIX-compliant codes.", "'POSIX-compliant'"),
    ],
)
def test_the_voice_check_names_each_problem(
    docs_repo: Path, line: str, problem: str
) -> None:
    _write(docs_repo, "guide/usage.md", f'---\ndescription: "Usage."\n---\n\n{line}\n')

    problems = check_docs_drift.check_writing_voice()

    assert len(problems) == 1
    assert problem in problems[0]
    assert problems[0].startswith("docs/guide/usage.md")
