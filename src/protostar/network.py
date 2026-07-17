"""Network utilities for fetching remote configurations."""

import re
import urllib.request
from urllib.error import URLError

from .errors import ConfigurationError


def fetch_remote_config(url: str, timeout: int = 10) -> str:
    """Fetches a remote TOML configuration via HTTPS.

    Translates GitHub and GitLab blob URLs to their raw text equivalents.

    Args:
        url: The remote URL to fetch.
        timeout: Maximum request duration in seconds.

    Returns:
        The raw string content of the fetched configuration.

    Raises:
        ConfigurationError: If the protocol is insecure or the network request fails.
    """
    if url.startswith("http://"):
        raise ConfigurationError(
            "Insecure protocol detected. Protostar requires HTTPS for remote configurations."
        )
    if not url.startswith("https://"):
        raise ConfigurationError(
            "Remote configuration URLs must start with 'https://'."
        )

    # Translate GitHub blob URLs
    url = re.sub(
        r"^https://github\.com/([^/]+)/([^/]+)/blob/(.+)$",
        r"https://raw.githubusercontent.com/\1/\2/\3",
        url,
    )

    # Translate GitLab blob URLs
    url = re.sub(
        r"^https://gitlab\.com/([^/]+)/([^/]+)/-/blob/(.+)$",
        r"https://gitlab.com/\1/\2/-/raw/\3",
        url,
    )

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return str(response.read().decode("utf-8"))
    except URLError as e:
        raise ConfigurationError(
            f"Failed to fetch remote configuration from {url}.\nDetails: {e}"
        ) from e
