"""Preview the metrics dashboard on localhost without publishing or copying source assets."""

from __future__ import annotations

import argparse
import io
import sys
import tempfile
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import DOCS_DIR, OutputStyle, fetch_bytes, report
from scripts.prepare_pages import (
    FOOTER_CSS,
    HEADER_CSS,
    HOUSE_DIR,
    METRICS_ASSETS,
    METRICS_DIR,
    render_metrics_index,
)

DEFAULT_PORT = 8765
DATA_URL = "https://protostar.jacksonferguson.me/metrics/"
DATA_FILES = (
    "data.js",
    "mutation-history.json",
    "rollback-history.json",
    "rollback-latest.json",
)


class PreviewHandler(SimpleHTTPRequestHandler):
    """Serve current source assets alongside a temporary published-data snapshot."""

    def translate_path(self, path: str) -> str:
        """Map sanitized preview routes to their repository source files."""
        translated = super().translate_path(path)
        relative = Path(translated).relative_to(self.directory)
        if relative == Path("metrics"):
            return str(METRICS_DIR)
        if relative.parts[:2] == ("metrics", "house"):
            return str(HOUSE_DIR.joinpath(*relative.parts[2:]))
        if relative.parent == Path("metrics"):
            if relative.name == "site-header.css":
                return str(HEADER_CSS)
            if relative.name == "site-footer.css":
                return str(FOOTER_CSS)
            if relative.name in METRICS_ASSETS:
                return str(METRICS_DIR / relative.name)
            if relative.name in ("favicon.svg", "favicon.png"):
                return str(DOCS_DIR / "assets" / relative.name)
        return translated

    def send_head(self) -> BinaryIO | None:
        """Render the live dashboard with the same footer the docs include."""
        path = Path(self.translate_path(self.path))
        if path in (METRICS_DIR, METRICS_DIR / "index.html"):
            content = render_metrics_index().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            return io.BytesIO(content)
        return super().send_head()

    def end_headers(self) -> None:
        """Ensure browser refreshes always pick up source edits."""
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    """Fetch published measurements, open the preview, and serve until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser.")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="protostar-metrics-") as directory:
        root = Path(directory)
        (root / "metrics").mkdir()
        for filename in DATA_FILES:
            (root / "metrics" / filename).write_bytes(fetch_bytes(DATA_URL + filename))
        (root / "index.html").write_text(
            '<meta http-equiv="refresh" content="0; url=/metrics/">',
            encoding="utf-8",
        )
        handler = partial(PreviewHandler, directory=directory)
        try:
            server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        except OSError as error:
            report(f"Cannot start the metrics preview: {error}", stderr=True)
            report(
                "Stop the other preview, or choose a port with `just serve-metrics 8766`.",
                stderr=True,
            )
            sys.exit(1)
        with server:
            url = f"http://127.0.0.1:{server.server_port}/metrics/"
            report(f"Metrics preview: {url}", style=OutputStyle.COMMAND)
            report("Refresh to see source edits. Ctrl+C stops the server.")
            if not args.no_open:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
