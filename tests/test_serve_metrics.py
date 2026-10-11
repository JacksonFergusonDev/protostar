"""The metrics preview reads live source without sharing the docs server's port."""

from email.message import Message
from functools import partial
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
        ("/metrics/benchmark-dashboard.js", "source/benchmark-dashboard.js"),
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


@pytest.mark.parametrize("optional_published", [False, True])
def test_preview_fetches_every_dashboard_dataset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    optional_published: bool,
) -> None:
    fetched: list[str] = []
    optional_fetched: list[str] = []

    def fetch(url: str) -> bytes:
        fetched.append(url)
        return url.encode()

    def fetch_optional(url: str, destination: Path) -> None:
        optional_fetched.append(url)
        if optional_published:
            destination.write_bytes(url.encode())

    def server(
        address: tuple[str, int], handler: partial[serve_metrics.PreviewHandler]
    ) -> None:
        directory = Path(handler.keywords["directory"])
        expected = {
            "data.js",
            "mutation-history.json",
            "mutation-latest.json",
            "rollback-history.json",
            "rollback-latest.json",
        }
        if optional_published:
            expected.add("benchmark-history.json")
        assert {path.name for path in (directory / "metrics").iterdir()} == expected
        for filename in expected:
            assert (directory / "metrics" / filename).read_bytes() == (
                serve_metrics.DATA_URL + filename
            ).encode()
        raise KeyboardInterrupt

    monkeypatch.setattr(serve_metrics, "fetch_bytes", fetch)
    monkeypatch.setattr(serve_metrics, "fetch_optional", fetch_optional)
    monkeypatch.setattr(serve_metrics, "ThreadingHTTPServer", server)
    monkeypatch.setattr("scripts.serve_metrics.tempfile.tempdir", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["serve_metrics.py", "--no-open"])
    with pytest.raises(KeyboardInterrupt):
        serve_metrics.main()
    assert set(fetched) == {
        serve_metrics.DATA_URL + filename for filename in serve_metrics.DATA_FILES
    }
    assert set(optional_fetched) == {
        serve_metrics.DATA_URL + filename
        for filename in serve_metrics.OPTIONAL_DATA_FILES
    }


def test_a_data_file_not_published_yet_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Benchmark history appears with the first nightly comparison."""
    import urllib.error
    import urllib.request

    def missing(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError("url", 404, "Not Found", Message(), None)

    monkeypatch.setattr(urllib.request, "urlopen", missing)
    destination = tmp_path / "benchmark-history.json"

    serve_metrics.fetch_optional(
        "https://example.test/benchmark-history.json", destination
    )

    assert not destination.exists()


def test_the_preview_fetches_every_file_pages_publishes():
    from scripts.prepare_pages import METRICS_DATA

    assert {*serve_metrics.DATA_FILES, *serve_metrics.OPTIONAL_DATA_FILES} == set(
        METRICS_DATA
    )
