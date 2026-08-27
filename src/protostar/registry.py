"""Remote registry fetching and caching for pre-commit hook revisions.

Architectural Context:
Historically, Protostar relied on executing `pre-commit autoupdate` or `prek update`
as a post-install task. This approach scaled poorly: for every remote repository,
the CLI halted while the machine performed full `git fetch` operations just to read
a semantic version tag.

To eliminate this client-side bottleneck, we shifted to an asynchronous static registry model:
1. An auxiliary repository (`protostar-hook-registry`) tracks upstream tools via Renovate Bot.
2. A GitHub Actions pipeline catches version bumps, compiles them, and deploys a lightweight `registry.json` payload to an edge CDN.
3. This module makes a single HTTP GET request during the `plan()` phase. It parses the JSON in memory and the Orchestrator injects these resolved semantic versions into the YAML string blocks before writing to disk.

This decoupling provides zero-dependency churn in core, maximum determinism, and graceful offline degradation.
"""

import enum
import json
import logging
import urllib.request
from urllib.error import URLError

logger = logging.getLogger("protostar")

__all__ = ["HookRegistry", "RemoteHook"]


class RemoteHook(enum.StrEnum):
    """Strongly typed enumeration of supported remote pre-commit hook repositories."""

    PRE_COMMIT_HOOKS = "https://github.com/pre-commit/pre-commit-hooks"
    GITLEAKS = "https://github.com/gitleaks/gitleaks"
    MARKDOWNLINT = "https://github.com/DavidAnson/markdownlint-cli2"
    COMMITIZEN = "https://github.com/commitizen-tools/commitizen"
    RENOVATE = "https://github.com/renovatebot/pre-commit-hooks"


# Immutable fallback state guarantees zero downtime if the user is offline
DEFAULT_REVISIONS: dict[RemoteHook, str] = {
    RemoteHook.PRE_COMMIT_HOOKS: "v6.0.0",
    RemoteHook.GITLEAKS: "v8.30.1",
    RemoteHook.MARKDOWNLINT: "v0.23.2",
    RemoteHook.COMMITIZEN: "v4.18.0",
    RemoteHook.RENOVATE: "44.48.0",
}


class HookRegistry:
    """Memoized fetcher for the static JSON pre-commit hook registry."""

    _cache: dict[str, str] | None = None
    _REGISTRY_URL = (
        "https://jacksonfergusondev.github.io/protostar-hook-registry/registry.json"
    )

    @classmethod
    def get_revision(cls, hook: RemoteHook) -> str:
        """Retrieves the latest revision for a hook, falling back to local defaults.

        Args:
            hook: The strongly typed RemoteHook enum value.

        Returns:
            The semantic version string (e.g., 'v6.0.0').
        """
        if cls._cache is None:
            cls._cache = cls._fetch_registry()

        return cls._cache.get(hook.value, DEFAULT_REVISIONS[hook])

    @classmethod
    def _fetch_registry(cls) -> dict[str, str]:
        """Performs a single HTTP GET to the static registry CDN."""
        try:
            with urllib.request.urlopen(cls._REGISTRY_URL, timeout=1.5) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, dict) and data.get("schema_version") == 1:
                    logger.debug("Successfully resolved remote hook registry.")
                    hooks = data.get("hooks", {})
                    if isinstance(hooks, dict):
                        return {str(k): str(v) for k, v in hooks.items()}
        except (URLError, json.JSONDecodeError, TimeoutError) as e:
            logger.debug(
                f"Remote registry unavailable, using offline fallbacks. Reason: {e}"
            )

        return {}
