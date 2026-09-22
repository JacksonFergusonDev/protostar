"""Recipe decisions backed by the shared recipe precedence and constraints."""

import importlib.resources
import tomllib
from dataclasses import replace
from enum import Enum, auto

from rich.text import Text
from textual import on
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
from protostar.init_draft import DraftTemplate, InitDraft
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


class RecipeScreen(Screen[InitDraft]):
    """Select a template, tools, and Docker before the remaining prompts."""

    def __init__(
        self, draft: InitDraft, catalog: list[TemplateInfo], config: UserConfig
    ) -> None:
        super().__init__()
        self.draft = draft
        self._recorded_template = draft.template
        self._template_error = False
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
        """Compose the template selector and grouped tool decisions."""
        yield Label("Build your recipe", id="title")
        yield Static(
            "Choose a starting point and the tools for your project.", id="subtitle"
        )
        with VerticalScroll(id="editor"):
            yield Label("Template", classes="section")
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
            yield Select(options, value=initial, allow_blank=False, id="template")
            yield Static("", id="error", markup=False)
            yield Static("", id="constraints", markup=False)
            yield Checkbox("Docker", value=self._docker(), id="docker")
            for title, tools in _GROUPS.items():
                yield Label(title, classes="section")
                for tool in tools:
                    yield Checkbox(
                        self._label(tool), value=self.enabled[tool], id=f"tool-{tool}"
                    )
            yield Label("Git hook manager", classes="section")
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
        with Horizontal(id="actions"):
            yield Button("Cancel", id="cancel")
            yield Button("Continue", variant="primary", id="continue")
        yield Footer()

    def on_mount(self) -> None:
        """Apply requirement availability to the initial controls."""
        self._refresh_tools()

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
        invalid = False
        message = ""
        try:
            validate_tools(enabled)
        except ConfigurationError as exc:
            invalid = True
            message = str(exc)
        self.query_one("#constraints", Static).update(Text(message))
        self.query_one("#continue", Button).disabled = invalid or self._template_error

    @on(Select.Changed, "#template")
    def select_template(self, event: Select.Changed) -> None:
        """Acquire the selected source, preserving explicit tool choices."""
        if not isinstance(event.value, (TemplateInfo, _TemplateChoice)):
            return
        if event.value == self._selected_template and not self._template_error:
            return
        template = None
        try:
            if event.value is _TemplateChoice.RECORDED:
                template = self._recorded_template
            elif isinstance(event.value, TemplateInfo):
                info = event.value
                external = info.type is TemplateType.GLOBAL_ALIAS
                target = (
                    info.source
                    if external
                    else str(
                        importlib.resources.files("protostar.templates").joinpath(
                            f"{info.alias}.toml"
                        )
                    )
                )
                template = DraftTemplate(
                    TemplateSource.load(
                        target,
                        built_in=None if external else info.alias,
                        display_name=info.alias,
                    ),
                    external,
                    external,
                    info.trusted,
                )
            old_draft = self.draft
            self.draft = replace(self.draft, template=template)
            try:
                self._resolve_selections()
            except ProtostarError:
                self.draft = old_draft
                raise
        except ProtostarError as exc:
            self._template_error = True
            self.query_one("#error", Static).update(Text(str(exc)))
            self.query_one("#continue", Button).disabled = True
            return
        self._template_error = False
        self._selected_template = event.value
        self.query_one("#error", Static).update("")
        with self.query_one("#docker", Checkbox).prevent(Checkbox.Changed):
            self.query_one("#docker", Checkbox).value = self._docker()
        self._refresh_tools()

    @on(Checkbox.Changed)
    def toggle_tool(self, event: Checkbox.Changed) -> None:
        """Record explicit choices and update requirement availability."""
        if event.checkbox.id == "docker":
            if event.value == self._docker():
                return
            self.docker_override = event.value
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

    @on(Button.Pressed)
    def finish(self, event: Button.Pressed) -> None:
        """Return decisions only; execution starts after the app has exited."""
        if event.button.id == "cancel":
            self.app.exit(None)
        else:
            self.app.exit(
                replace(
                    self.draft,
                    tool_choices=tuple(sorted(self.enabled.items())),
                    docker=self._docker(),
                )
            )
