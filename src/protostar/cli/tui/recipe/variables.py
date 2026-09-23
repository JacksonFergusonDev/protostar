"""Template variable fields, checked by the secret guard when submitted."""

from collections.abc import Collection, Mapping
from dataclasses import replace
from typing import ClassVar

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.validation import ValidationResult, Validator
from textual.widgets import Button, Checkbox, Footer, Input, Label, Static

from protostar.config import TemplateSource, UserConfig
from protostar.errors import ConfigurationError, ProtostarError, SecretDetectedError
from protostar.init_draft import InitDraft
from protostar.secret_guard import check_variable_values, credential_named

from ..keys import ActionBar, Field, Form, KeyboardScreen, Toggle, key_label, move
from .preview import PlanPreview


def draft_variables(draft: InitDraft) -> dict[str, str]:
    """Returns the recorded values a draft carries, overridden by its own."""
    recorded = dict(draft.existing_recipe.variables) if draft.existing_recipe else {}
    return {**recorded, **dict(draft.variables)}


class _NotACredential(Validator):
    """Rejects a value the secret guard flags, naming the rule but never the value.

    A flagged value passes once the user confirms it is not a secret.
    """

    def __init__(self, name: str, allowed: Collection[str]) -> None:
        super().__init__()
        self.name = name
        self.allowed = allowed
        self.flagged = False

    def validate(self, value: str) -> ValidationResult:
        """Runs the secret guard on one variable's value."""
        self.flagged = False
        try:
            check_variable_values({self.name: value})
        except SecretDetectedError as exc:
            self.flagged = True
            if self.name in self.allowed:
                return self.success()
            rule = exc.findings[0].rule
            return self.failure(f"Looks like a credential (gitleaks rule {rule}).")
        except ConfigurationError as exc:
            return self.failure(str(exc))
        return self.success()


class VariableFields(Vertical):
    """One field per template variable, checked on submit and never per keystroke."""

    class Committed(Message):
        """A value passed the secret guard and now feeds the preview."""

    def __init__(
        self, values: Mapping[str, str], allowed: Collection[str] = frozenset()
    ) -> None:
        super().__init__()
        self.names: tuple[str, ...] = ()
        self.descriptions: dict[str, str] = {}
        self.credential_names: tuple[str, ...] = ()
        # Accepted values feed the preview; typed text survives a template switch.
        self.committed = dict(values)
        self._typed = dict(values)
        self._allowed = set(allowed)

    @property
    def allowed_secrets(self) -> frozenset[str]:
        """The shown variables whose flagged values the user kept."""
        return frozenset(self._allowed & set(self.names))

    def compose(self) -> ComposeResult:
        """Compose a field, its notes, and an error line for each variable."""
        yield Label("Template variables", classes="section")
        yield Static("Saved to pyproject.toml; don't enter secrets.", classes="note")
        for name in self.names:
            yield Label(name, classes="field-label")
            if name in self.descriptions:
                yield Static(Text(self.descriptions[name]), classes="note")
            if name in self.credential_names:
                yield Static(
                    "Named like a credential; enter a non-secret value.",
                    classes="field-warning",
                )
            yield Field(
                self._typed.get(name, ""),
                id=f"var-{name}",
                validators=[_NotACredential(name, self._allowed)],
                validate_on=["submitted", "blur"],
            )
            error = Static("", id=f"var-{name}-error", classes="field-error")
            error.display = False
            yield error
            allow = Toggle(
                "Not a secret; keep this value",
                name in self._allowed,
                id=f"var-{name}-allow",
            )
            allow.display = name in self._allowed
            yield allow

    async def show(self, source: TemplateSource | None) -> None:
        """Replace the fields with those of a newly chosen template."""
        names = source.variables if source else frozenset()
        try:
            self.descriptions = source.descriptions if source else {}
        except ProtostarError:
            # The preview reports an invalid declaration; the fields still work.
            self.descriptions = {}
        self.names = tuple(sorted(names))
        self.credential_names = credential_named(names)
        self.display = bool(self.names)
        await self.recompose()

    @property
    def missing(self) -> tuple[str, ...]:
        """The variables that have no value yet."""
        return tuple(name for name in self.names if name not in self.committed)

    def values(self) -> dict[str, str] | None:
        """Check every field; return the values, or None if any is rejected."""
        rejected: list[Input] = []
        for name in self.names:
            field = self.query_one(f"#var-{name}", Input)
            self._report(name, field.validate(field.value))
            if not field.is_valid:
                rejected.append(field)
        if rejected:
            rejected[0].focus()
            return None
        values = {
            name: self.query_one(f"#var-{name}", Input).value for name in self.names
        }
        self.committed.update(values)
        return values

    def _report(self, name: str, result: ValidationResult | None) -> None:
        message = "" if result is None else " ".join(result.failure_descriptions)
        for error in self.query(f"#var-{name}-error").results(Static):
            error.update(Text(message))
            error.display = bool(message)
        field = self.query_one(f"#var-{name}", Input)
        validator = next(v for v in field.validators if isinstance(v, _NotACredential))
        self.query_one(f"#var-{name}-allow", Checkbox).display = validator.flagged

    @on(Input.Changed)
    def _remember(self, event: Input.Changed) -> None:
        event.stop()
        name = str(event.input.id).removeprefix("var-")
        if self._typed.get(name) == event.value:
            return
        self._typed[name] = event.value
        # A confirmation covers the value the user saw flagged, not its edits.
        if name in self._allowed:
            self._allowed.discard(name)
            allow = self.query_one(f"#var-{name}-allow", Checkbox)
            with allow.prevent(Checkbox.Changed):
                allow.value = False

    @on(Checkbox.Changed)
    def _allow(self, event: Checkbox.Changed) -> None:
        event.stop()
        name = str(event.checkbox.id).removeprefix("var-").removesuffix("-allow")
        if event.value:
            self._allowed.add(name)
        else:
            self._allowed.discard(name)
        field = self.query_one(f"#var-{name}", Input)
        result = field.validate(field.value)
        self._report(name, result)
        if result is not None and not result.is_valid:
            if self.committed.pop(name, None) is not None:
                self.post_message(self.Committed())
            return
        self._accept(name, field.value)

    @on(Input.Submitted)
    @on(Input.Blurred)
    def _commit(self, event: Input.Submitted | Input.Blurred) -> None:
        event.stop()
        name = str(event.input.id).removeprefix("var-")
        self._report(name, event.validation_result)
        if event.validation_result is not None and not event.validation_result.is_valid:
            return
        if isinstance(event, Input.Submitted):
            move(self.screen, 1)
        self._accept(name, event.value)

    def _accept(self, name: str, value: str) -> None:
        if self.committed.get(name) != value:
            self.committed[name] = value
            self.post_message(self.Committed())


