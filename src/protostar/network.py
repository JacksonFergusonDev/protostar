"""Network utilities for fetching remote configurations."""

import enum
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.error import URLError
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from urllib.request import OpenerDirector

from .errors import (
    NetworkFetchError,
    SecurityViolationError,
    TemplateResolutionError,
)
from .fs import ArchiveFormat, safe_extract_archive

__all__ = [
    "GitHost",
    "fetch_remote_config",
    "fetch_template_archive",
    "resolve_remote_template",
]

_BLOB_TRANSLATORS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"^https://github\.com/([^/]+)/([^/]+)/blob/(.+)$"),
        r"https://raw.githubusercontent.com/\1/\2/\3",
    ),
    (
        re.compile(r"^https://gitlab\.com/([^/]+)/([^/]+)/-/blob/(.+)$"),
        r"https://gitlab.com/\1/\2/-/raw/\3",
    ),
    (
        re.compile(r"^https://bitbucket\.org/([^/]+)/([^/]+)/src/(.+)$"),
        r"https://bitbucket.org/\1/\2/raw/\3",
    ),
    (
        re.compile(r"^https://codeberg\.org/([^/]+)/([^/]+)/src/(.+)$"),
        r"https://codeberg.org/\1/\2/raw/\3",
    ),
    (
        re.compile(r"^https://git\.sr\.ht/([^/]+)/([^/]+)/tree/(.+?)/item/(.+)$"),
        r"https://git.sr.ht/\1/\2/blob/\3/\4",
    ),
]

_ARCHIVE_TRANSLATORS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"^https://github\.com/([^/]+)/([^/]+)/?$"),
        r"https://github.com/\1/\2/archive/refs/heads/main.zip",
    ),
    (
        re.compile(r"^https://gitlab\.com/([^/]+)/([^/]+)/?$"),
        r"https://gitlab.com/\1/\2/-/archive/main/\2-main.zip",
    ),
    (
        re.compile(r"^https://bitbucket\.org/([^/]+)/([^/]+)/?$"),
        r"https://bitbucket.org/\1/\2/get/main.zip",
    ),
    (
        re.compile(r"^https://codeberg\.org/([^/]+)/([^/]+)/?$"),
        r"https://codeberg.org/\1/\2/archive/main.zip",
    ),
]

_opener: "OpenerDirector | None" = None


def _get_opener() -> "OpenerDirector":
    global _opener
    if _opener is None:
        import urllib.request

        _opener = urllib.request.build_opener()
    return _opener


class GitHost(enum.StrEnum):
    """Enumeration of supported remote Git hosting platforms."""

    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    CODEBERG = "codeberg"
    SOURCEHUT = "sourcehut"

    @classmethod
    def from_url(cls, url: str) -> "GitHost | None":
        """Identifies the Git host from a repository or file URL."""
        lower = url.lower()
        if "github.com" in lower or "raw.githubusercontent.com" in lower:
            return cls.GITHUB
        if "gitlab.com" in lower:
            return cls.GITLAB
        if "bitbucket.org" in lower:
            return cls.BITBUCKET
        if "codeberg.org" in lower:
            return cls.CODEBERG
        if "git.sr.ht" in lower:
            return cls.SOURCEHUT
        return None


def fetch_remote_config(url: str, timeout: int = 10) -> str:
    """Fetches a remote TOML configuration via HTTPS.

    Translates GitHub and GitLab blob URLs to their raw text equivalents.

    Args:
        url: The remote URL to fetch.
        timeout: Maximum request duration in seconds.

    Returns:
        The raw string content of the fetched configuration.

    Raises:
        NetworkFetchError: If the protocol is insecure or the network request fails.
    """
    if url.startswith("http://"):
        raise NetworkFetchError(
            url,
            message="Insecure protocol detected. Protostar requires HTTPS for remote configurations.",
        )
    if not url.startswith("https://"):
        raise NetworkFetchError(
            url,
            message="Remote configuration URLs must start with 'https://'.",
        )

    for pattern, replacement in _BLOB_TRANSLATORS:
        url = pattern.sub(replacement, url)

    try:
        with _get_opener().open(url, timeout=timeout) as response:
            return str(response.read(1024 * 1024).decode("utf-8"))
    except URLError as e:
        raise NetworkFetchError(
            url,
            original=e,
            message=f"Failed to fetch remote configuration from '{url}'.\nDetails: {e}",
        ) from e


def fetch_template_archive(url: str, dest_dir: Path, timeout: int = 10) -> Path:
    """Fetches and extracts a remote template archive (.zip, .tar.gz, .tgz, .tar).

    Args:
        url: The URL to the archive.
        dest_dir: The directory to extract the archive into.
        timeout: Network timeout in seconds.

    Returns:
        The path to the directory containing protostar.toml.

    Raises:
        NetworkFetchError: On network connectivity or protocol failure.
        TemplateResolutionError: On archive extraction or format failure.
    """
    if url.startswith("http://"):
        raise NetworkFetchError(
            url,
            message="Insecure protocol detected. Protostar requires HTTPS for remote configurations.",
        )
    if not url.startswith("https://"):
        raise NetworkFetchError(
            url,
            message="Remote configuration URLs must start with 'https://'.",
        )

    archive_format = ArchiveFormat.from_path(url)
    if archive_format is None:
        raise TemplateResolutionError(
            url,
            f"Unsupported archive format for '{url}'. Expected .zip, .tar.gz, .tgz, or .tar.",
        )

    try:
        with (
            _get_opener().open(url, timeout=timeout) as response,
            tempfile.NamedTemporaryFile(delete=False) as tmp_file,
        ):
            tmp_file.write(response.read())
            tmp_path = Path(tmp_file.name)
    except URLError as e:
        raise NetworkFetchError(
            url,
            original=e,
            message=f"Failed to fetch archive from '{url}'.\nDetails: {e}",
        ) from e

    try:
        safe_extract_archive(tmp_path, dest_dir, archive_format=archive_format)
    except (SecurityViolationError, TemplateResolutionError):
        raise
    except Exception as e:
        raise TemplateResolutionError(
            url,
            f"Failed to extract archive from '{url}'.\nDetails: {e}",
        ) from e
    finally:
        tmp_path.unlink(missing_ok=True)

    # Find the directory containing protostar.toml
    for path in dest_dir.rglob("protostar.toml"):
        if path.is_file():
            return path.parent

    raise TemplateResolutionError(
        url, f"No protostar.toml found in archive extracted from '{url}'."
    )


