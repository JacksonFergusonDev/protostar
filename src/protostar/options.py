"""Template options, and the conditions that gate template content on them.

An option chooses what a template includes; it never renders into text, which
is what variables do. A bool option is on or off; a choice option picks one of
the values its template lists. Content opts in with a ``requires`` condition
naming tools and options. A condition only lists what must hold: it has no
"or" and no "not". Content that needs either side of a choice is listed once
per side, and a question with two answers is a choice, not a bool.
"""

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Final

from .errors import ConfigurationError, InvalidOptionValueError
from .interpolation import VARIABLE_NAME

OptionValue = bool | str
"""A bool option's state, or the value a choice option picked."""

CHOICE_VALUE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
"""A choice value: safe to write after ``=`` in a condition or on a command line."""

_BOOL_WORDS: Final[dict[str, bool]] = {"true": True, "false": False}


@dataclass(frozen=True)
class Term:
    """One thing a condition requires.

    Attributes:
        name: A tool's key, or an option's name.
        value: The value a choice option must hold, or None for an enabled
            tool or a bool option that is on.
    """

    name: str
    value: str | None = None

    def holds(self, tools: Collection[str], options: Mapping[str, OptionValue]) -> bool:
        """Returns whether the term holds for these tools and option values."""
        if self.value is not None:
            return options.get(self.name) == self.value
        return self.name in tools or options.get(self.name) is True

    def __str__(self) -> str:
        """Returns the term as a template spells it."""
        return self.name if self.value is None else f"{self.name}={self.value}"


@dataclass(frozen=True)
class Condition:
    """When a template contribution applies: every term must hold.

    Attributes:
        terms: What must hold, in the order the template lists them.
    """

    terms: tuple[Term, ...]

    def holds(self, tools: Collection[str], options: Mapping[str, OptionValue]) -> bool:
        """Returns whether every term holds.

        Args:
            tools: The keys of the enabled tools.
            options: Every option's resolved value.
        """
        return all(term.holds(tools, options) for term in self.terms)

    @property
    def names(self) -> frozenset[str]:
        """The tools and options the condition names."""
        return frozenset(term.name for term in self.terms)

    def __str__(self) -> str:
        """Returns the condition as a template spells it."""
        return ", ".join(str(term) for term in self.terms)


def parse_condition(raw: object, location: str, source: str) -> Condition:
    """Parses a ``requires`` value: one term, or an array of terms that all hold.

    Each term is a tool key or bool option name, or ``option=value`` for a
    choice option. Whether each name exists is checked once the template's
    options are known.

    Args:
        raw: The value the template gives.
        location: Where it appears, for errors.
        source: The template, for errors.

    Returns:
        The condition.

    Raises:
        ConfigurationError: If the value is not a term or a non-empty array of them.
    """
    items = [raw] if isinstance(raw, str) else raw
    hint = (
        'Use requires = "tool", "option", or "option=value", or an array of '
        "them that must all hold."
    )
    if not isinstance(items, list) or not items:
        raise ConfigurationError(
            f"Invalid requires in configuration source '{source}' for '{location}'.",
            hint=hint,
        )
    terms: list[Term] = []
    for item in items:
        if not isinstance(item, str):
            raise ConfigurationError(
                f"Invalid requires in configuration source '{source}' for '{location}'.",
                hint=hint,
            )
        name, separator, value = item.partition("=")
        if not VARIABLE_NAME.fullmatch(name) or (
            separator and not CHOICE_VALUE.fullmatch(value)
        ):
            raise ConfigurationError(
                f"Invalid requires term {item!r} in configuration source "
                f"'{source}' for '{location}'.",
                hint=hint,
            )
        terms.append(Term(name, value if separator else None))
    return Condition(tuple(terms))


