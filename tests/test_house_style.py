from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_the_docs_load_only_vendored_house_files():
    """Every docs/house/ path the site references was vendored."""
    house = REPO_ROOT / "docs" / "house"
    config = (REPO_ROOT / "zensical.toml").read_text(encoding="utf-8")
    template = (REPO_ROOT / "overrides" / "home.html").read_text(encoding="utf-8")
    for referenced in (
        "css/fonts.css",
        "css/tokens.css",
        "css/terminal.css",
        "css/icons.css",
    ):
        assert f'"house/{referenced}"' in config
        assert (house / referenced).is_file()
    for referenced in ("css/components.css", "css/install.css"):
        assert f"'house/{referenced}'" in template
        assert (house / referenced).is_file()
