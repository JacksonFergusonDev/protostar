"""The keys each decision screen understands, read from the screens themselves.

The same rows fill each screen's ``?`` list, so the documentation and the
terminal can't disagree about a key.
"""

from __future__ import annotations

from protostar.cli.tui.keys import KeyRows
from scripts.generate_docs_assets.common import (
    _format_markdown_table,
    _write_generated_doc,
)

# How a key the screens write in the terminal's shorthand reads in prose.
_DISPLAY = {
    "^s": "Ctrl+S",
    "^c": "Ctrl+C",
    "esc": "Esc",
    "space": "Space",
    "enter": "Enter",
    "tab": "Tab",
    "shift+tab": "Shift+Tab",
    "pgup": "PgUp",
    "pgdn": "PgDn",
    "?": "?",
}


def screen_keys() -> dict[str, KeyRows]:
    """Returns each documented screen's keybindings rows, keyed by fixture name."""
    from protostar.cli.tui.config.screen import ConfigScreen
    from protostar.cli.tui.conflicts.screen import ConflictScreen
    from protostar.cli.tui.recipe.screen import RecipeScreen
    from protostar.cli.tui.review.screen import ReviewScreen
    from protostar.cli.tui.trust import TrustScreen

    help_row = ("?", "Show every key")
    return {
        "keys_recipe_editor.md": (*RecipeScreen.KEYS, help_row),
        # As init shows it, after the recipe editor it can go back to.
        "keys_change_review.md": (*ReviewScreen.keys(can_go_back=True), help_row),
        "keys_sync_conflicts.md": (*ConflictScreen.KEYS, help_row),
        "keys_trust.md": (*TrustScreen.KEYS, help_row),
        "keys_config.md": (*ConfigScreen.KEYS, help_row),
    }


def key_tokens(keys: str) -> list[str]:
    """Splits a row's keys, such as ``k / u / b`` or ``pgup pgdn``, into keys."""
    return [token for token in keys.replace("/", " ").split() if token]


def _display(keys: str) -> str:
    return " ".join(f"`{_DISPLAY.get(token, token)}`" for token in key_tokens(keys))


def generate_key_tables() -> None:
    """Writes one table of keys per decision screen."""
    for fixture, rows in screen_keys().items():
        _write_generated_doc(
            fixture,
            _format_markdown_table(
                ["Key", "Action"],
                [[_display(keys), action] for keys, action in rows],
            ),
        )
