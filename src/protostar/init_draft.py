"""Shared init input and resolution for command-line and interactive callers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, cast

from .config import TemplateSource, UserConfig
from .manifest import CollisionStrategy, ProjectMetadata
from .models import InitRequest
from .modules import BootstrapModule, PythonCore, SystemWorkspaceModule
from .recipe import (
    ProjectRecipe,
    RecipeIntent,
    Tool,
    decode_recipe,
    establish_recipe,
    select_tooling,
)


@dataclass(frozen=True)
class DraftTemplate:
    """An acquired template and the trust facts established by its caller."""

    source: TemplateSource
    is_external: bool = False
    is_user_aliased: bool = False
    is_trusted: bool = False


@dataclass(frozen=True)
class InitDraft:
    """Unresolved init choices shared by flags and the interactive editor."""

    template: DraftTemplate | None = None
    tool_overrides: tuple[tuple[Tool, bool], ...] = ()
    tool_choices: tuple[tuple[Tool, bool], ...] | None = None
    docker: bool | None = None
    python_version: str | None = None
    metadata: tuple[tuple[str, str | tuple[str, ...]], ...] | None = None
    variables: tuple[tuple[str, str], ...] = ()
    collision_strategy: CollisionStrategy | None = None
    existing_recipe: ProjectRecipe | None = None


def resolve_init(
    draft: InitDraft, user_config: UserConfig
) -> tuple[list[BootstrapModule], InitRequest]:
    """Resolve a draft into one reproducible recipe, module stack, and request."""
    existing = draft.existing_recipe
    config = (
        replace(user_config, python_version=existing.python, ide=existing.ide)
        if existing
        else user_config
    )
    source = draft.template.source if draft.template else None
    context = existing.rendering_context() if existing else {}
    variables = {
        name: value
        for name, value in (existing.variables if existing else ())
        if source and name in source.variables
    }
    variables.update(draft.variables)
    blueprint = source.render({**context, **variables}) if source else None
    opinions = blueprint.tooling_overrides if blueprint else {}

    fallback = (
        dict(existing.fallback)
        if existing
        else {tool: bool(getattr(config, tool)) for tool in Tool}
    )
    overrides = {
        **(dict(existing.tools) if existing else {}),
        **dict(draft.tool_overrides),
    }
    if draft.tool_choices is not None:
        overrides = {
            tool: enabled
            for tool, enabled in draft.tool_choices
            if enabled != opinions.get(tool.value, fallback[tool])
        }
    selection_recipe = establish_recipe(config)
    selection_recipe = replace(
        selection_recipe,
        tools=tuple(sorted(overrides.items())),
        fallback=tuple(sorted(fallback.items())),
    )
    tooling = select_tooling(selection_recipe, opinions)
    if draft.metadata is None:
        from .metadata import resolve_auto_metadata

        required = {key for module in tooling for key in module.required_metadata}
        metadata: dict[str, Any] = resolve_auto_metadata(required, config=config)
        if existing:
            metadata = {
                key: list(value) if isinstance(value, tuple) else value
                for key, value in existing.metadata
            }
    else:
        metadata = {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in draft.metadata
        }

    template_docker = bool(opinions.get("docker", False))
    docker = (
        draft.docker
        if draft.docker is not None
        else existing.docker
        if existing
        else template_docker
    )
    recipe = establish_recipe(
        config,
        RecipeIntent(
            blueprint.reference if blueprint else None,
            cast(ProjectMetadata, metadata),
            docker,
            draft.python_version,
            tuple(sorted(variables.items())),
        ),
    )
    recipe = replace(
        recipe,
        tools=tuple(sorted(overrides.items())),
        fallback=tuple(sorted(fallback.items())),
        context=existing.context if existing else recipe.context,
    )
    if draft.python_version:
        resolved_context = dict(recipe.context)
        resolved_context["PYTHON_VERSION"] = draft.python_version
        recipe = replace(recipe, context=tuple(sorted(resolved_context.items())))
    recipe = decode_recipe(recipe.to_dict())

    core = PythonCore(
        python_version=recipe.python,
        project_license=str(metadata["license"]) if metadata.get("license") else None,
    )
    modules: list[BootstrapModule] = [SystemWorkspaceModule(), core, *tooling]
    template = draft.template
    request = InitRequest(
        recipe=recipe,
        python_version=recipe.python,
        template_blueprint=blueprint,
        template_reference=blueprint.reference if blueprint else None,
        docker=docker,
        collision_strategy=draft.collision_strategy,
        metadata=metadata,
        is_external=template.is_external if template else False,
        is_user_aliased=template.is_user_aliased if template else False,
        is_trusted=template.is_trusted if template else False,
    )
    return modules, request