@dataclass(frozen=True)
class TemplateOption:
    """A choice a template offers, which its content opts into with ``requires``.

    Attributes:
        name: The option's name.
        default: The value a project that never chose follows.
        choices: A choice option's values, in the template's order; empty for
            a bool option.
        description: Explains the option while it is chosen.
    """

    name: str
    default: OptionValue
    choices: tuple[str, ...] = ()
    description: str = ""

    @property
    def values(self) -> tuple[OptionValue, ...]:
        """Every value the option can hold."""
        return self.choices or (False, True)

    def parse(self, text: str) -> OptionValue:
        """Reads a value spelled on the command line.

        Args:
            text: ``true`` or ``false`` for a bool option, or one of a choice
                option's values.

        Returns:
            The value.

        Raises:
            InvalidOptionValueError: If the option cannot hold the value.
        """
        if not self.choices:
            if text.lower() not in _BOOL_WORDS:
                raise InvalidOptionValueError(self.name, text, ("true", "false"))
            return _BOOL_WORDS[text.lower()]
        return self.check(text)

    def check(self, value: object) -> OptionValue:
        """Returns the value if the option can hold it.

        Raises:
            InvalidOptionValueError: If it cannot.
        """
        if isinstance(value, bool) and not self.choices:
            return value
        if isinstance(value, str) and value in self.choices:
            return value
        raise InvalidOptionValueError(
            self.name,
            format_value(value) if isinstance(value, bool | str) else repr(value),
            tuple(format_value(v) for v in self.values),
        )


def format_value(value: OptionValue) -> str:
    """Spells a value as the command line and the recipe show it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def parse_options(raw: object, source: str) -> dict[str, TemplateOption]:
    """Parses a template's ``[options]`` table.

    A bool option declares a bool ``default``. A choice option declares
    ``choices``, at least two distinct values, and a ``default`` among them.
    Both may add a ``description``.

    Args:
        raw: The table's value.
        source: The template, for errors.

    Returns:
        The options, by name.

    Raises:
        ConfigurationError: If the table or an option is malformed.
    """
    hint = (
        "Declare [options.NAME] with default = true or false, or with "
        'choices = ["a", "b"] and default = "a"; description is optional.'
    )
    if not isinstance(raw, dict):
        raise ConfigurationError(
            f"The [options] table in configuration source '{source}' is malformed.",
            hint=hint,
        )
    options: dict[str, TemplateOption] = {}
    for name, entry in raw.items():
        where = f"Option {name!r} in configuration source '{source}'"
        if not VARIABLE_NAME.fullmatch(name):
            raise ConfigurationError(
                f"{where} needs a name made of letters, digits, and underscores.",
                hint=hint,
            )
        if (
            not isinstance(entry, dict)
            or "default" not in entry
            or set(entry) - {"default", "choices", "description"}
            or not isinstance(entry.get("description", ""), str)
        ):
            raise ConfigurationError(f"{where} is malformed.", hint=hint)
        default = entry["default"]
        choices = entry.get("choices")
        if choices is None:
            if not isinstance(default, bool):
                raise ConfigurationError(
                    f"{where} needs a bool default, or a list of choices.",
                    hint=hint,
                )
            options[name] = TemplateOption(
                name, default, description=entry.get("description", "")
            )
            continue
        if (
            not isinstance(choices, list)
            or len(choices) < 2
            or not all(
                isinstance(choice, str) and CHOICE_VALUE.fullmatch(choice)
                for choice in choices
            )
            or len(set(choices)) != len(choices)
        ):
            raise ConfigurationError(
                f"{where} needs at least two distinct choices made of letters, "
                "digits, dots, dashes, and underscores.",
                hint=hint,
            )
        if default not in choices or not isinstance(default, str):
            raise ConfigurationError(
                f"{where} needs a default among its choices.", hint=hint
            )
        options[name] = TemplateOption(
            name, default, tuple(choices), entry.get("description", "")
        )
    return options


def resolve_options(
    options: Mapping[str, TemplateOption], chosen: Mapping[str, OptionValue]
) -> dict[str, OptionValue]:
    """Returns every option's value: the chosen one, or else its default.

    Args:
        options: The template's options.
        chosen: The values a project chose, by name.

    Returns:
        Every option's value, by name.

    Raises:
        InvalidOptionValueError: If a chosen value is not one its option offers.
        ConfigurationError: If a value is chosen for an option the template
            does not offer.
    """
    unknown = sorted(chosen.keys() - options.keys())
    if unknown:
        raise ConfigurationError(
            f"The template offers no option named {', '.join(unknown)}.",
            hint="Choose among the template's [options], or remove the value "
            "from [tool.protostar.options].",
        )
    return {
        name: option.check(chosen[name]) if name in chosen else option.default
        for name, option in options.items()
    }
