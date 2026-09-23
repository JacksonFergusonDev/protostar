"""Live preview of the planned files, re-planned off the main thread."""

import asyncio

from rich.console import RenderableType
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
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

    def __init__(self, config: UserConfig) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose the summary, collision, and tree lines."""
        yield Static("Planning…", id="preview-summary")
        yield Static("", id="preview-collisions")
        yield Static("", id="preview-tree")

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
            self._show(Text(f"Waiting for values: {', '.join(exc.variables)}."))
            return
        except ProtostarError as exc:
            self._show(Text(str(exc)), error=True)
            return
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

    def _show(
        self,
        summary: Text,
        *,
        collisions: Text | None = None,
        tree: RenderableType = "",
        error: bool = False,
    ) -> None:
        line = self.query_one("#preview-summary", Static)
        line.update(summary)
        line.set_class(error, "-error")
        self.query_one("#preview-collisions", Static).update(collisions or Text(""))
        self.query_one("#preview-tree", Static).update(tree)
