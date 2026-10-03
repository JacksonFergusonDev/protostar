#!/usr/bin/env python3
"""Renders the docs' social share card (docs/assets/og-card.png).

Link previews (Slack, Discord, iMessage, LinkedIn, X) show this 1200x630
image beside the page's title and description. It draws the house palette
and fonts, as jacksonferguson.me's card does, with the tagline from
zensical.toml. The PNG is committed: re-render it with `just og-card` after
changing the name, tagline, or mark.

Usage:
    uv run --with playwright python scripts/render_og_card.py
"""

from __future__ import annotations

import base64
import random
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts._common import DOCS_DIR, REPO_ROOT

OUTPUT = DOCS_DIR / "assets" / "og-card.png"
FONTS = DOCS_DIR / "house" / "fonts"
MARK = DOCS_DIR / "assets" / "favicon.svg"
WIDTH, HEIGHT = 1200, 630


def _font(name: str) -> str:
    return base64.b64encode((FONTS / name).read_bytes()).decode("ascii")


def _stars() -> str:
    """A fixed star field, so re-renders are byte-stable."""
    rng = random.Random(7)
    circles = []
    for _ in range(160):
        x = 520 + rng.random() * 680
        y = rng.random() * HEIGHT
        r = 1.6 if rng.random() < 0.08 else 0.5 + rng.random() * 0.7
        fill = "#22d3ee" if rng.random() < 0.12 else "#e8edef"
        opacity = 0.15 + rng.random() * 0.5 * ((x - 520) / 680)
        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" '
            f'fill="{fill}" opacity="{opacity:.2f}"/>'
        )
    return "".join(circles)


def card_html() -> str:
    """The card as a self-contained page: fonts and mark inlined."""
    with (REPO_ROOT / "zensical.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    name = project["site_name"]
    tagline = project["site_description"]
    host = urlsplit(project["site_url"]).hostname
    mark = MARK.read_text(encoding="utf-8")
    return f"""<!doctype html><html><head><style>
@font-face {{ font-family: 'DM Sans'; font-weight: 400; src: url(data:font/woff2;base64,{_font("dm-sans-latin-400-normal.woff2")}) format('woff2'); }}
@font-face {{ font-family: 'DM Sans'; font-weight: 700; src: url(data:font/woff2;base64,{_font("dm-sans-latin-700-normal.woff2")}) format('woff2'); }}
@font-face {{ font-family: 'JetBrains Mono'; font-weight: 400; src: url(data:font/woff2;base64,{_font("jetbrains-mono-latin-400-normal.woff2")}) format('woff2'); }}
* {{ margin: 0; box-sizing: border-box; }}
body {{ width: {WIDTH}px; height: {HEIGHT}px; background: #0a0c0e; color: #e8edef; font-family: 'DM Sans'; position: relative; overflow: hidden; }}
.field {{ position: absolute; inset: 0; }}
.glow {{ position: absolute; right: -140px; top: -120px; width: 760px; height: 760px; border-radius: 50%;
  background: radial-gradient(circle, rgba(34, 211, 238, 0.12), rgba(34, 211, 238, 0) 62%); }}
.inner {{ position: absolute; inset: 72px 80px; display: flex; flex-direction: column; }}
.mark {{ width: 64px; height: 64px; }}
.mark svg {{ width: 100%; height: 100%; }}
h1 {{ margin-top: auto; font-size: 120px; font-weight: 700; line-height: 0.95; letter-spacing: -0.035em; }}
h1 .accent {{ color: #22d3ee; }}
p {{ margin-top: 28px; font-size: 34px; line-height: 1.3; color: #939da6; max-width: 620px; }}
.rule {{ margin-top: 44px; height: 1px; background: #252c31; }}
.meta {{ margin-top: 20px; display: flex; justify-content: space-between; font-family: 'JetBrains Mono'; font-size: 19px; letter-spacing: 0.06em; color: #939da6; }}
.meta .url {{ color: #22d3ee; }}
</style></head><body>
<svg class="field" viewBox="0 0 {WIDTH} {HEIGHT}">{_stars()}</svg>
<div class="glow"></div>
<div class="inner">
  <div class="mark">{mark}</div>
  <h1>{name}<span class="accent">.</span></h1>
  <p>{tagline}</p>
  <div class="rule"></div>
  <div class="meta"><span class="url">{host}</span><span>uv tool install protostar</span></div>
</div>
</body></html>"""


def main() -> None:
    """Render the card to docs/assets/og-card.png."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.set_content(card_html())
        page.evaluate("document.fonts.ready")
        page.screenshot(path=OUTPUT)
        browser.close()
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
