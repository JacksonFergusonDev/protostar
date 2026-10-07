"""Counts what a Protostar command does while it runs.

Every cost passes through a seam: a managed command through
``ProcessRunner.run``, any other process through ``subprocess.Popen``, the hook
registry through ``registry._download``, and each document through its parser.
``record()`` wraps them for the length of a run and counts each call by a
label that is the same on every host. A parser is wrapped when its module is
first imported, so recording loads nothing the command would not, and the
third-party packages a command imports can be counted too.

``tests/test_cost_budgets.py`` checks that every seam in ``SEAMS`` still exists,
so a refactor that moves one fails loudly instead of quietly counting nothing.
"""

from __future__ import annotations

import contextlib
import importlib.abc
import importlib.machinery
import importlib.metadata
import subprocess
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

# Command-line tokens that take the following token as their value, so a
# label never mistakes the value for a package.
VALUED_OPTIONS = frozenset({"--group", "--python"})

# Every attribute ``record()`` wraps or reads, as (module, dotted attribute).
SEAMS: tuple[tuple[str, str], ...] = (
    ("protostar.system", "ProcessRunner.run"),
    ("protostar.registry", "_download"),
    ("protostar.registry", "_pending"),
    ("protostar.jsonc_ast", "parse_jsonc"),
    ("tomlkit", "parse"),
    ("tomlkit.api", "parse"),
    ("ruamel.yaml.main", "YAML.compose"),
    ("ruamel.yaml.main", "YAML.load"),
    ("subprocess", "Popen.__init__"),
)

# Which wrapper is running on this thread, so a call that makes another
# counted call (``tomlkit.parse`` calling ``tomlkit.api.parse``) counts once.
_active = threading.local()


def command_label(command: Sequence[str]) -> str:
    """Names a command by its program, words, and options.

    Option values (a Python version) and the packages ``uv add`` takes are left
    out, so the label is the same on every host and for every package.

    Args:
        command: The command and its arguments.

    Returns:
        The label, such as ``uv add --no-sync --dev``.
    """
    arguments = list(command)
    words = [Path(arguments[0]).stem]
    is_add = arguments[1:2] == ["add"]
    skip = False
    for word in arguments[1:]:
        if skip:
            skip = False
        elif word.startswith("-"):
            words.append(word)
            skip = word in VALUED_OPTIONS
        elif not (is_add and len(words) > 1):
            words.append(word)
    return " ".join(words)


class Recorder:
    """The counts one recording has taken, safe to add to from any thread."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self._lock = threading.Lock()

    def add(self, key: str) -> None:
        """Counts one call.

        Args:
            key: The call's label, prefixed by its kind (``parse:toml``).
        """
        with self._lock:
            self.counts[key] += 1

    def settle(self) -> None:
        """Waits for a hook-registry fetch still under way, so its count is final.

        The fetch runs on a background thread a command may never wait for.
        """
        registry = sys.modules.get("protostar.registry")
        pending = getattr(registry, "_pending", None)
        if pending is not None:
            # Its outcome is the command's business; only its count matters here.
            with contextlib.suppress(Exception):
                pending.result(timeout=30)


def imported_packages(before: frozenset[str]) -> list[str]:
    """Returns the third-party top-level packages imported since ``before``.

    Args:
        before: The names in ``sys.modules`` when the command started.

    Returns:
        The packages' import names, sorted. Protostar itself is not one.
    """
    started = {name.partition(".")[0] for name in before}
    now = {name.partition(".")[0] for name in list(sys.modules)}
    distributions = importlib.metadata.packages_distributions()
    return sorted(
        name for name in now - started if name in distributions and name != "protostar"
    )


def _counted(recorder: Recorder, key: str, guard: str, original: Any) -> Any:
    """Wraps a callable to count each outermost call under ``key``."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if getattr(_active, guard, False):
            return original(*args, **kwargs)
        setattr(_active, guard, True)
        try:
            recorder.add(key)
            return original(*args, **kwargs)
        finally:
            setattr(_active, guard, False)

    return wrapper


