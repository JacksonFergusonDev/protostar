import io
import zipfile

import pytest

from protostar.errors import (
    ConfigurationError,
    NetworkFetchError,
    SecurityViolationError,
    TemplateEncodingError,
    TemplateRefNotFoundError,
    TemplateResolutionError,
)
from protostar.fs import ArchiveFormat
from protostar.network import (
    AcquiredTemplate,
    GitHost,
    RefKind,
    RefListing,
    RemoteRequest,
    RemoteSource,
    ResolvedRef,
    acquire_remote,
    fetch_remote_template,
    list_refs,
    parse_ref_advertisement,
    parse_remote_url,
    template_path,
)

GITHUB = RemoteSource("https://github.com/org/tmpl", GitHost.GITHUB)
SHA = "a" * 40
TEMPLATE = "[env]\nruff = true\n"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/org/tmpl", RemoteRequest(GITHUB)),
        ("https://github.com/org/tmpl/", RemoteRequest(GITHUB)),
        ("https://github.com/org/tmpl.git", RemoteRequest(GITHUB)),
        ("https://GitHub.com/org/tmpl", RemoteRequest(GITHUB)),
        (
            "https://github.com/org/tmpl/tree/release/v2/api",
            RemoteRequest(GITHUB, ref_and_path="release/v2/api"),
        ),
        (
            "https://github.com/org/tmpl/blob/v1.2.0/protostar.toml",
            RemoteRequest(GITHUB, ref_and_path="v1.2.0/protostar.toml"),
        ),
        (
            "https://github.com/org/tmpl/archive/refs/tags/v1.2.0.zip",
            RemoteRequest(GITHUB, "v1.2.0"),
        ),
        (
            "https://github.com/org/tmpl/archive/refs/heads/main.zip",
            RemoteRequest(GITHUB, "main"),
        ),
        (
            f"https://github.com/org/tmpl/archive/{SHA}.tar.gz",
            RemoteRequest(GITHUB, SHA),
        ),
        (
            "https://raw.githubusercontent.com/org/tmpl/refs/heads/main/api.toml",
            RemoteRequest(GITHUB, ref_and_path="main/api.toml"),
        ),
        (
            "https://gitlab.com/group/sub/proj",
            RemoteRequest(
                RemoteSource("https://gitlab.com/group/sub/proj", GitHost.GITLAB)
            ),
        ),
        (
            "https://gitlab.com/group/proj/-/tree/v1.0.0/api",
            RemoteRequest(
                RemoteSource("https://gitlab.com/group/proj", GitHost.GITLAB),
                ref_and_path="v1.0.0/api",
            ),
        ),
        (
            "https://gitlab.com/group/proj/-/archive/release/v2/proj-release-v2.zip",
            RemoteRequest(
                RemoteSource("https://gitlab.com/group/proj", GitHost.GITLAB),
                "release/v2",
            ),
        ),
        (
            "https://bitbucket.org/org/tmpl/src/main/api.toml",
            RemoteRequest(
                RemoteSource("https://bitbucket.org/org/tmpl", GitHost.BITBUCKET),
                ref_and_path="main/api.toml",
            ),
        ),
        (
            "https://bitbucket.org/org/tmpl/get/v1.2.0.zip",
            RemoteRequest(
                RemoteSource("https://bitbucket.org/org/tmpl", GitHost.BITBUCKET),
                "v1.2.0",
            ),
        ),
        (
            "https://codeberg.org/org/tmpl/src/tag/v1.2.0/api.toml",
            RemoteRequest(
                RemoteSource("https://codeberg.org/org/tmpl", GitHost.CODEBERG),
                ref_and_path="v1.2.0/api.toml",
            ),
        ),
        (
            "https://codeberg.org/org/tmpl/archive/v1.2.0.zip",
            RemoteRequest(
                RemoteSource("https://codeberg.org/org/tmpl", GitHost.CODEBERG),
                "v1.2.0",
            ),
        ),
        (
            "https://git.sr.ht/~user/tmpl/tree/v1.2.0/item/templates/api",
            RemoteRequest(
                RemoteSource(
                    "https://git.sr.ht/~user/tmpl", GitHost.SOURCEHUT, "templates/api"
                ),
                "v1.2.0",
            ),
        ),
        (
            "https://git.sr.ht/~user/tmpl/archive/v1.2.0.tar.gz",
            RemoteRequest(
                RemoteSource("https://git.sr.ht/~user/tmpl", GitHost.SOURCEHUT),
                "v1.2.0",
            ),
        ),
        (
            "https://example.com/templates/api.toml",
            RemoteRequest(RemoteSource("https://example.com/templates/api.toml")),
        ),
    ],
)
def test_template_urls_parse_into_repository_ref_and_path(url, expected):
    assert parse_remote_url(url) == expected


