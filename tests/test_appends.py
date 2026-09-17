from pathlib import Path

from protostar.appends import append_marker_blocks, get_comment_markers
from protostar.intent import AppendContribution


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
    payloads = [AppendContribution("template:environment", "export FOO=bar")]
    result = append_marker_blocks(orig, payloads, Path(".envrc"))

    assert result.content
    assert "# --- Protostar Region:" in result.content
    assert "export FOO=bar" in result.content
    assert "# --- End Protostar Region: template:environment ---" in result.content
    assert result.content.endswith("\n")


def test_append_marker_blocks_existing_file():
    orig = "export EXISTING=1\n"
    payloads = [AppendContribution("template:environment", "export FOO=bar")]
    result = append_marker_blocks(orig, payloads, Path(".envrc"))

    assert result.content
    assert result.content.startswith("export EXISTING=1\n\n# --- Protostar Region:")
    assert "export FOO=bar" in result.content


def test_append_marker_blocks_deduplication():
    payloads = [AppendContribution("template:environment", "export FOO=bar")]
    first_pass = append_marker_blocks("", payloads, Path(".envrc"))
    assert first_pass.content

    # Second pass without overwrite should return None
    second_pass = append_marker_blocks(
        first_pass.content, payloads, Path(".envrc"), overwrite=False
    )
    assert second_pass.content == first_pass.content


def test_append_marker_blocks_overwrite():
    payloads = [AppendContribution("template:environment", "export FOO=bar")]
    first_pass = append_marker_blocks("", payloads, Path(".envrc"))
    assert first_pass.content

    # Pass with overwrite=True should re-append
    second_pass = append_marker_blocks(
        first_pass.content, payloads, Path(".envrc"), overwrite=True
    )
    assert second_pass.content == first_pass.content


def test_append_marker_blocks_html_comment_syntax():
    payloads = [AppendContribution("template:html", "<div>Injected Block</div>")]
    result = append_marker_blocks("", payloads, Path("index.html"))

    assert result.content
    assert "<!-- --- Protostar Region:" in result.content
    assert "--- End Protostar Region: template:html --- -->" in result.content
