"""Confirm the commands a run executes for a template that isn't trusted.

The init review shows the gate beside its other decisions. A sync has nothing
else to show when its only open decision is trust, so it confirms on a screen
of its own, after its conflicts are settled and the commands are final.
"""

import shlex
from typing import ClassVar

from rich.console import Group, RenderableType
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Static

from protostar.cli.changes import count, indented_lines

from .chrome import Column, Columns, Heading, Headline, Masthead, Panel, Section
from .keys import ActionBar, KeyboardScreen, KeyRows, Toggle, key_label
from .theme import TEXT_FAINT

Commands = tuple[tuple[str, ...], ...]


def trust_text(commands: Commands, *, hint: str) -> RenderableType:
    """Explains why an untrusted template's commands need confirming.

    Args:
        commands: The commands the run executes, in order.
        hint: How to skip the confirmation next time.

    Returns:
        The explanation, the commands, and the hint.
    """
    return Group(
        Text(
            "This template comes from a source you haven't marked trusted. "
            "Applying runs these commands in the files it writes, and those files "
            "can make them run the template's code:"
        ),
        *indented_lines([shlex.join(command) for command in commands], "bold"),
        Text(hint, TEXT_FAINT),
    )


SYNC_HINT = (
    "Configure it as an alias with trusted = true to skip this check, "
    "or pass --trust to skip it for one sync."
)


class TrustScreen(KeyboardScreen[Commands]):
    """Confirm an untrusted template's commands, then apply the sync.

    The screen exits with exactly the commands it listed, so the CLI can check
    that the sync runs those and no others.
    """

    LEAVE = "Leave without syncing?"
    KEYS: ClassVar[KeyRows] = (
        ("t", "Trust this template to run these commands"),
        ("a", "Apply the sync"),
        ("tab", "Next control"),
        ("shift+tab", "Previous control"),
        ("esc", "Cancel, after asking"),
        ("^c", "Quit immediately"),
    )
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("t", "trust", "Trust", show=False),
        Binding("a", "apply", "Apply", show=False),
    ]

    def __init__(self, commands: Commands) -> None:
        """Create the screen.

        Args:
            commands: The commands the sync runs, in order.
        """
        super().__init__()
        self.commands = commands

    def compose(self) -> ComposeResult:
        """Compose the commands, the confirmation, and the actions."""
        yield Masthead("sync", "trust")
        yield Headline(
            "Confirm sync",
            Text(
                f"The update needs {count(len(self.commands), 'command')}. "
                "Nothing runs until you confirm them."
            ),
        )
        with Columns(id="body"), Column(id="trust-column"):
            with Panel("Untrusted template", id="trust-panel"), VerticalScroll():
                yield Static(trust_text(self.commands, hint=SYNC_HINT), id="trust-note")
            with Section(id="trust-gate"):
                yield Heading("Confirm")
                yield Toggle(
                    key_label("I trust this template to run these commands", "t"),
                    id="trust",
                )
            with ActionBar(id="actions"):
                yield Button(key_label("Cancel", "esc"), id="cancel")
                yield Button(
                    key_label("Apply", "a"),
                    variant="primary",
                    id="apply",
                    disabled=True,
                )
        yield Footer()

    def on_mount(self) -> None:
        """Start on the confirmation, the one control that matters here."""
        self.query_one("#trust", Checkbox).focus()

    @on(Checkbox.Changed, "#trust")
    def _confirmed(self, event: Checkbox.Changed) -> None:
        self.query_one("#apply", Button).disabled = not event.value

    def action_trust(self) -> None:
        """Toggle the confirmation by key."""
        self.query_one("#trust", Checkbox).toggle()

    @on(Button.Pressed, "#cancel")
    def _cancel_pressed(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#apply")
    def action_apply(self) -> None:
        """Exit with the confirmed commands; the sync applies after exit."""
        if not self.query_one("#apply", Button).disabled:
            self.app.exit(self.commands)
