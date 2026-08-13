"""Utility functions for Protostar."""


def generate_python_version_range(min_version: str, max_minor: int = 15) -> list[str]:
    """Generates a list of Python version strings from the minimum up to a maximum minor version.

    Args:
        min_version: The minimum Python version (e.g. "3.9").
        max_minor: The maximum minor version to generate up to. Defaults to 15.

    Returns:
        A list of version strings (e.g. ["3.9", "3.10", ...]).
    """
    versions = []
    try:
        major, minor = map(int, min_version.split("."))
        if major == 3:
            for v in range(minor, max_minor):
                versions.append(f"3.{v}")
    except Exception:
        pass
    return versions
