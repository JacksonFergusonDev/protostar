import json
import urllib.error
from unittest.mock import MagicMock

import pytest

from protostar.registry import DEFAULT_REVISIONS, HookRegistry, RemoteHook


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset the registry cache before each test."""
    HookRegistry._cache = None


def test_get_revision_success(mocker):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "schema_version": 1,
            "hooks": {
                RemoteHook.PRE_COMMIT_HOOKS.value: "v9.9.9",
            },
        }
    ).encode("utf-8")

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    rev = HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert rev == "v9.9.9"

    # Should use default for missing hook in the JSON
    rev2 = HookRegistry.get_revision(RemoteHook.GITLEAKS)
    assert rev2 == DEFAULT_REVISIONS[RemoteHook.GITLEAKS]


def test_get_revision_fallback_on_url_error(mocker):
    mocker.patch(
        "urllib.request.urlopen", side_effect=urllib.error.URLError("test error")
    )

    rev = HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert rev == DEFAULT_REVISIONS[RemoteHook.PRE_COMMIT_HOOKS]


def test_get_revision_fallback_on_timeout(mocker):
    mocker.patch("urllib.request.urlopen", side_effect=TimeoutError("timeout"))

    rev = HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert rev == DEFAULT_REVISIONS[RemoteHook.PRE_COMMIT_HOOKS]


def test_get_revision_fallback_on_bad_json(mocker):
    mock_response = MagicMock()
    mock_response.read.return_value = b"invalid json"

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    rev = HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert rev == DEFAULT_REVISIONS[RemoteHook.PRE_COMMIT_HOOKS]


def test_get_revision_fallback_on_bad_schema(mocker):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "schema_version": 2,  # Wrong schema
            "hooks": {
                RemoteHook.PRE_COMMIT_HOOKS.value: "v9.9.9",
            },
        }
    ).encode("utf-8")

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    rev = HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert rev == DEFAULT_REVISIONS[RemoteHook.PRE_COMMIT_HOOKS]


def test_get_revision_caches_result(mocker):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "schema_version": 1,
            "hooks": {
                RemoteHook.PRE_COMMIT_HOOKS.value: "v9.9.9",
            },
        }
    ).encode("utf-8")

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    # First call
    rev1 = HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert rev1 == "v9.9.9"

    # Change the mock response to see if it's still cached
    mock_response.read.return_value = json.dumps(
        {
            "schema_version": 1,
            "hooks": {
                RemoteHook.PRE_COMMIT_HOOKS.value: "v8.8.8",
            },
        }
    ).encode("utf-8")

    # Second call, should still be v9.9.9
    rev2 = HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert rev2 == "v9.9.9"

    # urlopen should only have been called once
    assert mock_urlopen.call_count == 1
