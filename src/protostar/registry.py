"""Remote registry fetching and caching for pre-commit hook revisions.

Architectural Context:
Historically, Protostar relied on executing `pre-commit autoupdate` or `prek update`
as a post-install task. This approach scaled poorly: for every remote repository,
the CLI halted while the machine performed full `git fetch` operations just to read
a semantic version tag.

To eliminate this client-side bottleneck, we shifted to a static registry model:
1. An auxiliary repository (`protostar-hook-registry`) tracks upstream tools via Renovate Bot.
2. A GitHub Actions pipeline catches version bumps, compiles them, and deploys a lightweight `registry.json` payload to an edge CDN.
3. Before the change review, the caller takes one registry snapshot with per-pin
   provenance, and execution reuses it so it writes the pins the review showed
   (the executor takes its own only when it is given none). Pure reconciliation
   consumes that snapshot without network access.
4. The request starts on a background thread as a command that pins hooks begins,
   so it overlaps the planning before the snapshot is taken; the snapshot waits
   for it. One request serves the whole run.

This decoupling provides zero-dependency churn in core, maximum determinism, and graceful offline degradation.
"""

import enum
import json
import logging
import os
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from http.client import HTTPException
from urllib.error import HTTPError, URLError

from ._fallbacks import DEFAULT_REVISIONS

logger = logging.getLogger("protostar")

__all__ = [
    "HookRegistry",
    "PinProvenance",
    "RemoteHook",
    "clear_hook_registry_cache",
    "hook_registry_unreachable",
    "prefetch_hook_registry",
]


class PinProvenance(enum.StrEnum):
    """Source of an applied hook revision, without replay authorization."""

    REGISTRY = "registry"
    TEMPLATE = "template"
    FALLBACK = "fallback"


class RemoteHook(enum.StrEnum):
    """Strongly typed enumeration of supported remote pre-commit hook repositories."""

    PRE_COMMIT_HOOKS = "https://github.com/pre-commit/pre-commit-hooks"
    GITLEAKS = "https://github.com/gitleaks/gitleaks"
    MARKDOWNLINT = "https://github.com/DavidAnson/markdownlint-cli2"
    COMMITIZEN = "https://github.com/commitizen-tools/commitizen"

    @property
    def placeholder(self) -> str:
        """Returns the template placeholder string for deferred revision interpolation."""
        return f"<% REV_{self.name} %>"


@dataclass(frozen=True)
class ResolvedHookRevision:
    """Resolved automatic pin carried from planning into execution."""

    hook: RemoteHook
    revision: str
    provenance: PinProvenance


def resolve_hook_revisions() -> tuple[ResolvedHookRevision, ...]:
    """Takes one registry snapshot, recording fallback provenance per repository."""
    registry = _fetch_hook_registry()
    return tuple(
        ResolvedHookRevision(
            hook,
            registry.get(hook.value, DEFAULT_REVISIONS[hook]),
            PinProvenance.REGISTRY
            if hook.value in registry
            else PinProvenance.FALLBACK,
        )
        for hook in RemoteHook
    )


_REGISTRY_URL = (
    "https://jacksonfergusondev.github.io/protostar-hook-registry/registry.json"
)


@dataclass(frozen=True)
class _Fetch:
    hooks: dict[str, str]
    unreachable: bool = False


