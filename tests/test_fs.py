from pathlib import Path

import pytest
from pytest_mock import MockerFixture

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

    with pytest.raises(OSError, match="Simulated IO fault: Disk Full"):
        atomic_write_text(target_file, payload)

    # The target file shouldn't have been created
    assert not target_file.exists()

    # The directory should be completely empty (the .critical_config.txt.*.tmp file must be unlinked)
    leftover_files = [f for f in tmp_path.iterdir() if f.name != "config.toml"]
    assert len(leftover_files) == 0, f"Temporary files leaked: {leftover_files}"
