"""Interpolation utilities for safely injecting variables into TOML strings."""

import re


def extract_variables(content: str) -> list[str]:
    """Scans a raw string for {{variable}} placeholders.

    Args:
        content: The raw text to scan.

    Returns:
        A deduplicated list of placeholder names, preserving insertion order.
    """
    pattern = r"<\%\s*([a-zA-Z0-9_]+)\s*\%>"
    matches = re.findall(pattern, content)
    # dict.fromkeys() preserves insertion order while removing duplicates
    return list(dict.fromkeys(matches))


def toml_escape(value: str) -> str:
    """Escapes a string for safe injection into a TOML document.

    Ensures that injected strings do not prematurely terminate TOML strings
    or inject invalid control characters that crash tomllib.
    """
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    return value.replace("\t", "\\t")


def render_template(content: str, context: dict[str, str]) -> str:
    """Replaces placeholders in the content with TOML-escaped context values.

    Args:
        content: The raw TOML specification content.
        context: A mapping of variable names to their raw substitution values.

    Returns:
        The interpolated, safely escaped TOML string.
    """
    rendered = content
    for key, value in context.items():
        safe_value = toml_escape(value)
        pattern = r"<\%\s*" + re.escape(key) + r"\s*\%>"
        rendered = re.sub(pattern, safe_value, rendered)
    return rendered
