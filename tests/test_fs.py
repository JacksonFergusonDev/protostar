from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protostar.errors import FileSystemError
from protostar.fs import atomic_write_text


def test_atomic_write_text_creates_new_file(tmp_path: Path) -> None:
    target_file = tmp_path / "config.toml"
    payload = "[tool.protostar]\nready = true\n"

    atomic_write_text(target_file, payload)

    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == payload


def test_atomic_write_text_overwrites_existing_file(tmp_path: Path) -> None:
    target_file = tmp_path / "state.txt"
    target_file.write_text("initial state")

    atomic_write_text(target_file, "updated state")

    assert target_file.read_text(encoding="utf-8") == "updated state"


def test_atomic_write_text_respects_encoding(tmp_path: Path) -> None:
    target_file = tmp_path / "encoded.txt"
    # Using some non-ASCII characters to verify encoding serialization
    payload = "🚀 Protostar: Δv = 5.4 km/s"

    atomic_write_text(target_file, payload, encoding="utf-16")

    # Bypassing the wrapper to ensure physical bytes on disk match the encoding
    assert target_file.read_text(encoding="utf-16") == payload


def test_atomic_write_text_cleans_up_temp_file_on_failure(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    target_file = tmp_path / "critical_config.txt"
    payload = "this should not persist"

    # Induce a simulated filesystem fault right when os.replace attempts the atomic swap
    mocker.patch("os.replace", side_effect=OSError("Simulated IO fault: Disk Full"))

    with pytest.raises(FileSystemError, match="Failed to write file"):
        atomic_write_text(target_file, payload)

    # The target file shouldn't have been created
    assert not target_file.exists()

    # The directory should be completely empty (the .critical_config.txt.*.tmp file must be unlinked)
    leftover_files = [f for f in tmp_path.iterdir() if f.name != "config.toml"]
    assert len(leftover_files) == 0, f"Temporary files leaked: {leftover_files}"


def test_atomic_write_text_handles_encoding_error(tmp_path: Path) -> None:
    target_file = tmp_path / "bad_encoding.txt"
    payload = "🚀 Unicode characters incompatible with ascii"

    with pytest.raises(FileSystemError, match="Failed to write file"):
        atomic_write_text(target_file, payload, encoding="ascii")

    assert not target_file.exists()
    leftover_files = [f for f in tmp_path.iterdir() if f.name != "config.toml"]
    assert len(leftover_files) == 0, f"Temporary files leaked: {leftover_files}"


def test_safe_extract_tar_and_archive(tmp_path: Path) -> None:
    import tarfile

    from protostar.enums import ArchiveFormat
    from protostar.errors import SecurityViolationError, TemplateResolutionError
    from protostar.fs import safe_extract_archive, safe_extract_tar

    # Create a valid tar.gz file
    tar_path = tmp_path / "valid.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        info = tarfile.TarInfo(name="template/protostar.toml")
        data = b"[env]\nruff = true\n"
        info.size = len(data)
        import io

        tf.addfile(info, io.BytesIO(data))

    dest_dir = tmp_path / "extracted_tar"
    dest_dir.mkdir()
    safe_extract_tar(tar_path, dest_dir)
    assert (dest_dir / "template" / "protostar.toml").exists()

    # Test via safe_extract_archive dispatch
    dest_dir2 = tmp_path / "extracted_archive"
    dest_dir2.mkdir()
    safe_extract_archive(tar_path, dest_dir2, archive_format=ArchiveFormat.TAR_GZ)
    assert (dest_dir2 / "template" / "protostar.toml").exists()

    # Create a malicious tar attempting path traversal
    bad_tar = tmp_path / "malicious.tar.gz"
    with tarfile.open(bad_tar, "w:gz") as tf:
        bad_info = tarfile.TarInfo(name="../../outside.txt")
        bad_data = b"malicious payload"
        bad_info.size = len(bad_data)
        tf.addfile(bad_info, io.BytesIO(bad_data))

    bad_dest = tmp_path / "bad_extract"
    bad_dest.mkdir()
    with pytest.raises(SecurityViolationError, match="SECURITY VIOLATION"):
        safe_extract_tar(bad_tar, bad_dest)

    # Test unsupported archive format
    with pytest.raises(
        TemplateResolutionError, match="Unsupported or unrecognized archive format"
    ):
        safe_extract_archive(tmp_path / "unknown.rar", dest_dir2)
