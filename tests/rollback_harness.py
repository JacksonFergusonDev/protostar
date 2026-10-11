"""Fault injection for rollback: fail a real init or sync at one site, then compare trees.

Every mutation execution makes goes through four seams: the three
``TransactionAwareFS`` operations and ``ProcessRunner.run``. The harness wraps
each one, names every call a *site* (``write:pyproject.toml#2``: its kind, its
target, and which occurrence it is), and can raise a fault at one site:

- **before** the operation starts,
- **mid**-way (a write's ``os.replace`` fails after its temporary file exists;
  a command does half its work), or
- **after** it finished.

A fault is an error (``OSError`` from the filesystem, ``CommandExecutionError``
from a command) or an interrupt (``KeyboardInterrupt``). Either way rollback
must leave the project and the home directory exactly as they were, apart
from the state the rollback boundary disclaims (``DISCLAIMED``).

Commands run for real (``Runner.REAL``) or through a fake that writes exactly
the paths the executor journaled for them (``Runner.FAKE``), which keeps the
exhaustive tier fast and offline.
"""

from __future__ import annotations

import contextlib
import dataclasses
import enum
import errno
import os
import shutil
import signal
import stat
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from protostar import fs_transaction, journal, system
from protostar.errors import CommandExecutionError, ProcessTerminationError
from scripts.benchmarks.probes import command_label
from scripts.nightly_matrix import TEMPLATES

SITES_DIR = Path(__file__).parent / "rollback_sites"

# The process a command that won't stop reports (RollbackFault.unstoppable).
UNSTOPPABLE_PID = 4242

# Paths outside the transacted boundary (AGENTS.md, "Rollback Boundary"):
# never compared, before or after a run. Each needs its reason.
DISCLAIMED = frozenset(
    {
        # The project environment uv creates and manages.
        ".venv",
    }
)
DISCLAIMED_HOME = frozenset(
    {
        # Global tool caches: prek clones the hook repositories here.
        ".cache",
    }
)


class SiteKind(enum.StrEnum):
    """What a site does."""

    WRITE = "write"
    MKDIR = "mkdir"
    REMOVE = "remove"
    COMMAND = "command"
    COMMIT = "commit"


class Position(enum.StrEnum):
    """When a fault fires, relative to the site's operation."""

    BEFORE = "before"
    MID = "mid"
    AFTER = "after"


class Fault(enum.StrEnum):
    """How the run fails."""

    ERROR = "error"
    INTERRUPT = "interrupt"


class Command(enum.StrEnum):
    """The command a scenario runs."""

    INIT = "init"
    SYNC = "sync"


class Runner(enum.StrEnum):
    """Whether commands run for real or through the fake."""

    FAKE = "fake"
    REAL = "real"


POSITIONS = {
    SiteKind.WRITE: (Position.BEFORE, Position.MID, Position.AFTER),
    SiteKind.MKDIR: (Position.BEFORE, Position.AFTER),
    SiteKind.REMOVE: (Position.BEFORE, Position.AFTER),
    SiteKind.COMMAND: (Position.BEFORE, Position.MID, Position.AFTER),
    SiteKind.COMMIT: (Position.BEFORE, Position.AFTER),
}

# Committing only changes the journal in memory, so nothing there can fail
# with an error; only an interrupt can arrive on either side of it.
FAULTS = {SiteKind.COMMIT: (Fault.INTERRUPT,)}


