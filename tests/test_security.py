import os
from pathlib import Path
from typing import Any

import pytest

from protostar.errors import SecurityViolationError
from protostar.security import (
    enforce_binary_safelist,
    enforce_path_jail,
    is_safe_relative_path,
    names_git_directory,
)


def test_enforce_path_jail_outside_traversal(tmp_path: Path):
    target = tmp_path / "../../../../etc/passwd"
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        enforce_path_jail(target, tmp_path)


def test_enforce_path_jail_relative_escape(tmp_path: Path):
    target = tmp_path / "../outside_dir"
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        enforce_path_jail(target, tmp_path)


def test_enforce_path_jail_symlink_bypass(tmp_path: Path):
    # Create a symlink in the temp dir that points outside (e.g. to /tmp)
    symlink_path = tmp_path / "logs"
    outside_dir = Path("/tmp")
    os.symlink(outside_dir, symlink_path)

    # Attempt to write into the symlink
    target = symlink_path / "passwd"
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        enforce_path_jail(target, tmp_path)


def test_enforce_path_jail_valid_path(tmp_path: Path):
    target = tmp_path / "sub" / "file.txt"
    # Should not raise
    normalized = enforce_path_jail(target, tmp_path)
    assert normalized == (tmp_path / "sub" / "file.txt").resolve()


def test_enforce_path_jail_dereference_leaf_false_preserves_leaf_symlink(
    tmp_path: Path,
):
    real_file = tmp_path / "real.txt"
    real_file.write_text("content")
    symlink_file = tmp_path / "link.txt"
    os.symlink(real_file, symlink_file)

    # dereference_leaf=False keeps the symlink path rather than resolving to real.txt
    result = enforce_path_jail(symlink_file, tmp_path, dereference_leaf=False)
    assert result == symlink_file.resolve().parent / "link.txt"
    assert result.is_symlink()

    # dereference_leaf=True resolves to the target
    dereferenced = enforce_path_jail(symlink_file, tmp_path, dereference_leaf=True)
    assert dereferenced == real_file.resolve()


def test_enforce_path_jail_dereference_leaf_false_catches_traversal(tmp_path: Path):
    sub = tmp_path / "sub"
    sub.mkdir()
    target = sub / "../../etc/passwd"
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        enforce_path_jail(target, tmp_path, dereference_leaf=False)


def test_is_safe_relative_path():
    assert is_safe_relative_path("foo")
    assert is_safe_relative_path("foo/bar.txt")
    assert is_safe_relative_path("src/app/main.py")

    assert not is_safe_relative_path("")
    assert not is_safe_relative_path("/etc/passwd")
    assert not is_safe_relative_path("../escape")
    assert not is_safe_relative_path("foo/../../escape")
    assert not is_safe_relative_path("C:/windows/system32")
    assert not is_safe_relative_path("D:file.txt")


def test_names_git_directory():
    assert names_git_directory(".git")
    assert names_git_directory(".GIT")
    assert names_git_directory(".git.")
    assert names_git_directory(".git ")
    assert names_git_directory("git~1")
    assert names_git_directory("GIT~1")

    assert not names_git_directory(".gitignore")
    assert not names_git_directory(".gitattributes")
    assert not names_git_directory("git")
    assert not names_git_directory("github")


def test_enforce_binary_safelist_deny():
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        enforce_binary_safelist(["bash", "-c", "echo hacked"])

    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        enforce_binary_safelist(["env", "bash"])


def test_enforce_binary_safelist_allow():
    # Empty command should not raise
    enforce_binary_safelist([])

    # Allowed binaries should not raise
    enforce_binary_safelist(["uv", "run", "pytest"])
    enforce_binary_safelist(["git", "init"])
    enforce_binary_safelist(["npm", "test"])
    enforce_binary_safelist(["prek", "run"])
    enforce_binary_safelist(["pre-commit", "run"])
    enforce_binary_safelist(["/usr/local/bin/direnv", "allow"])
    enforce_binary_safelist(["just", "build"])


def test_safelist_binary_enum():
    from protostar.security import ALLOWED_BINARIES, SafelistBinary

    assert SafelistBinary.UV.value == "uv"
    assert SafelistBinary.GIT.value == "git"
    assert SafelistBinary.NPM.value == "npm"
    assert SafelistBinary.YARN.value == "yarn"
    assert SafelistBinary.PNPM.value == "pnpm"
    assert SafelistBinary.PRE_COMMIT.value == "pre-commit"
    assert SafelistBinary.PREK.value == "prek"
    assert SafelistBinary.DIRENV.value == "direnv"
    assert SafelistBinary.JUST.value == "just"

    for binary in SafelistBinary:
        assert binary in ALLOWED_BINARIES


def test_global_executables_covered_by_safelist():
    """Ensures every GlobalExecutable is authorized in SafelistBinary."""
    from protostar.security import SafelistBinary
    from protostar.system_deps import GlobalExecutable

    safelist_values = {b.value for b in SafelistBinary}
    for global_exe in GlobalExecutable:
        assert global_exe.value in safelist_values, (
            f"Global executable {global_exe.value} is missing from SafelistBinary"
        )


