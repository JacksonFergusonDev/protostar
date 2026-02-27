import logging
from pathlib import Path

from protostar.config import ProtostarConfig

from .base import TargetGenerator

logger = logging.getLogger("protostar")


class CircuitPythonGenerator(TargetGenerator):
    """Generates a CircuitPython boilerplate with a non-blocking state machine."""

    @property
    def target_name(self) -> str:
        """Returns the generator's target name."""
        return "circuitpython"

    def execute(self, identifier: str | None, config: ProtostarConfig) -> list[Path]:
        """Generates a CircuitPython code.py with a non-blocking state machine.

        Args:
            identifier: Unused; accepted for interface conformance.
            config: The active Protostar configuration.

        Returns:
            A list of created paths, including code.py and optionally
            .pyrightconfig.json.

        Raises:
            FileExistsError: If code.py already exists.
        """
        code_path = Path("code.py")
        if code_path.exists():
            raise FileExistsError("code.py already exists in this directory.")

        code_content = """import time
import board
import digitalio

# Initialize hardware peripherals here
# led = digitalio.DigitalInOut(board.LED)
# led.direction = digitalio.Direction.OUTPUT

def main():
    \"\"\"Main execution loop utilizing a non-blocking delta-time architecture.\"\"\"
    last_tick = time.monotonic()
    interval = 1.0  # State execution interval in seconds

    while True:
        current_time = time.monotonic()
        
        if current_time - last_tick >= interval:
            # led.value = not led.value
            last_tick = current_time
            
        time.sleep(0.01)

if __name__ == "__main__":
    main()
"""
        code_path.write_text(code_content)
        generated_files = [code_path]

        pyright_path = Path(".pyrightconfig.json")
        if not pyright_path.exists():
            pyright_content = """{
    "reportMissingImports": false,
    "reportMissingModuleSource": false
}
"""
            pyright_path.write_text(pyright_content)
            generated_files.append(pyright_path)

        return generated_files


class PlatformIOGenerator(TargetGenerator):
    """Generates a standard PlatformIO environment configuration."""

    @property
    def target_name(self) -> str:
        """Returns the generator's target name."""
        return "pio"

    def execute(self, identifier: str | None, config: ProtostarConfig) -> list[Path]:
        """Generates a platformio.ini for the specified board target.

        Args:
            identifier: The PlatformIO board ID (e.g., 'esp32dev', 'pico').
            config: The active Protostar configuration.

        Returns:
            A list containing the created platformio.ini path.

        Raises:
            ValueError: If no board identifier is provided.
            FileExistsError: If platformio.ini already exists.
        """
        if not identifier:
            raise ValueError(
                "A board target must be specified (e.g., `proto generate pio esp32dev`)."
            )

        target_path = Path("platformio.ini")
        if target_path.exists():
            raise FileExistsError("platformio.ini already exists in this directory.")

        platform = "atmelavr"
        if "esp32" in identifier.lower():
            platform = "espressif32"
        elif "pico" in identifier.lower() or "rp2040" in identifier.lower():
            platform = "raspberrypi"

        ini_content = f"""; PlatformIO Project Configuration File

[env:{identifier}]
platform = {platform}
board = {identifier}
framework = arduino
monitor_speed = 115200
"""
        target_path.write_text(ini_content)
        return [target_path]
