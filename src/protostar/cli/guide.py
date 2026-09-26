"""CLI presentation of ``protostar guide``."""

import argparse

from rich.console import Group, RenderableType
from rich.text import Text

from protostar.cli import schema, ui
from protostar.guide import ProjectGuide, project_guide


def render_guide(guide: ProjectGuide) -> Group:
    """Renders the guide as a section, one block per action.

    Commands are printed alone on their lines, so each copies cleanly.

    Args:
        guide: The guide to render.

    Returns:
        A ``Guide`` heading over the actions and notes, then the missing tools
        and the command that installs them, when any is missing.
    """
    blocks: list[RenderableType] = []
    for action in guide.actions:
        lines: list[RenderableType] = [
            Text(action.title, "bold"),
            # Explanations quote commands in backticks: data, never markup.
            Text(action.explanation, "dim"),
        ]
        lines.extend(Text(f"    {command}", "bold cyan") for command in action.commands)
        lines.extend(
            Text(f"    {path}", ui.path_style(path.rsplit("/", 1)[-1], directory=False))
            for path in action.paths
        )
        blocks.extend([*lines, Text("")])
    blocks.extend(Text(note.message) for note in guide.notes)
    if not guide.actions and not guide.notes:
        blocks.append(
            Text("This project records nothing the guide can describe.", "dim")
        )
    while blocks and isinstance(blocks[-1], Text) and not blocks[-1].plain:
        blocks.pop()
    parts: list[RenderableType] = [ui.heading("Guide"), ui.indented(Group(*blocks))]
    if guide.missing_tools:
        parts.extend(
            [
                Text(""),
                ui.missing_tools_report(
                    guide.missing_tools, ui.missing_install(guide.missing_tools)
                ),
            ]
        )
    return Group(*parts)


def handle_guide(args: argparse.Namespace) -> None:
    """Prints how to run, test, check, and document the current project."""
    guide = project_guide()
    if ui.is_json_mode:
        ui.emit_json(
            {
                "api_version": schema.CLI_API_VERSION,
                "status": "success",
                "guide": guide.to_dict(),
                **ui.missing_tools_payload(guide.missing_tools),
            }
        )
        return
    ui.console.print(render_guide(guide))
