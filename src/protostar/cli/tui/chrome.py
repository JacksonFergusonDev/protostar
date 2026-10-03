"""The frame every decision screen shares: a masthead, panels, and headings.

Spacing belongs to the layout, never to what it holds. A screen's body is
``Columns`` of ``Column`` stacks and panels, and every gap between blocks is
one cell across or one row down. A panel's rule is drawn in that row, so a
panel stacked on a panel shares its rule instead of adding a second one.
``tests/test_tui_layout.py`` measures every screen against this.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from rich.console import RenderableType
from rich.style import Style
from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.widget import Widget
from textual.widgets import ContentSwitcher, Label, Static

from protostar.cli.palette import MARK
from protostar.errors import ProtostarError

from .keys import key_hint
from .theme import ACCENT, FOREGROUND, KEY, RULE, TEXT_FAINT, TITLE


class Masthead(Static):
    """The top bar: the mark, the product, and where the user is."""

    def __init__(self, *path: str) -> None:
        """Create the bar.

        Args:
            *path: The command and the screen's phase, outermost first.
        """
        super().__init__()
        self.path = path
        self.cramped = False
        """Whether the screen needs more room than the terminal gives it."""

    def render(self) -> Content:
        """Render the mark and the product, then the path with its last step lit."""
        parts: list[Content | str | tuple[str, str]] = [
            (MARK, TITLE),
            " ",
            ("PROTOSTAR", "bold"),
            ("   ", ""),
        ]
        for index, step in enumerate(self.path):
            if index:
                parts.append(("  /  ", RULE))
            last = index == len(self.path) - 1
            parts.append((step, FOREGROUND if last else TEXT_FAINT))
        if self.cramped:
            parts.append(
                ("   ·   A larger terminal shows more of each change", TEXT_FAINT)
            )
        return Content.assemble(*parts)


def error_text(error: ProtostarError) -> Text:
    """Returns an error as a status line says it, its hint fainter after it.

    Args:
        error: The error to report.

    Returns:
        The message, then the hint when the error has one.
    """
    return Text.assemble(
        str(error), (f"  {error.hint}", TEXT_FAINT) if error.hint else ""
    )


class Headline(Horizontal):
    """The screen's title on one line with, dimmer beside it, its status.

    The status is ``#subtitle``: a screen updates it with what it found or
    what went wrong, and a long message wraps under itself.
    """

    def __init__(self, title: str, status: RenderableType) -> None:
        """Create the headline.

        Args:
            title: What the screen is for.
            status: What to do here, or what the screen found.
        """
        super().__init__(
            Label(f"{title}:", id="title"), Static(status, id="subtitle"), id="headline"
        )


class Columns(Horizontal):
    """Blocks side by side, one cell apart."""


class Column(Vertical):
    """Blocks stacked one row apart.

    A panel's bottom rule is its row, so the panel under it draws no top rule.
    A ``Section`` ends in a blank row, and the ``ActionBar`` last in a column
    ends a row early, level with the last row of the panel beside it.
    """


class Section(Vertical):
    """A headed group of controls that stands in a column under its panels."""


class PanelTitle(Static):
    """A panel's title row, whose tab names are links in their own colors.

    Textual paints every link in one color, so a shown tab would read like
    the others. A link under the pointer is underlined instead.
    """

    @property
    def link_style(self) -> Style:
        """Leaves a link's own style alone."""
        return Style()

    @property
    def link_style_hover(self) -> Style:
        """Underlines the link under the pointer."""
        return Style(underline=True)


class Panel(Vertical):
    """A titled panel, ruled above and below, with its title under the top rule.

    The rules hug the panel's filled contents, so a title never breaks them.
    """

    def __init__(
        self,
        title: str,
        *children: Widget,
        id: str | None = None,  # noqa: A002 - Textual's name
    ) -> None:
        """Create the panel.

        Args:
            title: The panel's name, shown in capitals.
            *children: The panel's contents, below the title.
            id: The widget's id.
        """
        super().__init__(
            PanelTitle(Content(title.upper()), classes="panel-title"), *children, id=id
        )
        self.label = title.upper()

    def name_subject(self, subject: str | None) -> None:
        """Name what the panel shows, such as a path, beside its title.

        Args:
            subject: The name, which is data and never read as markup, or
                ``None`` to show the title alone.
        """
        title = Content(self.label)
        if subject is not None:
            title = Content.assemble(title, "  ", (subject, FOREGROUND))
        self.retitle(title)

    def retitle(self, title: Content) -> None:
        """Replace the title, which may carry data such as a path.

        Args:
            title: The new title; Content never reads its text as markup.
        """
        self.query_one(PanelTitle).update(title)


