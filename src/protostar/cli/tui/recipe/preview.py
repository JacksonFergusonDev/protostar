"""Live preview of the planned files, re-planned off the main thread."""

import asyncio

from rich.console import RenderableType
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from protostar.cli.ui import plan_tree, planned_paths
from protostar.config import UserConfig
from protostar.errors import MissingTemplateVariablesError, ProtostarError
from protostar.init_draft import InitDraft, resolve_init
from protostar.manifest import EnvironmentManifest
from protostar.orchestrator import Orchestrator

# A warm plan() takes 1-7 ms, so the pause only folds a burst of changes into one run.
DEBOUNCE_SECONDS = 0.1


def _plan(draft: InitDraft, config: UserConfig) -> EnvironmentManifest:
    modules, request = resolve_init(draft, config)
    return Orchestrator(modules, config, request=request).plan()


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


class PlanPreview(VerticalScroll):
    """The tree ``--dry-run`` prints, plus any collisions, for the current draft."""

    class PlanUpdated(Message):
        """Posted when planning finishes or fails."""

        def __init__(self, *, error: ProtostarError | None = None) -> None:
            super().__init__()
            self.error = error

    def __init__(self, config: UserConfig) -> None:
        super().__init__()
        self.config = config
        self.error: ProtostarError | None = None
        # Held, not queried: a plan can finish while the app tears its
        # children down, and updating a removed line is harmless.
        self._summary = Static("Planning…", id="preview-summary")
        self._collisions = Static("", id="preview-collisions")
        self._tree = Static("", id="preview-tree")

    def compose(self) -> ComposeResult:
        """Compose the summary, collision, and tree lines."""
        yield self._summary
        yield self._collisions
        yield self._tree

    @work(exclusive=True, group="preview")
    async def update_plan(self, draft: InitDraft) -> None:
        """Re-plan the draft; a newer call cancels this one.

        ``plan()`` is read-only, so it runs in a thread. ``execute()`` never
        runs while the app does.
        """
        await asyncio.sleep(DEBOUNCE_SECONDS)
        try:
            manifest = await asyncio.to_thread(_plan, draft, self.config)
        except MissingTemplateVariablesError as exc:
            self.error = None
            self._show(Text(f"Waiting for values: {', '.join(exc.variables)}."))
            self.post_message(self.PlanUpdated(error=None))
            return
        except ProtostarError as exc:
            self.error = exc
            hint = f"  {exc.hint}" if exc.hint else ""
            self._show(
                Text.assemble(str(exc), (hint, "dim") if hint else ""),
                error=True,
            )
            self.post_message(self.PlanUpdated(error=exc))
            return
        self.error = None
        paths, _ = planned_paths(manifest)
        dependencies = manifest.dependencies
        packages = (
            len(dependencies.dependencies)
            + len(dependencies.dev_dependencies)
            + len(dependencies.docs_dependencies)
        )
        tasks = len(manifest.tasks.system_tasks) + len(
            manifest.tasks.post_install_tasks
        )
        collisions = sorted(path.as_posix() for path in manifest.collisions)
        self._show(
            Text(
                " · ".join(
                    _count(number, noun)
                    for number, noun in (
                        (len(paths), "path"),
                        (packages, "package"),
                        (tasks, "task"),
                    )
                )
            ),
            collisions=Text(f"Already exist: {', '.join(collisions)}")
            if collisions
            else Text(""),
            tree=plan_tree(manifest) if paths else Text(""),
        )
        self.post_message(self.PlanUpdated(error=None))

    def _show(
        self,
        summary: Text,
        *,
        collisions: Text | None = None,
        tree: RenderableType = "",
        error: bool = False,
    ) -> None:
        self._summary.update(summary)
        self._summary.set_class(error, "-error")
        self._collisions.update(collisions or Text(""))
        self._tree.update(tree)
