**`code.py`**

```python
import time
import board
import digitalio

# Initialize hardware peripherals here
# led = digitalio.DigitalInOut(board.LED)
# led.direction = digitalio.Direction.OUTPUT

def main():
    """Main execution loop utilizing a non-blocking delta-time architecture."""
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
```

**`.pyrightconfig.json`**

```json
{
    "reportMissingImports": false,
    "reportMissingModuleSource": false
}
```
