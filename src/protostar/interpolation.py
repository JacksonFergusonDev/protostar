"""``<% NAME %>`` placeholders and the values that replace them.

Substitution never escapes. Whoever writes content knows its syntax, so it
escapes a value exactly where the value sits inside a quoted string, and
nowhere else. Loading a template parses its TOML first and renders each
string's decoded text, so a value means the same in every string style; only
a ``[dev.pyproject]`` payload escapes (``escaped``), for the TOML document it
holds. Planning renders the rest: a module renders what it
generates, quoting each value that sits inside a string (``quoted``), and the
orchestrator renders the built-ins a template left. Reconciliation renders
only target paths, which are inside no string.

TOML, JSON, and YAML share the escapes JSON defines, so one escape serves
every structured format.
"""

import json
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
# `{`, `$`, and `%` in a file alone.
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


def escape(value: str) -> str:
    """Escapes a value to sit inside a double-quoted TOML, JSON, or YAML string.

    The value can then neither close the string it lands in nor carry a
    control character the format rejects.

    Args:
        value: The raw value.

    Returns:
        The value's escaped form, without surrounding quotes.
    """
    # JSON leaves DEL unescaped; TOML and YAML both reject it raw.
    return json.dumps(value, ensure_ascii=False)[1:-1].replace("\x7f", "\\u007f")


def escaped(context: dict[str, str]) -> dict[str, str]:
    """Escapes every value in a context, for placeholders inside quoted strings.

    Args:
        context: A mapping of variable names to their raw values.

    Returns:
        The same names, each mapped to its escaped value.
    """
    return {name: escape(value) for name, value in context.items()}


def quoted(value: str) -> str:
    """Returns a value as a double-quoted TOML, JSON, or YAML string.

    Args:
        value: The raw value.

    Returns:
        The string literal, quotes included.
    """
    return f'"{escape(value)}"'


def render_template(content: str, context: dict[str, str]) -> str:
    """Replaces placeholders in the content with context values in a single pass.

    Values are substituted as given. To place them inside quoted strings,
    escape them first.

    Args:
        content: The raw text content.
        context: A mapping of variable names to their substitution values.

    Returns:
        The interpolated string, with placeholders absent from ``context`` kept.
    """

    def replacement(match: re.Match[str]) -> str:
        return context.get(match.group(1), match.group(0))

    return VARIABLE_PATTERN.sub(replacement, content)
