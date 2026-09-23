"""Full-screen decision app; execution belongs to the CLI after exit."""

from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType
from textual.screen import Screen


class DecisionApp[ResultT](App[ResultT]):
    """Run one decision flow and exit with its immutable result."""

    CSS_PATH = "protostar.tcss"
    TITLE = "Protostar"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel", show=False, priority=True),
    ]

    def __init__(self, screen: Screen[ResultT]) -> None:
        super().__init__()
        self.theme = "textual-dark"
        self.decision_screen = screen

    def on_mount(self) -> None:
        """Open the first decision screen without starting engine execution."""
        self.push_screen(self.decision_screen)

    def action_cancel(self) -> None:
        """Leave the app without a result."""
        self.exit(None)
