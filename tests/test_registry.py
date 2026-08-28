import json
import urllib.error
from unittest.mock import MagicMock

import pytest

from protostar._fallbacks import DEFAULT_REVISIONS
from protostar.registry import HookRegistry, RemoteHook


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


def test_remote_hook_placeholders():
    assert RemoteHook.PRE_COMMIT_HOOKS.placeholder == "<% REV_PRE_COMMIT_HOOKS %>"
    assert RemoteHook.GITLEAKS.placeholder == "<% REV_GITLEAKS %>"
    assert RemoteHook.MARKDOWNLINT.placeholder == "<% REV_MARKDOWNLINT %>"
    assert RemoteHook.COMMITIZEN.placeholder == "<% REV_COMMITIZEN %>"
    assert RemoteHook.RENOVATE.placeholder == "<% REV_RENOVATE %>"


def test_resolve_placeholders_skips_fetch_when_no_placeholders(mocker):
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    content = "repos:\n  - repo: builtin\n    hooks:\n      - id: check-yaml\n"

    result = HookRegistry.resolve_placeholders(content)
    assert result == content
    assert mock_urlopen.call_count == 0


def test_resolve_placeholders_replaces_all_present_hooks(mocker):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "schema_version": 1,
            "hooks": {
                RemoteHook.MARKDOWNLINT.value: "v0.50.0",
                RemoteHook.COMMITIZEN.value: "v3.15.0",
            },
        }
    ).encode("utf-8")

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    raw_yaml = (
        f"  - repo: {RemoteHook.MARKDOWNLINT.value}\n"
        f"    rev: {RemoteHook.MARKDOWNLINT.placeholder}\n"
        f"  - repo: {RemoteHook.COMMITIZEN.value}\n"
        f"    rev: {RemoteHook.COMMITIZEN.placeholder}\n"
    )

    resolved = HookRegistry.resolve_placeholders(raw_yaml)
    assert "rev: v0.50.0" in resolved
    assert "rev: v3.15.0" in resolved
    assert RemoteHook.MARKDOWNLINT.placeholder not in resolved
    assert RemoteHook.COMMITIZEN.placeholder not in resolved
    assert mock_urlopen.call_count == 1


def test_plan_phase_makes_zero_network_requests(mocker):
    """Test that orchestrator.plan() with all tooling modules makes zero network calls."""
    from protostar.config import UserConfig
    from protostar.models import InitRequest
    from protostar.modules import TOOLING_MODULES
    from protostar.orchestrator import Orchestrator

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    orchestrator = Orchestrator(
        modules=list(TOOLING_MODULES),
        user_config=UserConfig(),
        request=InitRequest(force_merge=True),
    )

    manifest = orchestrator.plan()
    assert manifest is not None
    # No network requests must be made during plan()
    assert mock_urlopen.call_count == 0
