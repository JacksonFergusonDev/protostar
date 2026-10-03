"""``<% NAME %>`` placeholders and the values that replace them.

Rendering happens in two places. Loading a template renders its TOML source
with escaping, since there a value lands inside a TOML string, and its
``[files]`` without. Reconciliation then renders what modules generated,
whose placeholders name only built-in variables.

``toml_escape`` assumes the placeholder sits inside a double-quoted string.
TOML, JSON, and YAML share those escapes, so one escape serves every
structured format. Free-form text keeps the escapes literally, so a value
containing a quote or backslash shows them there.
"""

import re
from typing import Final

# A variable name is an identifier. Placeholders, recorded variables, and
# --var flags all use this one definition.
VARIABLE_NAME: Final[re.Pattern[str]] = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
VARIABLE_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"<\%\s*({VARIABLE_NAME.pattern})\s*\%>"
)

# Variables Protostar computes for every project. Templates use them without
# declaring them, and they are never prompted for.
BUILT_IN_VARIABLES: Final[frozenset[str]] = frozenset(
    {"PROJECT_NAME", "PACKAGE_NAME", "PYTHON_VERSION", "CURRENT_YEAR", "AUTHOR_NAME"}
)


# A regex over `<% var %>` replaces Jinja2 and string.Template: it adds no
# dependency, has no logic for a template to abuse, and leaves every other
# `{`, `$`, and `%` in a file alone. `toml_escape()` keeps a value from closing
# the string it is substituted into.
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
