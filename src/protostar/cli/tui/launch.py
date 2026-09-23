"""Lazy entry point: importing this module never imports Textual."""

from protostar.config import UserConfig
from protostar.init_draft import InitDraft
from protostar.templates import TemplateInfo


def edit_recipe(
    draft: InitDraft, catalog: list[TemplateInfo], config: UserConfig
) -> InitDraft | None:
    """Run the recipe editor and return its draft, or None on cancellation."""
    from .app import DecisionApp
    from .recipe.screen import RecipeScreen

    return DecisionApp(RecipeScreen(draft, catalog, config)).run()


def edit_variables(draft: InitDraft, config: UserConfig) -> InitDraft | None:
    """Collect a template's missing variables, or return None on cancellation."""
    from .app import DecisionApp
    from .recipe.variables import VariablesScreen

    return DecisionApp(VariablesScreen(draft, config)).run()
