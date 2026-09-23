"""Recipe decisions backed by the shared recipe precedence and constraints."""

import asyncio
import importlib.resources
import tomllib
from collections.abc import Mapping
from dataclasses import replace
from enum import Enum, auto

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Label,
    RadioButton,
    RadioSet,
    Select,
    Static,
)

from protostar.config import TemplateSource, UserConfig
from protostar.errors import ConfigurationError, ProtostarError
from protostar.init_draft import DraftTemplate, InitDecision, InitDraft
from protostar.metadata import MetadataKey
from protostar.modules import TOOLING_MODULES
from protostar.recipe import (
    EXCLUSIVE_TOOL_PAIRS,
    TOOL_REQUIREMENTS,
    SelectionLayer,
    Tool,
    establish_recipe,
    validate_tools,
)
from protostar.templates import TemplateInfo, TemplateType

from ..review.screen import ReviewScreen
from .metadata import MetadataFields, metadata_defaults, metadata_keys
from .preview import PlanPreview
from .variables import VariableFields, draft_variables

_GROUPS = {
    "Quality": (
        Tool.RUFF,
        Tool.MYPY,
        Tool.TY,
        Tool.PYREFLY,
        Tool.PYTEST,
        Tool.RUMDL,
        Tool.MARKDOWNLINT,
    ),
    "Automation": (Tool.CI, Tool.RELEASE, Tool.COMMITIZEN, Tool.RENOVATE, Tool.CODECOV),
    "Documentation & workspace": (
        Tool.ZENSICAL,
        Tool.READTHEDOCS,
        Tool.DIRENV,
        Tool.JUST,
        Tool.AGENTS,
    ),
}
_NAMES = {Tool(module.config_key): module.name for module in TOOLING_MODULES}
_SOURCES = {
    SelectionLayer.TEMPLATE: "from template",
    SelectionLayer.PROJECT: "from recipe",
    SelectionLayer.FALLBACK: "from config",
}


class _TemplateChoice(Enum):
    NONE = auto()
    RECORDED = auto()


