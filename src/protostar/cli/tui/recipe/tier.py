"""The tier control: workbench or production, directly under the template.

It shows only while the chosen template declares tiers. ``i`` on it explains
what each tier turns on for that template, read from the template's own flags.
"""

from typing import ClassVar

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RadioButton, RadioSet, Static

from protostar.recipe import Tool
from protostar.tiers import TemplateTiers, Tier

from ..keys import Choice, key_label
from ..tool_info import prose, tool_module

TIER_INFO_KEY: tuple[str, str] = ("i", "What each tier turns on, on the tier")
"""The keybindings row for a screen with the tier control."""

_PURPOSE = {
    Tier.WORKBENCH: "lean, for exploring",
    Tier.PRODUCTION: "full quality gate, for publishing",
}

_ABOUT = {
    Tier.WORKBENCH: (
        "For trying ideas, analyzing data, and code only you run. It keeps the "
        "setup small: fewer checks to satisfy and less automation to learn."
    ),
    Tier.PRODUCTION: (
        "For code other people will install or rely on. It adds a quality gate: "
        "checks that run on every commit and every push, so a mistake is caught "
        "before it is released."
    ),
}

_WIDTH = max(len(tier.value) for tier in Tier) + 3


def _flag(key: str) -> tuple[str, str]:
    """Returns a tier flag's name and what it does."""
    module = tool_module(Tool(key))
    return module.name, module.info.summary


class TierInfoScreen(ModalScreen[None]):
    """What each of a template's tiers is for, and which tools only it turns on."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
    ]

    def __init__(self, tiers: TemplateTiers) -> None:
        """Create the popup.

        Args:
            tiers: The template's tiers.
        """
        super().__init__()
        self.tiers = tiers

    def compose(self) -> ComposeResult:
        """Compose each tier's purpose and the tools only it turns on."""
        with Vertical(id="dialog"):
            yield Static("TIERS", classes="dialog-title")
            yield Static(
                prose(
                    "How much tooling the project starts with. Both tiers build "
                    "the same kind of project; switch later with "
                    "`protostar sync --tier`."
                ),
                classes="question",
            )
            for tier in Tier:
                flags = self.tiers.flags(tier)
                other = self.tiers.flags(
                    Tier.PRODUCTION if tier is Tier.WORKBENCH else Tier.WORKBENCH
                )
                title = tier.value.upper()
                if tier is self.tiers.default:
                    title += " · DEFAULT"
                yield Static(Text(title, style="bold"), classes="info-heading")
                yield Static(_ABOUT[tier])
                only = sorted(
                    (
                        _flag(key)
                        for key, value in flags.items()
                        if value and not other[key]
                    )
                )
                if not only:
                    continue
                yield Static(Text("Turns on", style="dim"), classes="tier-turns-on")
                for name, summary in only:
                    with Horizontal(classes="tier-tool"):
                        yield Static(Text(name), classes="tier-tool-name")
                        yield Static(prose(summary))
            yield Static(
                Text("Press i on a tool for more about it.", style="dim"),
                classes="note",
            )
            with Horizontal(classes="dialog-actions"):
                close = Button(key_label("Close", "esc"), id="close")
                # Keys answer directly, as in every dialog.
                close.can_focus = False
                yield close

    def on_button_pressed(self) -> None:
        """Close on the clicked button."""
        self.dismiss()


class TierChoice(Choice):
    """The two tiers; ``i`` explains what each turns on."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("i", "tier_info", "Tier info"),
    ]

    def __init__(self, tiers: TemplateTiers) -> None:
        """Create the choice.

        Args:
            tiers: The template's tiers.
        """
        super().__init__(id="tier")
        self.tiers = tiers

    def action_tier_info(self) -> None:
        """Show what each tier turns on."""
        self.app.push_screen(TierInfoScreen(self.tiers))


class TierFields(Vertical):
    """The tier control, shown only for a template that declares tiers."""

    class Changed(Message):
        """The user chose a tier."""

        def __init__(self, tier: Tier) -> None:
            super().__init__()
            self.tier = tier

    def __init__(self) -> None:
        super().__init__()
        self.tiers: TemplateTiers | None = None
        self.tier: Tier | None = None

    def compose(self) -> ComposeResult:
        """Compose the label and one button per tier, the default marked."""
        if self.tiers is None:
            return
        yield Label(
            Content.assemble(
                "Tier  ", ("i", "$text-faint"), "  ", ("what each turns on", "dim")
            ),
            classes="field-label",
        )
        with TierChoice(self.tiers):
            for tier in Tier:
                parts: list[str | tuple[str, str]] = [
                    tier.value.capitalize().ljust(_WIDTH),
                    (_PURPOSE[tier], "$text-faint"),
                ]
                if tier is self.tiers.default:
                    parts.append((" · default", "$text-faint"))
                yield RadioButton(
                    Content.assemble(*parts),
                    value=tier is self.tier,
                    id=f"tier-{tier.value}",
                )

    async def show(self, tiers: TemplateTiers | None, tier: Tier | None) -> None:
        """Replace the control with the chosen template's tiers.

        Args:
            tiers: The template's tiers, or None when it declares none.
            tier: The tier to show pressed, or None for the default.
        """
        self.tiers = tiers
        self.tier = (tier or tiers.default) if tiers else None
        self.display = tiers is not None
        await self.recompose()

    @on(RadioSet.Changed)
    def _choose(self, event: RadioSet.Changed) -> None:
        event.stop()
        self.tier = Tier(str(event.pressed.id).removeprefix("tier-"))
        self.post_message(self.Changed(self.tier))
