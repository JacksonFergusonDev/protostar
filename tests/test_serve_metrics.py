"""The metrics preview reads live source without sharing the docs server's port."""

from pathlib import Path

import pytest

from scripts import serve_metrics


@pytest.fixture
def handler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> serve_metrics.PreviewHandler:
    monkeypatch.setattr(serve_metrics, "METRICS_DIR", tmp_path / "source")
    monkeypatch.setattr(serve_metrics, "HOUSE_DIR", tmp_path / "house")
    monkeypatch.setattr(serve_metrics, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(serve_metrics, "HEADER_CSS", tmp_path / "header.css")
    instance = object.__new__(serve_metrics.PreviewHandler)
    instance.directory = str(tmp_path / "preview")
    return instance


@pytest.mark.parametrize(
    ("route", "target"),
    [
        ("/metrics/", "source"),
        ("/metrics/index.html", "source/index.html"),
        ("/metrics/style.css?reload=1", "source/style.css"),
        ("/metrics/site-header.css", "header.css"),
        ("/metrics/dashboard.js", "source/dashboard.js"),
        ("/metrics/metrics.mjs", "source/metrics.mjs"),
        ("/metrics/house/css/tokens.css", "house/css/tokens.css"),
        (
            "/metrics/house/fonts/dm-sans-latin.woff2",
            "house/fonts/dm-sans-latin.woff2",
        ),
        ("/metrics/favicon.svg", "docs/assets/favicon.svg"),
        ("/metrics/data.js", "preview/metrics/data.js"),
        ("/metrics/house/../../../pyproject.toml", "preview/pyproject.toml"),
    ],
)
def test_routes_read_live_assets_and_keep_data_in_the_preview(
    handler: serve_metrics.PreviewHandler, tmp_path: Path, route: str, target: str
) -> None:
    assert Path(handler.translate_path(route)) == tmp_path / target


def test_source_edits_are_visible_without_restarting(
    handler: serve_metrics.PreviewHandler, tmp_path: Path
) -> None:
    source = tmp_path / "source" / "style.css"
    source.parent.mkdir()
    source.write_text("original", encoding="utf-8")
    assert Path(handler.translate_path("/metrics/style.css")).read_text() == "original"
    source.write_text("edited", encoding="utf-8")
    assert Path(handler.translate_path("/metrics/style.css")).read_text() == "edited"


def test_the_default_port_is_separate_from_zensical() -> None:
    assert serve_metrics.DEFAULT_PORT == 8765
    assert serve_metrics.DEFAULT_PORT != 8000
