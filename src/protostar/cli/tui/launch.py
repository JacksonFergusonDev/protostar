"""Lazy entry point: importing this module never imports Textual."""

from protostar.config import UserConfig
from protostar.init_draft import InitDecision, InitDraft
from protostar.templates import TemplateInfo


def edit_recipe(
    draft: InitDraft,
    catalog: list[TemplateInfo],
    config: UserConfig,
    *,
    exit_after_first_frame: bool = False,
) -> InitDecision | None:
    """Run the recipe editor and its change review, or return None on cancellation.

    Args:
        draft: The draft the editor starts from.
        catalog: Templates the editor offers.
        config: The user's configuration.
        exit_after_first_frame: Exit with None once the first frame is drawn,
            which the wizard benchmark measures.
    """
    from .app import DecisionApp
    from .recipe.screen import RecipeScreen

    return DecisionApp(
        RecipeScreen(draft, catalog, config),
        exit_after_first_frame=exit_after_first_frame,
    ).run()


def edit_variables(draft: InitDraft, config: UserConfig) -> InitDraft | None:
    """Collect a template's missing variables, or return None on cancellation."""
    from .app import DecisionApp
    from .recipe.variables import VariablesScreen

    return DecisionApp(VariablesScreen(draft, config)).run()


def review_changes(draft: InitDraft, config: UserConfig) -> InitDecision | None:
    """Review a draft's changes and settle its open decisions, or return None."""
    from .app import DecisionApp
    from .review.screen import ReviewScreen

    return DecisionApp(ReviewScreen(draft, config)).run()
