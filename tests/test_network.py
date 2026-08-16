from pathlib import Path
from urllib.error import URLError

import pytest

from protostar.errors import (
    NetworkFetchError,
    TemplateResolutionError,
)
from protostar.network import (
    fetch_remote_config,
    fetch_template_archive,
    resolve_remote_template,
)


def test_fetch_remote_config_https_success(mocker):
    """Test successful fetching of an HTTPS URL."""
    mock_response = mocker.Mock()
    mock_response.read.return_value = b"[env]\nruff = true"
    mock_context_manager = mocker.Mock()
    mock_context_manager.__enter__ = mocker.Mock(return_value=mock_response)
    mock_context_manager.__exit__ = mocker.Mock(return_value=None)

    mocker.patch("urllib.request.urlopen", return_value=mock_context_manager)

    result = fetch_remote_config("https://example.com/config.toml")
    assert result == "[env]\nruff = true"


def test_fetch_remote_config_rejects_http():
    """Test that insecure HTTP URLs are explicitly rejected."""
    with pytest.raises(NetworkFetchError, match="Insecure protocol detected"):
        fetch_remote_config("http://example.com/config.toml")


def test_fetch_remote_config_github_translation(mocker):
    """Test that GitHub blob URLs are translated to raw."""
    mock_urlopen = mocker.patch("urllib.request.urlopen")

    # Mocking the context manager for urlopen
    mock_response = mocker.Mock()
    mock_response.read.return_value = b""
    mock_urlopen.return_value.__enter__.return_value = mock_response

    fetch_remote_config("https://github.com/user/repo/blob/main/protostar.toml")

    mock_urlopen.assert_called_once()
    called_url = mock_urlopen.call_args[0][0]
    assert (
        called_url == "https://raw.githubusercontent.com/user/repo/main/protostar.toml"
    )


def test_fetch_remote_config_gitlab_translation(mocker):
    """Test that GitLab blob URLs are translated to raw."""
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_response = mocker.Mock()
    mock_response.read.return_value = b""
    mock_urlopen.return_value.__enter__.return_value = mock_response

    fetch_remote_config("https://gitlab.com/user/repo/-/blob/main/protostar.toml")

    called_url = mock_urlopen.call_args[0][0]
    assert called_url == "https://gitlab.com/user/repo/-/raw/main/protostar.toml"


def test_fetch_remote_config_bitbucket_translation(mocker):
    """Test that Bitbucket source URLs are translated to raw."""
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_response = mocker.Mock()
    mock_response.read.return_value = b""
    mock_urlopen.return_value.__enter__.return_value = mock_response

    fetch_remote_config("https://bitbucket.org/user/repo/src/main/protostar.toml")

    called_url = mock_urlopen.call_args[0][0]
    assert called_url == "https://bitbucket.org/user/repo/raw/main/protostar.toml"


def test_fetch_remote_config_codeberg_translation(mocker):
    """Test that Codeberg source URLs are translated to raw."""
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_response = mocker.Mock()
    mock_response.read.return_value = b""
    mock_urlopen.return_value.__enter__.return_value = mock_response

    fetch_remote_config("https://codeberg.org/user/repo/src/branch/main/protostar.toml")

    called_url = mock_urlopen.call_args[0][0]
    assert called_url == "https://codeberg.org/user/repo/raw/branch/main/protostar.toml"


def test_fetch_remote_config_sourcehut_translation(mocker):
    """Test that Sourcehut tree URLs are translated to blob."""
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_response = mocker.Mock()
    mock_response.read.return_value = b""
    mock_urlopen.return_value.__enter__.return_value = mock_response

    fetch_remote_config("https://git.sr.ht/~user/repo/tree/master/item/protostar.toml")

    called_url = mock_urlopen.call_args[0][0]
    assert called_url == "https://git.sr.ht/~user/repo/blob/master/protostar.toml"


def test_fetch_remote_config_handles_url_error(mocker):
    """Test that URLErrors are caught and wrapped in a NetworkFetchError."""
    mocker.patch("urllib.request.urlopen", side_effect=URLError("Connection refused"))

    with pytest.raises(NetworkFetchError, match="Failed to fetch remote configuration"):
        fetch_remote_config("https://example.com/missing.toml")


def test_resolve_remote_template_github_archive_translation(mocker, tmp_path):
    """Test that GitHub repo URLs are translated to zip endpoints."""
    mock_fetch = mocker.patch("protostar.network.fetch_template_archive")
    mock_fetch.return_value = tmp_path

    result = resolve_remote_template("https://github.com/user/repo", tmp_path)

    mock_fetch.assert_called_once_with(
        "https://github.com/user/repo/archive/refs/heads/main.zip", tmp_path, timeout=10
    )
    assert result == tmp_path


def test_resolve_remote_template_gitlab_archive_translation(mocker, tmp_path):
    """Test that GitLab repo URLs are translated to zip endpoints."""
    mock_fetch = mocker.patch("protostar.network.fetch_template_archive")
    mock_fetch.return_value = tmp_path

    resolve_remote_template("https://gitlab.com/user/repo", tmp_path)

    mock_fetch.assert_called_once_with(
        "https://gitlab.com/user/repo/-/archive/main/repo-main.zip",
        tmp_path,
        timeout=10,
    )


def test_resolve_remote_template_raw_fallback(mocker, tmp_path):
    """Test that raw files are downloaded directly."""
    mock_fetch = mocker.patch("protostar.network.fetch_remote_config")
    mock_fetch.return_value = "[env]\nruff = true"

    result = resolve_remote_template("https://example.com/raw.toml", tmp_path)

    mock_fetch.assert_called_once_with("https://example.com/raw.toml", timeout=10)
    assert result == tmp_path
    assert (tmp_path / "protostar.toml").read_text() == "[env]\nruff = true"


def test_fetch_template_archive_zip_extraction(mocker, tmp_path):
    """Test downloading and extracting a zip archive."""
    import zipfile

    # Create a mock zip file in memory
    zip_path = tmp_path / "mock.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("repo-main/protostar.toml", "[env]\nruff = true")

    mock_response = mocker.Mock()
    mock_response.read.return_value = zip_path.read_bytes()
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    result = fetch_template_archive("https://example.com/archive.zip", dest_dir)

    # Result should be the directory containing protostar.toml
    assert result == dest_dir / "repo-main"
    assert (result / "protostar.toml").exists()


def test_fetch_template_archive_rejects_http():
    with pytest.raises(NetworkFetchError, match="Insecure protocol detected"):
        fetch_template_archive("http://example.com/archive.zip", Path("/tmp"))


def test_fetch_template_archive_handles_url_error(mocker, tmp_path):
    mocker.patch("urllib.request.urlopen", side_effect=URLError("Network down"))
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    with pytest.raises(NetworkFetchError, match="Failed to fetch archive"):
        fetch_template_archive("https://example.com/archive.zip", dest_dir)


def test_fetch_template_archive_unsupported_format(mocker, tmp_path):
    mock_response = mocker.Mock()
    mock_response.read.return_value = b"some data"
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    with pytest.raises(TemplateResolutionError, match="Unsupported archive format"):
        fetch_template_archive("https://example.com/archive.unknown", dest_dir)


def test_fetch_template_archive_missing_protostar_toml(mocker, tmp_path):
    import zipfile

    zip_path = tmp_path / "empty.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("repo-main/readme.md", "# Hello")

    mock_response = mocker.Mock()
    mock_response.read.return_value = zip_path.read_bytes()
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    with pytest.raises(TemplateResolutionError, match=r"No protostar\.toml found"):
        fetch_template_archive("https://example.com/archive.zip", dest_dir)