@dataclass(frozen=True)
class RemoteTemplateSource:
    """Canonical download locator and immutable revision when recognizable."""

    locator: str
    revision: str | None = None


def resolve_remote_source(url: str) -> RemoteTemplateSource:
    """Normalizes supported blob/repository sources without fetching bytes."""
    parsed = urlsplit(url)
    if parsed.username is not None or parsed.password is not None or parsed.query:
        from .errors import ConfigurationError

        raise ConfigurationError(
            "Template source URLs cannot contain credentials or query parameters.",
            hint="Select a credential-free canonical HTTPS template URL; provenance must not persist secrets.",
        )
    locator = url
    for pattern, replacement in _BLOB_TRANSLATORS:
        locator = pattern.sub(replacement, locator)
    for pattern, replacement in _ARCHIVE_TRANSLATORS:
        locator = pattern.sub(replacement, locator)
    revision_match = re.search(
        r"/([0-9a-f]{40}|[0-9a-f]{64})(?:/|\.tar\.gz|\.zip|$)", locator
    )
    revision = revision_match.group(1) if revision_match else None
    return RemoteTemplateSource(locator, revision)


def resolve_remote_template(url: str, temp_workspace: Path, timeout: int = 10) -> Path:
    """Resolves a remote template URL, downloading and extracting it if necessary.

    Args:
        url: The URL pointing to a raw TOML file or a repository archive.
        temp_workspace: A temporary directory to extract into.
        timeout: Network timeout in seconds.

    Returns:
        The path to the directory containing the resolved protostar.toml.
    """
    archive_url = resolve_remote_source(url).locator

    if ArchiveFormat.from_path(archive_url) is not None:
        return fetch_template_archive(archive_url, temp_workspace, timeout=timeout)

    # Otherwise it's treated as a raw file URL.
    raw_content = fetch_remote_config(archive_url, timeout=timeout)
    toml_path = temp_workspace / "protostar.toml"
    toml_path.write_text(raw_content, encoding="utf-8")
    return temp_workspace


@dataclass(frozen=True)
class AcquiredTemplate:
    """One in-memory source revision with its file payloads."""

    template_bytes: bytes
    files: dict[str, str]


def acquire_inspection_source(url: str) -> AcquiredTemplate:
    """Acquires raw or archived template sources without filesystem writes.

    Validates every archive member before reading template data; links and
    special nodes are never accepted as template inputs.
    """
    import io
    import stat
    import tarfile
    import zipfile
    from pathlib import PurePosixPath, PureWindowsPath

    source = resolve_remote_source(url)
    if not source.locator.startswith("https://"):
        raise NetworkFetchError(url, message="Remote templates require HTTPS.")
    fmt = ArchiveFormat.from_path(source.locator)
    if fmt is None:
        return AcquiredTemplate(fetch_remote_config(source.locator).encode(), {})
    try:
        with _get_opener().open(source.locator, timeout=10) as response:
            payload = response.read()
    except URLError as error:
        raise NetworkFetchError(url, original=error) from error

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
                        if name in files:
                            raise SecurityViolationError(
                                f"Duplicate archive member: {name}"
                            )
                        files[name] = archive.read(member)
        else:
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as tar_archive:
                for tar_member in tar_archive:
                    name = validate(tar_member.name)
                    if tar_member.isdir():
                        continue
                    if not tar_member.isfile():
                        raise SecurityViolationError(
                            f"Unsupported archive member: {name}"
                        )
                    content = tar_archive.extractfile(tar_member)
                    if content is not None:
                        if name in files:
                            raise SecurityViolationError(
                                f"Duplicate archive member: {name}"
                            )
                        files[name] = content.read()
    except (zipfile.BadZipFile, tarfile.TarError, OSError) as error:
        raise TemplateResolutionError(url, "Cannot read template archive.") from error
    roots = sorted(
        name for name in files if PurePosixPath(name).name == "protostar.toml"
    )
    if len(roots) != 1:
        raise TemplateResolutionError(
            url, "Archive must contain exactly one protostar.toml."
        )
    prefix = str(PurePosixPath(roots[0]).parent / "template") + "/"
    return AcquiredTemplate(
        files[roots[0]],
        {
            name[len(prefix) :]: content.decode("utf-8")
            for name, content in sorted(files.items())
            if name.startswith(prefix)
            and not {".DS_Store", "__pycache__"}.intersection(PurePosixPath(name).parts)
        },
    )
