from rich.text import Text

from protostar.docs_registry import DocsPage


def format_docs_link(page: DocsPage, anchor: str | None = None) -> Text:
    """Creates a Rich Text object formatted as a clickable documentation hyperlink.

    Args:
        page: The registered documentation page enum.
        anchor: Optional anchor to link to a specific section.

    Returns:
        A Rich Text object with OSC 8 hyperlink formatting.
    """
    url = page.build_url(anchor)
    return Text.from_markup(
        f"[bold cyan][link={url}]Docs: {page.label} ↗[/link][/bold cyan]"
    )
