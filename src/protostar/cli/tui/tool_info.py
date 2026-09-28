"""What a tool does, on demand: a tooltip on hover and a popup on ``i``.

Both read the tool's ``ToolInfo``, the record ``--help`` reads too. Only a
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

from protostar.modules import TOOLING_MODULES, ToolInfo, ToolModule
from protostar.recipe import Tool

from .keys import Choice, Toggle, key_label

TOOL_INFO_KEY: tuple[str, str] = ("i", "What the focused tool does to the project")
"""The keybindings row for every screen with tool controls."""

TOOL_GROUPS: dict[str, tuple[Tool, ...]] = {
    "Quality": (
        Tool.RUFF,
        Tool.MYPY,
        Tool.TY,
        Tool.PYREFLY,
        Tool.PYTEST,
        Tool.RUMDL,
        Tool.MARKDOWNLINT,
    ),
    "Automation": (
        Tool.CI,
        Tool.RELEASE,
        Tool.DOCKER,
        Tool.COMMITIZEN,
        Tool.RENOVATE,
        Tool.CODECOV,
    ),
    "Documentation & workspace": (
        Tool.ZENSICAL,
        Tool.READTHEDOCS,
        Tool.DIRENV,
        Tool.JUST,
        Tool.AGENTS,
        Tool.COMMUNITY,
    ),
}
"""Every tool with its own checkbox, by purpose; hook managers are a choice."""

_MODULES = {Tool(module.config_key): module for module in TOOLING_MODULES}


def tool_module(tool: Tool) -> ToolModule:
    """Returns the module that sets up the tool.

    Args:
        tool: The tool.

    Returns:
        Its tooling module, which carries its ``ToolInfo``.
    """
    return _MODULES[tool]


def prose(text: str) -> Content:
    """Renders copy whose backticked spans are commands, in the accent colour.

    Args:
        text: The copy, with commands in backticks.

    Returns:
        The copy, ready for a widget.
    """
    return Content.assemble(
        *(
            (part, "$accent") if index % 2 else part
            for index, part in enumerate(text.split("`"))
        )
    )


def _joined(items: tuple[str, ...]) -> list[tuple[str, str] | str]:
    """Lists paths in the accent colour, as data, never markup."""
    parts: list[tuple[str, str] | str] = []
    for index, item in enumerate(items):
        if index:
            parts.append(", ")
        parts.append((item, "$accent"))
    return parts


class ToolInfoScreen(ModalScreen[None]):
    """A tool's summary, where the project already uses it, what it adds, and its docs."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("o", "open_docs", "Open docs"),
    ]

    def __init__(
        self,
        name: str,
        info: ToolInfo,
        *,
        found: tuple[str, ...] = (),
        notes: tuple[str, ...] = (),
    ) -> None:
        """Create the popup.

        Args:
            name: The tool's display name.
            info: What the tool does.
            found: What shows the project already uses it.
            notes: What else analysis saw that concerns it.
        """
        super().__init__()
        self.tool_name = name
        self.info = info
        self.found = found
        self.notes = notes

    @classmethod
    def of(
        cls, tool: Tool, *, found: tuple[str, ...] = (), notes: tuple[str, ...] = ()
    ) -> "ToolInfoScreen":
        """Create the popup for a tooling module's tool.

        Args:
            tool: The tool.
            found: What shows the project already uses it.
            notes: What else analysis saw that concerns it.

        Returns:
            The popup, showing its module's ``info``.
        """
        module = tool_module(tool)
        return cls(module.name, module.info, found=found, notes=notes)

    def compose(self) -> ComposeResult:
        """Compose the information and the two keys that leave it."""
        info = self.info
        with Vertical(id="dialog"):
            yield Static(Text(self.tool_name.upper()), classes="dialog-title")
            yield Label(prose(info.summary), classes="question")
            if self.found or self.notes:
                yield Static(
                    Text("IN THIS PROJECT", style="bold"), classes="info-heading"
                )
                if self.found:
                    yield Static(
                        Content.assemble(
                            "Found in ",
                            *_joined(self.found),
                            ". Protostar merges its settings into what is "
                            "there and keeps yours.",
                        )
                    )
                for note in self.notes:
                    yield Static(Content(note))
            yield Static(Text("ADDS", style="bold"), classes="info-heading")
            yield Static(prose(info.adds))
            yield Static(Text("DAY TO DAY", style="bold"), classes="info-heading")
            yield Static(prose(info.workflow))
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
        self.app.open_url(self.info.docs_url)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Answer the clicked button."""
        if event.button.id == "docs":
            self.action_open_docs()
        else:
            self.dismiss()


class InfoToggle(Toggle):
    """A checkbox with its tool's summary on hover and its details on ``i``."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("i", "tool_info", "Tool info"),
    ]

    def __init__(
        self,
        label: ContentText,
        name: str,
        info: ToolInfo,
        *,
        value: bool = False,
        id: str | None = None,  # noqa: A002 - Textual's name
        found: tuple[str, ...] = (),
        notes: tuple[str, ...] = (),
    ) -> None:
        """Create the checkbox.

        Args:
            label: The checkbox's label.
            name: The display name of the tool it switches on or off.
            info: What that tool does.
            value: Whether it starts checked.
            id: The widget's id.
            found: What shows the project already uses the tool.
            notes: What else analysis saw that concerns it.
        """
        super().__init__(label, value, id=id)
        self.tool_name = name
        self.info = info
        self.found = found
        self.notes = notes
        self.tooltip = info.summary

    def action_tool_info(self) -> None:
        """Show what the tool does, and where the project already uses it."""
        self.app.push_screen(
            ToolInfoScreen(
                self.tool_name, self.info, found=self.found, notes=self.notes
            )
        )


class ToolToggle(InfoToggle):
    """A tooling module's checkbox."""

    def __init__(
        self,
        label: ContentText,
        tool: Tool,
        *,
        value: bool = False,
        id: str | None = None,  # noqa: A002 - Textual's name
        found: tuple[str, ...] = (),
        notes: tuple[str, ...] = (),
    ) -> None:
        """Create the checkbox.

        Args:
            label: The checkbox's label.
            tool: The tool it switches on or off.
            value: Whether it starts checked.
            id: The widget's id.
            found: What shows the project already uses the tool.
            notes: What else analysis saw that concerns it.
        """
        module = tool_module(tool)
        super().__init__(
            label,
            module.name,
            module.info,
            value=value,
            id=id,
            found=found,
            notes=notes,
        )
        self.tool = tool


class ToolRadio(RadioButton):
    """A radio button that chooses a tool, with its summary on hover."""

    def __init__(
        self,
        label: ContentText,
        tool: Tool,
        *,
        value: bool = False,
        id: str | None = None,  # noqa: A002 - Textual's name
        found: tuple[str, ...] = (),
    ) -> None:
        """Create the button.

        Args:
            label: The button's label.
            tool: The tool it chooses.
            value: Whether it starts pressed.
            id: The widget's id.
            found: What shows the project already uses the tool.
        """
        super().__init__(label, value, id=id)
        self.tool = tool
        self.found = found
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
            self.app.push_screen(ToolInfoScreen.of(button.tool, found=button.found))
