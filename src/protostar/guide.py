"""How to work on a project, from its recorded recipe and ``pyproject.toml``.

``protostar guide`` is a fourth renderer of the ``GuideSpec`` that AGENTS.md,
CONTRIBUTING.md, and the pull request template render from, so it can never
disagree with them. Its commands come only from that spec and from facts the
project records, such as ``[project.scripts]``. Discovery plans the recorded
recipe exactly as ``sync`` does, which is read-only: it runs no project
command and imports no project code.
"""

import enum
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .errors import ConfigurationError, NetworkFetchError
from .manifest import MissingTool, missing_tools_record
from .recipe import read_recipe
from .system_deps import GlobalExecutable
from .workflows import (
    DOCS_SERVE_COMMAND,
    Check,
    CIFlag,
    GuideSpec,
    HookRunner,
    check_commands,
    just_recipes,
)


class Topic(enum.StrEnum):
    """What a guide action helps with, in the order the guide lists them."""

    RUN = "run"
    START = "start"
    TEST = "test"
    CHECK = "check"
    DOCS = "docs"
    MORE = "more"


class GuideNote(enum.StrEnum):
    """Something the guide could not know, and why."""

    NO_RECIPE = "no-recipe"
    """The directory records no recipe, so its tooling is unknown."""

    TEMPLATE_UNAVAILABLE = "template-unavailable"
    """The recorded template could not be fetched, so the recipe was not planned."""

    @property
    def message(self) -> str:
        """Returns what the note means for the reader."""
        return _NOTE_MESSAGES[self]


_NOTE_MESSAGES = {
    GuideNote.NO_RECIPE: (
        "This directory has no Protostar recipe, so its tests, checks, and docs "
        "are unknown. Run `protostar init` to record one."
    ),
    GuideNote.TEMPLATE_UNAVAILABLE: (
        "The project's template could not be fetched, so its tests, checks, and "
        "docs are unknown. Run `protostar guide` again once it can be reached."
    ),
}


@dataclass(frozen=True)
class Entrypoint:
    """A command ``[project.scripts]`` installs, and where its code starts.

    Attributes:
        name: The command's name.
        target: The ``module:function`` it runs.
        path: The workspace-relative POSIX path of the module's file, or None
            when no such file exists.
    """

    name: str
    target: str
    path: str | None


@dataclass(frozen=True)
class GuideAction:
    """One thing someone working on the project does, and how.

    Attributes:
        topic: What the action helps with.
        title: A short imperative heading.
        explanation: What the commands do, for someone new to the tools.
        commands: Shell commands to run, in order.
        paths: Workspace-relative files the action points to.
    """

    topic: Topic
    title: str
    explanation: str
    commands: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serializes the action."""
        return {
            "topic": self.topic.value,
            "title": self.title,
            "explanation": self.explanation,
            "commands": list(self.commands),
            "paths": list(self.paths),
        }


@dataclass(frozen=True)
class ProjectGuide:
    """How to work on the project.

    Attributes:
        actions: What to do, in topic order.
        missing_tools: Enabled tools' executables missing from ``PATH``; the
            actions already avoid them.
        notes: What the guide could not know.
    """

    actions: tuple[GuideAction, ...]
    missing_tools: frozenset[MissingTool] = frozenset()
    notes: tuple[GuideNote, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serializes the guide deterministically."""
        return {
            "actions": [action.to_dict() for action in self.actions],
            "missing_tools": missing_tools_record(self.missing_tools),
            "notes": [
                {"note": note.value, "message": note.message} for note in self.notes
            ],
        }


_CHECK_PHRASES = {
    Check.FORMAT: "formatting rewrites code into one consistent style",
    Check.LINT: "linting flags likely bugs",
    Check.TYPECHECK: "type checking catches a value used as the wrong type",
}


def read_entrypoints(root: Path) -> tuple[Entrypoint, ...]:
    """Reads the commands ``[project.scripts]`` installs, sorted by name.

    Args:
        root: The project root.

    Raises:
        ConfigurationError: If ``pyproject.toml`` is not valid TOML.
    """
    path = root / "pyproject.toml"
    if not path.is_file():
        return ()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(
            "Cannot read pyproject.toml.",
            hint="Correct pyproject.toml encoding and TOML syntax.",
        ) from error
    project = data.get("project")
    scripts = project.get("scripts") if isinstance(project, dict) else None
    if not isinstance(scripts, dict):
        return ()
    return tuple(
        Entrypoint(name, target, _module_path(root, target))
        for name, target in sorted(scripts.items())
        if isinstance(target, str)
    )


def _module_path(root: Path, target: str) -> str | None:
    """Returns the file a ``module:function`` target's module lives in, if found."""
    parts = target.partition(":")[0].strip().split(".")
    if not all(parts):
        return None
    module = Path(*parts)
    for base in (Path("src"), Path()):
        for candidate in (module.with_suffix(".py"), module / "__init__.py"):
            if (root / base / candidate).is_file():
                return (base / candidate).as_posix()
    return None