def _download() -> _Fetch:
    """Performs one HTTP GET to the static registry CDN."""
    if os.environ.get("PROTOSTAR_OFFLINE_HOOK_REGISTRY") == "1":
        logger.debug("Offline hook registry mode active, using fallback revisions.")
        return _Fetch({})

    try:
        import urllib.request

        with urllib.request.urlopen(_REGISTRY_URL, timeout=1.5) as response:
            raw = response.read(65_536)
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict) and data.get("schema_version") == 1:
                logger.debug("Successfully resolved remote hook registry.")
                hooks = data.get("hooks", {})
                if isinstance(hooks, dict):
                    return _Fetch({str(k): str(v) for k, v in hooks.items()})
    except HTTPError as e:
        # The server answered: the network works, the registry didn't.
        logger.debug(f"Remote registry answered {e.code}, using offline fallbacks.")
    except (URLError, OSError) as e:
        # URLError wraps a failed lookup or connection; OSError covers timeouts
        # and a connection dropped mid-read.
        logger.debug(f"Remote registry unreachable, using offline fallbacks: {e}")
        return _Fetch({}, unreachable=True)
    except (json.JSONDecodeError, UnicodeDecodeError, HTTPException) as e:
        logger.debug(
            f"Remote registry unavailable, using offline fallbacks. Reason: {e}"
        )

    return _Fetch({})


_lock = threading.Lock()
_pending: Future[_Fetch] | None = None


def _run(future: Future[_Fetch]) -> None:
    """Fills a fetch's future with its result, or with whatever it raised."""
    try:
        result = _download()
    except BaseException as error:
        future.set_exception(error)
    else:
        future.set_result(result)


def _start() -> Future[_Fetch]:
    """Returns the run's one fetch, starting it on a background thread if needed.

    The fetch happens at most once per run however many callers ask: a caller
    that comes while it is under way waits for that result instead of making a
    second request.
    """
    global _pending
    with _lock:
        if _pending is None:
            future: Future[_Fetch] = Future()
            _pending = future
            # A daemon, so a command that finishes first never waits on a slow
            # network at exit.
            threading.Thread(
                target=_run, args=(future,), name="hook-registry", daemon=True
            ).start()
        return _pending


def prefetch_hook_registry() -> None:
    """Starts the registry fetch now so it overlaps the work before its pins are used.

    It changes no result: the snapshot is taken, and the pins decided, where
    they were before. Calling it again, or never, only changes how long a later
    snapshot waits. Nothing here reads the project or raises.
    """
    _start()


def _fetch() -> _Fetch:
    """Returns the registry fetch, waiting for it if it is still under way."""
    return _start().result()


def _fetch_hook_registry() -> dict[str, str]:
    """Returns the registry's revisions, or nothing when it can't be read."""
    return _fetch().hooks


def hook_registry_unreachable() -> bool:
    """Returns whether the registry fetch failed to reach any server.

    It shares the one cached fetch, taking it if no snapshot has yet. A
    registry that answered with an error still reached the network, and an
    offline registry mode never counts.

    Returns:
        True when the request never connected, as when the machine is offline.
    """
    return _fetch().unreachable


def clear_hook_registry_cache() -> None:
    """Forgets the run's fetch, so the next snapshot makes its own request.

    A fetch still under way finishes into the future it was given and is
    ignored.
    """
    global _pending
    with _lock:
        _pending = None


class HookRegistry:
    """Memoized fetcher for the static JSON pre-commit hook registry."""

    @classmethod
    def resolve_placeholders(cls, content: str) -> str:
        """Replaces any remote hook revision placeholders with resolved revisions.

        Only fetches from the remote registry if at least one placeholder is present.

        Args:
            content: Text content containing optional `<% REV_* %>` placeholders.

        Returns:
            The content with all remote hook placeholders replaced by resolved versions.
        """
        rendered = content
        for hook in RemoteHook:
            if hook.placeholder in rendered:
                rev = cls.get_revision(hook)
                rendered = rendered.replace(hook.placeholder, rev)
        return rendered

    @classmethod
    def get_revision(cls, hook: RemoteHook) -> str:
        """Retrieves the latest revision for a hook, falling back to local defaults.

        Args:
            hook: The strongly typed RemoteHook enum value.

        Returns:
            The semantic version string (e.g., 'v6.0.0').
        """
        registry = _fetch_hook_registry()
        return registry.get(hook.value, DEFAULT_REVISIONS[hook])
