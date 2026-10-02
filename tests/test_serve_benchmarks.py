"""The benchmark preview reads live source without sharing the docs server's port."""

from pathlib import Path

import pytest

from scripts import serve_benchmarks


@pytest.fixture
def handler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> serve_benchmarks.PreviewHandler:
    monkeypatch.setattr(serve_benchmarks, "BENCHMARK_DIR", tmp_path / "source")
    monkeypatch.setattr(serve_benchmarks, "HOUSE_DIR", tmp_path / "house")
    monkeypatch.setattr(serve_benchmarks, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(serve_benchmarks, "HEADER_CSS", tmp_path / "header.css")
    instance = object.__new__(serve_benchmarks.PreviewHandler)
    instance.directory = str(tmp_path / "preview")
    return instance


@pytest.mark.parametrize(
    ("route", "target"),
    [
        ("/benchmarks/", "source"),
        ("/benchmarks/index.html", "source/index.html"),
        ("/benchmarks/style.css?reload=1", "source/style.css"),
        ("/benchmarks/site-header.css", "header.css"),
        ("/benchmarks/dashboard.js", "source/dashboard.js"),
        ("/benchmarks/metrics.mjs", "source/metrics.mjs"),
        ("/benchmarks/house/css/tokens.css", "house/css/tokens.css"),
        (
            "/benchmarks/house/fonts/dm-sans-latin.woff2",
            "house/fonts/dm-sans-latin.woff2",
        ),
        ("/benchmarks/favicon.svg", "docs/assets/favicon.svg"),
        ("/benchmarks/data.js", "preview/benchmarks/data.js"),
        ("/benchmarks/house/../../../pyproject.toml", "preview/pyproject.toml"),
    ],
)
def test_routes_read_live_assets_and_keep_data_in_the_preview(
    handler: serve_benchmarks.PreviewHandler, tmp_path: Path, route: str, target: str
) -> None:
    assert Path(handler.translate_path(route)) == tmp_path / target


def test_source_edits_are_visible_without_restarting(
    handler: serve_benchmarks.PreviewHandler, tmp_path: Path
) -> None:
    source = tmp_path / "source" / "style.css"
    source.parent.mkdir()
    source.write_text("original", encoding="utf-8")
    assert (
        Path(handler.translate_path("/benchmarks/style.css")).read_text() == "original"
    )
    source.write_text("edited", encoding="utf-8")
    assert Path(handler.translate_path("/benchmarks/style.css")).read_text() == "edited"


def test_the_default_port_is_separate_from_zensical() -> None:
    assert serve_benchmarks.DEFAULT_PORT == 8765
    assert serve_benchmarks.DEFAULT_PORT != 8000
