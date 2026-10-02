"""Preview benchmark history on localhost without publishing or copying source assets."""

from __future__ import annotations

import argparse
import sys
import tempfile
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import DOCS_DIR, OutputStyle, fetch_bytes, report
from scripts.prepare_pages import BENCHMARK_ASSETS, BENCHMARK_DIR, HEADER_CSS, HOUSE_DIR

DEFAULT_PORT = 8765
DATA_URL = "https://protostar.jacksonferguson.me/benchmarks/data.js"


class PreviewHandler(SimpleHTTPRequestHandler):
    """Serve current source assets alongside a temporary published-data snapshot."""

    def translate_path(self, path: str) -> str:
        """Map sanitized preview routes to their repository source files."""
        translated = super().translate_path(path)
        relative = Path(translated).relative_to(self.directory)
        if relative == Path("benchmarks"):
            return str(BENCHMARK_DIR)
        if relative.parts[:2] == ("benchmarks", "house"):
            return str(HOUSE_DIR.joinpath(*relative.parts[2:]))
        if relative.parent == Path("benchmarks"):
            if relative.name == "site-header.css":
                return str(HEADER_CSS)
            if relative.name in BENCHMARK_ASSETS:
                return str(BENCHMARK_DIR / relative.name)
            if relative.name in ("favicon.svg", "favicon.png"):
                return str(DOCS_DIR / "assets" / relative.name)
        return translated

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
    data = fetch_bytes(DATA_URL)
    with tempfile.TemporaryDirectory(prefix="protostar-benchmarks-") as directory:
        root = Path(directory)
        (root / "benchmarks").mkdir()
        (root / "benchmarks" / "data.js").write_bytes(data)
        (root / "index.html").write_text(
            '<meta http-equiv="refresh" content="0; url=/benchmarks/">',
            encoding="utf-8",
        )
        handler = partial(PreviewHandler, directory=directory)
        try:
            server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        except OSError as error:
            report(f"Cannot start the benchmark preview: {error}", stderr=True)
            report(
                "Stop the other preview, or choose a port with `just serve-benchmarks 8766`.",
                stderr=True,
            )
            sys.exit(1)
        with server:
            url = f"http://127.0.0.1:{server.server_port}/benchmarks/"
            report(f"Benchmark preview: {url}", style=OutputStyle.COMMAND)
            report("Refresh to see source edits. Ctrl+C stops the server.")
            if not args.no_open:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
