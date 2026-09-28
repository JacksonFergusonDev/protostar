"""Live preview of what the draft changes, re-planned off the main thread."""

import asyncio
import contextlib
import functools
import threading
from collections.abc import Callable
from dataclasses import replace

from rich.console import RenderableType
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from protostar.cli.changes import (
    NETWORK_NOTE,
    HookSnapshot,
    Review,
    count,
    entry_tree,
    hook_snapshot,
    plan_draft,
    prepare_draft,
    summary,
)
from protostar.cli.ui import plan_tree, planned_paths
from protostar.config import UserConfig
from protostar.errors import MissingTemplateVariablesError, ProtostarError
from protostar.init_draft import InitDraft
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.registry import ResolvedHookRevision

# A warm plan() takes 1-11 ms and preparing up to ~100 ms, so the pause only
# folds a burst of changes into one run.
DEBOUNCE_SECONDS = 0.1


def _error(error: ProtostarError) -> Text:
    message = Text(str(error))
    if error.hint:
        message.append(f"  {error.hint}", style="dim")
    return message


class PlanPreview(VerticalScroll):
    """What the current draft changes: each planned file's change, and the totals.

    With ``prepare`` it prepares the draft's review, so every file says what
    init does to it (new, modified, or a conflict) exactly as the change
    review will; the review is where those decisions are settled. Without
    it, the preview only plans, for a step that leads to no review.
    """

    class PlanUpdated(Message):
        """Posted when planning finishes or fails."""

        def __init__(self, *, error: ProtostarError | None = None) -> None:
            super().__init__()
            self.error = error

    def __init__(self, config: UserConfig, *, prepare: bool = True) -> None:
        super().__init__()
        self.config = config
        self.prepare = prepare
        self.hooks: HookSnapshot | None = None
        """The registry snapshot, once its fetch has finished."""
        self._fetch: asyncio.Future[HookSnapshot] | None = None
        self._review: Review | None = None
        self._reviewed: InitDraft | None = None
        # Held, not queried: a plan can finish while the app tears its
        # children down, and updating a removed line is harmless.
        self._network = Static(Text(NETWORK_NOTE), id="preview-network")
        self._summary = Static("Planning…", id="preview-summary")
        self._notes = Static("", id="preview-notes")
        self._tree = Static("", id="preview-tree")

    def compose(self) -> ComposeResult:
        """Compose the network warning, summary, skipped steps, and tree."""
        yield self._network
        yield self._summary
        yield self._notes
        yield self._tree

    def review_of(self, draft: InitDraft) -> Review | None:
        """Returns the review the preview shows, if it was prepared for ``draft``.

        Args:
            draft: The draft about to be reviewed.

        Returns:
            The prepared review, or ``None`` if the preview shows another draft.
        """
        return self._review if self._reviewed == draft else None

    @work(exclusive=True, group="preview")
    async def update_plan(self, draft: InitDraft) -> None:
        """Re-plan the draft and prepare its review; a newer call cancels this one.

        ``plan()`` and ``prepare_review()`` are read-only, so they run in a
        thread. ``execute()`` never runs while the app does.
        """
        self._review = self._reviewed = None
        await asyncio.sleep(DEBOUNCE_SECONDS)
        # The review prepares with this strategy unless the user changes it there.
        planned = replace(
            draft,
            collision_strategy=draft.collision_strategy or CollisionStrategy.MERGE,
        )
        try:
            request, manifest = await asyncio.to_thread(
                plan_draft, planned, self.config
            )
            review = (
                await asyncio.to_thread(
                    prepare_draft,
                    request,
                    manifest,
                    self.config,
                    await self._snapshot(manifest),
                    {},
                )
                if self.prepare
                else None
            )
        except MissingTemplateVariablesError as exc:
            self._show(Text(f"Waiting for values: {', '.join(exc.variables)}."))
            self.post_message(self.PlanUpdated(error=None))
            return
        except ProtostarError as exc:
            self._show(_error(exc), error=True)
            self.post_message(self.PlanUpdated(error=exc))
            return
        notes = Text("\n".join(event.message for event in manifest.diagnostics), "dim")
        if review is None:
            paths, _ = planned_paths(manifest)
            self._show(
                _totals(manifest, len(paths)),
                notes=notes,
                tree=plan_tree(manifest) if paths else "",
            )
        else:
            self._review, self._reviewed = review, draft
            self._show(
                _review_summary(review),
                notes=notes,
                tree=entry_tree(review.entries) if review.entries else "",
            )
        self.post_message(self.PlanUpdated(error=None))

    def on_mount(self) -> None:
        """Start taking the registry snapshot while the user reads the screen."""
        self._network.display = False
        if self.prepare:
            self._start_fetch()

    def _start_fetch(self) -> asyncio.Future[HookSnapshot]:
        if self._fetch is None:
            self._fetch = _in_background(hook_snapshot)
            self._fetch.add_done_callback(self._fetched)
        return self._fetch

    def _fetched(self, fetch: asyncio.Future[HookSnapshot]) -> None:
        """Keep the snapshot, and warn at once if it never reached the network."""
        if fetch.cancelled() or fetch.exception() is not None:
            return
        self.hooks = fetch.result()
        self._network.display = self.hooks.unreachable

    async def _snapshot(
        self, manifest: EnvironmentManifest
    ) -> tuple[ResolvedHookRevision, ...]:
        """Returns the snapshot's pins, waiting only if it is still being taken.

        The fetch outlives a cancelled preview, so one snapshot serves the
        preview, the review, and execution.
        """
        if not manifest.tooling.wants_hooks:
            return ()
        return (await asyncio.shield(self._start_fetch())).revisions

    def show_error(self, error: ProtostarError) -> None:
        """Show an error the editor found before planning, in place of the plan."""
        self.workers.cancel_group(self, "preview")
        self._review = self._reviewed = None
        self._show(_error(error), error=True)

    def _show(
        self,
        summary: Text,
        *,
        notes: Text | None = None,
        tree: RenderableType = "",
        error: bool = False,
    ) -> None:
        self._summary.update(summary)
        self._summary.set_class(error, "-error")
        self._notes.update(notes or Text(""))
        # Most plans skip nothing, so the line takes no room until one does.
        self._notes.display = bool(notes and notes.plain)
        self._tree.update(tree)