@dataclasses.dataclass(frozen=True)
class Scenario:
    """One command run on one template's seed project."""

    template: str
    seed: str
    command: Command = Command.INIT

    @property
    def name(self) -> str:
        """The scenario's name, as its site list file is named."""
        prefix = "" if self.command is Command.INIT else f"{self.command}-"
        return f"{prefix}{self.template}-{self.seed}"

    @property
    def argv(self) -> list[str]:
        """The command line the scenario runs."""
        if self.command is Command.SYNC:
            return ["protostar", "sync", "--json", "--no-config"]
        flags = [] if self.seed == "empty" else ["--force-merge"]
        return [
            "protostar",
            "init",
            "--json",
            "--no-config",
            "-t",
            self.template,
            *flags,
        ]

    @property
    def sites_file(self) -> Path:
        """The committed list of the sites a clean run passes, in order."""
        return SITES_DIR / f"{self.name}.txt"

    def recorded_sites(self) -> list[str]:
        """Returns the committed site list, or none before it is first recorded."""
        if not self.sites_file.exists():
            return []
        return self.sites_file.read_text(encoding="utf-8").splitlines()


@dataclasses.dataclass(frozen=True)
class Case:
    """One fault at one site of one scenario."""

    scenario: Scenario
    site: str
    position: Position
    fault: Fault

    @property
    def id(self) -> str:
        """The case's pytest id."""
        return f"{self.scenario.name}:{self.site}:{self.position}:{self.fault}"


def site_kind(site: str) -> SiteKind:
    """Returns the kind of a site from its id."""
    return SiteKind(site.split(":", 1)[0])


def site_target(site: str) -> str:
    """Returns what a site acts on: a path, a command, or the transaction."""
    return site.split(":", 1)[1].rsplit("#", 1)[0]


def cases(scenario: Scenario) -> list[Case]:
    """Returns every fault at every recorded site of a scenario."""
    return [
        Case(scenario, site, position, fault)
        for site in scenario.recorded_sites()
        for position in POSITIONS[site_kind(site)]
        for fault in FAULTS.get(site_kind(site), tuple(Fault))
    ]


# ---------------------------------------------------------------- seeds ---- #


