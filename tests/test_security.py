import os
from pathlib import Path

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
    from protostar.enums import SafelistBinary
    from protostar.security import ALLOWED_BINARIES

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
