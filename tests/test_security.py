import os
from pathlib import Path
from typing import Any

import pytest

from protostar.errors import SecurityViolationError
from protostar.fs import safe_extract_zip
from protostar.security import enforce_binary_safelist, enforce_path_jail


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
    enforce_path_jail(target, tmp_path)


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

    for binary in SafelistBinary:
        assert binary in ALLOWED_BINARIES


def test_safe_extract_zip_denies_traversal(tmp_path: Path):
    import zipfile

    # Create a malicious zip file
    zip_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../etc/passwd", "hacked")

    target_dir = tmp_path / "target"
    target_dir.mkdir()

    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        safe_extract_zip(zip_path, target_dir)


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
    with pytest.raises(SecurityViolationError, match="Untrusted external template"):
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


def test_trust_boundary_runs_exactly_the_confirmed_commands(mocker: Any) -> None:
    """A review's confirmation lets the commands it listed run, and no others."""
    from protostar.cli.ui import _run_engine
    from protostar.errors import ProtostarError
    from protostar.init_draft import InitDecision, InitDraft
    from protostar.models import InitRequest

    request = InitRequest(is_external=True)
    engine = _untrusted_engine(mocker)
    stale = InitDecision(InitDraft(), (), (("git", "init"),))
    with pytest.raises(ProtostarError, match="Untrusted external template"):
        _run_engine(engine, request, stale)
    engine.execute.assert_not_called()

    confirmed = InitDecision(InitDraft(), (), (("git", "init"), ("uv", "run", "setup")))
    _run_engine(engine, request, confirmed)
    engine.execute.assert_called_once()
    assert engine.execute.call_args.kwargs["hook_revisions"] == ()
