from pathlib import Path

import pytest

from protostar.appends import (
    append_marker_blocks,
    attach_regions,
    cut_regions,
    detach_regions,
    get_comment_markers,
)
from protostar.errors import ConfigurationError
from protostar.intent import AppendContribution, region_tag
from protostar.merge import (
    MISSING,
    ConflictReason,
    ConflictSides,
    MergeConflict,
    MergeLocation,
    ResolutionChoice,
)


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


def test_detach_and_attach_regions_preserves_crlf():
    tag = region_tag("template:recipes")
    text = (
        f"base v1\r\n\r\n"
        f"# region: protostar {tag}\r\n"
        f"recipe v1\r\n"
        f"# endregion: protostar {tag}\r\n"
    )
    filepath = Path("justfile")
    omitted = {"template:recipes": "recipe v1"}
    detached, kept = detach_regions(text, omitted, filepath)
    assert detached == "base v1\r\n"
    re_attached = attach_regions("base v2\r\n", kept)
    assert re_attached == (
        f"base v2\r\n\r\n"
        f"# region: protostar {tag}\r\n"
        f"recipe v1\r\n"
        f"# endregion: protostar {tag}\r\n"
    )


def test_an_omitted_region_retracts_cleanly_under_crlf():
    tag = region_tag("gone")
    content = (
        f"export A=1\r\n\r\n"
        f"# region: protostar {tag}\r\n"
        f"export B=2\r\n"
        f"# endregion: protostar {tag}\r\n"
    )
    baselines = {
        "gone": f"# region: protostar {tag}\nexport B=2\n# endregion: protostar {tag}"
    }
    result = append_marker_blocks(content, [], Path(".envrc"), baselines=baselines)
    assert result.content == "export A=1\r\n"
    assert result.baselines == {}


TAG = region_tag("cut")


def _region(newline: str) -> str:
    return f"# region: protostar {TAG}{newline}x{newline}# endregion: protostar {TAG}"


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        # Between lines, with and without the blank lines appending adds.
        ("a\n{R}\nb\n", "LF", "a\nb\n"),
        ("a\r\n{R}\r\nb\r\n", "CRLF", "a\r\nb\r\n"),
        ("a\n\n{R}\n\nb\n", "LF", "a\n\nb\n"),
        ("a\r\n\r\n{R}\r\n\r\nb\r\n", "CRLF", "a\r\n\r\nb\r\n"),
        ("a\n\n{R}\nb\n", "LF", "a\n\nb\n"),
        ("a\n{R}\n\nb\n", "LF", "a\n\nb\n"),
        # Last in the file.
        ("a\n{R}\n", "LF", "a\n"),
        ("a\n\n{R}\n", "LF", "a\n"),
        ("a\r\n\r\n{R}\r\n", "CRLF", "a\r\n"),
        ("a\n\n{R}", "LF", "a\n"),
        # First in the file.
        ("{R}\n", "LF", ""),
        ("{R}\n\nb\n", "LF", "b\n"),
        ("{R}\r\n\r\nb\r\n", "CRLF", "b\r\n"),
        # Mixed line endings around the region.
        ("a\r\n\r\n{R}\n\nb\n", "LF", "a\r\n\nb\n"),
        ("a\n\n{R}\r\n\r\nb\r\n", "CRLF", "a\n\r\nb\r\n"),
    ],
)
def test_cutting_a_region_takes_its_line_break_and_one_blank_line(
    before, after, expected
):
    region = _region("\r\n" if after == "CRLF" else "\n")
    text = before.replace("{R}", region)

    assert cut_regions(text, ["cut"], Path(".envrc")) == expected
    assert detach_regions(text, ["cut"], Path(".envrc")) == (expected, (region,))


def test_cutting_an_absent_region_changes_nothing():
    assert cut_regions("a\n", ["cut"], Path(".envrc")) == "a\n"
    assert detach_regions("a\n", ["cut"], Path(".envrc")) == ("a\n", ())


