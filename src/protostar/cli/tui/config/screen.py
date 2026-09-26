"""Identity, environment, and tool defaults as a form, beside the file's change."""

from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Select,
    Static,
)

from protostar.config import UserConfig
from protostar.config_edit import (
    IDENTITY_KEYS,
    ConfigEdit,
    EnvValue,
    OpenInEditor,
    SaveConfig,
    config_values,
    edit_config,
)
from protostar.errors import ConfigurationError
from protostar.ide import IDEType
from protostar.recipe import EXCLUSIVE_TOOL_PAIRS

from ..chrome import Heading, Headline, Masthead, Panel
from ..code import CodeSource, DiffLabels, diff_text
from ..keys import (
    ActionBar,
    ChoiceGroup,
    Field,
    Form,
    KeyboardScreen,
    KeyRows,
    LeaveScreen,
    Picker,
    key_label,
)
from ..tool_info import (
    TOOL_GROUPS,
    TOOL_INFO_KEY,
    ToolChoice,
    ToolRadio,
    ToolToggle,
    tool_module,
)

_UNSET = ""
"""The picker's and a field's value for a key left unset."""

_TEXT_FIELDS = {
    "author_name": "Name",
    "author_email": "Email",
    "github_username": "GitHub username (optional)",
    "python_version": "Default Python version",
}

_IDES = {
    _UNSET: "Not set",
    IDEType.VSCODE.value: "VS Code",
    IDEType.CURSOR.value: "Cursor",
    IDEType.NONE.value: "None",
}

_HOOK_MANAGERS = next(iter(EXCLUSIVE_TOOL_PAIRS))

_KEYS: KeyRows = (
    ("↑ ↓", "Move between rows"),
    ("space", "Toggle a checkbox, choose an option, or open a menu"),
    ("enter", "Same as space; in a text field, accept it and move on"),
    TOOL_INFO_KEY,
    ("tab", "Next control; a group of checkboxes is one stop"),
    ("shift+tab", "Previous control"),
    ("^s", "Save the change shown beside the form"),
    ("e", "Open the file in $EDITOR instead"),
    ("esc", "Cancel, after asking if anything changed"),
    ("^c", "Quit immediately"),
)