def _seed_adopted(root: Path) -> None:
    """An existing project with no recipe: user files Protostar merges into."""
    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        "# The team's own notes stay.\n"
        "[project]\n"
        'name = "demo"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.12"\n'
        "\n"
        "[tool.custom]\n"
        "keep = true\n",
        encoding="utf-8",
    )
    pyproject.chmod(0o640)
    (root / ".gitignore").write_bytes(b"my-stuff/\r\n*.log\r\n")
    (root / "README.md").write_text("# Demo\n\nOur own readme.\n", encoding="utf-8")
    (root / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: ours\n"
        "        name: ours\n        entry: true\n        language: system\n",
        encoding="utf-8",
    )
    package = root / "src" / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Demo."""\n', encoding="utf-8")
    script = root / "run.sh"
    script.write_text("#!/bin/sh\necho run\n", encoding="utf-8")
    script.chmod(0o755)
    private = root / "local.cfg"
    private.write_text("token-free = true\n", encoding="utf-8")
    private.chmod(0o600)
    (root / "data.bin").write_bytes(bytes(range(256)))
    (root / "empty").mkdir()
    notes = root / "docs" / "notes" / "deep"
    notes.mkdir(parents=True)
    (notes / "keep.md").write_text("# Kept\n", encoding="utf-8")


def _seed_repository(root: Path) -> None:
    """The adopted project, already a git repository (so `git init` is skipped)."""
    _seed_adopted(root)
    git = root / ".git"
    for directory in ("hooks", "info", "objects/info", "objects/pack", "refs/heads"):
        (git / directory).mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "config").write_text(
        "[core]\n\trepositoryformatversion = 0\n\tbare = false\n", encoding="utf-8"
    )
    (git / "info" / "exclude").write_text("# ours\n", encoding="utf-8")


SEEDS: dict[str, Callable[[Path], None]] = {
    "empty": lambda _root: None,
    "adopted": _seed_adopted,
    "repository": _seed_repository,
}


def _retool(project: Path) -> None:
    """Edits an initialized project's recipe so sync has every kind of work.

    Turning tools off retracts their files, a dependency, and a generated
    hook (removals); turning one on adds a file; and a deleted hook makes
    sync install the hooks again.
    """
    import tomlkit

    pyproject = project / "pyproject.toml"
    document = tomlkit.parse(pyproject.read_text(encoding="utf-8"))
    recipe = document["tool"]["protostar"]
    tools = recipe.setdefault("tools", tomlkit.table())
    tools.update(
        {"renovate": False, "codecov": False, "commitizen": False, "agents": True}
    )
    pyproject.write_text(tomlkit.dumps(document), encoding="utf-8")
    (project / ".git" / "hooks" / "pre-push").unlink()


# What a sync scenario does to a freshly initialized empty project first.
SYNC_SEEDS: dict[str, Callable[[Path], None]] = {"retooled": _retool}

SCENARIOS = tuple(Scenario(t, s) for t in TEMPLATES for s in SEEDS) + tuple(
    Scenario(t, s, Command.SYNC) for t in ("cli", "lib") for s in SYNC_SEEDS
)


# ----------------------------------------------------------------- trees --- #


@dataclasses.dataclass(frozen=True)
class Node:
    """A filesystem node as rollback must restore it."""

    kind: str
    content: bytes | None
    mode: int | None


@dataclasses.dataclass(frozen=True)
class Tree:
    """Every node under a root, and each file's identity (inode, mtime)."""

    nodes: dict[str, Node]
    identities: dict[str, tuple[int, int]]

    @classmethod
    def capture(cls, root: Path, ignore: frozenset[str] = frozenset()) -> Tree:
        """Snapshots a tree without following symbolic links.

        Args:
            root: The directory to snapshot.
            ignore: Top-level names to leave out.
        """
        nodes: dict[str, Node] = {}
        identities: dict[str, tuple[int, int]] = {}
        # Windows reports no POSIX modes worth comparing.
        compare_modes = sys.platform != "win32"
        pending = [root]
        while pending:
            directory = pending.pop()
            for entry in os.scandir(directory):
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if relative in ignore:
                    continue
                info = entry.stat(follow_symlinks=False)
                mode = stat.S_IMODE(info.st_mode) if compare_modes else None
                if stat.S_ISDIR(info.st_mode):
                    nodes[relative] = Node("directory", None, mode)
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    nodes[relative] = Node("file", path.read_bytes(), mode)
                    identities[relative] = (info.st_ino, info.st_mtime_ns)
                else:
                    nodes[relative] = Node("other", None, mode)
        return cls(nodes, identities)

    def changed(self, other: Tree) -> list[str]:
        """Returns every path whose node differs in ``other``, sorted."""
        return sorted(
            path
            for path in self.nodes.keys() | other.nodes.keys()
            if self.nodes.get(path) != other.nodes.get(path)
        )

    def differences(self, other: Tree) -> list[str]:
        """Describes how ``other`` differs from this tree, one line per path."""
        lines = []
        for path in self.changed(other):
            before, after = self.nodes.get(path), other.nodes.get(path)
            if before is None:
                lines.append(f"left behind: {path}")
            elif after is None:
                lines.append(f"missing: {path}")
            elif before.kind != after.kind:
                lines.append(f"{path}: {before.kind} became {after.kind}")
            elif before.content != after.content:
                lines.append(f"{path}: content changed")
            else:
                lines.append(f"{path}: mode {before.mode:o} became {after.mode:o}")
        return lines


# ------------------------------------------------------------ the harness -- #


@dataclasses.dataclass(frozen=True)
class RollbackFault:
    """A second fault, raised while rollback restores the first one's damage.

    Attributes:
        path: A journaled path whose restore fails, relative to the project.
        interrupt: Whether a real SIGINT arrives as rollback starts.
        unstoppable: Whether the run's command survives being stopped before
            rollback.
    """

    path: str | None = None
    interrupt: bool = False
    unstoppable: bool = False


@dataclasses.dataclass(frozen=True)
class Declared:
    """A path the executor journaled for a command it is about to run."""

    path: Path
    tree: bool


