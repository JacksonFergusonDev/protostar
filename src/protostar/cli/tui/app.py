"""Full-screen decision app; execution belongs to the CLI after exit."""

from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType
from textual.screen import Screen

from protostar.cli.palette import ANSI
from protostar.errors import ProtostarError

from .theme import PROTOSTAR


class DecisionApp[ResultT](App[ResultT]):
    """Run one decision flow and exit with its immutable result.

    A screen that meets an error no choice on it can fix leaves through
    ``fail``, and ``decide`` raises it once the terminal is restored.
    """

    CSS_PATH = "protostar.tcss"
    TITLE = "Protostar"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = [
        # A screen asks before leaving; one with somewhere to go back to binds
        # escape itself.
        Binding("escape", "screen.cancel", "Cancel", show=False),
        Binding("ctrl+c", "abort", "Quit", show=False, priority=True),
    ]

    def __init__(
        self, screen: Screen[ResultT], *, exit_after_first_frame: bool = False
    ) -> None:
        super().__init__()
        self.register_theme(PROTOSTAR)
        self.theme = PROTOSTAR.name
        self.ansi_theme_dark = ANSI
        self.decision_screen = screen
        self.exit_after_first_frame = exit_after_first_frame
        self.failure: ProtostarError | None = None

    def decide(self) -> ResultT | None:
        """Run the flow and return its result, or None on cancellation.

        Raises:
            ProtostarError: The error a screen left with through ``fail``.
        """
        result = self.run()
        if self.failure is not None:
            raise self.failure
        return result

    def fail(self, error: ProtostarError) -> None:
        """Leave without a result, handing the error to the CLI to report.

        Args:
            error: The error, with its hint, that the CLI prints.
        """
        self.failure = error
        self.exit(None)

    def on_mount(self) -> None:
        """Open the first decision screen without starting engine execution."""
        self.push_screen(self.decision_screen)
        if self.exit_after_first_frame:
            self.call_after_refresh(self.exit, None)

    def action_abort(self) -> None:
        """Leave at once without a result; ctrl+c never asks."""
        self.exit(None)
