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
from urllib.error import URLError

from ._fallbacks import DEFAULT_REVISIONS

logger = logging.getLogger("protostar")

__all__ = ["HookRegistry", "RemoteHook"]


class RemoteHook(enum.StrEnum):
    """Strongly typed enumeration of supported remote pre-commit hook repositories."""

    PRE_COMMIT_HOOKS = "https://github.com/pre-commit/pre-commit-hooks"
    GITLEAKS = "https://github.com/gitleaks/gitleaks"
    MARKDOWNLINT = "https://github.com/DavidAnson/markdownlint-cli2"
    COMMITIZEN = "https://github.com/commitizen-tools/commitizen"
    RENOVATE = "https://github.com/renovatebot/pre-commit-hooks"

    @property
    def placeholder(self) -> str:
        """Returns the template placeholder string for deferred revision interpolation."""
        return f"<% REV_{self.name} %>"


class HookRegistry:
    """Memoized fetcher for the static JSON pre-commit hook registry."""

    _cache: dict[str, str] | None = None
    _REGISTRY_URL = (
        "https://jacksonfergusondev.github.io/protostar-hook-registry/registry.json"
    )

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
        if cls._cache is None:
            cls._cache = cls._fetch_registry()

        return cls._cache.get(hook.value, DEFAULT_REVISIONS[hook])

    @classmethod
    def _fetch_registry(cls) -> dict[str, str]:
        """Performs a single HTTP GET to the static registry CDN."""
        try:
            import urllib.request

            with urllib.request.urlopen(cls._REGISTRY_URL, timeout=1.5) as response:  # noqa: S310
                raw = response.read(65_536)
                data = json.loads(raw.decode("utf-8"))
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
