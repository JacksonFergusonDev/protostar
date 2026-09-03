"""User interface helpers for Protostar.

Centralizes interactive terminal prompts (TUI) and lazily loads the underlying
prompt library (questionary) to keep CLI startup times fast.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from questionary import Choice, Separator, Style
else:

    class Choice:
        """Lazily constructs a questionary Choice."""

        def __new__(cls, *args: Any, **kwargs: Any) -> Any:
            """Constructs and returns a questionary Choice instance."""
            import questionary

            return questionary.Choice(*args, **kwargs)

    class Separator:
        """Lazily constructs a questionary Separator."""

        def __new__(cls, *args: Any, **kwargs: Any) -> Any:
            """Constructs and returns a questionary Separator instance."""
            import questionary

            return questionary.Separator(*args, **kwargs)

    class Style:
        """Lazily constructs a questionary Style."""

        def __new__(cls, *args: Any, **kwargs: Any) -> Any:
            """Constructs and returns a questionary Style instance."""
            import questionary

            return questionary.Style(*args, **kwargs)


def _ask(question: Any) -> Any:
    """Executes a questionary prompt with suppressed KeyboardInterrupt noise.

    Args:
        question: A questionary Question instance.

    Returns:
        The result of asking the question.
    """
    return question.ask(kbi_msg="")


def select(message: str, choices: Sequence[Any], **kwargs: Any) -> Any:
    """Prompt user to select an option from a list.

    Args:
        message: The prompt question text.
        choices: A list of options or Choices.
        **kwargs: Additional options forwarded to questionary.select.

    Returns:
        The selected choice value, or None if aborted.
    """
    import questionary

    return _ask(questionary.select(message, choices=choices, **kwargs))


def confirm(message: str, **kwargs: Any) -> bool | None:
    """Prompt user for a yes/no confirmation.

    Args:
        message: The prompt question text.
        **kwargs: Additional options forwarded to questionary.confirm (e.g. default).

    Returns:
        True/False for user confirmation, or None if aborted.
    """
    import questionary

    return cast(
        bool | None,
        _ask(questionary.confirm(message, **kwargs)),
    )


def checkbox(message: str, choices: Sequence[Any], **kwargs: Any) -> list[Any] | None:
    """Prompt user to toggle multiple options from a list.

    Args:
        message: The prompt question text.
        choices: A list of options or Choices.
        **kwargs: Additional options forwarded to questionary.checkbox.

    Returns:
        A list of selected values, or None if aborted.
    """
    import questionary

    return cast(
        list[Any] | None,
        _ask(questionary.checkbox(message, choices=choices, **kwargs)),
    )


def text(message: str, **kwargs: Any) -> str | None:
    """Prompt user for free-form text input.

    Args:
        message: The prompt question text.
        **kwargs: Additional options forwarded to questionary.text (e.g. default).

    Returns:
        The entered text string, or None if aborted.
    """
    import questionary

    return cast(
        str | None,
        _ask(questionary.text(message, **kwargs)),
    )


__all__ = [
    "Choice",
    "Separator",
    "Style",
    "checkbox",
    "confirm",
    "select",
    "text",
]
