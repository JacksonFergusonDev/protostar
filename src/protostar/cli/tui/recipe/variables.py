"""Template variable fields, checked by the secret guard when submitted."""

from collections.abc import Mapping
from dataclasses import replace

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.validation import ValidationResult, Validator
from textual.widgets import Button, Footer, Input, Label, Static

from protostar.config import UserConfig
from protostar.errors import ConfigurationError, SecretDetectedError
from protostar.init_draft import InitDraft
from protostar.secret_guard import check_variable_values

from .preview import PlanPreview


def draft_variables(draft: InitDraft) -> dict[str, str]:
    """Returns the recorded values a draft carries, overridden by its own."""
    recorded = dict(draft.existing_recipe.variables) if draft.existing_recipe else {}
    return {**recorded, **dict(draft.variables)}


class _NotACredential(Validator):
    """Rejects a value the secret guard flags, naming the rule but never the value."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name

    def validate(self, value: str) -> ValidationResult:
        """Runs the secret guard on one variable's value."""
        try:
            check_variable_values({self.name: value})
        except SecretDetectedError as exc:
            rule = exc.findings[0].rule
            return self.failure(f"Looks like a credential (gitleaks rule {rule}).")
        except ConfigurationError as exc:
            return self.failure(str(exc))
        return self.success()


class VariableFields(Vertical):
    """One field per template variable, checked on submit and never per keystroke."""

    class Committed(Message):
        """A value passed the secret guard and now feeds the preview."""

    def __init__(self, values: Mapping[str, str]) -> None:
        super().__init__()
        self.names: tuple[str, ...] = ()
        # Accepted values feed the preview; typed text survives a template switch.
        self.committed = dict(values)
        self._typed = dict(values)

    def compose(self) -> ComposeResult:
        """Compose a field and an error line for each variable."""
        yield Label("Template variables", classes="section")
        yield Static("Saved to pyproject.toml; don't enter secrets.", classes="note")
        for name in self.names:
            yield Label(name, classes="field-label")
            yield Input(
                self._typed.get(name, ""),
                id=f"var-{name}",
                validators=[_NotACredential(name)],
                validate_on=["submitted", "blur"],
            )
            error = Static("", id=f"var-{name}-error", classes="field-error")
            error.display = False
            yield error

    async def show(self, names: frozenset[str]) -> None:
        """Replace the fields with those of a newly chosen template."""
        self.names = tuple(sorted(names))
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

    @on(Input.Changed)
    def _remember(self, event: Input.Changed) -> None:
        event.stop()
        self._typed[str(event.input.id).removeprefix("var-")] = event.value

    @on(Input.Submitted)
    @on(Input.Blurred)
    def _commit(self, event: Input.Submitted | Input.Blurred) -> None:
        event.stop()
        name = str(event.input.id).removeprefix("var-")
        self._report(name, event.validation_result)
        if event.validation_result is not None and not event.validation_result.is_valid:
            return
        if isinstance(event, Input.Submitted):
            self.screen.focus_next()
        if self.committed.get(name) != event.value:
            self.committed[name] = event.value
            self.post_message(self.Committed())


class VariablesScreen(Screen[InitDraft]):
    """The editor's variables step alone, for a flag-driven init missing values."""

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
            with VerticalScroll(id="editor"):
                yield VariableFields(draft_variables(self.draft))
            yield PlanPreview(self.config)
        with Horizontal(id="actions"):
            yield Button("Cancel", id="cancel")
            yield Button("Continue", variant="primary", id="continue")
        yield Footer()

    async def on_mount(self) -> None:
        """Show the template's variables and focus the first without a value."""
        fields = self.query_one(VariableFields)
        await fields.show(
            self.draft.template.source.variables if self.draft.template else frozenset()
        )
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
            replace(self.draft, variables=tuple(sorted(committed.items())))
        )

    @on(Button.Pressed)
    def finish(self, event: Button.Pressed) -> None:
        """Exit with every value once each passes the secret guard."""
        if event.button.id == "cancel":
            self.app.exit(None)
            return
        values = self.query_one(VariableFields).values()
        if values is not None:
            self.app.exit(replace(self.draft, variables=tuple(sorted(values.items()))))
