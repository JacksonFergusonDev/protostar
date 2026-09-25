"""Remote template sources: where they live, which revisions they have, and their bytes.

A template in a forge repository is identified by its repository and the path
of the template inside it. Which revision a project applies is a separate
fact: a ref (tag, branch, or commit) the project chose, and the commit that
ref named when it was applied. Every revision is downloaded by its commit, so
the same recorded commit always yields the same bytes.
"""

import enum
import io
import re
import stat
import tarfile
import zipfile
from dataclasses import dataclass, replace
from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING
from urllib.error import URLError
from urllib.parse import urlsplit

from packaging.version import InvalidVersion, Version

if TYPE_CHECKING:
    from urllib.request import OpenerDirector

from .errors import (
    ConfigurationError,
    NetworkFetchError,
    SecurityViolationError,
    TemplateEncodingError,
    TemplateRefNotFoundError,
    TemplateResolutionError,
)
from .fs import ArchiveFormat

__all__ = [
    "AcquiredTemplate",
    "GitHost",
    "RefKind",
    "RefListing",
    "RemoteRequest",
    "RemoteSource",
    "RemoteTemplate",
    "ResolvedRef",
    "acquire_remote",
    "fetch_remote_template",
    "list_refs",
    "parse_ref_advertisement",
    "parse_remote_url",
]

_TIMEOUT = 10
_MAX_RAW_TEMPLATE = 1024 * 1024
_MAX_ADVERTISEMENT = 16 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")

_opener: "OpenerDirector | None" = None


def _get_opener() -> "OpenerDirector":
    global _opener
    if _opener is None:
        import urllib.request

        _opener = urllib.request.build_opener()
    return _opener


class GitHost(enum.StrEnum):
    """Supported Git forges, whose repositories have versioned templates."""

    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    CODEBERG = "codeberg"
    SOURCEHUT = "sourcehut"

    @property
    def domain(self) -> str:
        """The forge's web domain."""
        return _DOMAINS[self]

    @classmethod
    def from_domain(cls, domain: str) -> "GitHost | None":
        """Returns the forge serving a web domain, or None for any other host."""
        return next((host for host in cls if host.domain == domain), None)


_DOMAINS = {
    GitHost.GITHUB: "github.com",
    GitHost.GITLAB: "gitlab.com",
    GitHost.BITBUCKET: "bitbucket.org",
    GitHost.CODEBERG: "codeberg.org",
    GitHost.SOURCEHUT: "git.sr.ht",
}


@dataclass(frozen=True)
class RemoteSource:
    """Where a remote template lives, independent of its revision.

    Attributes:
        locator: The canonical repository URL for a forge; otherwise the exact
            URL of a raw ``protostar.toml`` or template archive.
        host: The forge, or None for a plain URL, which has no revisions.
        path: The template's directory, or its single ``.toml`` file, inside
            the repository; empty for the repository root.
    """

    locator: str
    host: GitHost | None = None
    path: str = ""

    @property
    def versioned(self) -> bool:
        """Whether the source has revisions to choose between."""
        return self.host is not None

    @property
    def refs_url(self) -> str:
        """The Git smart-HTTP endpoint that lists the repository's refs."""
        suffix = "" if self.host is GitHost.SOURCEHUT else ".git"
        return f"{self.locator}{suffix}/info/refs?service=git-upload-pack"

    def download_url(self, revision: str | None) -> str:
        """Returns the URL of the template's bytes at one commit.

        Args:
            revision: A full commit SHA; ignored for a plain URL.
        """
        if self.host is None or revision is None:
            return self.locator
        base, path = self.locator, self.path
        if path.endswith(".toml"):
            return {
                GitHost.GITHUB: f"https://raw.githubusercontent.com/"
                f"{urlsplit(base).path.strip('/')}/{revision}/{path}",
                GitHost.GITLAB: f"{base}/-/raw/{revision}/{path}",
                GitHost.BITBUCKET: f"{base}/raw/{revision}/{path}",
                GitHost.CODEBERG: f"{base}/raw/commit/{revision}/{path}",
                GitHost.SOURCEHUT: f"{base}/blob/{revision}/{path}",
            }[self.host]
        name = base.rsplit("/", 1)[1]
        return {
            GitHost.GITHUB: f"{base}/archive/{revision}.zip",
            GitHost.GITLAB: f"{base}/-/archive/{revision}/{name}-{revision}.zip",
            GitHost.BITBUCKET: f"{base}/get/{revision}.zip",
            GitHost.CODEBERG: f"{base}/archive/{revision}.zip",
            GitHost.SOURCEHUT: f"{base}/archive/{revision}.tar.gz",
        }[self.host]


