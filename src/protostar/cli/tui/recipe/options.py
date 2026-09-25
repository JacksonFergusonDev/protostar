"""Template option controls: a toggle per bool option, a choice per choice option."""

from collections.abc import Mapping

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Checkbox, Label, RadioButton, RadioSet, Static

from protostar.config import TemplateSource
from protostar.errors import InvalidOptionValueError, ProtostarError
from protostar.init_draft import InitDraft
from protostar.options import OptionValue, TemplateOption

from ..chrome import Heading
from ..keys import Choice, Toggle


def draft_options(draft: InitDraft) -> dict[str, OptionValue]:
    """Returns the option values a draft carries over the recorded ones."""
    recorded = dict(draft.existing_recipe.options) if draft.existing_recipe else {}
    return {
        **recorded,
        **dict(draft.option_overrides),
        **dict(draft.option_choices or ()),
    }


class OptionFields(Vertical):
    """One control per template option; every value starts at its default."""

    class Changed(Message):
        """An option's value changed, so the preview is stale."""

    def __init__(self, values: Mapping[str, OptionValue]) -> None:
        super().__init__()
        self.options: dict[str, TemplateOption] = {}
        # A choice survives a template switch for an option of the same name
        # that can still hold it.
        self._chosen = dict(values)

    def compose(self) -> ComposeResult:
        """Compose a labelled control and its description for each option."""
        yield Heading("Template options")
        for option in self.options.values():
            value = self.value(option)
            if option.choices:
                yield Label(option.name, classes="field-label")
                if option.description:
                    yield Static(Text(option.description), classes="note")
                with Choice(id=f"option-{option.name}"):
                    for index, choice in enumerate(option.choices):
                        yield RadioButton(
                            Text(choice),
                            value=choice == value,
                            id=f"option-{option.name}-{index}",
                        )
                continue
            yield Toggle(
                Text(option.name), value=value is True, id=f"option-{option.name}"
            )
            if option.description:
                yield Static(Text(option.description), classes="note")

    async def show(self, source: TemplateSource | None) -> None:
        """Replace the controls with those of a newly chosen template."""
        try:
            self.options = source.options if source else {}
        except ProtostarError:
            # The preview reports an invalid declaration.
            self.options = {}
        self.display = bool(self.options)
        await self.recompose()

    def value(self, option: TemplateOption) -> OptionValue:
        """Returns the option's chosen value, or its default if it can't hold it."""
        try:
            return option.check(self._chosen.get(option.name, option.default))
        except InvalidOptionValueError:
            return option.default

    @property
    def values(self) -> dict[str, OptionValue]:
        """Every shown option's value, by name."""
        return {name: self.value(option) for name, option in self.options.items()}

    @on(Checkbox.Changed)
    def _toggle(self, event: Checkbox.Changed) -> None:
        event.stop()
        name = str(event.checkbox.id).removeprefix("option-")
        self._chosen[name] = event.value
        self.post_message(self.Changed())

    @on(RadioSet.Changed)
    def _choose(self, event: RadioSet.Changed) -> None:
        event.stop()
        name = str(event.radio_set.id).removeprefix("option-")
        index = int(str(event.pressed.id).rsplit("-", 1)[1])
        self._chosen[name] = self.options[name].choices[index]
        self.post_message(self.Changed())
