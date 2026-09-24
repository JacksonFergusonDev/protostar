"""Keyboard-first navigation shared by every decision screen.

Arrow keys move and never change a value; only space and enter do. Up and down
walk a form one row at a time, and a list hands off to the next row at its
edges instead of wrapping. Tab moves one control at a time, where a
``ChoiceGroup`` counts as one. Every action a button or option offers has a
key, shown on the control itself; the footer is the legend for moving.
"""

from typing import Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Select,
    SelectionList,
    Static,
)
from textual.widgets._toggle_button import ToggleButton

MOVE = Binding.Group("Move", compact=True)
"""Groups up and down under one footer entry."""

KeyRows = tuple[tuple[str, str], ...]


def key_label(label: str, key: str) -> Text:
    """Returns a control's label followed by the key that activates it.

    Args:
        label: The control's label.
        key: The key as Textual's footer displays it.

    Returns:
        The label, with the key dimmed after it.
    """
    return Text.assemble(label, "  ", (key, "dim"))


class Form(VerticalScroll, can_focus=False):
    """A scrolling form whose arrow keys move between rows instead of scrolling.

    Focusing a row scrolls it into view, so the form itself never takes focus.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "screen.move(-1)", "Up", group=MOVE),
        Binding("down", "screen.move(1)", "Down", group=MOVE),
    ]


class ChoiceGroup(Vertical):
    """Related toggles that tab treats as one control; arrows move within."""


class ActionBar(Horizontal):
    """The screen's buttons, primary last; left and right move between them."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "screen.move(-1)", "Up", group=MOVE),
        Binding("left", "step(-1)", "Previous button", show=False),
        Binding("right", "step(1)", "Next button", show=False),
    ]

    def action_step(self, direction: int) -> None:
        """Focus the neighbouring button, stopping at either end."""
        buttons = [button for button in self.query(Button) if button.focusable]
        if self.screen.focused in buttons:
            index = buttons.index(self.screen.focused) + direction
            if 0 <= index < len(buttons):
                buttons[index].focus()


# A square lamp tells a checkbox from a radio button's round one. SelectionList
# draws its boxes from ToggleButton itself, so the lamp is set there.
ToggleButton.BUTTON_INNER = "■"


class Toggle(Checkbox):
    """A checkbox whose footer entry says space toggles it."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle_button", "Toggle"),
        Binding("enter", "toggle_button", "Toggle", show=False),
    ]


class Field(Input):
    """A text field; enter accepts it and moves to the next row.

    Input's own up and down scroll a single line, which is never possible, so
    they move between rows instead and say so in the footer.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "screen.move(-1)", "Up", group=MOVE),
        Binding("down", "screen.move(1)", "Down", group=MOVE),
        Binding("enter", "submit", "Accept"),
    ]


# The list widgets below don't inherit bindings: the footer keeps a key's
# inherited position, which would split the up and down group.


class Picker[ValueT](Select[ValueT], inherit_bindings=False):
    """A dropdown that opens on space or enter, so arrows can pass over it."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "screen.move(-1)", "Up", group=MOVE),
        Binding("down", "screen.move(1)", "Down", group=MOVE),
        Binding("space", "show_overlay", "Open"),
        Binding("enter", "show_overlay", "Open", show=False),
    ]


class Choice(RadioSet, inherit_bindings=False):
    """Radio buttons whose arrows move the highlight, never the choice.

    Up and down hand off to the neighbouring row at the ends instead of
    wrapping, so walking a form never gets stuck in the set.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "step(-1)", "Up", group=MOVE),
        Binding("down", "step(1)", "Down", group=MOVE),
        Binding("space", "toggle_button", "Choose"),
        Binding("enter", "toggle_button", "Choose", show=False),
        Binding("left", "previous_button", "Previous option", show=False),
        Binding("right", "next_button", "Next option", show=False),
    ]

    def _enabled(self) -> list[int]:
        return [
            index for index, button in enumerate(self._nodes) if not button.disabled
        ]

    def action_step(self, direction: int) -> None:
        """Move the highlight, or leave the set from its first or last button."""
        enabled = self._enabled()
        if not enabled or self._selected == enabled[-1 if direction > 0 else 0]:
            move(self.screen, direction)
        elif direction > 0:
            self.action_next_button()
        else:
            self.action_previous_button()

    def enter(self, direction: int) -> None:
        """Highlight the button nearest the row the cursor came from."""
        enabled = self._enabled()
        if enabled:
            self._selected = enabled[0] if direction > 0 else enabled[-1]

    def show(self, pressed: RadioButton | None) -> None:
        """Press one button, or none, without announcing a change.

        RadioSet presses a button again when code switches it off, so the
        buttons are set with their messages held and the set told directly.

        Args:
            pressed: The button to press, or ``None`` to press none.
        """
        with self.prevent(RadioButton.Changed, RadioSet.Changed):
            for button in self.query(RadioButton):
                button.value = button is pressed
        self._pressed_button = pressed