def test_detached_regions_keep_their_order_in_the_file():
    first, second = region_tag("first"), region_tag("second")
    text = (
        f"# region: protostar {second}\n2\n# endregion: protostar {second}\n\n"
        f"# region: protostar {first}\n1\n# endregion: protostar {first}\n"
    )

    _, blocks = detach_regions(text, ["first", "second"], Path(".envrc"))

    assert blocks == (
        f"# region: protostar {second}\n2\n# endregion: protostar {second}",
        f"# region: protostar {first}\n1\n# endregion: protostar {first}",
    )


@pytest.mark.parametrize(
    ("text", "block", "expected"),
    [
        ("", "B", "B\n"),
        ("a", "B", "a\n\nB\n"),
        ("a\n", "B", "a\n\nB\n"),
        ("a\r\n", "B", "a\r\n\r\nB\r\n"),
        ("a\n", "B\r\nC", "a\n\r\nB\r\nC\r\n"),
        ("a", "B\r\nC", "a\r\n\r\nB\r\nC\r\n"),
    ],
)
def test_attaching_a_region_follows_a_blank_line_and_the_file_s_newlines(
    text, block, expected
):
    assert attach_regions(text, [block]) == expected


@pytest.mark.parametrize(
    ("markers", "extensions"),
    [
        (
            ("//", ""),
            ".js .ts .jsx .tsx .c .cpp .h .hpp .java .go .rs .cs .swift .kt .scala",
        ),
        (("<!--", "-->"), ".html .htm .xml .svg .md"),
        (("/*", "*/"), ".css .scss .sass .less"),
        (("--", ""), ".sql .hs .lua"),
        (("#", ""), ".py .toml .yaml .sh .gitignore"),
    ],
)
def test_every_listed_extension_takes_its_comment_syntax(markers, extensions):
    for extension in extensions.split():
        assert get_comment_markers(Path(f"file{extension}")) == markers
        assert get_comment_markers(Path(f"FILE{extension.upper()}")) == markers


@pytest.mark.parametrize(
    ("content", "message", "hint"),
    [
        (
            "# region: protostar nothex\n",
            "Malformed append boundary.",
            "Repair the region markers.",
        ),
        (
            f"# region: protostar {TAG}\n# region: protostar {region_tag('b')}\n",
            "Duplicate, nested, or mismatched append boundaries.",
            "Give each region one unique matching begin/end pair.",
        ),
        (
            f"{_region(chr(10))}\n{_region(chr(10))}\n",
            "Duplicate, nested, or mismatched append boundaries.",
            "Give each region one unique matching begin/end pair.",
        ),
        (
            f"# region: protostar {TAG}\nx\n",
            "Unclosed append region.",
            "Restore the matching end marker.",
        ),
    ],
    ids=["malformed", "nested", "repeated", "unclosed"],
)
def test_broken_boundaries_are_refused(content, message, hint):
    with pytest.raises(ConfigurationError) as caught:
        append_marker_blocks(content, [], Path(".envrc"))

    assert str(caught.value) == message
    assert caught.value.hint == hint


@pytest.mark.parametrize(
    ("identities", "message"),
    [
        (("a", "a"), "Duplicate desired region identities."),
        # Two identities whose tags collide.
        (("r50007", "r102831"), "Duplicate desired region tags."),
    ],
)
def test_desired_regions_need_unique_identities_and_tags(identities, message):
    payloads = [AppendContribution(identity, "x") for identity in identities]

    with pytest.raises(ConfigurationError) as caught:
        append_marker_blocks("", payloads, Path(".envrc"))

    assert str(caught.value) == message
    assert caught.value.hint == "Use unique stable IDs."


def test_a_region_ending_in_a_newline_gets_no_second_one():
    tag = region_tag("a")
    result = append_marker_blocks("", [AppendContribution("a", "x\n")], Path(".envrc"))

    assert result.content == (
        f"# region: protostar {tag}\nx\n# endregion: protostar {tag}\n"
    )


