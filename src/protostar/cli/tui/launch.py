"""Lazy entry point: importing this module never imports Textual."""

from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING

from protostar.config import UserConfig
from protostar.init_draft import InitDecision, InitDraft
from protostar.merge import ResolutionChoice
from protostar.templates import TemplateInfo

if TYPE_CHECKING:
    from protostar.lifecycle import PreparedProject


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
    ).decide()


def edit_variables(
    draft: InitDraft,
    config: UserConfig,
    flagged: Collection[str] = (),
    *,
    command: str = "init",
) -> InitDraft | None:
    """Collect a template's variables, or return None on cancellation.

    Args:
        draft: The draft whose variables to collect.
        config: The user's configuration.
        flagged: Variables whose values the secret guard flagged; each must be
            changed or confirmed as not a secret.
        command: The command the screen collects them for.
    """
    from .app import DecisionApp
    from .recipe.variables import VariablesScreen

    return DecisionApp(
        VariablesScreen(draft, config, flagged, command=command)
    ).decide()


def review_changes(draft: InitDraft, config: UserConfig) -> InitDecision | None:
    """Review a draft's changes and settle its open decisions, or return None.

    Raises:
        ProtostarError: If the first review fails, since nothing on the screen
            could change its outcome.
    """
    from .app import DecisionApp
    from .review.screen import ReviewScreen

    return DecisionApp(ReviewScreen(draft, config)).decide()


def resolve_conflicts(project: PreparedProject) -> dict[str, ResolutionChoice] | None:
    """Choose how a sync's conflicts are settled, or return None on cancellation.

    Args:
        project: The prepared sync whose conflicts to settle.

    Returns:
        Choices keyed by conflict identity; conflicts left out stay open.
    """
    from .app import DecisionApp
    from .conflicts.screen import ConflictScreen

    return DecisionApp(ConflictScreen(project)).decide()
