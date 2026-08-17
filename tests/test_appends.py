from pathlib import Path

from protostar.appends import append_marker_blocks, get_comment_markers


def test_get_comment_markers_hash_family():
    assert get_comment_markers(Path("script.py")) == ("#", "")
    assert get_comment_markers(Path("config.toml")) == ("#", "")
    assert get_comment_markers(Path("pipeline.yaml")) == ("#", "")
    assert get_comment_markers(Path(".gitignore")) == ("#", "")
    assert get_comment_markers(Path("justfile")) == ("#", "")
    assert get_comment_markers(Path("Dockerfile")) == ("#", "")


def test_get_comment_markers_slash_family():
    assert get_comment_markers(Path("main.ts")) == ("//", "")
    assert get_comment_markers(Path("App.tsx")) == ("//", "")
    assert get_comment_markers(Path("server.go")) == ("//", "")
    assert get_comment_markers(Path("lib.rs")) == ("//", "")
    assert get_comment_markers(Path("Main.java")) == ("//", "")


def test_get_comment_markers_html_and_markdown():
    assert get_comment_markers(Path("index.html")) == ("<!--", "-->")
    assert get_comment_markers(Path("README.md")) == ("<!--", "-->")
    assert get_comment_markers(Path("icon.svg")) == ("<!--", "-->")


def test_get_comment_markers_css():
    assert get_comment_markers(Path("style.css")) == ("/*", "*/")
    assert get_comment_markers(Path("theme.scss")) == ("/*", "*/")


def test_get_comment_markers_sql_and_lua():
    assert get_comment_markers(Path("schema.sql")) == ("--", "")
    assert get_comment_markers(Path("init.lua")) == ("--", "")


def test_get_comment_markers_fallback():
    assert get_comment_markers(Path("custom.unknownext")) == ("#", "")


def test_append_marker_blocks_fresh():
    orig = ""
    payloads = ["export FOO=bar"]
    result = append_marker_blocks(orig, payloads, Path(".envrc"))

    assert result is not None
    assert "# --- Protostar Injection:" in result
    assert "export FOO=bar" in result
    assert "# --- End Protostar Injection ---" in result
    assert result.endswith("\n")


def test_append_marker_blocks_existing_file():
    orig = "export EXISTING=1\n"
    payloads = ["export FOO=bar"]
    result = append_marker_blocks(orig, payloads, Path(".envrc"))

    assert result is not None
    assert result.startswith("export EXISTING=1\n\n# --- Protostar Injection:")
    assert "export FOO=bar" in result


def test_append_marker_blocks_deduplication():
    payloads = ["export FOO=bar"]
    first_pass = append_marker_blocks("", payloads, Path(".envrc"))
    assert first_pass is not None

    # Second pass without overwrite should return None
    second_pass = append_marker_blocks(
        first_pass, payloads, Path(".envrc"), overwrite=False
    )
    assert second_pass is None


def test_append_marker_blocks_overwrite():
    payloads = ["export FOO=bar"]
    first_pass = append_marker_blocks("", payloads, Path(".envrc"))
    assert first_pass is not None

    # Pass with overwrite=True should re-append
    second_pass = append_marker_blocks(
        first_pass, payloads, Path(".envrc"), overwrite=True
    )
    assert second_pass is not None
    assert second_pass.count("export FOO=bar") == 2


def test_append_marker_blocks_html_comment_syntax():
    payloads = ["<div>Injected Block</div>"]
    result = append_marker_blocks("", payloads, Path("index.html"))

    assert result is not None
    assert "<!-- --- Protostar Injection:" in result
    assert "--- End Protostar Injection --- -->" in result