def _framed(identity: str, content: str) -> str:
    tag = region_tag(identity)
    return f"# region: protostar {tag}\n{content}\n# endregion: protostar {tag}"


def test_a_deleted_owned_file_refuses_every_changed_region():
    baselines = {"a": _framed("a", "old"), "b": _framed("b", "old")}
    payloads = [AppendContribution("a", "new"), AppendContribution("b", "new")]

    result = append_marker_blocks(
        "", payloads, Path(".envrc"), baselines=baselines, missing_owned_file=True
    )

    assert result.content == ""
    assert result.baselines == baselines
    assert result.conflicts == tuple(
        MergeConflict(
            MergeLocation(".envrc", identity=identity), ConflictReason.DELETED_ANCESTOR
        )
        for identity in ("a", "b")
    )


def test_a_deleted_owned_file_keeps_unchanged_regions_deleted():
    baselines = {"a": _framed("a", "x"), "b": _framed("b", "y")}
    payloads = [AppendContribution("a", "x"), AppendContribution("b", "y")]

    def run(resolutions=None):
        return append_marker_blocks(
            "",
            payloads,
            Path(".envrc"),
            baselines=baselines,
            missing_owned_file=True,
            resolutions=resolutions or {},
        )

    result = run()

    assert result.content == ""
    assert result.baselines == baselines
    assert not result.conflicts
    assert result.preserved == tuple(
        MergeConflict(
            MergeLocation(".envrc", identity=identity),
            ConflictReason.PRESERVED,
            ConflictSides(baselines[identity], MISSING, baselines[identity], line=0),
        )
        for identity in ("a", "b")
    )
    first, second = result.preserved

    kept = run({first.id: ResolutionChoice.LOCAL})
    assert kept.content == ""
    assert kept.resolved == (first.settle({first.id: ResolutionChoice.LOCAL}),)
    assert kept.preserved == (second,)

    restored = run({first.id: ResolutionChoice.DESIRED})
    assert restored.content == baselines["a"] + "\n"
    assert restored.preserved == (second,)


def test_a_retracted_region_s_conflict_shows_what_is_removed():
    baselines = {"a": _framed("a", "x"), "b": _framed("b", "y")}
    edited = f"{_framed('a', 'edited')}\n\n{_framed('b', 'edited')}\n"

    result = append_marker_blocks(edited, [], Path(".envrc"), baselines=baselines)

    assert result.content == edited
    assert result.conflicts == tuple(
        MergeConflict(
            MergeLocation(".envrc", identity=identity),
            ConflictReason.RETRACTED,
            ConflictSides(
                baselines[identity], _framed(identity, "edited"), MISSING, line=0
            ),
        )
        for identity in ("a", "b")
    )


def test_each_retracted_region_is_decided_on_its_own():
    baselines = {
        "a": _framed("a", "x"),
        "b": _framed("b", "y"),
        "c": _framed("c", "z"),
    }
    text = (
        f"{_framed('a', 'edited')}\n\n{_framed('b', 'edited')}\n\n{_framed('c', 'z')}\n"
    )
    first, second = append_marker_blocks(
        text, [], Path(".envrc"), baselines=baselines
    ).conflicts

    # Keeping the first edit, leaving the second open, removes the third.
    result = append_marker_blocks(
        text,
        [],
        Path(".envrc"),
        baselines=baselines,
        resolutions={first.id: ResolutionChoice.LOCAL},
    )

    assert result.content == f"{_framed('a', 'edited')}\n\n{_framed('b', 'edited')}\n"
    assert result.baselines == {"b": baselines["b"]}
    assert result.conflicts == (second,)
    assert [conflict.id for conflict in result.resolved] == [first.id]


def test_a_region_already_gone_does_not_stop_the_next_retraction():
    baselines = {"a": _framed("a", "x"), "b": _framed("b", "y")}

    result = append_marker_blocks(
        f"keep\n\n{_framed('b', 'y')}\n", [], Path(".envrc"), baselines=baselines
    )

    assert result.content == "keep\n"
    assert result.baselines == {}
