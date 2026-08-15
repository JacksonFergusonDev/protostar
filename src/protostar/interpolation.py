"""Interpolation utilities for safely injecting variables into TOML strings."""

import re


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


def render_template(
    content: str, context: dict[str, str], escape_toml: bool = True
) -> str:
    """Replaces placeholders in the content with context values.

    Args:
        content: The raw text content.
        context: A mapping of variable names to their raw substitution values.
        escape_toml: Whether to escape the values for safe TOML injection.

    Returns:
        The interpolated string.
    """
    rendered = content
    for key, value in context.items():
        safe_value = toml_escape(value) if escape_toml else value
        pattern = r"<\%\s*" + re.escape(key) + r"\s*\%>"

        def replacement(_match: re.Match[str], sv: str = safe_value) -> str:
            return sv

        rendered = re.sub(pattern, replacement, rendered)
    return rendered
