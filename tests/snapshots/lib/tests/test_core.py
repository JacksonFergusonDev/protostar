"""Tests for the core library module."""

from demo_project.core import greet


def test_greet_default() -> None:
    """Default name produces the expected greeting."""
    assert greet() == "Hello, world!"


def test_greet_custom() -> None:
    """Custom name is reflected in the greeting."""
    assert greet("Ada") == "Hello, Ada!"
