import io
import sys
import tarfile
from pathlib import Path

import pytest

from scripts import sync_house_style
from scripts.sync_house_style import (
    HOUSE_STYLE_TAG,
    committed_files,
    release_files,
    write_files,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _archive(files: dict[str, bytes], root: str = "house-style-1.0.0") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(f"{root}/{name}")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


RELEASE = {
    "LICENSE": b"MIT",
    "README.md": b"# house-style",
    "package.json": b"{}",
    "css/tokens.css": b":root {}",
    "css/notes.txt": b"not a stylesheet",
    "js/cast.js": b"export {};",
    "js/cast.d.ts": b"export {};",
    "fonts/dm-sans.woff2": b"font",
    "fonts/OFL.txt": b"license",
    "fonts/README.md": b"# Fonts",
    "icons/arrow-right.svg": b"<svg/>",
    "icons/README.md": b"# Icons",
    "GUIDELINES.md": b"# Guidelines",
    "AGENTS.md": b"# Agents",
}


def test_release_files_keep_what_the_docs_serve():
    files = release_files(_archive(RELEASE), "v9.9.9")

    assert set(files) == {
        "LICENSE",
        "README.txt",
        "css/tokens.css",
        "js/cast.js",
        "fonts/dm-sans.woff2",
        "fonts/OFL.txt",
        "fonts/README.txt",
        "icons/arrow-right.svg",
        "icons/README.txt",
        "GUIDELINES.txt",
    }
    assert files["fonts/README.txt"] == b"# Fonts"
    assert files["GUIDELINES.txt"] == b"# Guidelines"
    assert b"house-style v9.9.9" in files["README.txt"]


def test_write_files_leaves_exactly_the_release(tmp_path: Path):
    (tmp_path / "css").mkdir()
    (tmp_path / "css" / "old.css").write_text("stale")
    (tmp_path / "gone").mkdir()
    (tmp_path / "gone" / "file.js").write_text("stale")
    files = release_files(_archive(RELEASE), "v9.9.9")

    write_files(tmp_path, files)

    assert committed_files(tmp_path) == files
    assert not (tmp_path / "gone").exists()


@pytest.mark.parametrize("edit", ["matches", "edited", "missing"])
def test_check_fails_unless_the_copy_matches(
    edit: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    archive = _archive(RELEASE)
    vendor = tmp_path / "docs" / "house"
    write_files(vendor, release_files(archive, HOUSE_STYLE_TAG))
    if edit == "edited":
        (vendor / "css" / "tokens.css").write_text(":root { --bg: red; }")
    elif edit == "missing":
        (vendor / "js" / "cast.js").unlink()
    monkeypatch.setattr(sync_house_style, "fetch_bytes", lambda url: archive)
    monkeypatch.setattr(sync_house_style, "VENDOR_DIR", vendor)
    monkeypatch.setattr(sync_house_style, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["sync_house_style.py", "--check"])

    if edit == "matches":
        sync_house_style.main()
        assert "matches" in capsys.readouterr().out
    else:
        with pytest.raises(SystemExit) as raised:
            sync_house_style.main()
        assert raised.value.code == 1
        assert "just sync-house-style" in capsys.readouterr().err


def test_the_docs_load_only_vendored_house_files():
    """Every docs/house/ path the site references was vendored."""
    vendored = committed_files(REPO_ROOT / "docs" / "house")
    config = (REPO_ROOT / "zensical.toml").read_text(encoding="utf-8")
    template = (REPO_ROOT / "overrides" / "home.html").read_text(encoding="utf-8")
    for referenced in ("css/fonts.css", "css/tokens.css", "css/terminal.css"):
        assert f'"house/{referenced}"' in config
        assert referenced in vendored
    for referenced in ("css/components.css", "css/install.css", "css/icons.css"):
        assert f"'house/{referenced}'" in template
        assert referenced in vendored