class VariablesScreen(KeyboardScreen[InitDraft]):
    """The editor's variables step alone, for a flag-driven init missing values."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+s", "continue", "Continue", show=False),
    ]

    def __init__(self, draft: InitDraft, config: UserConfig) -> None:
        super().__init__()
        self.draft = draft
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose the variable fields beside the plan preview."""
        reference = (
            self.draft.template.source.reference if self.draft.template else None
        )
        name = (reference.display_name or reference.locator) if reference else ""
        yield Label("Template needs values", id="title")
        yield Static(
            Text(f"{name} uses variables that have no value yet."), id="subtitle"
        )
        with Horizontal(id="body"):
            with Form(id="editor"):
                yield VariableFields(
                    draft_variables(self.draft), self.draft.allowed_secrets
                )
            yield PlanPreview(self.config)
        with ActionBar(id="actions"):
            yield Button(key_label("Cancel", "esc"), id="cancel")
            yield Button(key_label("Continue", "^s"), variant="primary", id="continue")
        yield Footer()

    async def on_mount(self) -> None:
        """Show the template's variables and focus the first without a value."""
        fields = self.query_one(VariableFields)
        await fields.show(self.draft.template.source if self.draft.template else None)
        if fields.missing:
            self.query_one(f"#var-{fields.missing[0]}", Input).focus()
        self.refresh_preview()

    @on(VariableFields.Committed)
    def refresh_preview(self) -> None:
        """Re-plan with the values accepted so far."""
        fields = self.query_one(VariableFields)
        committed = {
            name: fields.committed[name]
            for name in fields.names
            if name in fields.committed
        }
        self.query_one(PlanPreview).update_plan(
            replace(
                self.draft,
                variables=tuple(sorted(committed.items())),
                allowed_secrets=fields.allowed_secrets,
            )
        )

    @on(Button.Pressed, "#cancel")
    def _cancel_pressed(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#continue")
    def action_continue(self) -> None:
        """Exit with every value once each passes the secret guard."""
        fields = self.query_one(VariableFields)
        values = fields.values()
        if values is not None:
            self.app.exit(
                replace(
                    self.draft,
                    variables=tuple(sorted(values.items())),
                    allowed_secrets=fields.allowed_secrets,
                )
            )
