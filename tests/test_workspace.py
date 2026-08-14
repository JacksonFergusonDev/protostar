from pathlib import Path

import pytest

from protostar.workspace import (
    generate_python_version_range,
    resolve_package_name,
    resolve_project_name,
    sanitize_package_name,
)


def test_generate_python_version_range() -> None:
    versions = generate_python_version_range("3.12", max_minor=15)
    assert versions == ["3.12", "3.13", "3.14"]

    assert generate_python_version_range("invalid") == []


@pytest.mark.parametrize(
    ("input_name", "expected"),
    [
        ("my-cool-cli", "my_cool_cli"),
        ("My-Cool-CLI", "my_cool_cli"),
        ("my.package.name", "my_package_name"),
        ("my package", "my_package"),
        ("my__package", "my_package"),
        ("---leading-trailing---", "leading_trailing"),
        ("123-numbers", "pkg_123_numbers"),
        ("42", "pkg_42"),
        ("", "app"),
        ("___", "app"),
        ("valid_name_123", "valid_name_123"),
    ],
)
def test_sanitize_package_name(input_name: str, expected: str) -> None:
    assert sanitize_package_name(input_name) == expected


def test_resolve_project_name_from_metadata() -> None:
    assert resolve_project_name({"project_name": "meta-project"}) == "meta-project"
    assert resolve_project_name({"name": "meta-name"}) == "meta-name"


def test_resolve_project_name_from_pyproject(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "file-project"\n')
    assert resolve_project_name(pyproject_path=pyproject) == "file-project"


def test_resolve_project_name_fallback_default() -> None:
    assert (
        resolve_project_name(
            metadata={},
            pyproject_path=Path("nonexistent_pyproject.toml"),
            default="fallback-app",
        )
        == "fallback-app"
    )


def test_resolve_package_name() -> None:
    assert resolve_package_name({"package_name": "custom_pkg"}) == "custom_pkg"
    assert resolve_package_name({"project_name": "my-app"}) == "my_app"
    assert (
        resolve_package_name(
            pyproject_path=Path("nonexistent_pyproject.toml"),
            default="my-cool-app",
        )
        == "my_cool_app"
    )
