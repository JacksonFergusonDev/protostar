"""IDE extension verification and settings synchronization."""

import enum
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .errors import FileSystemError
from .fs import atomic_write_text
from .manifest import IDESettings, Severity

__all__ = ["IDEType", "check_ide_extensions", "write_ide_settings"]


class IDEType(enum.StrEnum):
    """Enumeration of supported integrated development environments."""

    VSCODE = "vscode"
    CURSOR = "cursor"
    NONE = "none"

    @property
    def binary_name(self) -> str | None:
        """Returns the CLI executable name for this IDE, or None if disabled."""
        mapping = {
            IDEType.VSCODE: "code",
            IDEType.CURSOR: "cursor",
            IDEType.NONE: None,
        }
        return mapping[self]


def check_ide_extensions(
    ide: IDEType | str | None,
    ide_extensions: set[str | tuple[str, ...]],
    on_diagnostic: Callable[[str, Severity], None],
) -> None:
    """Verifies that the configured IDE has the recommended extensions installed.

    Fails silently if the IDE CLI is unavailable or execution fails. Appends a warning
    diagnostic only on a successful check that uncovers missing extensions.

    Args:
        ide: Configured IDE identifier (e.g. IDEType.VSCODE, "cursor").
        ide_extensions: Set of required extension IDs or alternatives tuple.
        on_diagnostic: Callback invoked with (message, severity) when extensions are missing
            or check fails.
    """
    if not ide_extensions or ide is None:
        return

    try:
        ide_type = ide if isinstance(ide, IDEType) else IDEType(str(ide))
    except ValueError:
        return

    if ide_type not in (IDEType.VSCODE, IDEType.CURSOR):
        return

    ide_binary = ide_type.binary_name
    if not ide_binary or not shutil.which(ide_binary):
        return

    try:
        result = subprocess.run(
            [ide_binary, "--list-extensions"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        # Normalize to lowercase for safe diffing
        installed = {ext.lower() for ext in result.stdout.strip().splitlines()}
        missing = []

        for ext_req in ide_extensions:
            if isinstance(ext_req, tuple):
                if not any(e.lower() in installed for e in ext_req):
                    missing.append(f"{' or '.join(ext_req)}")
            else:
                if ext_req.lower() not in installed:
                    missing.append(ext_req)

        if missing:
            on_diagnostic(
                f"Missing recommended {ide_type.value} extensions: {', '.join(missing)}",
                Severity.WARNING,
            )
    except Exception as e:
        # Reached if the CLI crashes, hangs past 5s, or throws an unexpected I/O error.
        on_diagnostic(
            f"IDE extension verification skipped due to an unexpected error: {e}",
            Severity.SKIP,
        )


def write_ide_settings(
    ide_settings: IDESettings,
    on_diagnostic: Callable[[str, Severity], None],
    on_record_touch: Callable[[Path], None],
) -> None:
    """Writes the aggregated IDE configuration to the appropriate local files.

    Args:
        ide_settings: Mapping of IDE setting keys to values.
        on_diagnostic: Callback invoked when existing settings cannot be merged safely.
        on_record_touch: Callback to record created or mutated paths.
    """
    if not ide_settings:
        return

    vscode_dir = Path(".vscode")
    settings_path = vscode_dir / "settings.json"
    settings: dict[str, Any] = {}

    if settings_path.exists():
        try:
            original_content = settings_path.read_text()
            if original_content.strip():
                parsed_data = json.loads(original_content)
                if not isinstance(parsed_data, dict):
                    on_diagnostic(
                        "Existing settings.json contains comments, trailing commas, or is malformed. Skipping IDE settings injection to prevent data loss.",
                        Severity.WARNING,
                    )
                    return
                settings = parsed_data
        except json.JSONDecodeError:
            on_diagnostic(
                "Existing settings.json contains comments, trailing commas, or is malformed. Skipping IDE settings injection to prevent data loss.",
                Severity.WARNING,
            )
            return
        except OSError as e:
            raise FileSystemError(
                "inspect active IDE settings files", str(settings_path), e
            ) from e

    # 1-level deep dictionary merge
    for key, value in ide_settings.items():
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            settings[key].update(value)
        else:
            settings[key] = value

    try:
        vscode_dir.mkdir(exist_ok=True)
        atomic_write_text(settings_path, json.dumps(settings, indent=4) + "\n")
        on_record_touch(settings_path)
    except OSError as e:
        raise FileSystemError(
            "synchronize IDE workspace preferences", str(settings_path), e
        ) from e