def _in_background[T](function: Callable[[], T]) -> asyncio.Future[T]:
    """Runs ``function`` on a daemon thread and returns a future of its result.

    Unlike ``asyncio.to_thread``, a daemon thread never holds up the app's
    exit: a DNS lookup that hangs offline has no timeout of its own.
    """
    loop = asyncio.get_running_loop()
    future: asyncio.Future[T] = loop.create_future()

    def settle(outcome: Callable[[], None]) -> None:
        if not future.done():
            outcome()

    def run() -> None:
        try:
            result = function()
        except Exception as error:
            report = functools.partial(future.set_exception, error)
        else:
            report = functools.partial(future.set_result, result)
        # The app may have exited, closing the loop, while this ran.
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(settle, report)

    threading.Thread(target=run, name="hook-registry", daemon=True).start()
    return future


def _totals(manifest: EnvironmentManifest, paths: int) -> Text:
    dependencies = manifest.dependencies
    packages = (
        len(dependencies.dependencies)
        + len(dependencies.dev_dependencies)
        + len(dependencies.docs_dependencies)
    )
    tasks = len(manifest.tasks.system_tasks) + len(manifest.tasks.post_install_tasks)
    return Text(
        " · ".join(
            count(number, noun)
            for number, noun in (
                (paths, "path"),
                (packages, "package"),
                (tasks, "task"),
            )
        )
    )


def _review_summary(review: Review) -> Text:
    line = summary(review)
    if review.prepared.conflicts or review.prepared.proposals:
        # The editor shows decisions; the next screen is where they are made.
        line.append("\nSettled on the next screen.", "dim")
    return line