def build_guide(
    spec: GuideSpec | None,
    entrypoints: tuple[Entrypoint, ...],
    missing_tools: frozenset[MissingTool] = frozenset(),
    notes: tuple[GuideNote, ...] = (),
) -> ProjectGuide:
    """Builds the guide from the project's guide spec and recorded facts.

    An action appears only when the spec or the facts support it. While a
    tool's executable is missing, its commands give way to the ones it runs:
    without just, each check is shown as the ``uv run`` commands its recipe
    runs.

    Args:
        spec: The planned tooling, or None when the recipe could not be planned.
        entrypoints: The commands ``[project.scripts]`` installs.
        missing_tools: Enabled tools' executables missing from ``PATH``.
        notes: What the guide could not know.

    Returns:
        The guide.
    """
    actions: list[GuideAction] = []
    if entrypoints:
        actions.append(
            GuideAction(
                Topic.RUN,
                "Run the app",
                "`uv run` runs a command inside the project's environment, "
                "creating the environment first if it is missing.",
                tuple(f"uv run {entry.name}" for entry in entrypoints),
            )
        )
    located = [entry for entry in entrypoints if entry.path]
    if located:
        actions.append(
            GuideAction(
                Topic.START,
                "Where the code starts",
                f"`{located[0].name}` runs `{located[0].target}`, defined in this file."
                if len(located) == 1
                else "Each command runs the function `[project.scripts]` names "
                "for it, defined in these files.",
                paths=tuple(dict.fromkeys(str(entry.path) for entry in located)),
            )
        )
    if spec is not None:
        missing = {item.executable for item in missing_tools}
        if spec.wants_just and GlobalExecutable.JUST in missing:
            spec = replace(spec, wants_just=False)
        actions.extend(_spec_actions(spec))
    return ProjectGuide(tuple(actions), missing_tools, notes)


def _spec_actions(spec: GuideSpec) -> list[GuideAction]:
    """Returns the test, check, docs, and justfile actions the spec supports."""
    if spec.wants_just:
        recipes = just_recipes(spec)
        tests = [r.command for r in recipes if r.check is Check.TEST]
        checks = [(r.check, r.command) for r in recipes if r.check is not Check.TEST]
    else:
        commands = check_commands(spec)
        tests = [c for check, cs in commands if check is Check.TEST for c in cs]
        checks = [
            (check, c) for check, cs in commands if check is not Check.TEST for c in cs
        ]
    actions: list[GuideAction] = []
    if tests:
        actions.append(
            GuideAction(
                Topic.TEST,
                "Run the tests",
                "pytest runs the project's tests and reports each one that fails.",
                tuple(tests),
            )
        )
    if checks:
        kinds = sorted({check for check, _ in checks}, key=list(Check).index)
        phrases = [_CHECK_PHRASES[kind] for kind in kinds if kind in _CHECK_PHRASES]
        explanation = _sentence(phrases)
        if Check.CI in kinds:
            explanation += " `just ci` runs every check" + (
                ", as CI does." if spec.wants_ci else "."
            )
        if spec.hook_runner is not HookRunner.NONE:
            explanation += (
                f" {spec.hook_runner.value} runs the project's git hooks on every "
                "commit, and a failing hook stops the commit."
            )
        actions.append(
            GuideAction(
                Topic.CHECK,
                "Check and format",
                explanation.strip(),
                tuple(command for _, command in checks),
            )
        )
    if CIFlag.ZENSICAL in spec.ci_flags:
        actions.append(
            GuideAction(
                Topic.DOCS,
                "Preview the docs",
                "Serves the documentation in `docs/` locally and reloads it as you "
                "edit.",
                ("just serve" if spec.wants_just else DOCS_SERVE_COMMAND,),
            )
        )
    if spec.wants_just:
        actions.append(
            GuideAction(
                Topic.MORE,
                "Everything else",
                "Lists every recipe in the justfile, with what each one does.",
                ("just --list",),
            )
        )
    return actions


def _sentence(phrases: list[str]) -> str:
    """Joins lowercase clauses into one sentence."""
    if not phrases:
        return ""
    joined = (
        phrases[0]
        if len(phrases) == 1
        else f"{', '.join(phrases[:-1])}{',' if len(phrases) > 2 else ''} and {phrases[-1]}"
    )
    return f"{joined[0].upper()}{joined[1:]}."


def project_guide() -> ProjectGuide:
    """Builds the guide for the project in the current directory.

    The recorded recipe is planned as ``sync`` plans it, without requiring
    the executables Protostar runs. A directory without a recipe, or whose
    template can't be fetched, still gets what ``pyproject.toml`` records,
    with a note saying what the guide could not know.

    Raises:
        ConfigurationError: If the recipe, its ledger, or ``pyproject.toml`` is
            invalid.
    """
    from .lifecycle import locate_project, plan_project

    root = Path.cwd().resolve()
    entrypoints = read_entrypoints(root)
    if read_recipe(root / "pyproject.toml") is None:
        return build_guide(None, entrypoints, notes=(GuideNote.NO_RECIPE,))
    try:
        manifest, _ = plan_project(locate_project(), check_executables=False)
    except NetworkFetchError:
        return build_guide(None, entrypoints, notes=(GuideNote.TEMPLATE_UNAVAILABLE,))
    return build_guide(manifest.guide_spec(), entrypoints, manifest.missing_tools)
