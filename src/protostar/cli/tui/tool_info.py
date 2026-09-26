"""What a tool does, on demand: a tooltip on hover and a popup on ``i``.

Both read the module's ``ToolInfo``, the record ``--help`` reads too. Only a
focused tool control binds ``i``, so typing it into a text field inserts it.
"""

from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.content import Content, ContentText
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RadioButton, Static

from protostar.modules import TOOLING_MODULES, BootstrapModule
from protostar.recipe import Tool

from .keys import Choice, Toggle, key_label

TOOL_INFO_KEY: tuple[str, str] = ("i", "What the focused tool does to the project")
"""The keybindings row for every screen with tool controls."""

_MODULES = {Tool(module.config_key): module for module in TOOLING_MODULES}


def tool_module(tool: Tool) -> BootstrapModule:
    """Returns the module that sets up the tool.

    Args:
        tool: The tool.

    Returns:
        Its tooling module, which carries its ``ToolInfo``.
    """
    return _MODULES[tool]


def _prose(text: str) -> Content:
    """Renders copy whose backticked spans are commands, in the accent colour."""
    return Content.assemble(
        *(
            (part, "$accent") if index % 2 else part
            for index, part in enumerate(text.split("`"))
        )
    )


class ToolInfoScreen(ModalScreen[None]):
    """A tool's summary, what it adds, what changes day to day, and its docs."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("o", "open_docs", "Open docs"),
    ]

    def __init__(self, module: BootstrapModule) -> None:
        """Create the popup.

        Args:
            module: The tooling module whose ``info`` to show.
        """
        super().__init__()
        self.module = module

    def compose(self) -> ComposeResult:
        """Compose the information and the two keys that leave it."""
        info = self.module.info
        with Vertical(id="dialog"):
            yield Static(Text(self.module.name.upper()), classes="dialog-title")
            yield Label(_prose(info.summary), classes="question")
            yield Static(Text("ADDS", style="bold"), classes="info-heading")
            yield Static(_prose(info.adds))
            yield Static(Text("DAY TO DAY", style="bold"), classes="info-heading")
            yield Static(_prose(info.workflow))
            yield Static(Text(info.docs_url, style="dim"), classes="note")
            with Horizontal(classes="dialog-actions"):
                close = Button(key_label("Close", "esc"), id="close")
                docs = Button(key_label("Open docs", "o"), id="docs")
                # Keys answer directly, as in every dialog.
                close.can_focus = docs.can_focus = False
                yield close
                yield docs

    def action_open_docs(self) -> None:
        """Open the tool's documentation in the browser."""
        self.app.open_url(self.module.info.docs_url)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Answer the clicked button."""
        if event.button.id == "docs":
            self.action_open_docs()
        else:
            self.dismiss()


class ToolToggle(Toggle):
    """A tool's checkbox, with its summary on hover and its details on ``i``."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("i", "tool_info", "Tool info"),
    ]

    def __init__(
        self,
        label: ContentText,
        tool: Tool,
        *,
        value: bool = False,
        id: str | None = None,  # noqa: A002 - Textual's name
    ) -> None:
        """Create the checkbox.

        Args:
            label: The checkbox's label.
            tool: The tool it switches on or off.
            value: Whether it starts checked.
            id: The widget's id.
        """
        super().__init__(label, value, id=id)
        self.tool = tool
        self.tooltip = tool_module(tool).info.summary

    def action_tool_info(self) -> None:
        """Show what the tool does."""
        self.app.push_screen(ToolInfoScreen(tool_module(self.tool)))


class ToolRadio(RadioButton):
    """A radio button that chooses a tool, with its summary on hover."""

    def __init__(
        self,
        label: ContentText,
        tool: Tool,
        *,
        value: bool = False,
        id: str | None = None,  # noqa: A002 - Textual's name
    ) -> None:
        """Create the button.

        Args:
            label: The button's label.
            tool: The tool it chooses.
            value: Whether it starts pressed.
            id: The widget's id.
        """
        super().__init__(label, value, id=id)
        self.tool = tool
        self.tooltip = tool_module(tool).info.summary


class ToolChoice(Choice):
    """Radio buttons choosing between tools; ``i`` explains the highlighted one."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("i", "tool_info", "Tool info"),
    ]

    def _highlighted(self) -> ToolRadio | None:
        if self._selected is None:
            return None
        button = self._nodes[self._selected]
        return button if isinstance(button, ToolRadio) else None

    def watch__selected(self) -> None:
        """Offer ``i`` only while a tool, not a "None" option, is highlighted."""
        super().watch__selected()
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Hide ``i`` while no tool is highlighted."""
        if action == "tool_info":
            return self._highlighted() is not None
        return True

    def action_tool_info(self) -> None:
        """Show what the highlighted tool does."""
        if button := self._highlighted():
            self.app.push_screen(ToolInfoScreen(tool_module(button.tool)))
