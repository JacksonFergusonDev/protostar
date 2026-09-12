"""Unit tests for protostar domain exceptions and exit codes."""

from pathlib import Path
from unittest.mock import patch

import pytest

from protostar.docs_registry import DocsPage
from protostar.errors import (
    DOCS_BASE_URL,
    AggregatedDependencyError,
    CommandExecutionError,
    CommandTimeoutError,
    ConfigurationError,
    ExecutionAbortedError,
    ExitCode,
    FileSystemError,
    InvalidUsageError,
    MissingDependencyError,
    NetworkFetchError,
    PartialExecutionAbortedError,
    ProtostarError,
    SecurityViolationError,
    TemplateResolutionError,
    WorkspaceCollisionError,
)
from protostar.system_deps import GlobalExecutable


def test_exit_code_values():
    """Ensure standard POSIX-aligned exit codes."""
    assert ExitCode.OK.value == 0
    assert ExitCode.USAGE.value == 64
    assert ExitCode.DATAERR.value == 65
    assert ExitCode.UNAVAILABLE.value == 69
    assert ExitCode.SOFTWARE.value == 70
    assert ExitCode.OSERR.value == 71
    assert ExitCode.IOERR.value == 74
    assert ExitCode.TEMPFAIL.value == 75
    assert ExitCode.NOPERM.value == 77
    assert ExitCode.CONFIG.value == 78


def test_protostar_error_hint_and_docs_url():
    """Test ProtostarError base attributes and docs_url resolution."""
    err = ProtostarError("Failure summary", hint="Try turning it off and on again")
    assert err.hint == "Try turning it off and on again"
    assert str(err) == "Failure summary"
    # When docs_path is not set, docs_url should be None
    assert err.docs_url is None

    # Custom DocsPage enum
    err_page = ProtostarError("Failure", docs_path=DocsPage.CONFIGURATION)
    assert err_page.docs_url == f"{DOCS_BASE_URL}usage/configuration/"

    # String docs_path (with and without leading slash)
    err_str = ProtostarError("Failure", docs_path="usage/advanced/")
    assert err_str.docs_url == f"{DOCS_BASE_URL}usage/advanced/"

    err_slash = ProtostarError("Failure", docs_path="/usage/advanced/")
    assert err_slash.docs_url == f"{DOCS_BASE_URL}usage/advanced/"

    # Docs anchor (with and without leading #)
    err_anchor = ProtostarError(
        "Failure", docs_path="usage/advanced/", docs_anchor="section-1"
    )
    assert err_anchor.docs_url == f"{DOCS_BASE_URL}usage/advanced/#section-1"

    err_hash_anchor = ProtostarError(
        "Failure", docs_path="usage/advanced/", docs_anchor="#section-2"
    )
    assert err_hash_anchor.docs_url == f"{DOCS_BASE_URL}usage/advanced/#section-2"


def test_configuration_error_defaults():
    err = ConfigurationError("Bad config", hint="Check syntax")
    assert str(err) == "Bad config"
    assert err.hint == "Check syntax"
    assert err.docs_url == f"{DOCS_BASE_URL}usage/configuration/"


def test_invalid_usage_error_defaults():
    err = InvalidUsageError("Invalid flag", hint="Try checking your syntax")
    assert str(err) == "Invalid flag"
    assert err.hint == "Try checking your syntax"
    assert err.docs_url == f"{DOCS_BASE_URL}usage/cli-reference/"


def test_network_fetch_error_defaults_and_custom():
    orig = ConnectionResetError("Connection reset")
    err = NetworkFetchError("https://example.com/repo.tar.gz", original=orig)
    assert "Could not fetch remote configuration" in str(err)
    assert "https://example.com/repo.tar.gz" in str(err)
    assert err.original is orig
    assert "active internet connection" in (err.hint or "")
    assert err.docs_url == f"{DOCS_BASE_URL}usage/templates/"

    custom_err = NetworkFetchError(
        "https://example.com",
        message="Custom network fail",
        hint="Custom hint",
    )
    assert str(custom_err) == "Custom network fail"
    assert custom_err.hint == "Custom hint"


def test_template_resolution_error():
    err = TemplateResolutionError(
        "starter", "file not found", hint="Check template name"
    )
    assert str(err) == "Failed to resolve template 'starter': file not found"
    assert err.target == "starter"
    assert err.detail == "file not found"
    assert err.hint == "Check template name"
    assert err.docs_url == f"{DOCS_BASE_URL}usage/authoring-templates/"


def test_missing_dependency_error_formatting():
    err = MissingDependencyError(
        dependency=GlobalExecutable.DIRENV,
        purpose="environment switching",
    )
    assert err.dependency == GlobalExecutable.DIRENV
    assert "Missing dependency: 'direnv' is required for environment switching." in str(
        err
    )
    assert (
        err.docs_url
        == f"{DOCS_BASE_URL}usage/troubleshooting/#missing-dependencies-environment-checks"
    )