class ConfigScreen(KeyboardScreen[SaveConfig | OpenInEditor]):
    """Edit the global defaults, and see the file's change before saving it."""

    KEYS = _KEYS

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("e", "open_editor", "Edit file", show=False),
    ]

    def __init__(
        self, content: str, path: Path, prefill: Mapping[str, EnvValue]
    ) -> None:
        """Create the form.

        Args:
            content: The configuration file's text, or the default text for a
                file that doesn't exist yet.
            path: Where the file is, for the headline and the diff.
            prefill: Each editable key's starting value: the file's, then
                Git's for an identity the file leaves unset.
        """
        super().__init__()
        self.content = content
        self.path = path
        self.initial = dict(prefill)
        self.edit: ConfigEdit | None = None
        saved = config_values(UserConfig.parse(content, str(path)))
        self.from_git = any(
            prefill.get(key) and saved[key] is None for key in IDENTITY_KEYS
        )

    def compose(self) -> ComposeResult:
        """Compose the form beside the change it makes and the actions."""
        yield Masthead("config")
        status = Text("Defaults for every new project, saved to ")
        status.append(str(self.path))
        status.append(".")
        if self.from_git:
            status.append(" Name and email come from Git until you save them.")
        yield Headline("Configure Protostar", status)
        with Horizontal(id="body"):
            with Panel("Settings", id="editor-panel"), Form(id="editor"):
                yield Heading("Identity")
                yield from self._text_field("author_name")
                yield from self._text_field("author_email")
                yield from self._text_field("github_username")
                yield Heading("Environment")
                with Vertical(classes="field"):
                    yield Label("Editor", classes="field-label")
                    yield Picker(
                        [(label, value) for value, label in _IDES.items()],
                        value=self._text("ide")
                        if self._text("ide") in _IDES
                        else _UNSET,
                        allow_blank=False,
                        id="ide",
                    )
                yield from self._text_field("python_version")
                yield Heading("Tool defaults", key=("Tool info", "i"))
                yield Static(
                    "The tools a new project starts with. "
                    "A template's own choices win over these.",
                    classes="note",
                )
                with ChoiceGroup(id="tools"):
                    for title, tools in TOOL_GROUPS.items():
                        yield Label(title, classes="group")
                        for tool in tools:
                            yield ToolToggle(
                                tool_module(tool).name,
                                tool,
                                value=bool(self.initial[tool.value]),
                                id=f"tool-{tool}",
                            )
                yield Label("Git hook manager", classes="group")
                with ToolChoice(id="hook-manager"):
                    yield RadioButton(
                        "None",
                        value=not any(
                            self.initial[tool.value] for tool in _HOOK_MANAGERS
                        ),
                        id="none",
                    )
                    for tool in sorted(_HOOK_MANAGERS):
                        yield ToolRadio(
                            tool_module(tool).name,
                            tool,
                            value=bool(self.initial[tool.value]),
                            id=f"tool-{tool}",
                        )
            with Vertical(id="aside"):
                with Panel("Changes", id="changes-panel"), VerticalScroll(id="changes"):
                    yield Static("", id="changes-summary")
                    yield Static("", id="changes-diff")
                with ActionBar(id="actions"):
                    yield Button(key_label("Cancel", "esc"), id="cancel")
                    yield Button(key_label("Edit file", "e"), id="edit-file")
                    yield Button(key_label("Save", "^s"), variant="primary", id="save")
        yield Footer()

    def _text(self, key: str) -> str:
        value = self.initial.get(key)
        return _UNSET if value is None else str(value)

    def _text_field(self, key: str) -> ComposeResult:
        with Vertical(classes="field"):
            yield Label(_TEXT_FIELDS[key], classes="field-label")
            yield Field(self._text(key), id=key)

    def on_mount(self) -> None:
        """Show the change the prefilled values already make."""
        self._changed()

    def values(self) -> dict[str, EnvValue]:
        """The form's current value for every key it edits."""
        values: dict[str, EnvValue] = {
            key: self.query_one(f"#{key}", Input).value.strip() for key in _TEXT_FIELDS
        }
        values["ide"] = str(self.query_one("#ide", Select).value)
        for tools in TOOL_GROUPS.values():
            for tool in tools:
                values[tool.value] = self.query_one(f"#tool-{tool}", Checkbox).value
        pressed = self.query_one("#hook-manager", RadioSet).pressed_button
        for tool in _HOOK_MANAGERS:
            values[tool.value] = pressed is not None and pressed.id == f"tool-{tool}"
        return values

    def _dirty(self) -> bool:
        """Whether the user changed anything since the form opened."""
        return any(
            (value or None) != (self.initial.get(key) or None)
            for key, value in self.values().items()
        )

    @on(Input.Changed)
    @on(Select.Changed)
    @on(Checkbox.Changed)
    @on(RadioSet.Changed)
    def _changed(self) -> None:
        """Show what saving would change in the file, or why it can't."""
        summary = self.query_one("#changes-summary", Static)
        diff = self.query_one("#changes-diff", Static)
        summary.remove_class("-error")
        try:
            self.edit = edit_config(self.content, self.values(), source=str(self.path))
        except ConfigurationError as error:
            self.edit = None
            message = Text(str(error))
            if error.hint:
                message.append(f"  {error.hint}", style="dim")
            summary.update(message)
            summary.add_class("-error")
            diff.update("")
        else:
            if self.edit.changed:
                count = len(self.edit.changed)
                summary.update(
                    Text(f"{count} setting{'' if count == 1 else 's'} will change.")
                )
                name = self.path.name
                diff.update(
                    diff_text(
                        CodeSource(self.edit.before, name),
                        CodeSource(self.edit.after, name),
                        labels=DiffLabels(name, name),
                    )
                )
            else:
                summary.update(Text("Nothing to save yet."))
                diff.update("")
        self.query_one("#save", Button).disabled = not (self.edit and self.edit.changed)

    @on(Input.Submitted)
    def _next_row(self) -> None:
        self.action_move(1)

    @on(Button.Pressed, "#save")
    def action_save(self) -> None:
        """Leave with the change to write, once there is one."""
        if self.edit is not None and self.edit.changed:
            self.app.exit(SaveConfig(self.edit))

    @on(Button.Pressed, "#edit-file")
    def action_open_editor(self) -> None:
        """Leave to open the file in ``$EDITOR``, asking first if that loses changes."""
        if not self._dirty():
            self.app.exit(OpenInEditor())
            return

        def answer(leave: bool | None) -> None:
            if leave:
                self.app.exit(OpenInEditor())

        self.app.push_screen(
            LeaveScreen("Open the file in your editor and drop the form's changes?"),
            answer,
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        """Leave without saving, asking first if anything changed."""
        if not self._dirty():
            self.app.exit(None)
            return

        def answer(leave: bool | None) -> None:
            if leave:
                self.app.exit(None)

        self.app.push_screen(LeaveScreen("Leave without saving your changes?"), answer)
