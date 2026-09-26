"""The frame every decision screen shares: a masthead, panels, and headings."""

from rich.console import RenderableType
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.widget import Widget
from textual.widgets import Label, Static

from protostar.cli.palette import MARK


class Masthead(Static):
    """The top bar: the mark, the product, and where the user is."""

    def __init__(self, *path: str) -> None:
        """Create the bar.

        Args:
            *path: The command and the screen's phase, outermost first.
        """
        super().__init__()
        self.path = path

    def render(self) -> Content:
        """Render the mark and the product, then the path with its last step lit."""
        parts: list[Content | str | tuple[str, str]] = [
            (MARK, "bold $accent"),
            " ",
            ("PROTOSTAR", "bold"),
            ("   ", ""),
        ]
        for index, step in enumerate(self.path):
            if index:
                parts.append(("  /  ", "$hairline"))
            last = index == len(self.path) - 1
            parts.append((step, "$foreground" if last else "$text-faint"))
        return Content.assemble(*parts)


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
            Static(Content(title.upper()), classes="panel-title"), *children, id=id
        )

    def retitle(self, title: Content) -> None:
        """Replace the title, which may carry data such as a path.

        Args:
            title: The new title; Content never reads its text as markup.
        """
        self.query_one(".panel-title", Static).update(title)


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
        tail = (
            Content.assemble(
                " ", (self.key[0], "$text-faint"), "  ", (self.key[1], "dim")
            )
            if self.key
            else Content()
        )
        rule = "─" * max(
            0, self.content_region.width - len(title) - 1 - tail.cell_length
        )
        return Content.assemble((title, "bold $accent"), " ", (rule, "$hairline"), tail)