class RefKind(enum.StrEnum):
    """What a ref names in a repository."""

    TAG = "tag"
    BRANCH = "branch"
    COMMIT = "commit"


@dataclass(frozen=True)
class ResolvedRef:
    """A ref and the commit it names."""

    name: str
    kind: RefKind
    revision: str


def _release(name: str) -> Version | None:
    try:
        return Version(name)
    except InvalidVersion:
        return None


@dataclass(frozen=True)
class RefListing:
    """A repository's tags and branches, each with the commit it names.

    Attributes:
        tags: Tag names and their commits, with annotated tags peeled.
        branches: Branch names and their commits.
        default_branch: The branch the repository's HEAD names, if advertised.
    """

    tags: tuple[tuple[str, str], ...] = ()
    branches: tuple[tuple[str, str], ...] = ()
    default_branch: str | None = None

    def releases(self, *, prereleases: bool = False) -> tuple[str, ...]:
        """Returns the tags that are PEP 440 versions, newest first.

        Args:
            prereleases: Include pre- and development releases.
        """
        found = [
            (version, name)
            for name, _ in self.tags
            if (version := _release(name)) is not None
            and (prereleases or not version.is_prerelease)
        ]
        return tuple(name for _, name in sorted(found, reverse=True))

    def latest(self, ref: str | None = None) -> str | None:
        """Returns the newest release, if any.

        Args:
            ref: The release a project is on; prereleases are offered only
                while it is one.
        """
        current = _release(ref) if ref else None
        prereleases = current is not None and current.is_prerelease
        return next(iter(self.releases(prereleases=prereleases)), None)

    def newer(self, ref: str) -> str | None:
        """Returns the newest release after the release ``ref`` names, if any."""
        current = _release(ref)
        newest = self.latest(ref)
        return newest if current and newest and Version(newest) > current else None

    def kind(self, ref: str) -> RefKind | None:
        """Returns what ``ref`` names, or None when it names nothing."""
        if ref in dict(self.tags):
            return RefKind.TAG
        if ref in dict(self.branches):
            return RefKind.BRANCH
        return RefKind.COMMIT if _SHA.fullmatch(ref) else None

    def resolve(self, ref: str, target: str) -> ResolvedRef:
        """Resolves a tag, branch, or full commit SHA to its commit.

        Tags win over branches of the same name, as they do in Git.

        Args:
            ref: The ref to resolve.
            target: The repository, for the error.

        Raises:
            TemplateRefNotFoundError: If the repository has no such ref.
        """
        kind = self.kind(ref)
        if kind is RefKind.TAG:
            return ResolvedRef(ref, kind, dict(self.tags)[ref])
        if kind is RefKind.BRANCH:
            return ResolvedRef(ref, kind, dict(self.branches)[ref])
        if kind is RefKind.COMMIT:
            return ResolvedRef(ref, kind, ref)
        raise TemplateRefNotFoundError(target, ref, self.releases())

    def default(self, target: str) -> ResolvedRef:
        """Resolves the ref a source that names none starts on.

        That is the newest release tag, or the default branch when the
        repository has no releases.

        Raises:
            TemplateResolutionError: If the repository has neither.
        """
        releases = self.releases()
        if releases:
            return self.resolve(releases[0], target)
        if self.default_branch is not None:
            return self.resolve(self.default_branch, target)
        raise TemplateResolutionError(
            target,
            "The repository has no release tags and advertises no default branch.",
            hint="Name a tag, branch, or commit in the template URL.",
        )

    def split(self, ref_and_path: str, target: str) -> tuple[str, str]:
        """Splits ``<ref>/<path>`` from a web URL at the longest matching ref.

        A branch name can contain slashes, so only the repository's own refs
        can tell where the ref ends.

        Raises:
            TemplateRefNotFoundError: If no ref of the repository matches.
        """
        names = [name for name, _ in (*self.tags, *self.branches)]
        first = ref_and_path.split("/", 1)[0]
        if _SHA.fullmatch(first):
            names.append(first)
        matches = [
            name
            for name in names
            if ref_and_path == name or ref_and_path.startswith(f"{name}/")
        ]
        if not matches:
            raise TemplateRefNotFoundError(target, first, self.releases())
        ref = max(matches, key=len)
        return ref, ref_and_path[len(ref) :].strip("/")