def test_command_execution_error_properties_and_output_detail():
    err = CommandExecutionError(
        ["uv", "sync"],
        returncode=2,
        stdout="resolving packages...\n",
        stderr="Resolution error: conflict\n",
    )
    assert err.command == ["uv", "sync"]
    assert err.returncode == 2
    assert "Protostar failed to execute command: uv sync" in str(err)
    assert err.output_detail == (
        "--- STDOUT ---\nresolving packages...\n\n--- STDERR ---\nResolution error: conflict"
    )

    # Empty stdout / stderr
    err_empty = CommandExecutionError(["git", "status"], returncode=1)
    assert err_empty.output_detail is None

    # Only stdout
    err_out = CommandExecutionError(["echo"], returncode=1, stdout="hello")
    assert err_out.output_detail == "--- STDOUT ---\nhello"

    # Only stderr
    err_err = CommandExecutionError(["cat"], returncode=1, stderr="failed")
    assert err_err.output_detail == "--- STDERR ---\nfailed"


def test_command_timeout_error_defaults():
    err = CommandTimeoutError(["git", "clone"], timeout=30)
    assert err.command == ["git", "clone"]
    assert err.timeout == 30
    assert "Command timed out after 30 seconds: git clone" in str(err)
    assert "stalled network request" in (err.hint or "")
    assert err.docs_url == f"{DOCS_BASE_URL}usage/templates/"


def test_filesystem_error_unwraps_os_error_and_generic():
    os_err = PermissionError(13, "Permission denied")
    err = FileSystemError("write", ".envrc", os_err)
    assert err.operation == "write"
    assert err.path == ".envrc"
    assert "Permission denied" in str(err)
    assert err.original == os_err

    generic_err = RuntimeError("Disk quota exceeded")
    err_gen = FileSystemError("mkdir", "/tmp/project", generic_err)
    assert "Disk quota exceeded" in str(err_gen)


def test_execution_aborted_error():
    err = ExecutionAbortedError()
    assert str(err) == "Execution aborted by user."
    assert err.docs_url is None

    custom = ExecutionAbortedError("Custom abort", hint="Run again with --yes")
    assert str(custom) == "Custom abort"
    assert custom.hint == "Run again with --yes"
    assert custom.docs_url is None


def test_partial_execution_aborted_error():
    from protostar.models import RollbackContext

    paths = frozenset(["path/to/a.txt", "path/to/b.txt"])
    context = RollbackContext(paths, (), None, False)
    err = PartialExecutionAbortedError(context)
    assert err.rollback_context == context
    assert "Execution interrupted" in str(err)
    assert err.docs_url is None


def test_workspace_collision_error():
    paths = frozenset([Path("pyproject.toml"), Path(".gitignore")])
    err = WorkspaceCollisionError(paths)
    assert err.paths == paths
    assert ".gitignore" in str(err)
    assert "pyproject.toml" in str(err)
    assert "--force-merge or --force-replace" in str(err)
    assert err.docs_url == f"{DOCS_BASE_URL}usage/troubleshooting/#workspace-collisions"


def test_security_violation_error():
    err = SecurityViolationError("Path traversal detected", hint="Check template paths")
    assert str(err) == "Path traversal detected"
    assert err.hint == "Check template paths"
    assert (
        err.docs_url
        == f"{DOCS_BASE_URL}usage/troubleshooting/#remote-template-security-alerts"
    )


def test_aggregated_dependency_error_empty_raises():
    with pytest.raises(ValueError, match="requires at least one error"):
        AggregatedDependencyError(())


@pytest.mark.parametrize(
    ("platform", "expected_cmd"),
    [
        ("darwin", "brew install uv git"),
        ("win32", "winget install astral-sh.uv Git.Git"),
        ("linux", "sudo apt install uv git"),
    ],
)
def test_aggregated_dependency_error_platform_commands(platform, expected_cmd):
    errors = (
        MissingDependencyError(GlobalExecutable.UV, "package management"),
        MissingDependencyError(GlobalExecutable.GIT, "version control"),
    )
    with patch("sys.platform", platform):
        err = AggregatedDependencyError(errors)
        assert "Missing 2 system dependencies" in str(err)
        assert expected_cmd in (err.hint or "")


@pytest.mark.parametrize(
    ("shell", "platform", "expected_reload"),
    [
        ("", "win32", "close and reopen your terminal"),
        ("/bin/zsh", "darwin", "source ~/.zshrc"),
        ("/bin/bash", "darwin", "source ~/.bash_profile"),
        ("/bin/bash", "linux", "source ~/.bashrc"),
        ("/usr/bin/fish", "linux", "source ~/.config/fish/config.fish"),
        ("/bin/csh", "linux", "source ~/.bashrc  # (or your shell's equivalent)"),
    ],
)
def test_aggregated_dependency_error_shell_reloads(shell, platform, expected_reload):
    errors = (MissingDependencyError(GlobalExecutable.UV, "package management"),)
    with (
        patch("sys.platform", platform),
        patch.dict("os.environ", {"SHELL": shell}),
    ):
        err = AggregatedDependencyError(errors)
        assert expected_reload in (err.hint or "")
