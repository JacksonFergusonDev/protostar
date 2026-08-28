"""Interpolation utilities for safely injecting variables into TOML strings."""

import re
from typing import Final

VARIABLE_PATTERN: Final[re.Pattern[str]] = re.compile(r"<\%\s*([a-zA-Z0-9_]+)\s*\%>")


# --- Design Note: Lightweight Regex Interpolation vs Jinja2 ---
# Custom regex matching with `<% var %>` delimiters and `toml_escape()` is used instead of Jinja2
# or string.Template:
#   1. Zero External Dependencies: Avoids adding heavy templating dependencies to the CLI footprint.
#   2. TOML Injection Prevention: `toml_escape()` sanitizes input variables against quotes and newline
#      breakouts before string substitution into target TOML manifests.
def extract_variables(content: str) -> list[str]:
    """Scans a raw string for <% variable %> placeholders.

    Args:
        content: The raw text to scan.

    Returns:
        A deduplicated list of placeholder names, preserving insertion order.
    """
    matches = VARIABLE_PATTERN.findall(content)
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


def render_template(
    content: str, context: dict[str, str], escape_toml: bool = True
) -> str:
    """Replaces placeholders in the content with context values in a single pass.

    Args:
        content: The raw text content.
        context: A mapping of variable names to their raw substitution values.
        escape_toml: Whether to escape the values for safe TOML injection.

    Returns:
        The interpolated string.
    """

    def replacement(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            val = context[key]
            return toml_escape(val) if escape_toml else val
        return match.group(0)

    return VARIABLE_PATTERN.sub(replacement, content)
