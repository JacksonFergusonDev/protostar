"""Core library logic."""


def greet(name: str = "world") -> str:
    """Return a greeting string.

    Args:
        name: The name to greet.

    Returns:
        A greeting of the form ``"Hello, <name>!"``.
    """
    return f"Hello, {name}!"