class FaultInjector:
    """Names every site a run passes and fails the run at one of them."""

    def __init__(
        self,
        workspace: Path,
        runner: Runner,
        armed: Case | None = None,
        rollback: RollbackFault | None = None,
    ) -> None:
        self.workspace = workspace
        self.runner = runner
        self.armed = armed
        self.rollback = rollback
        self.sites: list[str] = []
        self.fired = False
        # The project as the commit left it, when a fault fires just after it.
        self.committed: Tree | None = None
        # Every path the journal captured, and those captured since the last
        # site: what the executor declared for the command about to run.
        self.journaled: set[Path] = set()
        self._declared: list[Declared] = []
        self._occurrences: Counter[tuple[SiteKind, str]] = Counter()
        self._real_run = system.ProcessRunner.run

    # -- naming -- #

    def _enter(self, kind: SiteKind, target: str) -> Position | None:
        """Records a site; returns the armed position when the fault is here."""
        self._occurrences[(kind, target)] += 1
        site = f"{kind}:{target}#{self._occurrences[(kind, target)]}"
        self.sites.append(site)
        if self.armed is not None and site == self.armed.site:
            return self.armed.position
        return None

    # -- faults -- #

    def _raise(self, kind: SiteKind, command: list[str] | None = None) -> None:
        assert self.armed is not None
        self.fired = True
        if self.armed.fault is Fault.INTERRUPT:
            raise KeyboardInterrupt
        if kind is SiteKind.COMMAND:
            assert command is not None
            raise CommandExecutionError(command, 1, stderr="injected fault")
        raise OSError(errno.EIO, "injected fault")

    # -- seams -- #

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Wraps the four seams and the journal for the rest of the test."""
        injector = self
        fs_class = fs_transaction.TransactionAwareFS
        write_bytes = fs_class.write_bytes
        ensure_directory = fs_class.ensure_directory
        remove_file = fs_class.remove_file
        record_mutation = journal.MutationJournal.record_mutation
        record_tree_creation = journal.MutationJournal.record_tree_creation
        commit = journal.MutationJournal.commit
        restore = journal.MutationJournal._restore

        def journaled(
            original: Callable[..., None], *, tree: bool
        ) -> Callable[..., None]:
            def capture(self: journal.MutationJournal, path: Path) -> None:
                original(self, path)
                normalized = self.normalize_path(path)
                injector.journaled.add(normalized)
                # A path journaled earlier in the run is declared again for
                # the command about to run, as the resolver does with
                # pyproject.toml.
                declared = Declared(normalized, tree)
                if declared not in injector._declared:
                    injector._declared.append(declared)

            return capture

        def filesystem(
            kind: SiteKind, original: Callable[..., None]
        ) -> Callable[..., None]:
            def seam(
                self: fs_transaction.TransactionAwareFS, path: Path, *args: Any
            ) -> None:
                normalized = self.journal.normalize_path(path)
                target = normalized.relative_to(self.journal.workspace_root)
                position = injector._enter(kind, target.as_posix())
                if position is Position.BEFORE:
                    injector._raise(kind)
                if position is Position.MID:
                    with injector._failing_replace():
                        original(self, path, *args)
                else:
                    original(self, path, *args)
                injector._declared.clear()
                if position is Position.AFTER:
                    injector._raise(kind)

            return seam

        def command(
            self: system.ProcessRunner,
            cmd: list[str],
            timeout: int | None = None,
            env: dict[str, str] | None = None,
        ) -> str:
            position = injector._enter(SiteKind.COMMAND, command_label(cmd))
            declared, injector._declared = injector._declared, []
            if position is Position.BEFORE:
                injector._raise(SiteKind.COMMAND, cmd)
            if position is Position.MID:
                injector._run_partially(cmd, declared)
                injector._raise(SiteKind.COMMAND, cmd)
            output = injector._run(self, cmd, declared, timeout, env)
            if position is Position.AFTER:
                injector._raise(SiteKind.COMMAND, cmd)
            return output

        monkeypatch.setattr(
            fs_class, "write_bytes", filesystem(SiteKind.WRITE, write_bytes)
        )
        monkeypatch.setattr(
            fs_class, "ensure_directory", filesystem(SiteKind.MKDIR, ensure_directory)
        )
        monkeypatch.setattr(
            fs_class, "remove_file", filesystem(SiteKind.REMOVE, remove_file)
        )
        monkeypatch.setattr(
            journal.MutationJournal,
            "record_mutation",
            journaled(record_mutation, tree=False),
        )
        monkeypatch.setattr(
            journal.MutationJournal,
            "record_tree_creation",
            journaled(record_tree_creation, tree=True),
        )

        def transaction(self: journal.MutationJournal) -> None:
            position = injector._enter(SiteKind.COMMIT, "transaction")
            if position is Position.BEFORE:
                injector._raise(SiteKind.COMMIT)
            commit(self)
            if position is Position.AFTER:
                injector.committed = Tree.capture(injector.workspace, DISCLAIMED)
                injector._raise(SiteKind.COMMIT)

        def restoring(path: Path, state: journal.OriginalState) -> str | None:
            fault = injector.rollback
            if fault is not None and fault.interrupt:
                # A real Ctrl+C, once, which rollback must shield itself from.
                injector.rollback = None
                os.kill(os.getpid(), signal.SIGINT)
            if (
                fault is not None
                and fault.path == path.relative_to(injector.workspace).as_posix()
            ):
                raise OSError(errno.EIO, "injected restore fault")
            return restore(path, state)

        def unstoppable(_self: system.ProcessRunner) -> None:
            raise ProcessTerminationError(UNSTOPPABLE_PID, "injected: still running")

        monkeypatch.setattr(system.ProcessRunner, "run", command)
        monkeypatch.setattr(journal.MutationJournal, "commit", transaction)
        if self.rollback is not None and self.rollback.unstoppable:
            monkeypatch.setattr(
                system.ProcessRunner, "terminate_active_process_tree", unstoppable
            )
        monkeypatch.setattr(
            journal.MutationJournal, "_restore", staticmethod(restoring)
        )

    def _failing_replace(self) -> contextlib.AbstractContextManager[Any]:
        """Fails the atomic write's final rename, after its temporary file exists.

        The patch lasts only for that one write, so rollback renames freely.
        """

        def fail(*_args: Any, **_kwargs: Any) -> None:
            self._raise(SiteKind.WRITE)

        return mock.patch.object(os, "replace", fail)

    # -- commands -- #

    def _run(
        self,
        runner: system.ProcessRunner,
        cmd: list[str],
        declared: list[Declared],
        timeout: int | None,
        env: dict[str, str] | None,
    ) -> str:
        if self.runner is Runner.REAL:
            return self._real_run(runner, cmd, timeout=timeout, env=env)
        if not fake_resolver(self.workspace, cmd, partial=False):
            for output in declared:
                fake_output(output, cmd)
        fake_environment(self.workspace, cmd)
        return ""

    def _run_partially(self, cmd: list[str], declared: list[Declared]) -> None:
        """Does part of a command's work: the first half of what it declared.

        Only the fake can stop at a known point; real commands are never
        failed mid-way.
        """
        assert self.runner is Runner.FAKE
        if not fake_resolver(self.workspace, cmd, partial=True):
            for output in declared[: (len(declared) + 1) // 2]:
                fake_output(output, cmd)


# A file a fake command creates, as the real command would leave it.
_FAKE_CONTENT = {
    "pyproject.toml": (
        b'[project]\nname = "project"\nversion = "0.1.0"\n'
        b'requires-python = ">=3.12"\ndependencies = []\n'
    ),
    ".python-version": b"3.12\n",
    "uv.lock": b'version = 1\nrequires-python = ">=3.12"\n',
}


def fake_output(output: Declared, command: list[str]) -> None:
    """Writes one path a command declared, as that command would change it.

    A declared tree gets a directory with one file in it; a declared file that
    exists gets a line appended (a comment, so TOML stays valid); a new one gets
    the content the real command would give it.
    """
    path = output.path
    line = f"# changed by {' '.join(command[:2])}\n".encode()
    if output.tree:
        path.mkdir(parents=True, exist_ok=True)
        (path / "created-by-command").write_bytes(line)
    elif path.is_file():
        path.write_bytes(path.read_bytes() + line)
    elif not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_FAKE_CONTENT.get(path.name, line))


def fake_resolver(workspace: Path, command: list[str], *, partial: bool) -> bool:
    """Does what ``uv add`` and ``uv lock`` do to the project, if it is one.

    The resolver journals ``pyproject.toml`` and ``uv.lock`` once and then
    runs several commands, so these write the files uv writes rather than
    what was declared since the last site. A later sync reads the
    requirements, so ``uv add`` records them as uv does.

    Args:
        workspace: The project.
        command: The command being faked.
        partial: Whether the command stops before it locks.

    Returns:
        Whether the command was a resolver command.
    """
    if command[:2] not in (["uv", "add"], ["uv", "lock"]):
        return False
    if command[1] == "add":
        _add_requirements(workspace / "pyproject.toml", command[2:])
    if not partial:
        lock = workspace / "uv.lock"
        line = f"# locked by {' '.join(command[:2])}\n".encode()
        lock.write_bytes(
            lock.read_bytes() + line if lock.exists() else _FAKE_CONTENT["uv.lock"]
        )
    return True


def _add_requirements(pyproject: Path, arguments: list[str]) -> None:
    """Adds requirements to a project, or a dependency group, as ``uv add`` does."""
    import tomlkit

    document = tomlkit.parse(pyproject.read_text(encoding="utf-8"))
    group = "dev" if "--dev" in arguments else None
    if "--group" in arguments:
        group = arguments[arguments.index("--group") + 1]
    packages = [
        word for word in arguments if not word.startswith("-") and word != group
    ]
    if group is None:
        target = document.setdefault("project", tomlkit.table())
        requirements = target.setdefault("dependencies", tomlkit.array())
    else:
        groups = document.setdefault("dependency-groups", tomlkit.table())
        requirements = groups.setdefault(group, tomlkit.array())
    for package in packages:
        requirements.append(f"{package}>=1.0")
    pyproject.write_text(tomlkit.dumps(document), encoding="utf-8")


def fake_environment(workspace: Path, command: list[str]) -> None:
    """Creates the project environment uv makes for the commands that need one."""
    if command[:2] in (["uv", "add"], ["uv", "run"], ["uv", "sync"]):
        venv = workspace / ".venv"
        venv.mkdir(exist_ok=True)
        (venv / "pyvenv.cfg").write_bytes(b"home = /usr/bin\n")


# ----------------------------------------------------------------- a run --- #


@dataclasses.dataclass(frozen=True)
class Outcome:
    """How one init run ended."""

    code: int
    payload: dict[str, Any]
    sites: list[str]
    journaled: frozenset[Path]
    fired: bool
    committed: Tree | None


@dataclasses.dataclass
class Workspace:
    """A seeded project and the home directory a run sees."""

    project: Path
    home: Path

    @classmethod
    def seed(
        cls, root: Path, scenario: Scenario, runner: Runner, cache: Path
    ) -> Workspace:
        """Creates the scenario's seed project under ``root``.

        A sync scenario starts from a project initialized with the same
        runner, built once in ``cache`` and copied, then changed by its seed.

        Args:
            root: Where the project and its home directory go.
            scenario: The scenario to seed.
            runner: How commands run, for a project a sync starts from.
            cache: Where initialized projects are kept between tests.
        """
        # A fixed name: an empty project takes its package name from it.
        project = root / "project"
        home = root / "home"
        home.mkdir(parents=True)
        if scenario.command is Command.SYNC:
            initialized = _initialized(scenario, runner, cache)
            # The environment's scripts name its own path; uv rebuilds it.
            shutil.copytree(
                initialized, project, symlinks=True, ignore=_ignore_environment
            )
            SYNC_SEEDS[scenario.seed](project)
        else:
            project.mkdir(parents=True)
            SEEDS[scenario.seed](project)
        return cls(project, home)

    def capture(self) -> tuple[Tree, Tree]:
        """Snapshots the project and the home directory."""
        return (
            Tree.capture(self.project, DISCLAIMED),
            Tree.capture(self.home, DISCLAIMED_HOME),
        )


def _ignore_environment(directory: str, names: list[str]) -> set[str]:
    return {".venv"} & set(names) if Path(directory).name == "project" else set()


def _initialized(scenario: Scenario, runner: Runner, cache: Path) -> Path:
    """Returns the project a sync scenario's template initializes, built once."""
    root = cache / f"{scenario.template}-{runner}"
    if not root.exists():
        start = Scenario(scenario.template, "empty")
        workspace = Workspace.seed(root, start, runner, cache)
        with pytest.MonkeyPatch.context() as monkeypatch:
            outcome = run(workspace, start, runner, monkeypatch)
        assert outcome.code == 0, outcome.payload
    return root / "project"