def _managed(recorder: Recorder, original: Any) -> Any:
    """Wraps ``ProcessRunner.run`` to count each command by its label."""

    def run(self: Any, cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        recorder.add(f"command:{command_label(cmd)}")
        _active.managed = True
        try:
            return original(self, cmd, *args, **kwargs)
        finally:
            _active.managed = False

    return run


def _launched(recorder: Recorder, original: Any) -> Any:
    """Wraps ``Popen.__init__`` to count processes no ``ProcessRunner`` started."""

    def init(self: Any, args: Any, *rest: Any, **kwargs: Any) -> None:
        if not getattr(_active, "managed", False):
            command = [args] if isinstance(args, (str, Path)) else list(args)
            recorder.add(f"subprocess:{command_label([str(c) for c in command])}")
        original(self, args, *rest, **kwargs)

    return init


class _Patches:
    """Attribute replacements, undone in reverse order."""

    def __init__(self) -> None:
        self._undo: list[Callable[[], None]] = []

    def replace(self, owner: Any, name: str, wrap: Callable[[Any], Any]) -> None:
        original = getattr(owner, name)
        setattr(owner, name, wrap(original))
        self._undo.append(lambda: setattr(owner, name, original))

    def undo(self) -> None:
        while self._undo:
            self._undo.pop()()


class _OnImport(importlib.abc.MetaPathFinder):
    """Runs a hook just after a watched module first executes."""

    def __init__(self, hooks: dict[str, Callable[[ModuleType], None]]) -> None:
        self._hooks = hooks

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        hook = self._hooks.get(fullname)
        if hook is None:
            return None
        for finder in sys.meta_path:
            find_spec = getattr(finder, "find_spec", None)
            if finder is self or find_spec is None:
                continue
            spec: importlib.machinery.ModuleSpec | None = find_spec(
                fullname, path, target
            )
            if spec is not None:
                break
        else:
            return None
        loader = spec.loader
        if loader is not None and hasattr(loader, "exec_module"):
            execute = loader.exec_module

            def execute_then_hook(module: ModuleType) -> None:
                execute(module)
                hook(module)

            # The loader belongs to this one spec, so the change goes no further.
            loader.exec_module = execute_then_hook  # type: ignore[method-assign]
        return spec


@contextlib.contextmanager
def record(*, commands: bool = True) -> Iterator[Recorder]:
    """Counts every command, process, registry fetch, and parse until exit.

    Args:
        commands: Whether to count managed commands at ``ProcessRunner.run``.
            Leave it off when another wrapper replaces that seam and counts
            them itself, as the rollback harness's fake runner does.

    Yields:
        The recorder, whose counts grow while the block runs.
    """
    recorder = Recorder()
    patches = _Patches()

    def system(module: ModuleType) -> None:
        if commands:
            patches.replace(
                module.ProcessRunner, "run", lambda run: _managed(recorder, run)
            )

    def registry(module: ModuleType) -> None:
        patches.replace(
            module,
            "_download",
            lambda download: _counted(recorder, "registry:fetch", "registry", download),
        )

    def jsonc(module: ModuleType) -> None:
        patches.replace(
            module,
            "parse_jsonc",
            lambda parse: _counted(recorder, "parse:jsonc", "jsonc", parse),
        )

    def toml(module: ModuleType) -> None:
        for owner in (module, sys.modules["tomlkit.api"]):
            for name in ("parse", "loads"):
                patches.replace(
                    owner,
                    name,
                    lambda parse: _counted(recorder, "parse:toml", "toml", parse),
                )

    def yaml(module: ModuleType) -> None:
        for name in ("compose", "load"):
            patches.replace(
                module.YAML,
                name,
                lambda parse: _counted(recorder, "parse:yaml", "yaml", parse),
            )

    patches.replace(
        subprocess.Popen, "__init__", lambda init: _launched(recorder, init)
    )
    hooks: dict[str, Callable[[ModuleType], None]] = {
        "protostar.system": system,
        "protostar.registry": registry,
        "protostar.jsonc_ast": jsonc,
        "tomlkit": toml,
        "ruamel.yaml.main": yaml,
    }
    with _watching(hooks, patches):
        yield recorder


class CommandClock:
    """The time the main thread spent waiting on managed commands."""

    def __init__(self) -> None:
        self.seconds = 0.0


@contextlib.contextmanager
def time_commands() -> Iterator[CommandClock]:
    """Times every managed command the main thread runs, until exit.

    A command on another thread, such as the editor probe's, overlaps the main
    thread's own work, so it is left out: what remains of a run's duration is
    the time Protostar's own code took. Any version of Protostar with a
    ``ProcessRunner`` can be timed, so a comparison can reach back before the
    other seams existed.

    Yields:
        The clock, whose total grows while the block runs.
    """
    clock = CommandClock()
    patches = _Patches()

    def timed(original: Any) -> Any:
        def run(self: Any, *args: Any, **kwargs: Any) -> Any:
            if threading.current_thread() is not threading.main_thread():
                return original(self, *args, **kwargs)
            started = time.perf_counter()
            try:
                return original(self, *args, **kwargs)
            finally:
                clock.seconds += time.perf_counter() - started

        return run

    def system(module: ModuleType) -> None:
        runner = getattr(module, "ProcessRunner", None)
        if runner is not None:
            patches.replace(runner, "run", timed)

    with _watching({"protostar.system": system}, patches):
        yield clock


@contextlib.contextmanager
def _watching(
    hooks: dict[str, Callable[[ModuleType], None]], patches: _Patches
) -> Iterator[None]:
    """Runs each hook on its module now if imported, or as it is imported.

    Every replacement the hooks made is undone on exit.
    """
    waiting: dict[str, Callable[[ModuleType], None]] = {}
    for name, hook in hooks.items():
        module = sys.modules.get(name)
        if module is None:
            waiting[name] = hook
        else:
            hook(module)
    finder = _OnImport(waiting)
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        sys.meta_path.remove(finder)
        patches.undo()