def parse_ref_advertisement(payload: bytes) -> RefListing:
    """Parses a Git smart-HTTP ref advertisement (``info/refs``).

    Args:
        payload: The response body, in pkt-line framing.

    Raises:
        ValueError: If the payload is not a ref advertisement.
    """
    refs: dict[str, str] = {}
    peeled: dict[str, str] = {}
    default_branch = None
    position = 0
    while position < len(payload):
        size = int(payload[position : position + 4], 16)
        if size == 0:
            position += 4
            continue
        if size < 4 or position + size > len(payload):
            raise ValueError("truncated pkt-line")
        line = payload[position + 4 : position + size].decode().rstrip("\n")
        position += size
        if line.startswith("#"):
            continue
        line, _, capabilities = line.partition("\0")
        for capability in capabilities.split():
            if capability.startswith("symref=HEAD:refs/heads/"):
                default_branch = capability.removeprefix("symref=HEAD:refs/heads/")
        revision, _, name = line.partition(" ")
        if not _SHA.fullmatch(revision) or not name:
            raise ValueError("malformed ref line")
        if name.endswith("^{}"):
            peeled[name.removesuffix("^{}")] = revision
        else:
            refs[name] = revision

    def named(prefix: str) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                (name.removeprefix(prefix), peeled.get(name, revision))
                for name, revision in refs.items()
                if name.startswith(prefix)
            )
        )

    return RefListing(named("refs/tags/"), named("refs/heads/"), default_branch)


def list_refs(source: RemoteSource) -> RefListing:
    """Lists a forge repository's tags and branches over Git smart HTTP.

    One read-only HTTPS request; no ``git`` process and no forge API.

    Raises:
        NetworkFetchError: If the request fails or the answer is not a ref
            advertisement.
    """
    try:
        with _get_opener().open(source.refs_url, timeout=_TIMEOUT) as response:
            payload = response.read(_MAX_ADVERTISEMENT)
    except URLError as error:
        raise NetworkFetchError(
            source.locator,
            original=error,
            message=f"Cannot list the revisions of '{source.locator}'.",
        ) from error
    try:
        return parse_ref_advertisement(payload)
    except (ValueError, UnicodeError) as error:
        raise NetworkFetchError(
            source.locator,
            message=f"'{source.locator}' did not answer as a Git repository.",
            hint="Check that the URL names a public Git repository.",
        ) from error


