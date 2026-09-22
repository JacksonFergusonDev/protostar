"""Project metadata fields, one widget per ``PromptType``."""

from collections.abc import Iterable, Mapping, Set
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, Select, SelectionList
from textual.widgets.selection_list import Selection

from protostar.config import UserConfig
from protostar.init_draft import InitDraft
from protostar.metadata import (
    METADATA_FIELDS,
    MetadataKey,
    PromptType,
    resolve_auto_metadata,
)
from protostar.modules import BootstrapModule

MetadataValue = str | tuple[str, ...]

# Asked for every project, whatever its tools.
_BASE_KEYS = frozenset(
    {
        MetadataKey.DESCRIPTION,
        MetadataKey.LICENSE,
        MetadataKey.AUTHOR_NAME,
        MetadataKey.AUTHOR_EMAIL,
        MetadataKey.GITHUB_USERNAME,
        MetadataKey.MINIMUM_PYTHON,
    }
)


def metadata_keys(
    modules: Iterable[BootstrapModule], *, docker: bool
) -> frozenset[MetadataKey]:
    """Returns the metadata the enabled tooling modules and Docker read."""
    keys = set(_BASE_KEYS)
    for module in modules:
        keys.update(
            MetadataKey(key)
            for key in (*module.required_metadata, *module.optional_metadata)
        )
    if docker:
        keys.add(MetadataKey.DOCKER_PORT)
    return frozenset(keys)


def metadata_defaults(draft: InitDraft, config: UserConfig) -> dict[str, Any]:
    """Recorded metadata first, then the auto-resolvers and field defaults."""
    defaults = resolve_auto_metadata(config=config)
    if draft.existing_recipe:
        defaults.update(draft.existing_recipe.metadata)
    if draft.metadata is not None:
        defaults.update(draft.metadata)
    return defaults


class MetadataFields(Vertical):
    """A field per metadata key; keys the recipe does not read stay hidden."""

    class Changed(Message):
        """A metadata value changed, so the preview is stale."""

    def __init__(self, defaults: Mapping[str, Any]) -> None:
        super().__init__()
        self.defaults = defaults
        self.keys: frozenset[MetadataKey] = _BASE_KEYS

    def compose(self) -> ComposeResult:
        """Compose a labelled widget for every known metadata field."""
        for key, field in METADATA_FIELDS.items():
            with Vertical(id=f"meta-{key}-row", classes="field"):
                yield Label(field.label, classes="field-label")
                yield self._widget(key, self.defaults.get(key, field.default))

    def _widget(self, key: MetadataKey, default: Any) -> Widget:
        field = METADATA_FIELDS[key]
        choices = field.choices or []
        if field.prompt_type is PromptType.SELECT:
            value = default if default in choices else field.default
            return Select(
                [(choice, choice) for choice in choices],
                value=value,
                allow_blank=False,
                id=f"meta-{key}",
            )
        if field.prompt_type is PromptType.CHECKBOX:
            selected = set(default or ())
            return SelectionList[str](
                *(Selection(choice, choice, choice in selected) for choice in choices),
                id=f"meta-{key}",
            )
        return Input("" if default is None else str(default), id=f"meta-{key}")

    def show(self, keys: Set[MetadataKey]) -> None:
        """Show only the fields for ``keys``."""
        self.keys = frozenset(keys)
        for key in METADATA_FIELDS:
            self.query_one(f"#meta-{key}-row").display = key in self.keys

    def values(self) -> dict[str, MetadataValue]:
        """The shown fields' current values."""
        values: dict[str, MetadataValue] = {}
        for key in METADATA_FIELDS:
            if key not in self.keys:
                continue
            widget = self.query_one(f"#meta-{key}")
            if isinstance(widget, SelectionList):
                values[key.value] = tuple(str(item) for item in widget.selected)
            elif isinstance(widget, Select):
                values[key.value] = str(widget.value)
            elif isinstance(widget, Input):
                values[key.value] = widget.value
        return values

    # Text re-plans once submitted or left, not on every keystroke.
    @on(Input.Submitted)
    @on(Input.Blurred)
    @on(Select.Changed)
    @on(SelectionList.SelectedChanged)
    def _changed(self, event: Message) -> None:
        event.stop()
        if isinstance(event, Input.Submitted):
            self.screen.focus_next()
        self.post_message(self.Changed())
