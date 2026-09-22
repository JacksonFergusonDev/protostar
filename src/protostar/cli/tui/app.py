"""Full-screen decision app; execution belongs to the CLI after exit."""

from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType

from protostar.config import UserConfig
from protostar.init_draft import InitDraft
from protostar.templates import TemplateInfo

from .recipe.screen import RecipeScreen


class RecipeApp(App[InitDraft]):
    """Edit a recipe and exit with an immutable draft."""

    CSS_PATH = "protostar.tcss"
    TITLE = "Protostar"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel", show=False, priority=True),
    ]

    def __init__(
        self, draft: InitDraft, catalog: list[TemplateInfo], config: UserConfig
    ) -> None:
        super().__init__()
        self.theme = "textual-dark"
        self.recipe_screen = RecipeScreen(draft, catalog, config)

    def on_mount(self) -> None:
        """Open the recipe editor without starting engine execution."""
        self.push_screen(self.recipe_screen)

    def action_cancel(self) -> None:
        """Leave the app without a result."""
        self.exit(None)
