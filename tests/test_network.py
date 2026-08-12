from urllib.error import URLError

import pytest

from protostar.errors import ConfigurationError
from protostar.network import fetch_remote_config


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
    with pytest.raises(ConfigurationError, match="Insecure protocol detected"):
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
    """Test that URLErrors are caught and wrapped in a ConfigurationError."""
    mocker.patch("urllib.request.urlopen", side_effect=URLError("Connection refused"))

    with pytest.raises(
        ConfigurationError, match="Failed to fetch remote configuration"
    ):
        fetch_remote_config("https://example.com/missing.toml")
