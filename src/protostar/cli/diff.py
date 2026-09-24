"""Text normalization and styling shared by plain and styled diff presentations."""

from rich.text import Text


def normalize_newlines(text: str) -> str:
    """Normalize CRLF and CR to LF for human-readable diffs."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def format_diff(diff: str) -> Text:
    """Style unified diff hunks with Rich styles matching git diff.

    Args:
        diff: The raw unified diff text.

    Returns:
        A Rich Text object with diff hunk coloring.
    """
    result = Text()
    in_hunks = False
    for line in diff.splitlines(keepends=True):
        if line.startswith("@@"):
            in_hunks = True
            result.append(line, style="cyan")
        elif not in_hunks and (line.startswith("+++") or line.startswith("---")):
            result.append(line, style="bold")
        elif line.startswith("+"):
            result.append(line, style="green")
        elif line.startswith("-"):
            result.append(line, style="red")
        else:
            result.append(line)
    return result
