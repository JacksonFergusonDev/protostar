"""Lazy entry point: importing this module never imports Textual."""

from protostar.config import UserConfig
from protostar.init_draft import InitDraft
from protostar.templates import TemplateInfo


def edit_recipe(
    draft: InitDraft, catalog: list[TemplateInfo], config: UserConfig
) -> InitDraft | None:
    """Run the decision app and return its draft, or None on cancellation."""
    from .app import RecipeApp

    return RecipeApp(draft, catalog, config).run()