def test_only_forge_sources_are_versioned():
    assert GITHUB.versioned
    assert not RemoteSource("https://example.com/api.toml").versioned


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@github.com/org/tmpl",
        "https://github.com/org/tmpl?token=secret",
    ],
)
def test_urls_with_credentials_or_queries_are_rejected(url):
    with pytest.raises(ConfigurationError, match="credentials or query"):
        parse_remote_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/org",
        "https://github.com/org/tmpl/pulls/1",
        "https://github.com/org/tmpl/tree",
        "https://github.com/org/tmpl#readme",
    ],
)
def test_unrecognized_forge_urls_are_rejected(url):
    with pytest.raises(ConfigurationError, match="Unrecognized repository URL"):
        parse_remote_url(url)


@pytest.mark.parametrize("url", ["http://github.com/org/tmpl", "file:///etc/passwd"])
def test_non_https_urls_are_rejected(url):
    with pytest.raises(NetworkFetchError, match="require HTTPS"):
        parse_remote_url(url)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("", ""),
        ("/api/", "api"),
        ("protostar.toml", ""),
        ("templates/api/protostar.toml", "templates/api"),
        ("api.toml", "api.toml"),
    ],
)
def test_template_paths_name_the_template_directory(path, expected):
    assert template_path(path) == expected


@pytest.mark.parametrize("path", ["../escape", "a//b", "a/./b", "a\\b", "a\x00b"])
def test_unsafe_template_paths_are_rejected(path):
    with pytest.raises(ConfigurationError, match="Unsafe template path"):
        template_path(path)


@pytest.mark.parametrize(
    ("source", "archive", "raw"),
    [
        (
            GITHUB,
            f"https://github.com/org/tmpl/archive/{SHA}.zip",
            f"https://raw.githubusercontent.com/org/tmpl/{SHA}/api.toml",
        ),
        (
            RemoteSource("https://gitlab.com/g/proj", GitHost.GITLAB),
            f"https://gitlab.com/g/proj/-/archive/{SHA}/proj-{SHA}.zip",
            f"https://gitlab.com/g/proj/-/raw/{SHA}/api.toml",
        ),
        (
            RemoteSource("https://bitbucket.org/o/r", GitHost.BITBUCKET),
            f"https://bitbucket.org/o/r/get/{SHA}.zip",
            f"https://bitbucket.org/o/r/raw/{SHA}/api.toml",
        ),
        (
            RemoteSource("https://codeberg.org/o/r", GitHost.CODEBERG),
            f"https://codeberg.org/o/r/archive/{SHA}.zip",
            f"https://codeberg.org/o/r/raw/commit/{SHA}/api.toml",
        ),
        (
            RemoteSource("https://git.sr.ht/~u/r", GitHost.SOURCEHUT),
            f"https://git.sr.ht/~u/r/archive/{SHA}.tar.gz",
            f"https://git.sr.ht/~u/r/blob/{SHA}/api.toml",
        ),
    ],
)
def test_every_forge_downloads_by_commit(source, archive, raw):
    assert source.download_url(SHA) == archive
    from dataclasses import replace

    assert replace(source, path="api.toml").download_url(SHA) == raw


def test_refs_are_listed_over_git_smart_http():
    assert GITHUB.refs_url == (
        "https://github.com/org/tmpl.git/info/refs?service=git-upload-pack"
    )
    assert RemoteSource("https://git.sr.ht/~u/r", GitHost.SOURCEHUT).refs_url == (
        "https://git.sr.ht/~u/r/info/refs?service=git-upload-pack"
    )


def _pkt(text: str) -> bytes:
    return f"{len(text.encode()) + 4:04x}".encode() + text.encode()


def test_ref_advertisement_peels_annotated_tags_and_reads_the_default_branch():
    payload = (
        _pkt("# service=git-upload-pack\n")
        + b"0000"
        + _pkt(f"{'1' * 40} HEAD\0multi_ack symref=HEAD:refs/heads/trunk agent=x\n")
        + _pkt(f"{'1' * 40} refs/heads/trunk\n")
        + _pkt(f"{'2' * 40} refs/tags/v1.0.0\n")
        + _pkt(f"{'3' * 40} refs/tags/v1.0.0^{{}}\n")
        + _pkt(f"{'4' * 40} refs/tags/v1.1.0\n")
        + _pkt(f"{'5' * 40} refs/pull/1/head\n")
        + b"0000"
    )
    listing = parse_ref_advertisement(payload)
    assert listing == RefListing(
        (("v1.0.0", "3" * 40), ("v1.1.0", "4" * 40)),
        (("trunk", "1" * 40),),
        "trunk",
    )