class RecipeScreen(Screen[InitDecision]):
    """Edit the template, its variables, tools, and metadata beside a live preview."""

    def __init__(
        self, draft: InitDraft, catalog: list[TemplateInfo], config: UserConfig
    ) -> None:
        super().__init__()
        self.draft = draft
        self.config = config
        self._recorded_template = draft.template
        self._template_error = False
        self._loading = False
        self._tools_invalid = False
        self.catalog = catalog
        self.base_recipe = draft.existing_recipe or establish_recipe(config)
        self.overrides = dict(draft.tool_overrides)
        if draft.tool_choices is not None:
            self.overrides.update(draft.tool_choices)
        self.opinions: dict[str, bool] = {}
        self.enabled: dict[Tool, bool] = {}
        self.sources: dict[Tool, str] = {}
        self.docker_override = draft.docker
        self._selected_template: TemplateInfo | _TemplateChoice | None = None
        self._resolve_selections()
        self._metadata_defaults = metadata_defaults(draft, config)

    def _resolve_selections(self) -> None:
        source = self.draft.template.source if self.draft.template else None
        try:
            data = (
                tomllib.loads(source.template_bytes.decode("utf-8")) if source else {}
            )
        except tomllib.TOMLDecodeError as exc:
            raise ConfigurationError("Invalid template TOML.", hint=str(exc)) from exc
        # Tool opinions are literal root booleans, independent of variable rendering.
        self.opinions = {
            key: value for key, value in data.items() if isinstance(value, bool)
        }
        recipe = replace(
            self.base_recipe,
            tools=tuple(
                sorted({**dict(self.base_recipe.tools), **self.overrides}.items())
            ),
        )
        selections = recipe.selections(self.opinions)
        self.enabled = {selection.tool: selection.enabled for selection in selections}
        self.sources = {
            selection.tool: "your choice"
            if selection.tool in self.overrides
            else _SOURCES[selection.layer]
            for selection in selections
        }

    def _label(self, tool: Tool) -> Text:
        label = f"{_NAMES[tool]} · {self.sources[tool]}"
        missing = TOOL_REQUIREMENTS.get(tool, frozenset()) - {
            tool for tool, enabled in self.enabled.items() if enabled
        }
        if missing:
            label += " · requires " + ", ".join(
                _NAMES[item] for item in sorted(missing)
            )
        return Text(label)

    def _docker(self) -> bool:
        if self.docker_override is not None:
            return self.docker_override
        if self.draft.existing_recipe:
            return self.draft.existing_recipe.docker
        return self.opinions.get("docker", False)

    def compose(self) -> ComposeResult:
        """Compose the editor sections beside the plan preview."""
        yield Label("Build your recipe", id="title")
        yield Static(
            "Choose a starting point, tools, and project details.", id="subtitle"
        )
        with Horizontal(id="body"):
            with VerticalScroll(id="editor"):
                yield Label("Template", classes="section")
                yield self._template_select()
                yield Static("", id="template-status", markup=False)
                yield VariableFields(
                    draft_variables(self.draft), self.draft.allowed_secrets
                )
                yield Label("Tools", classes="section")
                yield Static("", id="constraints", markup=False)
                yield Checkbox("Docker", value=self._docker(), id="docker")
                for title, tools in _GROUPS.items():
                    yield Label(title, classes="group")
                    for tool in tools:
                        yield Checkbox(
                            self._label(tool),
                            value=self.enabled[tool],
                            id=f"tool-{tool}",
                        )
                yield Label("Git hook manager", classes="group")
                for index, pair in enumerate(EXCLUSIVE_TOOL_PAIRS):
                    with RadioSet(id=f"exclusive-{index}"):
                        yield RadioButton(
                            "None",
                            value=not any(self.enabled[tool] for tool in pair),
                            id=f"none-{index}",
                        )
                        for tool in sorted(pair):
                            yield RadioButton(
                                self._label(tool),
                                value=self.enabled[tool],
                                id=f"tool-{tool}",
                            )
                yield Label("Project details", classes="section")
                yield MetadataFields(self._metadata_defaults)
            yield PlanPreview(self.config)
        with Horizontal(id="actions"):
            yield Button("Cancel", id="cancel")
            yield Button("Continue", variant="primary", id="continue")
        yield Footer()

    def _template_select(self) -> Select[TemplateInfo | _TemplateChoice]:
        options: list[tuple[Text, TemplateInfo | _TemplateChoice]] = [
            (Text("No template"), _TemplateChoice.NONE)
        ]
        options.extend(
            (Text(f"{item.name} · {item.type.value} — {item.description}"), item)
            for item in self.catalog
        )
        initial: TemplateInfo | _TemplateChoice = _TemplateChoice.NONE
        if self.draft.template:
            reference = self.draft.template.source.reference
            initial = next(
                (
                    item
                    for item in self.catalog
                    if item.alias == reference.display_name
                    or item.source == reference.locator
                    or (
                        item.type is TemplateType.BUILT_IN
                        and item.alias == reference.locator
                    )
                ),
                _TemplateChoice.RECORDED,
            )
            if initial is _TemplateChoice.RECORDED:
                options.append(
                    (Text(f"Recorded template · {reference.locator}"), initial)
                )
        self._selected_template = initial
        return Select(options, value=initial, allow_blank=False, id="template")

    async def on_mount(self) -> None:
        """Show the template's variables, then plan the initial draft."""
        await self.query_one(VariableFields).show(
            self.draft.template.source if self.draft.template else None
        )
        self._status(Text(""))
        self._refresh_tools()
        self._changed()

    def _refresh_tools(self) -> None:
        enabled = {tool for tool, value in self.enabled.items() if value}
        for tool in Tool:
            widget = (
                self.query_one(f"#tool-{tool}", RadioButton)
                if any(tool in pair for pair in EXCLUSIVE_TOOL_PAIRS)
                else self.query_one(f"#tool-{tool}", Checkbox)
            )
            widget.label = self._label(tool)
            widget.disabled = not TOOL_REQUIREMENTS.get(tool, frozenset()) <= enabled
            if isinstance(widget, Checkbox):
                with widget.prevent(Checkbox.Changed):
                    widget.value = self.enabled[tool]
        for index, pair in enumerate(EXCLUSIVE_TOOL_PAIRS):
            chosen = [tool for tool in sorted(pair) if self.enabled[tool]]
            if len(chosen) <= 1:
                target = f"tool-{chosen[0]}" if chosen else f"none-{index}"
                self.query_one(f"#{target}", RadioButton).value = True
        # Invalid inherited choices stay visible and must be resolved explicitly.
        message = ""
        try:
            validate_tools(enabled)
        except ConfigurationError as exc:
            message = str(exc)
        self._tools_invalid = bool(message)
        constraints = self.query_one("#constraints", Static)
        constraints.update(Text(message))
        constraints.display = bool(message)
        self._refresh_continue()

    def _refresh_continue(self) -> None:
        self.query_one("#continue", Button).disabled = (
            self._tools_invalid or self._template_error or self._loading
        )

    def _current_draft(self, variables: Mapping[str, str] | None = None) -> InitDraft:
        fields = self.query_one(VariableFields)
        if variables is None:
            variables = {
                name: fields.committed[name]
                for name in fields.names
                if name in fields.committed
            }
        metadata = self.query_one(MetadataFields).values()
        minimum = metadata.get(MetadataKey.MINIMUM_PYTHON)
        return replace(
            self.draft,
            tool_choices=tuple(sorted(self.enabled.items())),
            docker=self._docker(),
            variables=tuple(sorted(variables.items())),
            allowed_secrets=fields.allowed_secrets,
            metadata=tuple(sorted(metadata.items())),
            python_version=str(minimum) if minimum else None,
        )

    @on(VariableFields.Committed)
    @on(MetadataFields.Changed)
    def _changed(self) -> None:
        """Show the metadata the current tools read, and re-plan the preview."""
        self.query_one(MetadataFields).show(
            metadata_keys(
                (
                    module
                    for module in TOOLING_MODULES
                    if self.enabled[Tool(module.config_key)]
                ),
                docker=self._docker(),
            )
        )
        self.query_one(PlanPreview).update_plan(self._current_draft())

    @on(Select.Changed, "#template")
    def select_template(self, event: Select.Changed) -> None:
        """Acquire the selected source in a worker; remote templates take a while."""
        if not isinstance(event.value, (TemplateInfo, _TemplateChoice)):
            return
        if event.value == self._selected_template and not self._template_error:
            # Returning to the current template abandons any load still running.
            self.workers.cancel_group(self, "template")
            self._loading = False
            self._status(Text(""))
            self._refresh_continue()
            return
        self._loading = True
        name = event.value.name if isinstance(event.value, TemplateInfo) else ""
        self._status(Text(f"Loading {name}…" if name else "Loading…"))
        self._refresh_continue()
        self._load_template(event.value)

    def _acquire(self, choice: TemplateInfo | _TemplateChoice) -> DraftTemplate | None:
        # Runs in a thread: no widget access here.
        template = None
        if choice is _TemplateChoice.RECORDED:
            template = self._recorded_template
        elif isinstance(choice, TemplateInfo):
            external = choice.type is TemplateType.GLOBAL_ALIAS
            target = (
                choice.source
                if external
                else str(
                    importlib.resources.files("protostar.templates").joinpath(
                        f"{choice.alias}.toml"
                    )
                )
            )
            template = DraftTemplate(
                TemplateSource.load(
                    target,
                    built_in=None if external else choice.alias,
                    display_name=choice.alias,
                ),
                external,
                external,
                choice.trusted,
            )
        if template:
            # An invalid [variables] table is a template error, shown inline.
            _ = template.source.descriptions
        return template

    @work(exclusive=True, group="template")
    async def _load_template(self, choice: TemplateInfo | _TemplateChoice) -> None:
        try:
            template = await asyncio.to_thread(self._acquire, choice)
            old_draft = self.draft
            self.draft = replace(self.draft, template=template)
            try:
                self._resolve_selections()
            except ProtostarError:
                self.draft = old_draft
                raise
        except ProtostarError as exc:
            self._loading = False
            self._template_error = True
            self._status(Text(str(exc)), error=True)
            self._refresh_continue()
            return
        self._loading = False
        self._template_error = False
        self._selected_template = choice
        self._status(Text(""))
        with self.query_one("#docker", Checkbox).prevent(Checkbox.Changed):
            self.query_one("#docker", Checkbox).value = self._docker()
        await self.query_one(VariableFields).show(template.source if template else None)
        self._refresh_tools()
        self._changed()

    def _status(self, message: Text, *, error: bool = False) -> None:
        status = self.query_one("#template-status", Static)
        status.update(message)
        status.set_class(error, "-error")
        status.display = bool(message)

    @on(Checkbox.Changed)
    def toggle_tool(self, event: Checkbox.Changed) -> None:
        """Record explicit choices and update requirement availability."""
        if event.checkbox.id == "docker":
            if event.value == self._docker():
                return
            self.docker_override = event.value
            self._changed()
            return
        tool = Tool(str(event.checkbox.id).removeprefix("tool-"))
        if self.enabled[tool] == event.value:
            return
        self.overrides[tool] = event.value
        # Disabling a prerequisite also clears its dependent tool.
        for dependent, required in TOOL_REQUIREMENTS.items():
            if tool in required and not event.value:
                self.overrides[dependent] = False
        self._resolve_selections()
        self._refresh_tools()
        self._changed()

    @on(RadioSet.Changed)
    def choose_exclusive(self, event: RadioSet.Changed) -> None:
        """A radio choice always clears every other member of its pair."""
        pair = EXCLUSIVE_TOOL_PAIRS[
            int(str(event.radio_set.id).removeprefix("exclusive-"))
        ]
        selected = str(event.pressed.id).removeprefix("tool-")
        values = {tool: tool.value == selected for tool in pair}
        if all(self.enabled[tool] == value for tool, value in values.items()):
            return
        self.overrides.update(values)
        self._resolve_selections()
        self._refresh_tools()
        self._changed()

    @on(Button.Pressed)
    def finish(self, event: Button.Pressed) -> None:
        """Continue to the change review, which returns the decisions."""
        if event.button.id == "cancel":
            self.app.exit(None)
            return
        variables = self.query_one(VariableFields).values()
        if variables is not None:
            self.app.push_screen(
                ReviewScreen(
                    self._current_draft(variables), self.config, can_go_back=True
                )
            )
