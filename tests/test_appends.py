from pathlib import Path

from protostar.appends import append_marker_blocks, get_comment_markers
from protostar.intent import AppendContribution
from protostar.merge import ConflictReason, ResolutionChoice


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
    assert f"# region: protostar {payloads[0].tag}" in result.content
    assert "export FOO=bar" in result.content
    assert f"# endregion: protostar {payloads[0].tag}" in result.content
    assert result.content.endswith("\n")


def test_append_marker_blocks_existing_file():
    orig = "export EXISTING=1\n"
    payloads = [AppendContribution("template:environment", "export FOO=bar")]
    result = append_marker_blocks(orig, payloads, Path(".envrc"))

    assert result.content
    assert result.content.startswith(
        f"export EXISTING=1\n\n# region: protostar {payloads[0].tag}"
    )
    assert "export FOO=bar" in result.content


def test_append_marker_blocks_deduplication():
    payloads = [AppendContribution("template:environment", "export FOO=bar")]
    first_pass = append_marker_blocks("", payloads, Path(".envrc"))
    assert first_pass.content

    # Second pass without overwrite should return unchanged content
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
    assert f"<!-- region: protostar {payloads[0].tag} -->" in result.content
    assert f"<!-- endregion: protostar {payloads[0].tag} -->" in result.content


def test_append_marker_blocks_slash_comment_syntax():
    payloads = [AppendContribution("template:ts", "console.log('test');")]
    result = append_marker_blocks("", payloads, Path("app.ts"))

    assert result.content
    assert f"// region: protostar {payloads[0].tag}" in result.content
    assert f"// endregion: protostar {payloads[0].tag}" in result.content


def test_append_marker_blocks_css_comment_syntax():
    payloads = [AppendContribution("template:css", ".box { color: red; }")]
    result = append_marker_blocks("", payloads, Path("style.css"))

    assert result.content
    assert f"/* region: protostar {payloads[0].tag} */" in result.content
    assert f"/* endregion: protostar {payloads[0].tag} */" in result.content


def test_append_marker_blocks_sql_comment_syntax():
    payloads = [AppendContribution("template:sql", "SELECT 1;")]
    result = append_marker_blocks("", payloads, Path("query.sql"))

    assert result.content
    assert f"-- region: protostar {payloads[0].tag}" in result.content
    assert f"-- endregion: protostar {payloads[0].tag}" in result.content


def _owned_region() -> tuple[str, dict[str, str]]:
    """A file holding one applied region, and its baselines."""
    applied = append_marker_blocks(
        "export A=1\n", [AppendContribution("gone", "export B=2")], Path(".envrc")
    )
    return applied.content, applied.baselines


def test_a_region_nothing_declares_is_removed_when_unedited():
    content, baselines = _owned_region()

    result = append_marker_blocks(content, [], Path(".envrc"), baselines=baselines)

    assert result.content == "export A=1\n"
    assert result.baselines == {}
    assert not result.conflicts


def test_an_edited_region_nothing_declares_is_a_decision():
    content, baselines = _owned_region()
    edited = content.replace("export B=2", "export B=3")

    result = append_marker_blocks(edited, [], Path(".envrc"), baselines=baselines)

    assert result.content == edited
    assert result.baselines == baselines
    [conflict] = result.conflicts
    assert conflict.reason is ConflictReason.RETRACTED
    assert conflict.location.identity == "gone"

    removed = append_marker_blocks(
        edited,
        [],
        Path(".envrc"),
        baselines=baselines,
        resolutions={conflict.id: ResolutionChoice.DESIRED},
    )
    assert removed.content == "export A=1\n"
    assert removed.baselines == {}
    kept = append_marker_blocks(
        edited,
        [],
        Path(".envrc"),
        baselines=baselines,
        resolutions={conflict.id: ResolutionChoice.LOCAL},
    )
    assert kept.content == edited
    assert kept.baselines == {}


def test_a_deleted_region_nothing_declares_is_forgotten():
    _, baselines = _owned_region()

    result = append_marker_blocks(
        "export A=1\n", [], Path(".envrc"), baselines=baselines
    )

    assert result.content == "export A=1\n"
    assert result.baselines == {}