@pytest.mark.parametrize(
    "payload",
    [b"<html>", b"0010not a ref\n", _pkt("nope refs/heads/main\n"), b"00ff"],
)
def test_malformed_ref_advertisements_are_rejected(payload):
    with pytest.raises(ValueError, match=r"pkt-line|ref line|invalid literal"):
        parse_ref_advertisement(payload)


LISTING = RefListing(
    tags=(
        ("v1.0.0", "1" * 40),
        ("v1.10.0", "2" * 40),
        ("v1.9.0", "3" * 40),
        ("v2.0.0rc1", "4" * 40),
        ("nightly", "5" * 40),
        ("release", "6" * 40),
    ),
    branches=(("main", "7" * 40), ("release", "8" * 40), ("release/v2", "9" * 40)),
    default_branch="main",
)


def test_releases_order_by_pep_440_not_by_name():
    assert LISTING.releases() == ("v1.10.0", "v1.9.0", "v1.0.0")
    assert LISTING.releases(prereleases=True)[0] == "v2.0.0rc1"


def test_newer_releases_skip_prereleases_unless_already_on_one():
    assert LISTING.newer("v1.9.0") == "v1.10.0"
    assert LISTING.newer("v1.10.0") is None
    assert LISTING.newer("v2.0.0a1") == "v2.0.0rc1"
    assert LISTING.newer("main") is None
    assert LISTING.latest() == "v1.10.0"
    assert LISTING.latest("v2.0.0a1") == "v2.0.0rc1"


def test_refs_resolve_tags_before_branches_and_accept_full_commits():
    assert LISTING.resolve("release", "repo").kind is RefKind.TAG
    assert LISTING.resolve("main", "repo").revision == "7" * 40
    assert LISTING.resolve("f" * 40, "repo").kind is RefKind.COMMIT
    assert LISTING.kind("gone") is None
    with pytest.raises(TemplateRefNotFoundError, match="'v9'") as error:
        LISTING.resolve("v9", "repo")
    assert "v1.10.0, v1.9.0, v1.0.0" in (error.value.hint or "")


def test_default_ref_is_the_newest_release_then_the_default_branch():
    assert LISTING.default("repo").name == "v1.10.0"
    trunk = RefListing(branches=(("trunk", "1" * 40),), default_branch="trunk")
    assert trunk.default("repo") == ResolvedRef("trunk", RefKind.BRANCH, "1" * 40)
    with pytest.raises(TemplateResolutionError, match="no release tags"):
        RefListing().default("repo")


def test_web_url_tails_split_at_the_longest_matching_ref():
    assert LISTING.split("release/v2/api", "repo") == ("release/v2", "api")
    assert LISTING.split("release/api", "repo") == ("release", "api")
    assert LISTING.split("main", "repo") == ("main", "")
    assert LISTING.split(f"{'f' * 40}/api", "repo") == ("f" * 40, "api")
    with pytest.raises(TemplateRefNotFoundError, match="'missing'"):
        LISTING.split("missing/api", "repo")


def test_bare_repository_url_starts_on_the_newest_release(forge):
    repo = forge.repository("https://github.com/org/tmpl")
    repo.commit({"protostar.toml": "version = '1'\n"}, tag="v1.0.0")
    newest = repo.commit(
        {"protostar.toml": TEMPLATE, "template/README.md": "hi\n"}, tag="v1.1.0"
    )
    repo.commit({"protostar.toml": "unreleased = true\n"}, branch="main")

    remote = fetch_remote_template("https://github.com/org/tmpl")

    assert (remote.ref, remote.revision) == ("v1.1.0", newest)
    assert remote.source == GITHUB
    assert remote.acquired.template_bytes == TEMPLATE.encode()
    assert remote.acquired.files == {"README.md": "hi\n"}


def test_repository_without_releases_starts_on_its_default_branch(forge):
    repo = forge.repository("https://codeberg.org/org/tmpl", default_branch="trunk")
    head = repo.commit({"protostar.toml": TEMPLATE}, branch="trunk")

    remote = fetch_remote_template("https://codeberg.org/org/tmpl")

    assert (remote.ref, remote.revision) == ("trunk", head)


def test_tree_url_selects_a_ref_with_slashes_and_a_nested_template(forge):
    repo = forge.repository("https://github.com/org/tmpl")
    revision = repo.commit(
        {
            "templates/api/protostar.toml": TEMPLATE,
            "templates/api/template/app.py": "print()\n",
            "templates/cli/protostar.toml": "other = true\n",
        },
        branch="release/v2",
    )

    remote = fetch_remote_template(
        "https://github.com/org/tmpl/tree/release/v2/templates/api"
    )

    assert remote.source.path == "templates/api"
    assert (remote.ref, remote.revision) == ("release/v2", revision)
    assert remote.acquired.files == {"app.py": "print()\n"}


