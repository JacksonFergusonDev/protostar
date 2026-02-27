import logging
import os
import subprocess
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

logger = logging.getLogger("protostar")

# Platform-agnostic resolution leveraging standard XDG-like fallbacks
CONFIG_FILE = Path.home() / ".config" / "protostar" / "config.toml"

# Local workspace configuration resolution
LOCAL_CONFIG_FILE = Path(".protostar.toml")

DEFAULT_CONFIG_CONTENT = """[env]
# Preferred IDE: 'vscode', 'cursor', 'jetbrains', or 'none'
ide = "vscode"

# Preferred Node.js package manager: 'npm', 'pnpm', or 'yarn'
node_package_manager = "npm"

[presets]
# Generator presets for scaffolding boilerplate
latex = "minimal"
"""


@dataclass
class ProtostarConfig:
    """Global configuration settings for the Protostar CLI.

    Attributes:
        ide (str): The preferred IDE (e.g., 'vscode', 'jetbrains', 'cursor', 'none').
        node_package_manager (str): The preferred JS manager ('npm', 'pnpm', 'yarn').
        presets (dict[str, str]): Generation presets mapped by language/framework.
    """

    ide: str = "vscode"
    node_package_manager: str = "npm"
    presets: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "ProtostarConfig":
        """Loads and parses global and local Protostar configuration files.

        Evaluates the global XDG configuration first, then merges any overrides
        from a local '.protostar.toml' file in the current working directory.
        """
        instance = cls()

        if CONFIG_FILE.exists():
            instance = cls._parse_and_merge(CONFIG_FILE, instance)

        if LOCAL_CONFIG_FILE.exists():
            logger.debug(
                f"Discovered local configuration override at {LOCAL_CONFIG_FILE}"
            )
            instance = cls._parse_and_merge(LOCAL_CONFIG_FILE, instance)

        return instance

    @classmethod
    def _parse_and_merge(
        cls, path: Path, instance: "ProtostarConfig"
    ) -> "ProtostarConfig":
        """Helper to parse a TOML file and merge its values into a config instance.

        Args:
            path (Path): The filepath of the TOML configuration to read.
            instance (ProtostarConfig): The current configuration state to update.

        Returns:
            ProtostarConfig: A newly immutable dataclass instance with applied updates.
        """
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)

            updates: dict[str, Any] = {}

            if "env" in data:
                env_data = data["env"]
                if "ide" in env_data:
                    updates["ide"] = env_data["ide"]
                if "node_package_manager" in env_data:
                    updates["node_package_manager"] = env_data["node_package_manager"]

            if "presets" in data:
                # Merge existing presets with new overrides to prevent clobbering
                # unrelated keys during the global -> local cascade.
                merged_presets = dict(instance.presets)
                merged_presets.update(data["presets"])
                updates["presets"] = merged_presets

            return replace(instance, **updates)

        except tomllib.TOMLDecodeError as e:
            logger.error(f"Config syntax error in {path}: {e}")
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}")

        return instance

    @staticmethod
    def open_in_editor() -> None:
        """Opens the global configuration file in the system's default editor.

        Ensures the parent directory exists and seeds a default configuration
        template if the file is missing.
        """
        if not CONFIG_FILE.parent.exists():
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(DEFAULT_CONFIG_CONTENT)
            logger.info(f"Initialized default configuration at {CONFIG_FILE}")

        # Fallback to nano if $EDITOR isn't exported in the user's shell profile
        editor = os.environ.get("EDITOR", "nano")

        try:
            subprocess.run([editor, str(CONFIG_FILE)], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Editor '{editor}' exited with non-zero status: {e}")
        except FileNotFoundError:
            logger.error(
                f"Could not resolve editor '{editor}'. "
                "Ensure your $EDITOR environment variable is set to a valid executable."
            )
