import json
import threading
import urllib.error
from email.message import Message
from unittest.mock import MagicMock

import pytest

from protostar._fallbacks import DEFAULT_REVISIONS
from protostar.manifest import CollisionStrategy
from protostar.registry import (
    HookRegistry,
    RemoteHook,
    clear_hook_registry_cache,
    hook_registry_unreachable,
    prefetch_hook_registry,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset the registry cache before each test."""
    clear_hook_registry_cache()
    yield
    clear_hook_registry_cache()


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


def test_clear_hook_registry_cache(mocker):
    """Verify that clear_hook_registry_cache evicts cached registry responses."""
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

    rev1 = HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert rev1 == "v9.9.9"
    assert mock_urlopen.call_count == 1

    # Clear cache and change response
    clear_hook_registry_cache()
    mock_response.read.return_value = json.dumps(
        {
            "schema_version": 1,
            "hooks": {
                RemoteHook.PRE_COMMIT_HOOKS.value: "v8.8.8",
            },
        }
    ).encode("utf-8")

    rev2 = HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert rev2 == "v8.8.8"
    assert mock_urlopen.call_count == 2


def test_remote_hook_placeholders():
    assert RemoteHook.PRE_COMMIT_HOOKS.placeholder == "<% REV_PRE_COMMIT_HOOKS %>"
    assert RemoteHook.GITLEAKS.placeholder == "<% REV_GITLEAKS %>"
    assert RemoteHook.MARKDOWNLINT.placeholder == "<% REV_MARKDOWNLINT %>"
    assert RemoteHook.COMMITIZEN.placeholder == "<% REV_COMMITIZEN %>"


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
    from protostar.modules import TOOLING_MODULES, PreCommitModule
    from protostar.orchestrator import Orchestrator

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    orchestrator = Orchestrator(
        modules=[m for m in TOOLING_MODULES if not isinstance(m, PreCommitModule)],
        user_config=UserConfig(),
        request=InitRequest(collision_strategy=CollisionStrategy.MERGE),
    )

    manifest = orchestrator.plan()
    assert manifest is not None
    # No network requests must be made during plan()
    assert mock_urlopen.call_count == 0


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError(OSError("nodename nor servname provided")),
        TimeoutError("timed out"),
        ConnectionResetError("reset mid-read"),
    ],
)
def test_a_fetch_that_never_connects_is_unreachable(mocker, error):
    mocker.patch("urllib.request.urlopen", side_effect=error)

    assert hook_registry_unreachable()
    rev = HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert rev == DEFAULT_REVISIONS[RemoteHook.PRE_COMMIT_HOOKS]


def test_a_registry_that_answers_with_an_error_is_reachable(mocker):
    error = urllib.error.HTTPError(
        "https://example.invalid", 503, "Unavailable", Message(), None
    )
    mocker.patch("urllib.request.urlopen", side_effect=error)

    assert not hook_registry_unreachable()


def test_an_unreadable_registry_is_reachable(mocker):
    mock_response = MagicMock()
    mock_response.read.return_value = b"invalid json"
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    assert not hook_registry_unreachable()


def test_offline_registry_mode_is_not_unreachable(mocker, monkeypatch):
    monkeypatch.setenv("PROTOSTAR_OFFLINE_HOOK_REGISTRY", "1")
    urlopen = mocker.patch("urllib.request.urlopen")

    assert not hook_registry_unreachable()
    urlopen.assert_not_called()


def test_reachability_shares_the_one_fetch(mocker):
    urlopen = mocker.patch(
        "urllib.request.urlopen", side_effect=urllib.error.URLError("down")
    )

    HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
    assert hook_registry_unreachable()
    urlopen.assert_called_once()


def _answer(revision: str) -> MagicMock:
    """A registry response that pins one hook to a revision."""
    body = MagicMock()
    body.read.return_value = json.dumps(
        {"schema_version": 1, "hooks": {RemoteHook.PRE_COMMIT_HOOKS.value: revision}}
    ).encode("utf-8")
    response = MagicMock()
    response.__enter__.return_value = body
    return response


def _held_request(mocker, revision: str = "v9.9.9"):
    """Patches urlopen to answer only once the test lets it, as a slow network does."""
    started, release = threading.Event(), threading.Event()

    def held(*_args, **_kwargs):
        started.set()
        assert release.wait(5)
        return _answer(revision)

    return started, release, mocker.patch("urllib.request.urlopen", side_effect=held)


def test_prefetch_returns_before_the_request_finishes(mocker):
    """The fetch runs in the background; a snapshot taken later waits for it."""
    started, release, urlopen = _held_request(mocker)

    prefetch_hook_registry()

    assert started.wait(5)
    taken: list[str] = []
    waiting = threading.Thread(
        target=lambda: taken.append(
            HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
        )
    )
    waiting.start()
    waiting.join(0.2)
    assert waiting.is_alive()
    release.set()
    waiting.join(5)
    assert taken == ["v9.9.9"]
    assert urlopen.call_count == 1


def test_callers_that_arrive_during_a_fetch_share_its_request(mocker):
    """However many ask while it is under way, the registry is asked once."""
    started, release, urlopen = _held_request(mocker)
    prefetch_hook_registry()
    assert started.wait(5)
    results: list[bool] = []
    callers = [
        threading.Thread(target=lambda: results.append(hook_registry_unreachable()))
        for _ in range(8)
    ]
    for caller in callers:
        caller.start()

    release.set()
    for caller in callers:
        caller.join(5)

    assert results == [False] * 8
    assert urlopen.call_count == 1


def test_prefetching_twice_makes_one_request(mocker):
    urlopen = mocker.patch("urllib.request.urlopen", return_value=_answer("v9.9.9"))

    prefetch_hook_registry()
    prefetch_hook_registry()

    assert HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS) == "v9.9.9"
    assert urlopen.call_count == 1


def test_clearing_during_a_fetch_is_not_overwritten_by_its_late_answer(mocker):
    """A fetch that was cleared away finishes into its own result, which no one reads."""
    started, release = threading.Event(), threading.Event()
    requests: list[str] = []

    def urlopen(*_args, **_kwargs):
        requests.append("request")
        if len(requests) == 1:
            started.set()
            assert release.wait(5)
            return _answer("v1.0.0")
        return _answer("v2.0.0")

    mocker.patch("urllib.request.urlopen", side_effect=urlopen)
    prefetch_hook_registry()
    assert started.wait(5)

    clear_hook_registry_cache()
    assert HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS) == "v2.0.0"
    release.set()

    assert HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS) == "v2.0.0"


def test_an_unexpected_error_in_the_fetch_reaches_the_caller(mocker):
    """Prefetching in the background does not swallow what a direct fetch raised."""
    mocker.patch("urllib.request.urlopen", side_effect=RuntimeError("boom"))

    prefetch_hook_registry()

    with pytest.raises(RuntimeError, match="boom"):
        HookRegistry.get_revision(RemoteHook.PRE_COMMIT_HOOKS)
