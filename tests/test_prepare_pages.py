"""Pages artifacts keep release content separate from permanent entry URLs."""

import json
from pathlib import Path

import pytest

from protostar.errors import ConfigurationError
from scripts.prepare_pages import (
    BENCHMARK_ASSETS,
    BENCHMARK_DIR,
    HEADER_CSS,
    HOUSE_DIR,
    assemble_pages,
    read_versions,
    render_benchmark_index,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _page(version: str, route: str, body: str) -> str:
    """A released page, built for its versioned URL as mike builds it."""
    url = f"https://docs.example/{version}/{route}"
    return (
        f'<html><head>\n<link rel="canonical" href="{url}">\n'
        f'<meta property="og:url" content="{url}">\n'
        f'<script type="application/ld+json">{{"url":"{url}"}}</script>\n'
        f"</head><article>{body}</article></html>"
    )


@pytest.fixture
def published_docs(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "archive"
    output = tmp_path / "artifact"
    config = tmp_path / "zensical.toml"
    _write(
        source / "versions.json",
        json.dumps(
            [
                {"version": "0.10.1", "title": "0.10.1", "aliases": ["latest"]},
                {"version": "0.9.0", "title": "0.9.0", "aliases": []},
            ]
        ),
    )
    for version in ("0.9.0", "0.10.1"):
        _write(
            source / version / "index.html",
            _page(version, "", f"<h1>Protostar {version}</h1><p>Home.</p>"),
        )
        _write(
            source / version / "why-protostar" / "index.html",
            _page(
                version,
                "why-protostar/",
                f"<h1>Why Protostar?</h1><p>Release {version} comparison.</p>",
            ),
        )
        _write(
            source / version / "sitemap.xml",
            f"<urlset><url><loc>https://docs.example/{version}/</loc></url>"
            f"<url><loc>https://docs.example/{version}/why-protostar/</loc></url></urlset>",
        )
        _write(source / version / "404.html", "Old theme's 404 and asset links")
    _write(
        source / "0.9.0" / "retired" / "index.html",
        _page("0.9.0", "retired/", "<h1>Retired</h1>"),
    )
    _write(source / "0.10.1" / "assets" / "favicon.png", "current favicon")
    _write(source / "why-protostar" / "index.html", "Stale root comparison")
    _write(source / "retired-page" / "index.html", "Stale deleted page")
    _write(source / "assets" / "outdated.js", "Old theme")
    _write(source / "llms-full.txt", "Old Markdown")
    _write(source / "latest" / "index.html", "Old alias")
    _write(source / "benchmarks" / "index.html", "Benchmark dashboard")
    _write(source / "benchmarks" / "data.js", "Historical measurements")
    _write(source / "benchmarks" / "retired.js", "Obsolete dashboard code")
    _write(
        config,
        '[project]\nsite_name = "Protostar"\nsite_description = "Python projects"\n'
        'site_url = "https://docs.example/"\n'
        'nav = [{ Home = "index.md" }, { Comparison = "why-protostar.md" }]\n',
    )
    return source, output, config


def test_latest_content_is_served_at_bare_urls_beside_every_release(
    published_docs: tuple[Path, Path, Path],
) -> None:
    source, output, config = published_docs
    before = {path: path.read_bytes() for path in source.rglob("*") if path.is_file()}

    assert assemble_pages(source, output, config) == "0.10.1"
    assert (
        output / "benchmarks" / "site-header.css"
    ).read_bytes() == HEADER_CSS.read_bytes()

    for relative in ("index.html", "why-protostar/index.html"):
        route = relative.removesuffix("index.html")
        bare = f"https://docs.example/{route}"
        for tree in (output, output / "0.10.1", output / "0.9.0"):
            page = (tree / relative).read_text(encoding="utf-8")
            assert f'<link rel="canonical" href="{bare}">' in page
            assert f'<meta property="og:url" content="{bare}">' in page
            assert f'{{"url":"{bare}"}}' in page
            assert "noindex" not in page
        assert "0.10.1" in (output / relative).read_text()
        assert "Stale" not in (output / relative).read_text()

        redirect = (output / "latest" / relative).read_text(encoding="utf-8")
        assert (
            f'window.location.replace("{bare}" + window.location.search + window.location.hash)'
            in redirect
        )
        assert (
            f'<noscript><meta http-equiv="refresh" content="0; url={bare}">' in redirect
        )
        assert f'<a href="{bare}">' in redirect

    retired = (output / "0.9.0" / "retired" / "index.html").read_text()
    assert '<head>\n<meta name="robots" content="noindex">' in retired
    assert 'href="https://docs.example/0.9.0/retired/"' in retired
    assert not (output / "retired").exists()

    assert (output / "benchmarks" / "data.js").read_bytes() == (
        source / "benchmarks" / "data.js"
    ).read_bytes()
    for filename in BENCHMARK_ASSETS:
        if filename == "index.html":
            assert (output / "benchmarks" / filename).read_text(
                encoding="utf-8"
            ) == render_benchmark_index()
            continue
        assert (output / "benchmarks" / filename).read_bytes() == (
            BENCHMARK_DIR / filename
        ).read_bytes()
    assert not (output / "benchmarks" / "retired.js").exists()
    assert {
        path.relative_to(output / "benchmarks" / "house"): path.read_bytes()
        for path in (output / "benchmarks" / "house").rglob("*")
        if path.is_file()
    } == {
        path.relative_to(HOUSE_DIR): path.read_bytes()
        for path in HOUSE_DIR.rglob("*")
        if path.is_file()
    }
    for filename in ("favicon.svg", "favicon.png"):
        assert (output / "benchmarks" / filename).is_file()
    assert not (output / "retired-page").exists()
    assert (
        output / "0.9.0" / "404.html"
    ).read_text() == "Old theme's 404 and asset links"
    assert not (output / "assets" / "outdated.js").exists()
    assert (output / "assets" / "favicon.png").read_text() == "current favicon"
    assert (output / "versions.json").read_bytes() == (
        source / "versions.json"
    ).read_bytes()
    assert (output / "sitemap.xml").read_text() == (
        "<urlset><url><loc>https://docs.example/</loc></url>"
        "<url><loc>https://docs.example/why-protostar/</loc></url></urlset>"
    )
    assert (output / "CNAME").read_text() == "docs.example\n"
    robots = (output / "robots.txt").read_text()
    assert robots.startswith("User-agent: *\nAllow: /\n")
    assert robots.endswith("Sitemap: https://docs.example/sitemap.xml\n")
    assert (output / ".nojekyll").is_file()
    assert '<a href="https://docs.example/">' in (output / "404.html").read_text()
    assert before == {
        path: path.read_bytes() for path in source.rglob("*") if path.is_file()
    }


def test_markdown_is_generated_from_latest_html_with_bare_links(
    published_docs: tuple[Path, Path, Path],
) -> None:
    source, output, config = published_docs
    assemble_pages(source, output, config)

    index = (output / "llms.txt").read_text()
    content = (output / "llms-full.txt").read_text()
    assert "https://docs.example/why-protostar/index.md" in index
    assert "Release 0.10.1 comparison." in content
    assert "0.9.0" not in content
    assert "Redirecting" not in content
    assert (
        "Release 0.10.1 comparison."
        in (output / "why-protostar" / "index.md").read_text()
    )
    assert not (output / "0.10.1" / "why-protostar" / "index.md").exists()


@pytest.mark.parametrize("name", ["benchmarks", "robots.txt", "0.9.0"])
def test_latest_content_cannot_shadow_what_the_root_publishes(
    published_docs: tuple[Path, Path, Path], name: str
) -> None:
    source, output, config = published_docs
    _write(source / "0.10.1" / name, "Shadowing entry")
    with pytest.raises(ConfigurationError, match="collides"):
        assemble_pages(source, output, config)
    assert not output.exists()


@pytest.mark.parametrize("aliases", [([], []), (["latest"], ["latest"])])
def test_invalid_latest_registry_fails_before_creating_output(
    published_docs: tuple[Path, Path, Path], aliases: tuple[list[str], list[str]]
) -> None:
    source, output, config = published_docs
    entries = json.loads((source / "versions.json").read_text())
    for entry, values in zip(entries, aliases, strict=True):
        entry["aliases"] = values
    _write(source / "versions.json", json.dumps(entries))

    with pytest.raises(ConfigurationError):
        assemble_pages(source, output, config)
    assert not output.exists()


@pytest.mark.parametrize("name", ["../escape", "benchmarks", "0.9.0"])
def test_registry_rejects_unsafe_or_colliding_names(
    published_docs: tuple[Path, Path, Path], name: str
) -> None:
    source, _, _ = published_docs
    entries = json.loads((source / "versions.json").read_text())
    entries[0]["aliases"].append(name)
    _write(source / "versions.json", json.dumps(entries))
    with pytest.raises(ConfigurationError):
        read_versions(source)


def test_existing_output_is_never_overwritten(
    published_docs: tuple[Path, Path, Path],
) -> None:
    source, output, config = published_docs
    _write(output / "index.html", "Already prepared")
    with pytest.raises(ConfigurationError, match="new directory"):
        assemble_pages(source, output, config)
    assert (output / "index.html").read_text() == "Already prepared"


def test_missing_navigation_page_blocks_incomplete_markdown(
    published_docs: tuple[Path, Path, Path],
) -> None:
    source, output, config = published_docs
    (source / "0.10.1" / "why-protostar" / "index.html").unlink()
    with pytest.raises(ConfigurationError, match="generate all"):
        assemble_pages(source, output, config)


def test_benchmarks_are_not_published_without_recorded_data(
    published_docs: tuple[Path, Path, Path],
) -> None:
    source, output, config = published_docs
    (source / "benchmarks" / "data.js").unlink()

    assemble_pages(source, output, config)

    assert not (output / "benchmarks").exists()