class Checklist[ValueT](SelectionList[ValueT], inherit_bindings=False):
    """A selection list that hands off to the neighbouring row at its ends."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "step(-1)", "Up", group=MOVE),
        Binding("down", "step(1)", "Down", group=MOVE),
        Binding("space", "select", "Toggle"),
        Binding("enter", "select", "Toggle", show=False),
    ]

    def _enabled(self) -> list[int]:
        return [
            index for index, option in enumerate(self.options) if not option.disabled
        ]

    def action_step(self, direction: int) -> None:
        """Move the highlight, or leave the list from its first or last option."""
        enabled = self._enabled()
        if not enabled or self.highlighted == enabled[-1 if direction > 0 else 0]:
            move(self.screen, direction)
        elif direction > 0:
            self.action_cursor_down()
        else:
            self.action_cursor_up()

    def enter(self, direction: int) -> None:
        """Highlight the option nearest the row the cursor came from."""
        enabled = self._enabled()
        if enabled:
            self.highlighted = enabled[0] if direction > 0 else enabled[-1]


def move(screen: Screen[Any], direction: int) -> None:
    """Focus the form's previous or next row.

    Stops at the first row; past the last, focuses the screen's primary
    button. Up from a button returns to the last row. A screen without a form
    moves through its whole focus chain instead.

    Args:
        screen: The screen to move within.
        direction: ``-1`` for the previous row, ``1`` for the next.
    """
    forms = screen.query(Form)
    if not forms:
        if direction > 0:
            screen.focus_next()
        else:
            screen.focus_previous()
        return
    form = forms.first()
    rows = [widget for widget in screen.focus_chain if form in widget.ancestors]
    focused = screen.focused
    target: Widget | None = None
    if focused in rows:
        index = rows.index(focused) + direction
        if 0 <= index < len(rows):
            target = rows[index]
        elif index == len(rows):
            buttons = [
                button
                for bar in screen.query(ActionBar)
                for button in bar.query(Button)
                if button.focusable
            ]
            target = buttons[-1] if buttons else None
    elif rows:
        target = rows[0] if direction > 0 else rows[-1]
    if target is None:
        return
    target.focus()
    if isinstance(target, (Choice, Checklist)):
        target.enter(direction)


def _control(widget: Widget) -> Widget:
    return next(
        (node for node in widget.ancestors if isinstance(node, ChoiceGroup)), widget
    )


class LeaveScreen(ModalScreen[bool]):
    """Asks before leaving, since leaving discards every choice made so far."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss(False)", "Stay"),
        Binding("enter", "dismiss(True)", "Leave"),
    ]

    def __init__(self, question: str) -> None:
        """Create the dialog.

        Args:
            question: What leaving abandons, asked as a question.
        """
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        """Compose the question and its two answers, each showing its key."""
        with Vertical(id="dialog") as dialog:
            dialog.border_title = "LEAVE"
            yield Label(self.question, classes="question")
            yield Static("Nothing has been written yet.", classes="note")
            with Horizontal(classes="dialog-actions"):
                stay = Button(key_label("Stay", "esc"), id="stay")
                leave = Button(key_label("Leave", "enter"), variant="error", id="leave")
                # Keys answer directly; a focused button would make enter ambiguous.
                stay.can_focus = leave.can_focus = False
                yield stay
                yield leave

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Answer with the clicked button."""
        self.dismiss(event.button.id == "leave")


class KeysScreen(ModalScreen[None]):
    """Every key the screen underneath understands."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,f1,question_mark", "dismiss", "Close"),
    ]

    def __init__(self, rows: KeyRows) -> None:
        super().__init__()
        self.rows = rows

    def compose(self) -> ComposeResult:
        """Compose one line per key and what it does."""
        width = max(len(keys) for keys, _ in self.rows)
        text = Text()
        for keys, description in self.rows:
            text.append(keys.ljust(width + 3), "bold cyan")
            text.append(description + "\n")
        text.rstrip()
        with Vertical(id="dialog") as dialog:
            dialog.border_title = "KEYS"
            yield Static(text)
            yield Static(Text("esc to close", style="dim"), classes="note")


FORM_KEYS: KeyRows = (
    ("↑ ↓", "Move between rows"),
    ("space", "Toggle a checkbox, choose an option, or open a menu"),
    ("enter", "Same as space; in a text field, accept it and move on"),
    ("tab", "Next control; a group of checkboxes is one stop"),
    ("shift+tab", "Previous control"),
    ("^s", "Continue"),
    ("esc", "Cancel, after asking"),
    ("^c", "Quit immediately"),
)


class KeyboardScreen[ResultT](Screen[ResultT]):
    """A decision screen driven from the keyboard first.

    Escape reaches ``action_cancel`` through the app, which asks before
    leaving; ctrl+c leaves at once.
    """

    KEYS: ClassVar[KeyRows] = FORM_KEYS
    """The rows the keys list shows, besides f1 itself."""

    LEAVE: ClassVar[str] = "Leave without setting up the project?"
    """What escape asks before leaving."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("tab", "step(1)", "Next"),
        Binding("shift+tab", "step(-1)", "Previous", show=False),
        Binding("f1", "keys", "Keys"),
        Binding("question_mark", "keys", "Keys", show=False),
    ]

    def action_move(self, direction: int) -> None:
        """Focus the form's previous or next row."""
        move(self, direction)

    def action_step(self, direction: int) -> None:
        """Focus the previous or next control, wrapping like tab always does."""
        stops: list[Widget] = []
        for widget in self.focus_chain:
            control = _control(widget)
            if control not in stops:
                stops.append(control)
        if not stops:
            return
        current = _control(self.focused) if self.focused else None
        if current in stops:
            target = stops[(stops.index(current) + direction) % len(stops)]
        else:
            target = stops[0] if direction > 0 else stops[-1]
        if isinstance(target, ChoiceGroup):
            target = next(
                widget for widget in self.focus_chain if target in widget.ancestors
            )
        target.focus()

    def key_rows(self) -> KeyRows:
        """The keys this screen understands, for the keys list."""
        return self.KEYS

    def action_keys(self) -> None:
        """List every key this screen understands."""
        self.app.push_screen(KeysScreen((*self.key_rows(), ("f1", "Show this list"))))

    def action_cancel(self) -> None:
        """Ask before leaving without a result."""

        def answer(leave: bool | None) -> None:
            if leave:
                self.app.exit(None)

        self.app.push_screen(LeaveScreen(self.LEAVE), answer)
