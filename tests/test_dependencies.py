import pytest

from protostar.dependencies import DependencyGroup, install_dependencies
from protostar.errors import CommandExecutionError, CommandTimeoutError
from protostar.manifest import DependencyManifest
from protostar.system import ProcessRunner


def test_install_dependencies_uv(mocker):
    """Dependency groups are installed with their explicit uv arguments."""
    runner = mocker.MagicMock(spec=ProcessRunner)

    install_dependencies(
        DependencyManifest(
            dependencies=["fastapi"],
            dev_dependencies=["pytest"],
            docs_dependencies=["mkdocs"],
        ),
        runner,
    )

    assert runner.run.call_args_list == [
        mocker.call(["uv", "add", "fastapi"], timeout=600),
        mocker.call(["uv", "add", "--dev", "pytest"], timeout=600),
        mocker.call(["uv", "add", "--group", "docs", "mkdocs"], timeout=600),
    ]


def test_install_dependencies_empty(mocker):
    """An empty dependency manifest does not start a process."""
    runner = mocker.MagicMock(spec=ProcessRunner)

    install_dependencies(DependencyManifest(), runner)

    runner.run.assert_not_called()


def test_install_dependencies_command_failure_is_fatal(mocker):
    """A failed dependency group aborts installation immediately."""
    runner = mocker.MagicMock(spec=ProcessRunner)
    error = CommandExecutionError(
        command=["uv", "add", "invalid"], returncode=1, stderr="not found"
    )
    runner.run.side_effect = error

    with pytest.raises(CommandExecutionError) as exc_info:
        install_dependencies(
            DependencyManifest(dependencies=["invalid"], dev_dependencies=["pytest"]),
            runner,
        )

    assert exc_info.value is error
    runner.run.assert_called_once_with(["uv", "add", "invalid"], timeout=600)


def test_install_dependencies_timeout_is_fatal(mocker):
    """A dependency timeout aborts installation immediately."""
    runner = mocker.MagicMock(spec=ProcessRunner)
    runner.run.side_effect = CommandTimeoutError(
        command=["uv", "add", "large"], timeout=600
    )

    with pytest.raises(CommandTimeoutError):
        install_dependencies(
            DependencyManifest(dependencies=["large"]),
            runner,
        )


def test_dependency_group_properties():
    assert DependencyGroup.MAIN.cli_args == []
    assert DependencyGroup.MAIN.label == "standard"
    assert DependencyGroup.DEV.cli_args == ["--dev"]
    assert DependencyGroup.DEV.label == "development"
    assert DependencyGroup.DOCS.cli_args == ["--group", "docs"]
    assert DependencyGroup.DOCS.label == "documentation"
