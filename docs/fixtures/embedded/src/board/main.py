"""Microcontroller main loop."""

import time


def main() -> None:
    """Execute continuous hardware loop."""
    while True:
        print("Running on hardware...")
        time.sleep(1)


if __name__ == "__main__":
    main()
