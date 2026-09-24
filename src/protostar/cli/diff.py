"""Text normalization shared by plain and styled diff presentations."""


def normalize_newlines(text: str) -> str:
    """Normalize CRLF and CR to LF for human-readable diffs."""
    return text.replace("\r\n", "\n").replace("\r", "\n")
