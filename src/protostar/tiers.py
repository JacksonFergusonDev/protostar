"""Template tiers: how much tooling a template's shape starts with.

A template is a project shape: a command-line tool, a web service, an analysis
workbench. A tier is a separate switch on that shape. ``workbench`` is lean,
for exploring and analyzing; ``production`` is the full quality gate, for
building something to publish. A template declares both tiers or neither, each
as a table of tool flags laid over its root flags, and names the one it
defaults to. Content that only one tier needs opts in with
``requires = "tier=production"``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .errors import ConfigurationError

TIER_TERM: Final[str] = "tier"
"""The name a ``requires`` term uses for the tier, as in ``tier=production``."""


class Tier(StrEnum):
    """How much tooling a template starts with."""

    WORKBENCH = "workbench"
    PRODUCTION = "production"


@dataclass(frozen=True)
class TemplateTiers:
    """The tiers a template declares.

    Attributes:
        default: The tier a project that never chose follows.
        workbench: The workbench tier's tool flags, by key.
        production: The production tier's tool flags, by key.
    """

    default: Tier
    workbench: tuple[tuple[str, bool], ...]
    production: tuple[tuple[str, bool], ...]

    def flags(self, tier: Tier) -> dict[str, bool]:
        """Returns one tier's tool flags, by key."""
        return dict(self.workbench if tier is Tier.WORKBENCH else self.production)

    def to_dict(self) -> dict[str, object]:
        """Returns deterministic public data: the default and each tier's flags."""
        return {
            "default": self.default.value,
            **{tier.value: dict(sorted(self.flags(tier).items())) for tier in Tier},
        }


def template_opinions(
    root: Mapping[str, bool], tiers: TemplateTiers | None, tier: Tier | None
) -> dict[str, bool]:
    """Returns a template's tool opinions: its root flags, then the tier's.

    Args:
        root: The flags the template sets at its root.
        tiers: The template's tiers, if it declares any.
        tier: The chosen tier, or None for the template's default.

    Returns:
        The tool flags the template sets, by key.
    """
    if tiers is None:
        return dict(root)
    return {**root, **tiers.flags(tier or tiers.default)}


def resolve_tier(tiers: TemplateTiers | None, chosen: Tier | None) -> Tier | None:
    """Returns the tier a project follows: the chosen one, or the default.

    Args:
        tiers: The template's tiers, if it declares any.
        chosen: The tier the project chose, if any.

    Returns:
        The tier, or None when the template declares no tiers.

    Raises:
        ConfigurationError: If a tier is chosen for a template without tiers.
    """
    if tiers is None:
        if chosen is not None:
            raise ConfigurationError(
                "The template declares no tiers.",
                hint="Remove --tier: this template has no workbench or production "
                "tier to choose between.",
            )
        return None
    return chosen or tiers.default


def parse_tier(raw: object, location: str) -> Tier:
    """Reads a tier's name.

    Args:
        raw: The value given.
        location: Where it appears, for errors.

    Returns:
        The tier.

    Raises:
        ConfigurationError: If the value names no tier.
    """
    for tier in Tier:
        if raw == tier.value:
            return tier
    raise ConfigurationError(
        f"{location} names no tier: {raw!r}.",
        hint=f"Use one of: {', '.join(tier.value for tier in Tier)}.",
    )


def parse_tiers(data: Mapping[str, object], source: str) -> TemplateTiers | None:
    """Parses a template's root ``tier`` and its ``[tiers]`` tables.

    A tier may set any flag the template's root may: every tool, and ``docker``.

    Args:
        data: The template's root table.
        source: The template, for errors.

    Returns:
        The tiers, or None when the template declares none.

    Raises:
        ConfigurationError: If only one of ``tier`` and ``[tiers]`` is given,
            either tier is missing, a tier sets something other than a known
            flag, the tiers set different flags, or a flag is also set at the
            root.
    """
    # Local import: recipe sits above this module in the import graph.
    from .recipe import Tool

    known = {tool.value for tool in Tool} | {"docker"}
    where = f"configuration source '{source}'"
    hint = (
        'Declare tier = "workbench" or "production" as the default, and both '
        "[tiers.workbench] and [tiers.production] with the same tool flags."
    )
    if "tier" not in data and "tiers" not in data:
        return None
    if "tier" not in data or "tiers" not in data:
        raise ConfigurationError(
            f"The tiers in {where} need both a default tier and [tiers].", hint=hint
        )
    default = parse_tier(data["tier"], f"The default tier in {where}")
    raw = data["tiers"]
    if not isinstance(raw, dict) or set(raw) != {tier.value for tier in Tier}:
        raise ConfigurationError(
            f"The [tiers] table in {where} must declare exactly workbench and "
            "production.",
            hint=hint,
        )
    flags: dict[Tier, dict[str, bool]] = {}
    for tier in Tier:
        table = raw[tier.value]
        if not isinstance(table, dict) or not table:
            raise ConfigurationError(
                f"[tiers.{tier.value}] in {where} must be a table of tool flags.",
                hint=hint,
            )
        unknown = sorted(
            key
            for key, value in table.items()
            if key not in known or not isinstance(value, bool)
        )
        if unknown:
            raise ConfigurationError(
                f"[tiers.{tier.value}] in {where} sets what is not a tool flag: "
                f"{', '.join(unknown)}.",
                hint=f"Set tools to true or false: {', '.join(sorted(known))}.",
            )
        flags[tier] = table
    if flags[Tier.WORKBENCH].keys() != flags[Tier.PRODUCTION].keys():
        uneven = sorted(flags[Tier.WORKBENCH].keys() ^ flags[Tier.PRODUCTION].keys())
        raise ConfigurationError(
            f"The tiers in {where} set different tools: {', '.join(uneven)}.",
            hint="Set each of these in both tiers, or at the root when both "
            "tiers agree.",
        )
    both = sorted(
        key for key in flags[Tier.WORKBENCH] if isinstance(data.get(key), bool)
    )
    if both:
        raise ConfigurationError(
            f"{where.capitalize()} sets {', '.join(both)} both at the root and in "
            "its tiers.",
            hint="Set a tool at the root when both tiers agree, or in both tiers "
            "when they differ.",
        )
    return TemplateTiers(
        default,
        tuple(sorted(flags[Tier.WORKBENCH].items())),
        tuple(sorted(flags[Tier.PRODUCTION].items())),
    )