@dataclass(frozen=True)
class RemoteRequest:
    """A remote template URL as given: its source, and the revision it names.

    Attributes:
        source: Where the template lives.
        ref: The ref the URL names exactly, or None.
        ref_and_path: A ``<ref>/<path>`` tail whose split depends on the
            repository's refs, or None.
    """

    source: RemoteSource
    ref: str | None = None
    ref_and_path: str | None = None

    def select(self, listing: RefListing) -> tuple[RemoteSource, str | None]:
        """Returns the source with its template path, and the named ref."""
        if self.ref_and_path is None:
            return self.source, self.ref
        ref, path = listing.split(self.ref_and_path, self.source.locator)
        return replace(self.source, path=template_path(path)), ref


def template_path(path: str) -> str:
    """Normalizes a template's path inside its repository.

    A path to a ``protostar.toml`` names its directory, so the template's
    ``template/`` files come with it.

    Raises:
        ConfigurationError: If the path is unsafe.
    """
    path = path.strip("/")
    parts = path.split("/") if path else []
    if any(part in {"", ".", ".."} for part in parts) or any(
        character in path for character in ("\\", "\x00")
    ):
        raise ConfigurationError(
            f"Unsafe template path '{path}'.",
            hint="Name the template's directory inside the repository.",
        )
    if parts and parts[-1] == "protostar.toml":
        parts.pop()
    return "/".join(parts)


def _unsupported(url: str) -> ConfigurationError:
    return ConfigurationError(
        f"Unrecognized repository URL '{url}'.",
        hint="Use the repository URL, optionally followed by a tree, blob, or "
        "archive path naming a tag, branch, or commit.",
    )


def _archive_ref(name: str) -> str:
    for extension in (".zip", ".tar.gz", ".tgz", ".tar"):
        if name.endswith(extension):
            return name.removesuffix(extension)
    return name


def _full_ref(name: str) -> str:
    for prefix in ("refs/heads/", "refs/tags/"):
        name = name.removeprefix(prefix)
    return name


def _route(
    url: str, host: GitHost, source: RemoteSource, tail: list[str]
) -> RemoteRequest:
    kind, rest = tail[0], "/".join(tail[1:])
    if not rest:
        raise _unsupported(url)
    if host is GitHost.GITHUB and kind in {"tree", "blob"}:
        return RemoteRequest(source, ref_and_path=_full_ref(rest))
    if host is GitHost.GITHUB and kind == "archive":
        return RemoteRequest(source, _full_ref(_archive_ref(rest)))
    if host is GitHost.GITLAB and kind in {"tree", "blob", "raw"}:
        return RemoteRequest(source, ref_and_path=rest)
    if host is GitHost.GITLAB and kind == "archive" and len(tail) > 2:
        return RemoteRequest(source, "/".join(tail[1:-1]))
    if host is GitHost.BITBUCKET and kind in {"src", "raw"}:
        return RemoteRequest(source, ref_and_path=rest)
    if host is GitHost.BITBUCKET and kind == "get":
        return RemoteRequest(source, _archive_ref(rest))
    if (
        host is GitHost.CODEBERG
        and kind in {"src", "raw"}
        and tail[1] in {"branch", "tag", "commit"}
        and len(tail) > 2
    ):
        return RemoteRequest(source, ref_and_path="/".join(tail[2:]))
    if host is GitHost.CODEBERG and kind == "archive":
        return RemoteRequest(source, _archive_ref(rest))
    if host is GitHost.SOURCEHUT and kind == "tree":
        ref, _, path = rest.partition("/item/")
        return RemoteRequest(replace(source, path=template_path(path)), ref)
    if host is GitHost.SOURCEHUT and kind == "blob":
        return RemoteRequest(source, ref_and_path=rest)
    if host is GitHost.SOURCEHUT and kind == "archive":
        return RemoteRequest(source, _archive_ref(rest))
    raise _unsupported(url)


