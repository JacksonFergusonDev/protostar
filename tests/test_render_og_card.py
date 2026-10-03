"""The share card draws the site's own name, tagline, and address."""

import tomllib

from scripts._common import REPO_ROOT
from scripts.render_og_card import card_html


def test_card_reads_its_words_from_the_site_configuration() -> None:
    with (REPO_ROOT / "zensical.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]

    html = card_html()

    assert f"<h1>{project['site_name']}<" in html
    assert f"<p>{project['site_description']}</p>" in html
    assert "protostar.jacksonferguson.me</span>" in html
    assert "url(data:font/woff2;base64," in html
    assert html == card_html()