def run(
    workspace: Workspace,
    scenario: Scenario,
    runner: Runner,
    monkeypatch: pytest.MonkeyPatch,
    armed: Case | None = None,
    rollback: RollbackFault | None = None,
) -> Outcome:
    """Runs the scenario's command in-process, failing it at the armed site.

    A run interrupted after it committed prints no payload: the CLI reports
    a plain interrupt on stderr, so the payload is empty.
    """
    import io
    import json

    from protostar.cli import ui
    from protostar.cli.main import main
    from protostar.registry import clear_hook_registry_cache

    monkeypatch.chdir(workspace.project)
    monkeypatch.setenv("HOME", str(workspace.home))
    monkeypatch.setenv("USERPROFILE", str(workspace.home))
    # Fallback hook pins: no network, and the same files on every host. The
    # registry is fetched once per process, so drop an earlier test's fetch.
    monkeypatch.setenv("PROTOSTAR_OFFLINE_HOOK_REGISTRY", "1")
    # Rollback restores what is on disk; whether it would survive a power cut
    # is not under test, and syncing every write is slow on Windows.
    monkeypatch.setattr(os, "fsync", lambda _descriptor: None)
    clear_hook_registry_cache()
    monkeypatch.setattr(ui, "is_json_mode", False)
    monkeypatch.setattr("sys.argv", scenario.argv)
    injector = FaultInjector(workspace.project.resolve(), runner, armed, rollback)
    stdout = io.StringIO()
    with monkeypatch.context() as patches, contextlib.redirect_stdout(stdout):
        injector.install(patches)
        code = 0
        try:
            main()
        except SystemExit as exit_:
            code = int(exit_.code or 0)
        finally:
            clear_hook_registry_cache()
    out = stdout.getvalue()
    return Outcome(
        code=code,
        payload=json.loads(out) if out else {},
        sites=injector.sites,
        journaled=frozenset(injector.journaled),
        fired=injector.fired,
        committed=injector.committed,
    )


def unaccounted(
    workspace: Path, before: Tree, after: Tree, journaled: frozenset[Path]
) -> list[str]:
    """Returns each changed path no journal entry covers.

    A path is covered when it, or a directory it sits in, was journaled: a
    declared tree accounts for everything a command writes inside it.
    """
    covered = {path.relative_to(workspace).as_posix() for path in journaled}
    changed = before.changed(after)

    def is_covered(path: str) -> bool:
        parts = path.split("/")
        return any("/".join(parts[:i]) in covered for i in range(1, len(parts) + 1))

    return sorted(path for path in changed if not is_covered(path))