def test_trust_boundary_bypassed_when_trusted_true(mocker: Any) -> None:
    """Verifies that external templates marked trusted=True bypass confirmation warnings."""
    from protostar.cli.ui import _run_engine
    from protostar.manifest import EnvironmentManifest
    from protostar.models import ExecutionResult, InitRequest
    from protostar.orchestrator import Orchestrator

    mock_engine = mocker.MagicMock(spec=Orchestrator)
    manifest = EnvironmentManifest()
    manifest.tasks.add_system_task(["uv", "run", "setup"])
    mock_engine.plan.return_value = manifest
    mock_engine.execute.return_value = ExecutionResult(
        created_paths=frozenset(),
        mutated_paths=frozenset(),
        diagnostics=(),
    )

    request = InitRequest(is_external=True, is_trusted=True)
    res = _run_engine(mock_engine, request)
    assert res is not None
    mock_engine.execute.assert_called_once()


def test_trust_boundary_rejects_untrusted_in_json_mode(mocker: Any) -> None:
    """Verifies that untrusted external templates with tasks abort in JSON mode."""
    from protostar.cli.ui import _run_engine
    from protostar.manifest import EnvironmentManifest
    from protostar.models import InitRequest
    from protostar.orchestrator import Orchestrator

    mock_engine = mocker.MagicMock(spec=Orchestrator)
    manifest = EnvironmentManifest()
    manifest.tasks.add_system_task(["uv", "run", "setup"])
    mock_engine.plan.return_value = manifest

    mocker.patch("protostar.cli.ui.is_json_mode", True)
    request = InitRequest(is_external=True, is_trusted=False)
    with pytest.raises(SecurityViolationError, match="isn't trusted"):
        _run_engine(mock_engine, request)


def _untrusted_engine(mocker: Any) -> Any:
    from protostar.manifest import EnvironmentManifest
    from protostar.models import ExecutionResult
    from protostar.orchestrator import Orchestrator

    engine = mocker.MagicMock(spec=Orchestrator)
    manifest = EnvironmentManifest()
    manifest.tasks.add_system_task(["git", "init"])
    manifest.tasks.add_post_install_task(["uv", "run", "setup"])
    engine.plan.return_value = manifest
    engine.execute.return_value = ExecutionResult(frozenset(), frozenset(), ())
    return engine


def test_untrusted_commands_lists_every_command_in_order(mocker: Any) -> None:
    """Built-in and trusted templates need no confirmation; others list all tasks."""
    from protostar.cli.ui import needs_review, untrusted_commands
    from protostar.models import InitRequest

    manifest = _untrusted_engine(mocker).plan()
    untrusted = InitRequest(is_external=True)
    assert untrusted_commands(untrusted, manifest) == (
        ("git", "init"),
        ("uv", "run", "setup"),
    )
    assert needs_review(untrusted, manifest)
    for request in (InitRequest(), InitRequest(is_external=True, is_trusted=True)):
        assert untrusted_commands(request, manifest) == ()
        assert not needs_review(request, manifest)


def test_untrusted_commands_include_the_dependency_installs(mocker: Any) -> None:
    """uv builds the project a template shaped, so its installs are gated too."""
    from protostar.cli.ui import needs_review, untrusted_commands
    from protostar.intent import DependencyGroup
    from protostar.manifest import EnvironmentManifest
    from protostar.models import InitRequest

    manifest = _untrusted_engine(mocker).plan()
    manifest.dependencies.add("fastapi")
    manifest.dependencies.add_dev("pytest")
    assert untrusted_commands(InitRequest(is_external=True), manifest) == (
        ("git", "init"),
        ("uv", "add", "fastapi"),
        ("uv", "add", "--dev", "pytest"),
        ("uv", "run", "setup"),
    )

    # A template with no tasks at all still needs confirmation for its installs.
    installs_only = EnvironmentManifest()
    installs_only.dependencies.add("fastapi")
    assert needs_review(InitRequest(is_external=True), installs_only)

    includes_only = EnvironmentManifest()
    includes_only.dependencies.add_include(DependencyGroup.DEV, DependencyGroup.DOCS)
    assert untrusted_commands(InitRequest(is_external=True), includes_only) == (
        ("uv", "lock"),
    )


def test_trust_boundary_runs_exactly_the_confirmed_commands(mocker: Any) -> None:
    """A review's confirmation lets the commands it listed run, and no others."""
    from protostar.cli.ui import _run_engine
    from protostar.errors import ProtostarError
    from protostar.init_draft import InitDecision, InitDraft
    from protostar.models import InitRequest

    request = InitRequest(is_external=True)
    engine = _untrusted_engine(mocker)
    stale = InitDecision(InitDraft(), (), (("git", "init"),))
    with pytest.raises(ProtostarError, match="isn't trusted"):
        _run_engine(engine, request, stale)
    engine.execute.assert_not_called()

    confirmed = InitDecision(InitDraft(), (), (("git", "init"), ("uv", "run", "setup")))
    _run_engine(engine, request, confirmed)
    engine.execute.assert_called_once()
    assert engine.execute.call_args.kwargs["hook_revisions"] == ()