def parse_remote_url(url: str) -> RemoteRequest:
    """Parses a template URL into its source and the revision it names.

    Forge web, raw, and archive URLs all name a repository, optionally a
    ref, and optionally a path inside the repository. Any other HTTPS URL
    is a plain source with no revisions.

    Raises:
        NetworkFetchError: If the URL is not HTTPS.
        ConfigurationError: If the URL carries credentials or a query, or is a
            forge URL of an unrecognized form.
    """
    if not url.startswith("https://"):
        raise NetworkFetchError(url, message="Remote templates require HTTPS.")
    try:
        parts = urlsplit(url)
        domain = (parts.hostname or "").lower()
    except ValueError as error:
        raise _unsupported(url) from error
    if parts.username is not None or parts.password is not None or parts.query:
        raise ConfigurationError(
            "Template source URLs cannot contain credentials or query parameters.",
            hint="Select a credential-free canonical HTTPS template URL; provenance must not persist secrets.",
        )
    if not domain or parts.fragment or parts.port is not None:
        raise _unsupported(url)
    segments = [segment for segment in parts.path.split("/") if segment]
    if domain == "raw.githubusercontent.com":
        if len(segments) < 3:
            raise _unsupported(url)
        source = RemoteSource(
            f"https://github.com/{segments[0]}/{segments[1]}", GitHost.GITHUB
        )
        return RemoteRequest(source, ref_and_path=_full_ref("/".join(segments[2:])))
    host = GitHost.from_domain(domain)
    if host is None:
        return RemoteRequest(RemoteSource(url))
    if host is GitHost.GITLAB and "-" in segments:
        split = segments.index("-")
        repository, tail = segments[:split], segments[split + 1 :]
    elif host is GitHost.GITLAB:
        repository, tail = segments, []
    else:
        repository, tail = segments[:2], segments[2:]
    if len(repository) < 2:
        raise _unsupported(url)
    repository[-1] = repository[-1].removesuffix(".git")
    source = RemoteSource(f"https://{domain}/{'/'.join(repository)}", host)
    return _route(url, host, source, tail) if tail else RemoteRequest(source)


@dataclass(frozen=True)
class AcquiredTemplate:
    """One in-memory template revision with its file payloads."""

    template_bytes: bytes
    files: dict[str, str]


def _download(url: str, limit: int | None = None) -> bytes:
    try:
        with _get_opener().open(url, timeout=_TIMEOUT) as response:
            return bytes(response.read(limit) if limit else response.read())
    except URLError as error:
        raise NetworkFetchError(url, original=error) from error


def _read_archive(payload: bytes, fmt: ArchiveFormat, url: str) -> dict[str, bytes]:
    """Reads every regular file of an archive, rejecting unsafe members."""
    files: dict[str, bytes] = {}

    def validate(name: str) -> str:
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or PureWindowsPath(name).drive
            or "\\" in name
        ):
            raise SecurityViolationError(f"Unsafe archive member: {name}")
        return path.as_posix()

    def add(name: str, content: bytes) -> None:
        if name in files:
            raise SecurityViolationError(f"Duplicate archive member: {name}")
        files[name] = content

    try:
        if fmt is ArchiveFormat.ZIP:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                for member in archive.infolist():
                    name = validate(member.filename)
                    mode = member.external_attr >> 16
                    if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                        raise SecurityViolationError(
                            f"Unsupported archive member: {name}"
                        )
                    if not member.is_dir():
                        add(name, archive.read(member))
        else:
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as tar_archive:
                for tar_member in tar_archive:
                    name = validate(tar_member.name)
                    if tar_member.isdir() or tar_member.type == tarfile.XGLTYPE:
                        continue
                    if not tar_member.isfile():
                        raise SecurityViolationError(
                            f"Unsupported archive member: {name}"
                        )
                    content = tar_archive.extractfile(tar_member)
                    if content is not None:
                        add(name, content.read())
    except (zipfile.BadZipFile, tarfile.TarError, OSError) as error:
        raise TemplateResolutionError(url, "Cannot read template archive.") from error
    return files


