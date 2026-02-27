import logging
import os
import subprocess
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

logger = logging.getLogger("protostar")

# Platform-agnostic resolution leveraging standard XDG-like fallbacks
CONFIG_FILE = Path.home() / ".config" / "protostar" / "config.toml"

DEFAULT_CONFIG_CONTENT = """[env]
# Preferred IDE: 'vscode', 'cursor', 'jetbrains', or 'none'
ide = "vscode"

# Preferred Node.js package manager: 'npm', 'pnpm', or 'yarn'
node_package_manager = "npm"
"""


@dataclass
class ProtostarConfig:
    """Global configuration settings for the Protostar CLI.

    Attributes:
        ide (str): The preferred IDE (e.g., 'vscode', 'jetbrains', 'cursor', 'none').
        node_package_manager (str): The preferred JS manager ('npm', 'pnpm', 'yarn').
    """

    ide: str = "vscode"
    node_package_manager: str = "npm"

    @classmethod
    def load(cls) -> "ProtostarConfig":
        """Loads and parses the global Protostar configuration file."""
        instance = cls()

        if not CONFIG_FILE.exists():
            return instance

        try:
            with open(CONFIG_FILE, "rb") as f:
                data = tomllib.load(f)

            if "env" in data:
                env_data = data["env"]
                updates = {}
                if "ide" in env_data:
                    updates["ide"] = env_data["ide"]
                if "node_package_manager" in env_data:
                    updates["node_package_manager"] = env_data["node_package_manager"]

                return replace(instance, **updates)

        except tomllib.TOMLDecodeError as e:
            logger.error(f"Config syntax error in {CONFIG_FILE}: {e}")
        except Exception as e:
            logger.warning(f"Failed to load config from {CONFIG_FILE}: {e}")

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
