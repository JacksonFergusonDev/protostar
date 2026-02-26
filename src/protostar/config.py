import logging
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

logger = logging.getLogger("protostar")

CONFIG_FILE = Path.home() / ".config/protostar/config.toml"


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