@dataclass(frozen=True)
class Tab:
    """One pane of a ``TabbedPanel``.

    Attributes:
        id: The pane's widget id.
        title: The pane's name in the panel's title.
        key: The key that shows it, bound by the screen to ``tab(id)``.
    """

    id: str
    title: str
    key: str


class TabbedPanel(Panel):
    """A panel showing one of its panes, every pane named in its title.

    Each name carries its key; the screen binds that key, and a click on the
    name, to its ``tab`` action. A pane can carry a short note beside its name,
    such as how many of its rows still wait on the user.
    """

    def __init__(
        self,
        tabs: Sequence[Tab],
        *panes: Widget,
        id: str | None = None,  # noqa: A002 - Textual's name
    ) -> None:
        """Create the panel, showing the first pane.

        Args:
            tabs: One tab per pane, in the same order.
            *panes: The panes, each with its tab's id.
            id: The widget's id.
        """
        super().__init__("", ContentSwitcher(*panes, initial=tabs[0].id), id=id)
        self.tabs = tuple(tabs)
        self.active = tabs[0].id
        self._hidden: set[str] = set()
        self._notes: dict[str, str] = {}

    def on_mount(self) -> None:
        """Name the tabs."""
        self._retitle()

    def show(self, tab: str) -> None:
        """Show a pane.

        Args:
            tab: The pane's id.
        """
        self.active = tab
        self.query_one(ContentSwitcher).current = tab
        self._retitle()

    def hide(self, tab: str, hidden: bool = True) -> None:
        """Hide or restore a pane's tab; hiding the shown pane shows the first left.

        Args:
            tab: The pane's id.
            hidden: Whether to hide it.
        """
        if hidden:
            self._hidden.add(tab)
        else:
            self._hidden.discard(tab)
        if self.active in self._hidden:
            self.show(next(t.id for t in self.tabs if t.id not in self._hidden))
        else:
            self._retitle()

    def is_shown(self, tab: str) -> bool:
        """Returns whether a pane's tab is offered."""
        return tab not in self._hidden

    def note(self, tab: str, note: str) -> None:
        """Set the note beside a pane's name, or clear it with an empty one.

        Args:
            tab: The pane's id.
            note: The note.
        """
        self._notes[tab] = note
        self._retitle()

    def _retitle(self) -> None:
        parts: list[Content | tuple[str, str] | str] = []
        for tab in self.tabs:
            if tab.id in self._hidden:
                continue
            if parts:
                parts.append("   ")
            click = f" @click=screen.tab('{tab.id}')"
            lit = tab.id == self.active
            # The shown tab takes the title's color, which lights with focus.
            parts.append((tab.title.upper(), ("" if lit else TEXT_FAINT) + click))
            if note := self._notes.get(tab.id):
                parts.append((f" {note}", ACCENT + click))
            parts.append((f" {tab.key}", KEY + click))
        self.retitle(Content.assemble(*parts))


class Heading(Static):
    """An uppercase section label followed by a rule to the panel's edge.

    A section whose controls share an action shows it, and its key, at the
    rule's end.
    """

    def __init__(self, label: str, *, key: tuple[str, str] | None = None) -> None:
        """Create the heading.

        Args:
            label: The section's name.
            key: The action its controls share and the key for it.
        """
        super().__init__(classes="section")
        self.label = label
        self.key = key

    def render(self) -> Content:
        """Render the label, then a hairline across the remaining width."""
        title = self.label.upper()
        tail = Content.assemble(" ", key_hint(*self.key)) if self.key else Content()
        rule = "─" * max(
            0, self.content_region.width - len(title) - 1 - tail.cell_length
        )
        return Content.assemble((title, TITLE), " ", (rule, RULE), tail)