def _template_root(
    files: dict[str, bytes], source: RemoteSource, url: str
) -> PurePosixPath:
    """Finds the ``protostar.toml`` an archive's template is rooted at."""
    if source.host is None:
        roots = sorted(
            name for name in files if PurePosixPath(name).name == "protostar.toml"
        )
        if len(roots) != 1:
            raise TemplateResolutionError(
                url, "Archive must contain exactly one protostar.toml."
            )
        return PurePosixPath(roots[0])
    # A forge archive holds the whole repository under one top-level directory.
    tops = {name.split("/", 1)[0] for name in files}
    if len(tops) != 1:
        raise TemplateResolutionError(url, "Cannot read template archive.")
    root = PurePosixPath(tops.pop(), source.path, "protostar.toml")
    if str(root) not in files:
        raise TemplateResolutionError(
            source.locator,
            f"No protostar.toml in '{source.path or '/'}' of the repository.",
            hint="Name the template's directory in the URL, as in "
            ".../tree/<ref>/<directory>.",
        )
    return root


def acquire_remote(source: RemoteSource, revision: str | None) -> AcquiredTemplate:
    """Downloads a template at one commit, entirely in memory.

    Validates every archive member before reading template data; links and
    special nodes are never accepted as template inputs.

    Args:
        source: Where the template lives.
        revision: The commit to download; None only for a plain URL.

    Raises:
        NetworkFetchError: If the download fails.
        TemplateResolutionError: If the archive is unreadable or holds no
            template where the source says.
        TemplateEncodingError: If a template file is not UTF-8 text.
    """
    url = source.download_url(revision)
    fmt = ArchiveFormat.from_path(url)
    if fmt is None:
        payload = _download(url, _MAX_RAW_TEMPLATE)
        try:
            payload.decode()
        except UnicodeError as error:
            raise TemplateEncodingError(source.locator, "protostar.toml") from error
        return AcquiredTemplate(payload, {})
    files = _read_archive(_download(url), fmt, url)
    root = _template_root(files, source, url)
    prefix = f"{root.parent / 'template'}/"
    template: dict[str, str] = {}
    for name, content in sorted(files.items()):
        if not name.startswith(prefix) or {".DS_Store", "__pycache__"}.intersection(
            PurePosixPath(name).parts
        ):
            continue
        try:
            template[name[len(prefix) :]] = content.decode()
        except UnicodeError as error:
            raise TemplateEncodingError(
                source.locator, f"template/{name[len(prefix) :]}"
            ) from error
    try:
        files[str(root)].decode()
    except UnicodeError as error:
        raise TemplateEncodingError(source.locator, root.name) from error
    return AcquiredTemplate(files[str(root)], template)


@dataclass(frozen=True)
class RemoteTemplate:
    """A remote template acquired at one revision.

    Attributes:
        source: Where the template lives, with its path inside the repository.
        acquired: The template's bytes at ``revision``.
        ref: The ref applied, or None for a plain URL.
        revision: The commit ``ref`` named, or None for a plain URL.
    """

    source: RemoteSource
    acquired: AcquiredTemplate
    ref: str | None = None
    revision: str | None = None


def fetch_remote_template(url: str) -> RemoteTemplate:
    """Acquires the template a URL names.

    A URL that names no ref starts on the repository's newest release.

    Raises:
        NetworkFetchError: If the URL is not HTTPS or a request fails.
        ConfigurationError: If the URL is unsafe or unrecognized.
        TemplateRefNotFoundError: If the repository has no such ref.
        TemplateResolutionError: If no template is found where the URL says.
    """
    request = parse_remote_url(url)
    if not request.source.versioned:
        return RemoteTemplate(request.source, acquire_remote(request.source, None))
    listing = list_refs(request.source)
    source, ref = request.select(listing)
    resolved = (
        listing.resolve(ref, source.locator) if ref else listing.default(source.locator)
    )
    return RemoteTemplate(
        source,
        acquire_remote(source, resolved.revision),
        resolved.name,
        resolved.revision,
    )
