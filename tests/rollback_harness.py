"""Fault injection for rollback: fail a real init at one site, then compare trees.

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
import stat
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from protostar import fs_transaction, journal, system
from protostar.errors import CommandExecutionError

SITES_DIR = Path(__file__).parent / "rollback_sites"

TEMPLATES = ("api", "astro", "cli", "lib", "ml")

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

# Command-line tokens that take the following token as their value, so a
# site label never mistakes the value for a package.
_VALUED_OPTIONS = frozenset({"--group", "--python"})


class SiteKind(enum.StrEnum):
    """What a site does."""

    WRITE = "write"
    MKDIR = "mkdir"
    REMOVE = "remove"
    COMMAND = "command"


class Position(enum.StrEnum):
    """When a fault fires, relative to the site's operation."""

    BEFORE = "before"
    MID = "mid"
    AFTER = "after"


class Fault(enum.StrEnum):
    """How the run fails."""

    ERROR = "error"
    INTERRUPT = "interrupt"


class Runner(enum.StrEnum):
    """Whether commands run for real or through the fake."""

    FAKE = "fake"
    REAL = "real"


POSITIONS = {
    SiteKind.WRITE: (Position.BEFORE, Position.MID, Position.AFTER),
    SiteKind.MKDIR: (Position.BEFORE, Position.AFTER),
    SiteKind.REMOVE: (Position.BEFORE, Position.AFTER),
    SiteKind.COMMAND: (Position.BEFORE, Position.MID, Position.AFTER),
}


@dataclasses.dataclass(frozen=True)
class Scenario:
    """One template initialized into one seed project."""

    template: str
    seed: str

    @property
    def name(self) -> str:
        """The scenario's name, as its site list file is named."""
        return f"{self.template}-{self.seed}"

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


def cases(scenario: Scenario) -> list[Case]:
    """Returns every fault at every recorded site of a scenario."""
    return [
        Case(scenario, site, position, fault)
        for site in scenario.recorded_sites()
        for position in POSITIONS[site_kind(site)]
        for fault in Fault
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

SCENARIOS = tuple(Scenario(t, s) for t in TEMPLATES for s in SEEDS)


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

    def differences(self, other: Tree) -> list[str]:
        """Describes how ``other`` differs from this tree, one line per path."""
        lines = []
        for path in sorted(self.nodes.keys() | other.nodes.keys()):
            before, after = self.nodes.get(path), other.nodes.get(path)
            if before == after:
                continue
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
    ) -> None:
        self.workspace = workspace
        self.runner = runner
        self.armed = armed
        self.sites: list[str] = []
        self.fired = False
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

    @staticmethod
    def command_label(command: list[str]) -> str:
        """Names a command by its program, words, and options.

        Option values (a Python version) and the packages ``uv add`` takes are
        left out, so the id is the same on every host and for every package.
        """
        words = [Path(command[0]).stem]
        is_add = command[1:2] == ["add"]
        skip = False
        for word in command[1:]:
            if skip:
                skip = False
            elif word.startswith("-"):
                words.append(word)
                skip = word in _VALUED_OPTIONS
            elif not (is_add and len(words) > 1):
                words.append(word)
        return " ".join(words)

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

        def journaled(
            original: Callable[..., None], *, tree: bool
        ) -> Callable[..., None]:
            def capture(self: journal.MutationJournal, path: Path) -> None:
                original(self, path)
                normalized = self.normalize_path(path)
                if normalized not in injector.journaled:
                    injector.journaled.add(normalized)
                    injector._declared.append(Declared(normalized, tree))

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
            position = injector._enter(SiteKind.COMMAND, injector.command_label(cmd))
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
        monkeypatch.setattr(system.ProcessRunner, "run", command)

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


@dataclasses.dataclass
class Workspace:
    """A seeded project and the home directory a run sees."""

    project: Path
    home: Path

    @classmethod
    def seed(cls, root: Path, scenario: Scenario) -> Workspace:
        """Creates the scenario's seed project under ``root``."""
        # A fixed name: an empty project takes its package name from it.
        project = root / "project"
        home = root / "home"
        project.mkdir()
        home.mkdir()
        SEEDS[scenario.seed](project)
        return cls(project, home)

    def capture(self) -> tuple[Tree, Tree]:
        """Snapshots the project and the home directory."""
        return (
            Tree.capture(self.project, DISCLAIMED),
            Tree.capture(self.home, DISCLAIMED_HOME),
        )


def init(
    workspace: Workspace,
    scenario: Scenario,
    runner: Runner,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    armed: Case | None = None,
) -> Outcome:
    """Runs ``protostar init --json`` in-process, failing it at the armed site."""
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
    flags = [] if scenario.seed == "empty" else ["--force-merge"]
    monkeypatch.setattr(
        "sys.argv",
        ["protostar", "init", "--json", "--no-config", "-t", scenario.template, *flags],
    )
    injector = FaultInjector(workspace.project.resolve(), runner, armed)
    with monkeypatch.context() as patches:
        injector.install(patches)
        code = 0
        try:
            main()
        except SystemExit as exit_:
            code = int(exit_.code or 0)
        finally:
            clear_hook_registry_cache()
    return Outcome(
        code=code,
        payload=json.loads(capsys.readouterr().out),
        sites=injector.sites,
        journaled=frozenset(injector.journaled),
        fired=injector.fired,
    )


def unaccounted(
    workspace: Path, before: Tree, after: Tree, journaled: frozenset[Path]
) -> list[str]:
    """Returns each changed path no journal entry covers.

    A path is covered when it, or a directory it sits in, was journaled: a
    declared tree accounts for everything a command writes inside it.
    """
    covered = {path.relative_to(workspace).as_posix() for path in journaled}
    changed = {
        path
        for path in before.nodes.keys() | after.nodes.keys()
        if before.nodes.get(path) != after.nodes.get(path)
    }

    def is_covered(path: str) -> bool:
        parts = path.split("/")
        return any("/".join(parts[:i]) in covered for i in range(1, len(parts) + 1))

    return sorted(path for path in changed if not is_covered(path))