def test_single_file_template_is_fetched_raw_at_its_commit(forge):
    repo = forge.repository("https://github.com/org/tmpl")
    revision = repo.commit({"api.toml": TEMPLATE}, tag="v1.0.0")

    remote = fetch_remote_template("https://github.com/org/tmpl/blob/v1.0.0/api.toml")

    assert remote.source.path == "api.toml"
    assert remote.acquired == AcquiredTemplate(TEMPLATE.encode(), {})
    assert forge.requests[-1] == (
        f"https://raw.githubusercontent.com/org/tmpl/{revision}/api.toml"
    )


def test_sourcehut_templates_arrive_as_tarballs(forge):
    repo = forge.repository("https://git.sr.ht/~user/tmpl")
    repo.commit({"protostar.toml": TEMPLATE, "template/a.txt": "a\n"}, tag="v1.0.0")

    remote = fetch_remote_template("https://git.sr.ht/~user/tmpl")

    assert remote.acquired.files == {"a.txt": "a\n"}


def test_a_path_without_a_template_is_reported(forge):
    repo = forge.repository("https://github.com/org/tmpl")
    repo.commit({"README.md": "no template\n"}, tag="v1.0.0")

    with pytest.raises(TemplateResolutionError, match=r"No protostar\.toml in '/'"):
        fetch_remote_template("https://github.com/org/tmpl")


def test_non_utf8_template_files_are_rejected(forge):
    repo = forge.repository("https://github.com/org/tmpl")
    repo.commit(
        {"protostar.toml": TEMPLATE, "template/logo.png": b"\x89PNG\xff"},
        tag="v1.0.0",
    )

    with pytest.raises(TemplateEncodingError, match=r"template/logo\.png"):
        fetch_remote_template("https://github.com/org/tmpl")


def test_plain_urls_are_fetched_as_given(forge):
    forge.plain["https://example.com/api.toml"] = TEMPLATE.encode()

    remote = fetch_remote_template("https://example.com/api.toml")

    assert (remote.ref, remote.revision) == (None, None)
    assert remote.acquired.template_bytes == TEMPLATE.encode()
    assert forge.requests == ["https://example.com/api.toml"]


def _zip(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_plain_archives_need_exactly_one_template(forge):
    forge.plain["https://example.com/t.zip"] = _zip(
        {"x/protostar.toml": TEMPLATE, "x/template/a.txt": "a\n"}
    )
    forge.plain["https://example.com/two.zip"] = _zip(
        {"a/protostar.toml": TEMPLATE, "b/protostar.toml": TEMPLATE}
    )

    assert fetch_remote_template("https://example.com/t.zip").acquired.files == {
        "a.txt": "a\n"
    }
    with pytest.raises(TemplateResolutionError, match=r"exactly one protostar\.toml"):
        fetch_remote_template("https://example.com/two.zip")


@pytest.mark.parametrize("member", ["../escape.txt", "/abs.txt", "C:/x.txt"])
def test_unsafe_archive_members_are_rejected_before_any_template_data(forge, member):
    forge.plain["https://example.com/t.zip"] = _zip(
        {"protostar.toml": TEMPLATE, member: "x"}
    )

    with pytest.raises(SecurityViolationError, match="Unsafe archive member"):
        acquire_remote(RemoteSource("https://example.com/t.zip"), None)


def test_ref_listing_failures_are_network_errors(forge):
    forge.offline = True
    with pytest.raises(NetworkFetchError, match="Cannot list the revisions"):
        list_refs(GITHUB)
    forge.offline = False
    forge.plain[GITHUB.refs_url] = b"<html>login</html>"
    with pytest.raises(NetworkFetchError, match="did not answer as a Git repository"):
        list_refs(GITHUB)


def test_unknown_ref_in_a_url_lists_the_releases(forge):
    repo = forge.repository("https://github.com/org/tmpl")
    repo.commit({"protostar.toml": TEMPLATE}, tag="v1.0.0")

    with pytest.raises(TemplateRefNotFoundError, match=r"'v9\.9\.9'"):
        fetch_remote_template(
            "https://github.com/org/tmpl/archive/refs/tags/v9.9.9.zip"
        )


def test_archive_formats_are_detected_from_urls():
    assert ArchiveFormat.from_path("https://example.com/file.zip") is ArchiveFormat.ZIP
    assert ArchiveFormat.from_path("https://x/f.tgz") is ArchiveFormat.TAR_GZ
    assert ArchiveFormat.from_path("https://example.com/file.toml") is None


def test_forges_are_recognized_by_domain():
    assert GitHost.from_domain("github.com") is GitHost.GITHUB
    assert GitHost.from_domain("git.sr.ht") is GitHost.SOURCEHUT
    assert GitHost.from_domain("example.com") is None
